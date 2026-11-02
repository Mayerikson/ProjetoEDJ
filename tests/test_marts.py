import contextlib
import io
from pathlib import Path

import duckdb
import pytest

from pipeline import marts


class CapturedStream(io.StringIO):
    def reconfigure(self, *, encoding: str) -> None:
        _ = encoding


@pytest.fixture
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    caminho_banco = tmp_path / "teste.duckdb"
    pasta_sql = tmp_path / "sql" / "marts"
    pasta_sql.mkdir(parents=True)

    con = duckdb.connect(str(caminho_banco))
    con.execute("CREATE SCHEMA refined")
    for tabela in marts.TABELAS_REFINED:
        con.execute(f'CREATE TABLE refined."{tabela}" AS SELECT 1 AS valor')
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.anterior AS SELECT 7 AS valor")
    con.close()

    monkeypatch.setattr(marts, "conectar", lambda: duckdb.connect(str(caminho_banco)))
    monkeypatch.setattr(marts, "PASTA_SQL", pasta_sql)
    return caminho_banco


@pytest.fixture
def pasta_sql(ambiente: Path) -> Path:
    assert ambiente.is_file()
    return Path(marts.PASTA_SQL)


def executar() -> tuple[int, str, str]:
    stdout = CapturedStream()
    stderr = CapturedStream()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            marts.main()
        except SystemExit as exc:
            return int(exc.code), stdout.getvalue(), stderr.getvalue()
    return 0, stdout.getvalue(), stderr.getvalue()


def tabelas_marts(caminho_banco: Path) -> list[str]:
    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        return [
            linha[0]
            for linha in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'marts' ORDER BY table_name"
            ).fetchall()
        ]
    finally:
        con.close()


def test_cria_mart_e_reexecuta_com_mesma_saida(ambiente: Path, pasta_sql: Path) -> None:
    (pasta_sql / "00_teste.sql").write_text("SELECT 1 AS x", encoding="utf-8")

    codigo, primeira_saida, erro = executar()
    assert codigo == 0
    assert erro == ""
    assert "marts.teste" in primeira_saida
    assert "1 linhas" in primeira_saida

    codigo, segunda_saida, erro = executar()
    assert codigo == 0
    assert erro == ""
    assert segunda_saida == primeira_saida

    (pasta_sql / "01_outro.sql").write_text("SELECT 2 AS y", encoding="utf-8")
    assert executar()[0] == 0
    (pasta_sql / "01_outro.sql").unlink()
    assert executar()[0] == 0
    assert tabelas_marts(ambiente) == ["teste"]


def test_erro_sql_preserva_schema_anterior(ambiente: Path, pasta_sql: Path) -> None:
    (pasta_sql / "00_teste.sql").write_text(
        "SELECT * FROM coluna_inexistente", encoding="utf-8"
    )

    codigo, _, erro = executar()

    assert codigo == 1
    assert "00_teste.sql" in erro
    assert "coluna_inexistente" in erro
    assert tabelas_marts(ambiente) == ["anterior"]


def test_mart_vazio_preserva_schema_anterior(ambiente: Path, pasta_sql: Path) -> None:
    (pasta_sql / "00_vazio.sql").write_text(
        "SELECT 1 AS x WHERE FALSE", encoding="utf-8"
    )

    codigo, _, erro = executar()

    assert codigo == 1
    assert "00_vazio.sql" in erro
    assert "zero linhas" in erro
    assert tabelas_marts(ambiente) == ["anterior"]


def test_nome_sem_prefixo_nao_executa_sql(ambiente: Path, pasta_sql: Path) -> None:
    (pasta_sql / "sem_prefixo.sql").write_text("SELECT 1 AS x", encoding="utf-8")

    codigo, saida, erro = executar()

    assert codigo == 1
    assert saida == ""
    assert "sem_prefixo.sql" in erro
    assert tabelas_marts(ambiente) == ["anterior"]


def test_nomes_de_tabela_duplicados_nao_executam_sql(
    ambiente: Path, pasta_sql: Path
) -> None:
    (pasta_sql / "00_teste.sql").write_text("SELECT 1 AS x;  \n", encoding="utf-8")
    (pasta_sql / "01_teste.sql").write_text("SELECT 2 AS x", encoding="utf-8")

    codigo, saida, erro = executar()

    assert codigo == 1
    assert saida == ""
    assert "00_teste.sql" in erro
    assert "01_teste.sql" in erro
    assert tabelas_marts(ambiente) == ["anterior"]


def test_tabela_refined_ausente_para_antes_de_alterar_marts(
    ambiente: Path, pasta_sql: Path
) -> None:
    (pasta_sql / "00_teste.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    con = duckdb.connect(str(ambiente))
    con.execute("DROP TABLE refined.itens_pedido_treino")
    con.close()

    codigo, saida, erro = executar()

    assert codigo == 1
    assert saida == ""
    assert "itens_pedido_treino" in erro
    assert "pipeline.transformacao" in erro
    assert tabelas_marts(ambiente) == ["anterior"]


def test_pasta_sql_vazia_nao_altera_schema_anterior(
    ambiente: Path, pasta_sql: Path
) -> None:
    codigo, saida, erro = executar()

    assert codigo == 1
    assert saida == ""
    assert "Nenhum arquivo .sql" in erro
    assert tabelas_marts(ambiente) == ["anterior"]
