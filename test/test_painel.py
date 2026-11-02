from pathlib import Path

import duckdb
import pandas as pd
import pytest

import painel


def test_formatadores_pt_br_com_entradas_inventadas() -> None:
    assert painel.reais(1234.5) == "R$ 1.234,50"
    assert painel.pct(12.34, 2) == "12,34%"
    assert painel.numero(1234567) == "1.234.567"


def test_ler_usa_banco_temporario_e_fecha_conexao(tmp_path: Path, monkeypatch) -> None:
    caminho = tmp_path / "painel.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.exemplo AS SELECT 7 AS valor")
    con.close()
    monkeypatch.setattr(painel, "CAMINHO_BANCO", caminho)

    dados = painel.ler(("exemplo",))

    assert dados["exemplo"].to_dict(orient="records") == [{"valor": 7}]
    con = duckdb.connect(str(caminho))
    assert con.execute("SELECT 8 AS escrita").fetchone() == (8,)
    con.close()


def test_ler_lista_todas_as_marts_ausentes(tmp_path: Path, monkeypatch) -> None:
    caminho = tmp_path / "ausentes.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA marts")
    con.close()
    monkeypatch.setattr(painel, "CAMINHO_BANCO", caminho)

    with pytest.raises(painel.MartsAusentesError) as erro:
        painel.ler(("faltante_a", "faltante_b"))

    assert erro.value.nomes == ("faltante_a", "faltante_b")


def test_graficos_devolvem_uma_marca_por_linha_inventada() -> None:
    def quadro(colunas: list[str], linhas: list[tuple]) -> pd.DataFrame:
        return pd.DataFrame(linhas, columns=colunas)

    amostras = (
        (
            painel.grafico_pedidos_por_dia,
            quadro(
                ["dia_semana", "quantidade_pedidos"],
                [
                    (0, 4),  # Dia inicial com quatro pedidos.
                    (1, 3),  # Dia seguinte prova um segundo ponto.
                    (2, 2),  # Terceiro dia prova que todos os registros viram pontos.
                ],
            ),
        ),
        (
            painel.grafico_pedidos_por_hora,
            quadro(
                ["hora", "quantidade_pedidos"],
                [
                    (8, 1),  # Hora da manhã com um pedido.
                    (9, 3),  # Hora de pico inventada.
                    (10, 2),  # Hora adjacente para validar três marcas.
                ],
            ),
        ),
        (
            painel.grafico_pedidos_por_dia_e_hora,
            quadro(
                ["dia_semana", "hora", "quantidade_pedidos"],
                [
                    (0, 8, 1),  # Primeiro par dia-hora.
                    (1, 9, 3),  # Segundo par, com volume maior.
                    (2, 10, 2),  # Terceiro par mantém a contagem de pontos.
                ],
            ),
        ),
        (
            painel.grafico_intervalo_entre_pedidos,
            quadro(
                ["dias_desde_pedido_anterior", "quantidade_pedidos"],
                [
                    (None, 1),  # Primeiro pedido sem intervalo conhecido.
                    (7.0, 3),  # Intervalo semanal inventado.
                    (14.0, 2),  # Intervalo quinzenal para terceiro ponto.
                ],
            ),
        ),
        (
            painel.grafico_tamanho_cestas,
            quadro(
                ["itens_por_pedido", "quantidade_pedidos"],
                [
                    (1, 3),  # Cestas unitárias.
                    (2, 2),  # Cestas de dois itens.
                    (3, 1),  # Cesta maior para manter três categorias.
                ],
            ),
        ),
        (
            painel.grafico_produtos_mais_comprados,
            quadro(
                ["product_name", "vezes_comprado"],
                [
                    ("Maçã", 3),  # Produto mais comprado da amostra.
                    ("Pera", 2),  # Produto intermediário.
                    ("Uva", 1),  # Produto menos comprado.
                ],
            ),
        ),
        (
            painel.grafico_departamentos,
            quadro(
                ["department", "quantidade_itens"],
                [
                    ("Frutas", 3),  # Departamento com maior contagem.
                    ("Laticínios", 2),  # Departamento intermediário.
                    ("Padaria", 1),  # Departamento com menor contagem.
                ],
            ),
        ),
        (
            painel.grafico_corredores,
            quadro(
                ["aisle", "quantidade_itens"],
                [
                    ("Frutas", 3),  # Corredor mais movimentado.
                    ("Leite", 2),  # Corredor intermediário.
                    ("Pães", 1),  # Corredor menos movimentado.
                ],
            ),
        ),
        (
            painel.grafico_recompra_por_posicao,
            quadro(
                [
                    "posicao_no_carrinho",
                    "quantidade_itens",
                    "percentual_recomprado",
                ],
                [
                    (1, 3, 20.0),  # Primeira posição com recompra mais baixa.
                    (2, 2, 40.0),  # Posição intermediária.
                    (3, 1, 60.0),  # Terceira posição com recompra mais alta.
                ],
            ),
        ),
    )

    for criar_figura, dados in amostras:
        figura = criar_figura(dados)
        assert len(figura.data[0].x) == len(dados)
