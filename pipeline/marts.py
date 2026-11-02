"""Materializa consultas SQL em tabelas do schema ``marts``.

Esta etapa lê somente ``refined`` e grava somente ``marts``. Neste projeto,
``refined`` contém as seis tabelas do Instacart (corredores, departamentos,
produtos, pedidos, itens_pedido_prior e itens_pedido_treino), em vez das oito
tabelas Olist da spec de referência; validar todas as seis evita publicar um
dashboard incompleto.

Cada arquivo ``sql/marts/*.sql`` é a fonte integral da regra de negócio de um
mart e sua ordem alfabética torna a execução e a saída previsíveis. O nome da
tabela deriva do sufixo após ``NN_``; validar prefixos e colisões antes de
executar SQL evita sobrescrever destinos por engano. O Python apenas remove
espaços externos e um ponto e vírgula terminal, sem reescrever a consulta.

O schema ``marts`` é apagado e recriado dentro de uma única transação. Assim,
arquivos SQL removidos não deixam tabelas obsoletas, e qualquer consulta com
erro ou mart vazio restaura o schema da última execução bem-sucedida. A
contagem vem do banco e zero linhas são tratadas como erro para não expor um
dashboard vazio como se fosse resultado válido. stdout e stderr usam UTF-8
para que a saída seja legível no Prompt de Comando do Windows.
"""

import re
import sys
from pathlib import Path

from pipeline.db import conectar

PASTA_SQL = Path(__file__).resolve().parent.parent / "sql" / "marts"
TABELAS_REFINED = (
    "corredores",
    "departamentos",
    "produtos",
    "pedidos",
    "itens_pedido_prior",
    "itens_pedido_treino",
)


def _identificador_sql(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _nome_tabela(caminho: Path) -> str | None:
    correspondencia = re.fullmatch(r"\d{2}_(.+)", caminho.stem)
    return correspondencia.group(1) if correspondencia else None


def _arquivos_sql() -> list[tuple[Path, str]]:
    arquivos = sorted(PASTA_SQL.glob("*.sql"))
    if not arquivos:
        print(f"Nenhum arquivo .sql encontrado em {PASTA_SQL}.", file=sys.stderr)
        raise SystemExit(1)

    sem_prefixo = [
        arquivo.name for arquivo in arquivos if _nome_tabela(arquivo) is None
    ]
    por_tabela: dict[str, list[str]] = {}
    for arquivo in arquivos:
        nome = _nome_tabela(arquivo)
        if nome is not None:
            por_tabela.setdefault(nome, []).append(arquivo.name)
    duplicados = {nome: nomes for nome, nomes in por_tabela.items() if len(nomes) > 1}

    if sem_prefixo or duplicados:
        if sem_prefixo:
            print(
                f"Arquivos sem prefixo NN_: {', '.join(sem_prefixo)}.",
                file=sys.stderr,
            )
        if duplicados:
            conflitos = "; ".join(
                f"{nome}: {', '.join(nomes)}"
                for nome, nomes in sorted(duplicados.items())
            )
            print(
                f"Arquivos que geram o mesmo nome de tabela: {conflitos}.",
                file=sys.stderr,
            )
        raise SystemExit(1)

    return [(arquivo, _nome_tabela(arquivo) or "") for arquivo in arquivos]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        tabelas_existentes = {
            linha[0]
            for linha in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'refined' AND table_type = 'BASE TABLE'"
            ).fetchall()
        }
        faltantes = [
            tabela for tabela in TABELAS_REFINED if tabela not in tabelas_existentes
        ]
        if faltantes:
            print(
                f"Tabelas ausentes em refined: {', '.join(faltantes)}. "
                "Execute `uv run python -m pipeline.transformacao` antes.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        arquivos = _arquivos_sql()
        consultas = [
            (arquivo, tabela, arquivo.read_text(encoding="utf-8").strip())
            for arquivo, tabela in arquivos
        ]
        consultas = [
            (arquivo, tabela, sql[:-1].rstrip() if sql.endswith(";") else sql)
            for arquivo, tabela, sql in consultas
        ]

        resultados = []
        arquivo_atual: Path | None = None
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute("DROP SCHEMA IF EXISTS marts CASCADE")
            con.execute("CREATE SCHEMA marts")
            for arquivo, tabela, sql in consultas:
                arquivo_atual = arquivo
                tabela_sql = _identificador_sql(tabela)
                con.execute(f"CREATE TABLE marts.{tabela_sql} AS {sql}")
                linhas = int(
                    con.execute(f"SELECT COUNT(*) FROM marts.{tabela_sql}").fetchall()[
                        0
                    ][0]
                )
                if linhas == 0:
                    raise ValueError(f"mart {tabela} retornou zero linhas")
                resultados.append((tabela, linhas))
            con.execute("COMMIT")
        except Exception as exc:
            con.execute("ROLLBACK")
            nome_arquivo = arquivo_atual.name if arquivo_atual else "schema marts"
            print(f"Erro em {nome_arquivo}: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        total_linhas = 0
        for tabela, linhas in resultados:
            print(f"✓ marts.{tabela:<34} {linhas:,} linhas".replace(",", "."))
            total_linhas += linhas
        print(
            f"Total: {len(resultados)} marts, {total_linhas:,} linhas".replace(",", ".")
        )
    finally:
        con.close()


if __name__ == "__main__":
    main()
