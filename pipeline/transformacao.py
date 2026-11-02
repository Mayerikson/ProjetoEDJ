"""Transforma todas as tabelas de ``raw`` para ``refined``.

As seis tabelas são incluídas porque nenhuma foi excluída nesta etapa. Os
nomes das colunas são mantidos: são o vocabulário escolhido para os JOINs das
próximas aulas, e uma tradução adicional não acrescentaria informação.

Somente contagens e tempos definidos na spec são convertidos; identificadores
continuam VARCHAR para preservar zeros à esquerda e permitir seu uso como
chaves textuais. ``TRY_CAST`` transforma apenas valores não conversíveis em
NULL, sem descartar a linha; valores como ``days_since_prior_order`` nulos
continuam nulos, pois zero teria outro significado. As faixas de dia e hora
descrevem os valores esperados, mas não rejeitam inteiros conversíveis fora
delas.

Duplicatas são avaliadas sobre a linha original completa, antes dos casts:
assim, uma conversão inválida não faz conteúdos raw diferentes parecerem
iguais. Linhas integralmente idênticas são reduzidas a uma ocorrência;
chaves nulas são agrupadas como duplicatas conforme confirmado para esta
etapa. Diferentes conteúdos sob a mesma chave permanecem e são avisados, pois
a escolha de uma versão não pertence a esta transformação. A contagem
informada como duplicada corresponde às ocorrências extras removidas; a
quantidade de conflitos corresponde a grupos de chaves conflitantes.

As tabelas de origem são verificadas em conjunto antes de criar ou escrever
em ``refined``, evitando uma transformação parcial quando falta uma tabela.
Cada destino é recriado. O processamento usa relações e operações DuckDB para
não carregar dezenas de milhões de linhas em pandas; ``gravar`` consulta no
banco a contagem efetivamente persistida. Saída e avisos usam UTF-8 para
permanecerem legíveis no Prompt de Comando do Windows.
"""

import sys
from uuid import uuid4

from pipeline.db import conectar, criar_schema, gravar

type EspecificacaoTabela = tuple[str, tuple[str, ...], tuple[str, ...], dict[str, str]]

TABELAS: tuple[EspecificacaoTabela, ...] = (
    (
        "corredores",
        ("aisle_id", "aisle"),
        ("aisle_id",),
        {},
    ),
    (
        "departamentos",
        ("department_id", "department"),
        ("department_id",),
        {},
    ),
    (
        "produtos",
        ("product_id", "product_name", "aisle_id", "department_id"),
        ("product_id",),
        {},
    ),
    (
        "pedidos",
        (
            "order_id",
            "user_id",
            "eval_set",
            "order_number",
            "order_dow",
            "order_hour_of_day",
            "days_since_prior_order",
        ),
        ("order_id",),
        {
            "order_number": "INTEGER",
            "order_dow": "INTEGER",
            "order_hour_of_day": "INTEGER",
            "days_since_prior_order": "DOUBLE",
        },
    ),
    (
        "itens_pedido_prior",
        ("order_id", "product_id", "add_to_cart_order", "reordered"),
        ("order_id", "product_id"),
        {"add_to_cart_order": "INTEGER", "reordered": "INTEGER"},
    ),
    (
        "itens_pedido_treino",
        ("order_id", "product_id", "add_to_cart_order", "reordered"),
        ("order_id", "product_id"),
        {"add_to_cart_order": "INTEGER", "reordered": "INTEGER"},
    ),
)


def _identificador_sql(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        tabelas_raw = {
            linha[0]
            for linha in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'raw' AND table_type = 'BASE TABLE'"
            ).fetchall()
        }
        faltantes = [tabela for tabela, _, _, _ in TABELAS if tabela not in tabelas_raw]
        if faltantes:
            print(
                f"Tabelas ausentes em raw: {', '.join(faltantes)}. "
                "Execute a ingestão antes da transformação.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        criar_schema(con, "refined")
        con.execute("BEGIN TRANSACTION")
        resultados = []
        try:
            for tabela, colunas, chaves, tipos in TABELAS:
                origem_sql = _identificador_sql(tabela)
                temporaria = f"_transformacao_{tabela}_{uuid4().hex}"
                temporaria_sql = _identificador_sql(temporaria)
                colunas_sql = ", ".join(
                    _identificador_sql(coluna) for coluna in colunas
                )
                chaves_sql = ", ".join(_identificador_sql(chave) for chave in chaves)

                con.execute(
                    f"CREATE TEMP TABLE {temporaria_sql} AS "
                    f'SELECT {colunas_sql}, COUNT(*) AS "_ocorrencias" '
                    f"FROM raw.{origem_sql} "
                    f"GROUP BY {colunas_sql}"
                )
                duplicatas_removidas = int(
                    con.execute(
                        f'SELECT COALESCE(SUM("_ocorrencias" - 1), 0) '
                        f"FROM {temporaria_sql}"
                    ).fetchall()[0][0]
                )
                conflitos = con.execute(
                    f'SELECT {chaves_sql}, COUNT(*) AS "_variantes" '
                    f"FROM {temporaria_sql} "
                    f"GROUP BY {chaves_sql} "
                    f"HAVING COUNT(*) > 1 "
                    f"ORDER BY {chaves_sql}"
                ).fetchall()

                selecoes = []
                for coluna in colunas:
                    coluna_sql = _identificador_sql(coluna)
                    if coluna in tipos:
                        selecoes.append(
                            f"TRY_CAST({coluna_sql} AS {tipos[coluna]}) AS {coluna_sql}"
                        )
                    else:
                        selecoes.append(coluna_sql)

                relacao = con.sql(f"SELECT {', '.join(selecoes)} FROM {temporaria_sql}")
                linhas = gravar(con, relacao, "refined", tabela)
                con.execute(f"DROP TABLE {temporaria_sql}")
                resultados.append(
                    (tabela, linhas, duplicatas_removidas, chaves, conflitos)
                )

            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

        total = 0
        for tabela, linhas, duplicatas, chaves, conflitos in resultados:
            print(
                f"refined.{tabela}: {linhas:,} "
                f"(duplicatas removidas: {duplicatas:,})".replace(",", ".")
            )
            total += linhas
            for conflito in conflitos:
                valores_chave = ", ".join(
                    f"{chave}={valor!r}"
                    for chave, valor in zip(chaves, conflito[:-1], strict=True)
                )
                print(
                    f"Aviso: refined.{tabela} chave ({valores_chave}) em conflito; "
                    f"{len(conflitos)} chaves conflitantes na tabela."
                )

        print(f"Total: {total:,}".replace(",", "."))
    finally:
        con.close()


if __name__ == "__main__":
    main()
