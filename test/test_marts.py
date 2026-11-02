import contextlib
import io
from pathlib import Path

import duckdb
import pytest

from pipeline import marts


class CapturedStream(io.StringIO):
    def reconfigure(self, *, encoding: str) -> None:
        self.configured_encoding = encoding


def criar_banco(caminho: Path, omitir: str | None = None) -> None:
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA refined")
    for tabela in marts.TABELAS_REFINED:
        if tabela != omitir:
            con.execute(f"CREATE TABLE refined.{tabela} (valor INTEGER)")
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.anterior AS SELECT 7 AS valor")
    con.close()


@contextlib.contextmanager
def capturar_saida():
    stdout, stderr = CapturedStream(), CapturedStream()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        yield stdout, stderr


def tabelas_marts(caminho: Path) -> list[str]:
    con = duckdb.connect(str(caminho), read_only=True)
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


def test_prefixo_invalido_para_antes_de_executar_sql(
    tmp_path: Path, monkeypatch
) -> None:
    caminho = tmp_path / "prefixo.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "teste.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    criar_banco(caminho)
    monkeypatch.setattr(marts, "PASTA_SQL", pasta_sql)
    monkeypatch.setattr(marts, "conectar", lambda: duckdb.connect(str(caminho)))

    with (
        capturar_saida() as (stdout, stderr),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    assert stdout.getvalue() == ""
    assert "teste.sql" in stderr.getvalue()
    assert tabelas_marts(caminho) == ["anterior"]


def test_mart_vazio_preserva_schema_anterior(tmp_path: Path, monkeypatch) -> None:
    caminho = tmp_path / "vazio.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "00_vazio.sql").write_text(
        "SELECT 1 AS x WHERE FALSE", encoding="utf-8"
    )
    criar_banco(caminho)
    monkeypatch.setattr(marts, "PASTA_SQL", pasta_sql)
    monkeypatch.setattr(marts, "conectar", lambda: duckdb.connect(str(caminho)))

    with (
        capturar_saida() as (_, stderr),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    assert "00_vazio.sql" in stderr.getvalue()
    assert "zero linhas" in stderr.getvalue()
    assert tabelas_marts(caminho) == ["anterior"]


def test_sql_apagado_remove_mart_na_execucao_seguinte(
    tmp_path: Path, monkeypatch
) -> None:
    caminho = tmp_path / "remocao.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    consulta = pasta_sql / "00_teste.sql"
    consulta.write_text("SELECT 1 AS valor", encoding="utf-8")
    (pasta_sql / "01_outro.sql").write_text("SELECT 2 AS valor", encoding="utf-8")
    criar_banco(caminho)
    monkeypatch.setattr(marts, "PASTA_SQL", pasta_sql)
    monkeypatch.setattr(marts, "conectar", lambda: duckdb.connect(str(caminho)))

    with capturar_saida() as (stdout, stderr):
        marts.main()
    primeira_saida = stdout.getvalue()
    assert stderr.getvalue() == ""
    assert "marts.teste" in primeira_saida
    assert tabelas_marts(caminho) == ["outro", "teste"]

    consulta.unlink()
    with capturar_saida() as (stdout, stderr):
        marts.main()
    assert stdout.getvalue()
    assert stderr.getvalue() == ""
    assert tabelas_marts(caminho) == ["outro"]


def test_cesta_conta_pedido_com_dois_itens_uma_vez() -> None:
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA refined")
    con.execute(
        "CREATE TABLE refined.itens_pedido_prior (order_id VARCHAR, product_id VARCHAR)"
    )
    con.execute(
        "CREATE TABLE refined.itens_pedido_treino "
        "(order_id VARCHAR, product_id VARCHAR)"
    )
    # O pedido A tem dois itens; o pedido B tem um item.
    con.executemany(
        "INSERT INTO refined.itens_pedido_prior VALUES (?, ?)",
        [
            ("A", "P1"),  # Primeiro item do pedido A.
            ("A", "P2"),  # Segundo item do mesmo pedido não duplica o pedido.
            ("B", "P1"),  # Pedido B de um item forma a segunda cesta.
        ],
    )

    sql = (
        Path(__file__).resolve().parents[1]
        / "sql"
        / "marts"
        / "06_distribuicao_tamanho_cestas.sql"
    ).read_text(encoding="utf-8")
    resultado = con.execute(sql).fetchall()

    assert resultado == [(1, 1, 50.0), (2, 1, 50.0)]
    con.close()


def test_mart_por_hora_exclui_eval_set_test() -> None:
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA refined")
    con.execute(
        "CREATE TABLE refined.pedidos (eval_set VARCHAR, order_hour_of_day INTEGER)"
    )
    # Um pedido prior e um train entram na hora 9; o pedido test da hora 9 fica fora.
    con.executemany(
        "INSERT INTO refined.pedidos VALUES (?, ?)",
        [
            ("prior", 9),  # Pedido prior incluído na hora 9.
            ("train", 9),  # Pedido train incluído na mesma hora.
            ("test", 9),  # Pedido test excluído do indicador.
            ("prior", 10),  # Pedido independente contado na hora 10.
        ],
    )

    sql = (
        Path(__file__).resolve().parents[1]
        / "sql"
        / "marts"
        / "03_pedidos_por_hora.sql"
    ).read_text(encoding="utf-8")
    resultado = con.execute(sql).fetchall()

    assert resultado == [(9, 2), (10, 1)]
    con.close()


def test_tabela_refined_ausente_preserva_schema_marts(
    tmp_path: Path, monkeypatch
) -> None:
    caminho = tmp_path / "ausente.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "00_teste.sql").write_text("SELECT 1 AS valor", encoding="utf-8")
    criar_banco(caminho, omitir="itens_pedido_treino")
    monkeypatch.setattr(marts, "PASTA_SQL", pasta_sql)
    monkeypatch.setattr(marts, "conectar", lambda: duckdb.connect(str(caminho)))

    with (
        capturar_saida() as (stdout, stderr),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    assert stdout.getvalue() == ""
    assert "itens_pedido_treino" in stderr.getvalue()
    assert tabelas_marts(caminho) == ["anterior"]


def test_pasta_sql_vazia_para_antes_de_trocar_schema(
    tmp_path: Path, monkeypatch
) -> None:
    caminho = tmp_path / "vazio_sql.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    criar_banco(caminho)
    monkeypatch.setattr(marts, "PASTA_SQL", pasta_sql)
    monkeypatch.setattr(marts, "conectar", lambda: duckdb.connect(str(caminho)))

    with (
        capturar_saida() as (stdout, stderr),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    assert stdout.getvalue() == ""
    assert "Nenhum arquivo .sql" in stderr.getvalue()
    assert tabelas_marts(caminho) == ["anterior"]


def test_nomes_de_tabela_duplicados_para_antes_de_executar_sql(
    tmp_path: Path, monkeypatch
) -> None:
    caminho = tmp_path / "duplicados.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "01_teste.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    (pasta_sql / "02_teste.sql").write_text("SELECT 2 AS x", encoding="utf-8")
    criar_banco(caminho)
    monkeypatch.setattr(marts, "PASTA_SQL", pasta_sql)
    monkeypatch.setattr(marts, "conectar", lambda: duckdb.connect(str(caminho)))

    with (
        capturar_saida() as (stdout, stderr),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    assert stdout.getvalue() == ""
    assert "01_teste.sql" in stderr.getvalue()
    assert "02_teste.sql" in stderr.getvalue()
    assert tabelas_marts(caminho) == ["anterior"]


def test_sql_com_erro_preserva_schema_anterior_e_interrompe(
    tmp_path: Path, monkeypatch
) -> None:
    caminho = tmp_path / "erro_sql.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "00_valido.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    (pasta_sql / "01_erro.sql").write_text("SELEC INVALIDO", encoding="utf-8")
    criar_banco(caminho)
    monkeypatch.setattr(marts, "PASTA_SQL", pasta_sql)
    monkeypatch.setattr(marts, "conectar", lambda: duckdb.connect(str(caminho)))

    with (
        capturar_saida() as (stdout, stderr),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    assert stdout.getvalue() == ""
    assert "01_erro.sql" in stderr.getvalue()
    assert tabelas_marts(caminho) == ["anterior"]
