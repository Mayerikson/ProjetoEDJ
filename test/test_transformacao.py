import contextlib
import io
from pathlib import Path

import duckdb
import pytest

from pipeline import transformacao


class CapturedStream(io.StringIO):
    def reconfigure(self, *, encoding: str) -> None:
        self.configured_encoding = encoding


def criar_banco_raw(caminho: Path, omitir: str | None = None) -> None:
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA raw")
    definicoes = {
        "corredores": "aisle_id VARCHAR, aisle VARCHAR",
        "departamentos": "department_id VARCHAR, department VARCHAR",
        "produtos": (
            "product_id VARCHAR, product_name VARCHAR, "
            "aisle_id VARCHAR, department_id VARCHAR"
        ),
        "pedidos": (
            "order_id VARCHAR, user_id VARCHAR, eval_set VARCHAR, "
            "order_number VARCHAR, order_dow VARCHAR, "
            "order_hour_of_day VARCHAR, days_since_prior_order VARCHAR"
        ),
        "itens_pedido_prior": (
            "order_id VARCHAR, product_id VARCHAR, "
            "add_to_cart_order VARCHAR, reordered VARCHAR"
        ),
        "itens_pedido_treino": (
            "order_id VARCHAR, product_id VARCHAR, "
            "add_to_cart_order VARCHAR, reordered VARCHAR"
        ),
    }
    for tabela, colunas in definicoes.items():
        if tabela != omitir:
            con.execute(f"CREATE TABLE raw.{tabela} ({colunas})")

    if omitir is None:
        # Duas cópias da primeira linha provam deduplicação exata.
        con.executemany(
            "INSERT INTO raw.corredores VALUES (?, ?)",
            [
                ("001", "Fresh"),  # Primeira ocorrência da chave de corredor.
                ("001", "Fresh"),  # Duplicata exata a ser removida.
                ("001", "Frozen"),  # Mesmo ID com conteúdo diferente gera aviso.
            ],
        )
        con.execute("INSERT INTO raw.departamentos VALUES ('01', 'Produce')")
        con.execute("INSERT INTO raw.produtos VALUES ('0001', 'Apple', '001', '01')")
        # Valor inválido vira NULL, enquanto dia e hora convertíveis são preservados.
        con.executemany(
            "INSERT INTO raw.pedidos VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("0001", "0002", "prior", "2", "6", "23", "2.5"),
                # Casts válidos e decimal preservado.
                ("0002", "0003", "prior", "ruim", "9", "30", ""),  # Cast falho vira NULL.
            ],
        )
        # A mesma chave com reordered diferente prova que conflitos não removem linhas.
        con.executemany(
            "INSERT INTO raw.itens_pedido_prior VALUES (?, ?, ?, ?)",
            [
                ("0001", "0001", "1", "0"),  # Primeira variante da chave do item.
                ("0001", "0001", "1", "1"),  # Variante conflitante preservada.
            ],
        )
        con.execute(
            "INSERT INTO raw.itens_pedido_treino VALUES ('0002', '0001', '1', '1')"
        )
    con.close()


def test_transformacao_deduplica_casts_tolerantes_e_preserva_raw(
    tmp_path: Path, monkeypatch
) -> None:
    caminho_banco = tmp_path / "transformacao.duckdb"
    criar_banco_raw(caminho_banco)
    monkeypatch.setattr(
        transformacao, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )
    stdout, stderr = CapturedStream(), CapturedStream()

    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        transformacao.main()

    assert stderr.getvalue() == ""
    assert "refined.corredores: 2 (duplicatas removidas: 1)" in stdout.getvalue()
    assert "1 chaves conflitantes na tabela." in stdout.getvalue()
    con = duckdb.connect(str(caminho_banco), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM raw.corredores").fetchone()[0] == 3
    assert con.execute("SELECT COUNT(*) FROM refined.corredores").fetchone()[0] == 2
    assert con.execute(
        "SELECT order_id, user_id, order_number, order_dow, "
        "order_hour_of_day, days_since_prior_order "
        "FROM refined.pedidos WHERE order_id = '0001'"
    ).fetchone() == ("0001", "0002", 2, 6, 23, 2.5)
    assert con.execute(
        "SELECT order_number, days_since_prior_order "
        "FROM refined.pedidos WHERE order_id = '0002'"
    ).fetchone() == (None, None)
    assert [
        coluna[1] for coluna in con.execute("DESCRIBE refined.pedidos").fetchall()
    ] == ["VARCHAR", "VARCHAR", "VARCHAR", "INTEGER", "INTEGER", "INTEGER", "DOUBLE"]
    assert (
        con.execute("SELECT COUNT(*) FROM refined.itens_pedido_prior").fetchone()[0]
        == 2
    )
    con.close()


def test_tabela_raw_ausente_para_antes_de_criar_refined(
    tmp_path: Path, monkeypatch
) -> None:
    caminho_banco = tmp_path / "incompleto.duckdb"
    criar_banco_raw(caminho_banco, omitir="itens_pedido_treino")
    monkeypatch.setattr(
        transformacao, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )
    stdout, stderr = CapturedStream(), CapturedStream()

    with (
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
        pytest.raises(SystemExit) as erro,
    ):
        transformacao.main()

    assert erro.value.code == 1
    assert stdout.getvalue() == ""
    assert "itens_pedido_treino" in stderr.getvalue()
    con = duckdb.connect(str(caminho_banco), read_only=True)
    assert (
        con.execute(
            "SELECT COUNT(*) FROM information_schema.schemata "
            "WHERE schema_name = 'refined'"
        ).fetchone()[0]
        == 0
    )
    con.close()


def test_erro_durante_transformacao_reverte_tabelas_parciais(
    tmp_path: Path, monkeypatch
) -> None:
    caminho_banco = tmp_path / "rollback.duckdb"
    criar_banco_raw(caminho_banco)
    con = duckdb.connect(str(caminho_banco))
    con.execute("CREATE SCHEMA refined")
    con.execute("CREATE TABLE refined.anterior AS SELECT 7 AS valor")
    con.close()
    monkeypatch.setattr(
        transformacao, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )
    gravar_original = transformacao.gravar

    def falhar_ao_gravar_departamentos(con, relacao, schema, tabela):
        if tabela == "departamentos":
            raise RuntimeError("falha inventada na gravação")
        return gravar_original(con, relacao, schema, tabela)

    monkeypatch.setattr(transformacao, "gravar", falhar_ao_gravar_departamentos)
    stdout, stderr = CapturedStream(), CapturedStream()

    with (
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
        pytest.raises(RuntimeError, match="falha inventada"),
    ):
        transformacao.main()

    assert stdout.getvalue() == ""
    assert stderr.getvalue() == ""
    con = duckdb.connect(str(caminho_banco), read_only=True)
    tabelas = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'refined' ORDER BY table_name"
    ).fetchall()
    assert tabelas == [("anterior",)]
    con.close()
