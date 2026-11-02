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

kpis = dados["indicadores_gerais"].iloc[0]
st.caption(
    "Pedidos e itens analisados combinam os conjuntos prior e train; os pedidos "
    "test não têm itens rotulados. O dataset não contém preço nem data de calendário."
)

st.subheader("Volume e alcance")
colunas = st.columns(3)
colunas[0].metric(
    "Pedidos observados · prior + train",
    painel.numero(kpis["total_pedidos"]),
    help="Quantidade total de pedidos dos conjuntos prior e train.",
)
colunas[1].metric(
    "Usuários · prior + train",
    painel.numero(kpis["total_usuarios"]),
    help="Usuários distintos com pedidos nos conjuntos prior e train.",
)
colunas[2].metric(
    "Itens nos pedidos · prior + train",
    painel.numero(kpis["total_itens"]),
    help="Itens combinados dos pedidos prior e train.",
)

st.subheader("Composição e recorrência")
colunas = st.columns(3)
colunas[0].metric(
    "Produtos distintos · prior + train",
    painel.numero(kpis["produtos_comprados"]),
    help="Produtos distintos presentes nos itens observados.",
)
colunas[1].metric(
    "Itens recomprados · % dos itens",
    painel.pct(kpis["percentual_itens_recomprados"], 2),
    help="Percentual dos itens marcado como recompra.",
)
colunas[2].metric(
    "Itens por pedido · média",
    painel.numero(kpis["media_itens_por_pedido"], 2),
    help="Média calculada no mart de indicadores gerais.",
)

st.subheader("Pedidos ao longo do dia")
st.plotly_chart(
    painel.grafico_pedidos_por_hora(dados["pedidos_por_hora"]),
    width="stretch",
)

st.subheader("Padrões da semana")
esquerda, direita = st.columns(2)
esquerda.plotly_chart(
    painel.grafico_pedidos_por_dia(dados["pedidos_por_dia_semana"]),
    width="stretch",
)
direita.plotly_chart(
    painel.grafico_pedidos_por_dia_e_hora(dados["pedidos_por_dia_e_hora"]),
    width="stretch",
)

st.subheader("Cestas e recompra")
colunas = st.columns(3)
colunas[0].plotly_chart(
    painel.grafico_intervalo_entre_pedidos(dados["intervalo_entre_pedidos"]),
    width="stretch",
)
colunas[1].plotly_chart(
    painel.grafico_tamanho_cestas(dados["distribuicao_tamanho_cestas"]),
    width="stretch",
)
colunas[2].plotly_chart(
    painel.grafico_recompra_por_posicao(dados["recompra_por_posicao_carrinho"]),
    width="stretch",
)

st.subheader("Produtos e categorias")
colunas = st.columns(3)
colunas[0].plotly_chart(
    painel.grafico_produtos_mais_comprados(dados["produtos_mais_comprados"]),
    width="stretch",
)
colunas[1].plotly_chart(
    painel.grafico_departamentos(dados["desempenho_departamentos"]),
    width="stretch",
)
colunas[2].plotly_chart(
    painel.grafico_corredores(dados["desempenho_corredores"]),
    width="stretch",
)
