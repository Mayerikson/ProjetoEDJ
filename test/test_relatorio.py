from pathlib import Path

import duckdb

import painel
import relatorio


def test_exporta_html_autocontido_com_dados_sinteticos(
    tmp_path: Path, monkeypatch
) -> None:
    caminho_banco = tmp_path / "dados.duckdb"
    con = duckdb.connect(str(caminho_banco))
    con.execute("CREATE SCHEMA marts")
    tabelas = {
        "indicadores_gerais": (
            "SELECT 12 AS total_pedidos, 5 AS total_usuarios, "
            "36 AS total_itens, 8 AS produtos_comprados, "
            "25.5 AS percentual_itens_recomprados, "
            "3.0 AS media_itens_por_pedido"
        ),
        "pedidos_por_dia_semana": ("SELECT 0 AS dia_semana, 4 AS quantidade_pedidos"),
        "pedidos_por_hora": "SELECT 9 AS hora, 4 AS quantidade_pedidos",
        "pedidos_por_dia_e_hora": (
            "SELECT 0 AS dia_semana, 9 AS hora, 4 AS quantidade_pedidos"
        ),
        "intervalo_entre_pedidos": (
            "SELECT CAST(NULL AS INTEGER) AS dias_desde_pedido_anterior, "
            "1 AS quantidade_pedidos"
        ),
        "distribuicao_tamanho_cestas": (
            "SELECT 2 AS itens_por_pedido, 3 AS quantidade_pedidos, "
            "100.0 AS percentual_pedidos"
        ),
        "produtos_mais_comprados": (
            "SELECT 'P1' AS product_id, 'Apple' AS product_name, "
            "4 AS vezes_comprado, 3 AS pedidos_com_produto, "
            "25.0 AS percentual_recomprado"
        ),
        "desempenho_departamentos": (
            "SELECT '1' AS department_id, 'Frutas' AS department, 4 AS quantidade_itens"
        ),
        "desempenho_corredores": (
            "SELECT '1' AS aisle_id, 'Frutas frescas' AS aisle, 4 AS quantidade_itens"
        ),
        "recompra_por_posicao_carrinho": (
            "SELECT 1 AS posicao_no_carrinho, 4 AS quantidade_itens, "
            "25.0 AS percentual_recomprado"
        ),
    }
    for tabela, consulta in tabelas.items():
        con.execute(f"CREATE TABLE marts.{tabela} AS {consulta}")
    con.close()

    monkeypatch.setattr(painel, "CAMINHO_BANCO", caminho_banco)
    destino = tmp_path / "preview.html"

    resultado = relatorio.gerar_dashboard_html(destino)

    conteudo = resultado.read_text(encoding="utf-8")
    assert resultado == destino
    assert '<html lang="pt-BR">' in conteudo
    assert "Pedidos observados" in conteudo
    assert "12" in conteudo
    assert "Pedidos por dia da semana" in conteudo
    assert "plotly.js" in conteudo
    assert "Apple" in conteudo
    assert conteudo.count('class="chart span-') == 9
    assert "grid-template-columns: repeat(12" in conteudo
    assert "Volume e alcance" in conteudo
    assert "Composição e recorrência" in conteudo
