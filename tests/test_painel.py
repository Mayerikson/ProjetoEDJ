from pathlib import Path

import duckdb
import pandas as pd
import pytest

import painel


def test_formatadores_usam_separadores_pt_br() -> None:
    assert painel.reais(1003862.14) == "R$ 1.003.862,14"
    assert painel.pct(93.2) == "93,2%"
    assert painel.numero(96470) == "96.470"
    assert painel.numero(10.107, 2) == "10,11"


def test_ler_retorna_dataframes_e_lista_marts_ausentes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caminho_banco = tmp_path / "teste.duckdb"
    con = duckdb.connect(str(caminho_banco))
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.presente AS SELECT 1 AS valor")
    con.close()
    monkeypatch.setattr(painel, "CAMINHO_BANCO", caminho_banco)

    with pytest.raises(painel.MartsAusentesError) as erro:
        painel.ler(("presente", "ausente"))

    assert erro.value.nomes == ("ausente",)
    con = duckdb.connect(str(caminho_banco))
    try:
        assert con.execute("SELECT * FROM marts.presente").fetchall() == [(1,)]
    finally:
        con.close()


def test_grafico_de_produtos_mostra_top_dez_maior_primeiro() -> None:
    dados = pd.DataFrame(
        {
            "product_name": [f"Produto {numero}" for numero in range(12)],
            "vezes_comprado": list(range(12, 0, -1)),
        }
    )

    figura = painel.grafico_produtos_mais_comprados(dados)

    assert len(figura.data[0].y) == 10
    assert figura.data[0].y[0] == "Produto 0"
    assert figura.layout.yaxis.autorange == "reversed"
