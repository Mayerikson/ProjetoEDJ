import duckdb
import streamlit as st

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
COMANDO_MARTS = "uv run python -m pipeline.marts"


@st.cache_data
def carregar_dados(nomes: tuple[str, ...]) -> dict:
    return painel.ler(nomes)


st.set_page_config(page_title="Instacart · visão das compras", layout="wide")

cabecalho, acao = st.columns([5, 1])
with cabecalho:
    st.title("Instacart · visão das compras")
with acao:
    st.write("")
    if st.button("Recarregar dados", width="stretch"):
        carregar_dados.clear()
        st.rerun()

if not painel.CAMINHO_BANCO.is_file():
    st.error(
        f"Banco não encontrado: {painel.CAMINHO_BANCO}. "
        f"Execute `{COMANDO_MARTS}` depois de preparar as camadas anteriores."
    )
    st.stop()

try:
    dados = carregar_dados(MARTS)
except painel.MartsAusentesError as exc:
    st.error(
        f"Faltam estas tabelas no schema marts: {', '.join(exc.nomes)}. "
        f"Execute `{COMANDO_MARTS}`."
    )
    st.stop()
except duckdb.Error as exc:
    st.error(f"Não foi possível ler os marts: {exc}. Execute `{COMANDO_MARTS}`.")
    st.stop()

st.caption(
    "Os itens analisados combinam prior e train; pedidos test não têm itens "
    "rotulados. O dataset não contém preço nem data de calendário."
)

kpis = dados["indicadores_gerais"].iloc[0]
for inicio in (0, 3):
    colunas = st.columns(3)
    metricas = (
        (
            "Pedidos observados",
            painel.numero(kpis["total_pedidos"]),
            "Pedidos prior e train.",
        ),
        (
            "Usuários",
            painel.numero(kpis["total_usuarios"]),
            "Usuários com pedidos prior ou train.",
        ),
        (
            "Itens nos pedidos",
            painel.numero(kpis["total_itens"]),
            "Itens combinados de prior e train.",
        ),
        (
            "Produtos comprados",
            painel.numero(kpis["produtos_comprados"]),
            "Produtos distintos presentes nos itens.",
        ),
        (
            "Itens recomprados",
            painel.pct(kpis["percentual_itens_recomprados"], 2),
            "Percentual de itens marcados como recompra.",
        ),
        (
            "Média de itens por pedido",
            painel.numero(kpis["media_itens_por_pedido"], 2),
            "Média já calculada no mart de indicadores gerais.",
        ),
    )
    for coluna, (rotulo, valor, ajuda) in zip(
        colunas, metricas[inicio : inicio + 3], strict=True
    ):
        coluna.metric(rotulo, valor, help=ajuda)

st.subheader("Padrões de pedidos")
esquerda, direita = st.columns(2)
esquerda.plotly_chart(
    painel.grafico_pedidos_por_dia(dados["pedidos_por_dia_semana"]),
    width="stretch",
)
direita.plotly_chart(
    painel.grafico_pedidos_por_hora(dados["pedidos_por_hora"]),
    width="stretch",
)
st.plotly_chart(
    painel.grafico_pedidos_por_dia_e_hora(dados["pedidos_por_dia_e_hora"]),
    width="stretch",
)

st.subheader("Cestas e recorrência")
esquerda, direita = st.columns(2)
esquerda.plotly_chart(
    painel.grafico_intervalo_entre_pedidos(dados["intervalo_entre_pedidos"]),
    width="stretch",
)
direita.plotly_chart(
    painel.grafico_tamanho_cestas(dados["distribuicao_tamanho_cestas"]),
    width="stretch",
)
st.plotly_chart(
    painel.grafico_recompra_por_posicao(dados["recompra_por_posicao_carrinho"]),
    width="stretch",
)

st.subheader("Produtos e categorias")
esquerda, direita = st.columns(2)
esquerda.plotly_chart(
    painel.grafico_produtos_mais_comprados(dados["produtos_mais_comprados"]),
    width="stretch",
)
direita.plotly_chart(
    painel.grafico_departamentos(dados["desempenho_departamentos"]),
    width="stretch",
)
st.plotly_chart(
    painel.grafico_corredores(dados["desempenho_corredores"]),
    width="stretch",
)
