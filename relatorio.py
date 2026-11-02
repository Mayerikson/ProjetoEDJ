"""Exporta uma prévia HTML estática do dashboard a partir dos marts existentes."""

from html import escape
from pathlib import Path

import plotly.io as pio

import painel

MARTS = (
    "indicadores_gerais",
    "pedidos_por_dia_semana",
    "pedidos_por_hora",
    "pedidos_por_dia_e_hora",
    "intervalo_entre_pedidos",
    "distribuicao_tamanho_cestas",
    "produtos_mais_comprados",
    "desempenho_departamentos",
    "desempenho_corredores",
    "recompra_por_posicao_carrinho",
)
CAMINHO_SAIDA = Path(__file__).resolve().parent / "dashboard_preview.html"


def gerar_dashboard_html(caminho_saida: str | Path = CAMINHO_SAIDA) -> Path:
    """Gera um HTML autocontido para abrir no navegador e compartilhar."""
    dados = painel.ler(MARTS)
    kpis = dados["indicadores_gerais"].iloc[0]
    metricas = (
        ("Pedidos observados", painel.numero(kpis["total_pedidos"]), "prior + train"),
        ("Usuários", painel.numero(kpis["total_usuarios"]), "prior + train"),
        ("Itens nos pedidos", painel.numero(kpis["total_itens"]), "prior + train"),
        ("Produtos comprados", painel.numero(kpis["produtos_comprados"]), "distintos"),
        (
            "Itens recomprados",
            painel.pct(kpis["percentual_itens_recomprados"], 2),
            "percentual dos itens",
        ),
        (
            "Média de itens por pedido",
            painel.numero(kpis["media_itens_por_pedido"], 2),
            "média calculada no SQL",
        ),
    )
    figuras = (
        (
            "Padrões de pedidos",
            painel.grafico_pedidos_por_dia(dados["pedidos_por_dia_semana"]),
        ),
        (
            "Padrões de pedidos",
            painel.grafico_pedidos_por_hora(dados["pedidos_por_hora"]),
        ),
        (
            "Padrões de pedidos",
            painel.grafico_pedidos_por_dia_e_hora(dados["pedidos_por_dia_e_hora"]),
        ),
        (
            "Cestas e recorrência",
            painel.grafico_intervalo_entre_pedidos(dados["intervalo_entre_pedidos"]),
        ),
        (
            "Cestas e recorrência",
            painel.grafico_tamanho_cestas(dados["distribuicao_tamanho_cestas"]),
        ),
        (
            "Cestas e recorrência",
            painel.grafico_recompra_por_posicao(dados["recompra_por_posicao_carrinho"]),
        ),
        (
            "Produtos e categorias",
            painel.grafico_produtos_mais_comprados(dados["produtos_mais_comprados"]),
        ),
        (
            "Produtos e categorias",
            painel.grafico_departamentos(dados["desempenho_departamentos"]),
        ),
        (
            "Produtos e categorias",
            painel.grafico_corredores(dados["desempenho_corredores"]),
        ),
    )

    conteudo_graficos = []
    secao_atual = None
    inclui_plotly = True
    for titulo_secao, figura in figuras:
        if titulo_secao != secao_atual:
            if secao_atual is not None:
                conteudo_graficos.append("</div></section>")
            conteudo_graficos.append(
                f'<section class="section"><h2>{escape(titulo_secao)}</h2><div class="grid">'
            )
            secao_atual = titulo_secao

        grafico_html = pio.to_html(
            figura,
            full_html=False,
            include_plotlyjs=inclui_plotly,
            config={"responsive": True, "displaylogo": False},
        )
        inclui_plotly = False
        conteudo_graficos.append(f'<article class="chart">{grafico_html}</article>')
    conteudo_graficos.append("</div></section>")

    cartoes = "".join(
        (
            '<article class="metric">'
            f'<span class="metric-label">{escape(rotulo)}</span>'
            f"<strong>{escape(valor)}</strong>"
            f'<span class="metric-help">{escape(ajuda)}</span>'
            "</article>"
        )
        for rotulo, valor, ajuda in metricas
    )
    documento = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Instacart · visão das compras</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
      color: #172b4d;
      background: #f3f6fa;
      font-synthesis: none;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; }}
    .page {{ max-width: 1440px; margin: 0 auto; padding: 38px clamp(18px, 4vw, 56px) 56px; }}
    header {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; margin-bottom: 28px; }}
    .eyebrow {{ color: #50708f; font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }}
    h1 {{ margin: 8px 0 0; font-size: clamp(28px, 4vw, 42px); letter-spacing: -.04em; }}
    .subhead {{ max-width: 660px; color: #60738a; font-size: 14px; line-height: 1.6; }}
    .metrics {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 14px; }}
    .metric, .chart {{ background: white; border: 1px solid #e6ecf2; border-radius: 16px; box-shadow: 0 5px 18px #2538580a; }}
    .metric {{ min-height: 126px; padding: 18px; display: flex; flex-direction: column; gap: 8px; }}
    .metric-label {{ color: #60738a; font-size: 12px; font-weight: 650; }}
    .metric strong {{ font-size: clamp(21px, 2vw, 29px); letter-spacing: -.035em; }}
    .metric-help {{ color: #8a9aab; font-size: 11px; }}
    .section {{ margin-top: 34px; }}
    h2 {{ margin: 0 0 14px; font-size: 20px; letter-spacing: -.02em; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .chart {{ min-width: 0; padding: 10px 12px; overflow: hidden; }}
    .chart:last-child:nth-child(odd) {{ grid-column: 1 / -1; }}
    footer {{ margin-top: 30px; color: #718198; font-size: 12px; line-height: 1.6; }}
    @media (max-width: 1050px) {{ .metrics {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
    @media (max-width: 680px) {{
      .page {{ padding-top: 26px; }}
      header {{ display: block; }}
      .subhead {{ margin-top: 12px; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
      .metric {{ min-height: 112px; padding: 14px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .chart:last-child:nth-child(odd) {{ grid-column: auto; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header>
      <div>
        <div class="eyebrow">Instacart · análise de compras</div>
        <h1>Visão das compras</h1>
      </div>
      <p class="subhead">Padrões de pedidos, composição das cestas e recorrência
      calculados nos dados prior e train. Valores apresentados conforme os marts.</p>
    </header>
    <section class="metrics" aria-label="Indicadores gerais">{cartoes}</section>
    {"".join(conteudo_graficos)}
    <footer>
      Os pedidos test não possuem itens rotulados. O dataset não contém preço
      nem data de calendário; portanto, esta prévia não mostra receita ou série mensal.
    </footer>
  </main>
</body>
</html>
"""
    destino = Path(caminho_saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(documento, encoding="utf-8")
    return destino


if __name__ == "__main__":
    print(gerar_dashboard_html())
