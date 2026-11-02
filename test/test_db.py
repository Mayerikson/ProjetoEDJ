from pathlib import Path

import duckdb
import pandas as pd
import pytest

from pipeline import db


def test_importar_modulo_nao_cria_banco(tmp_path: Path, monkeypatch) -> None:
    pasta_raw = tmp_path / "raw"
    pasta_raw.mkdir()
    caminho_banco = tmp_path / "instacart.duckdb"
    monkeypatch.setattr(db, "PASTA_RAW", pasta_raw)

    assert not caminho_banco.exists()

    con = db.conectar()
    con.close()

    assert caminho_banco.is_file()


def test_conectar_usa_raiz_do_modulo_mesmo_fora_do_projeto(
    tmp_path: Path, monkeypatch
) -> None:
    raiz_projeto = tmp_path / "projeto"
    pasta_raw = raiz_projeto / "raw"
    pasta_raw.mkdir(parents=True)
    outra_pasta = tmp_path / "outra_pasta"
    outra_pasta.mkdir()
    monkeypatch.setattr(db, "PASTA_RAW", pasta_raw)
    monkeypatch.chdir(outra_pasta)

    con = db.conectar()
    con.close()

    assert (raiz_projeto / "instacart.duckdb").is_file()
    assert not (outra_pasta / "instacart.duckdb").exists()


def test_criar_schema_e_gravar_dataframe_repetidamente(
    tmp_path: Path,
) -> None:
    con = duckdb.connect(str(tmp_path / "teste.duckdb"))
    dados = pd.DataFrame(
        [
            ("001", "texto"),  # ID com zero à esquerda deve continuar texto.
            (None, None),  # Nulos devem continuar NULL após a gravação.
            ("003", "outro"),  # Uma terceira linha distingue count da deduplicação.
        ],
        columns=["id", "descricao"],
    )

    db.criar_schema(con, 'dados"raw')
    db.criar_schema(con, 'dados"raw')
    assert db.gravar(con, dados, 'dados"raw', "itens") == 3
    assert db.gravar(con, dados, 'dados"raw', "itens") == 3
    assert con.execute('SELECT * FROM "dados""raw".itens').fetchall() == [
        ("001", "texto"),
        (None, None),
        ("003", "outro"),
    ]
    assert [
        coluna[1] for coluna in con.execute('DESCRIBE "dados""raw".itens').fetchall()
    ] == ["VARCHAR", "VARCHAR"]
    assert (
        con.execute(
            "SELECT COUNT(*) FROM duckdb_views() WHERE view_name LIKE '_dataframe_%'"
        ).fetchone()[0]
        == 0
    )
    con.close()


def test_gravar_aceita_relacao_duckdb(tmp_path: Path) -> None:
    con = duckdb.connect(str(tmp_path / "relacao.duckdb"))
    db.criar_schema(con, "refined")
    relacao = con.sql(
        "SELECT '0007' AS product_id UNION ALL SELECT NULL"
    )  # ID textual e nulo provam que a relação mantém tipos e valores.

    assert db.gravar(con, relacao, "refined", "produtos") == 2
    assert con.execute("SELECT * FROM refined.produtos").fetchall() == [
        ("0007",),
        (None,),
    ]
    con.close()


def test_gravar_remove_registro_temporario_se_a_escrita_falhar(
    tmp_path: Path,
) -> None:
    con = duckdb.connect(str(tmp_path / "erro.duckdb"))
    db.criar_schema(con, "refined")
    dados = pd.DataFrame({"id": ["1"]})

    with pytest.raises(duckdb.CatalogException):
        db.gravar(con, dados, "schema_inexistente", "tabela")

    assert (
        con.execute(
            "SELECT COUNT(*) FROM duckdb_views() WHERE view_name LIKE '_dataframe_%'"
        ).fetchone()[0]
        == 0
    )
    con.close()
