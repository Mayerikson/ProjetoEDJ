"""Leitura, formatação e gráficos puros para o dashboard Instacart.

Esta versão usa o escopo Instacart confirmado para este workspace, em vez das
tabelas Olist da spec de referência. Lê apenas as dez tabelas já materializadas
em ``marts``; cada nome gera uma consulta ``SELECT *``. A conexão é read-only
e fecha dentro de ``ler`` para não manter o arquivo bloqueado enquanto o
pipeline atualiza os marts. Se faltar uma tabela, os nomes ausentes são
devolvidos juntos para a página orientar a regeneração dos marts.

Os seis indicadores gerais e os dados de cada gráfico já vêm calculados das
consultas SQL. Esta camada não cria agregações nem regras de negócio: apenas
formata texto, seleciona as dez primeiras linhas onde o gráfico pede um top
10 e configura figuras Plotly. As funções de figura não dependem de Streamlit
ou do banco para também poderem ser reutilizadas em outros relatórios.

O dataset contém dia da semana e hora, mas não data de calendário ou preço.
Por isso, o dashboard mostra padrões por dia/hora, não faturamento mensal,
ticket em reais ou filtro por mês. Os pedidos de ``test`` não têm itens
rotulados; os marts de comportamento combinam ``prior`` e ``train``.
"""

from collections.abc import Sequence
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

CAMINHO_BANCO = Path(__file__).resolve().parent / "instacart.duckdb"
COR = "#2E86C1"
DIAS_SEMANA = ("Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado")


class MartsAusentesError(Exception):
    """Informa todas as tabelas mart que não existem no banco."""

    def __init__(self, nomes: Sequence[str]) -> None:
        self.nomes = tuple(nomes)
        super().__init__(", ".join(self.nomes))


def ler(marts: Sequence[str]) -> dict[str, pd.DataFrame]:
    """Lê uma tabela de mart por nome, usando somente SELECT *."""
    con = duckdb.connect(str(CAMINHO_BANCO), read_only=True)
    dados: dict[str, pd.DataFrame] = {}
    ausentes = []
    try:
        for nome in marts:
            try:
                dados[nome] = con.execute(f"SELECT * FROM marts.{nome}").fetchdf()
            except duckdb.CatalogException as exc:
                if "does not exist" not in str(exc):
                    raise
                ausentes.append(nome)
    finally:
        con.close()

    if ausentes:
        raise MartsAusentesError(ausentes)
    return dados


def _decimal_pt(valor: float, casas: int) -> str:
    formatado = f"{valor:,.{casas}f}"
    return formatado.replace(",", "\0").replace(".", ",").replace("\0", ".")


def reais(valor: float, casas: int = 2) -> str:
    return f"R$ {_decimal_pt(valor, casas)}"


def pct(valor: float, casas: int = 1) -> str:
    return f"{_decimal_pt(valor, casas)}%"


def numero(valor: float, casas: int = 0) -> str:
    return _decimal_pt(valor, casas)


def grafico_pedidos_por_dia(dados: pd.DataFrame) -> go.Figure:
    figura = px.bar(
        dados,
        x="dia_semana",
        y="quantidade_pedidos",
        title="02 · Pedidos por dia da semana",
        color_discrete_sequence=[COR],
    )
    figura.update_xaxes(
        title="Dia da semana (0 = domingo)",
        tickmode="array",
        tickvals=list(range(7)),
        ticktext=list(DIAS_SEMANA),
    )
    figura.update_yaxes(title="Pedidos")
    return figura


def grafico_pedidos_por_hora(dados: pd.DataFrame) -> go.Figure:
    figura = px.line(
        dados,
        x="hora",
        y="quantidade_pedidos",
        markers=True,
        title="03 · Pedidos por hora",
        color_discrete_sequence=[COR],
    )
    figura.update_xaxes(title="Hora do dia")
    figura.update_yaxes(title="Pedidos")
    return figura


def grafico_pedidos_por_dia_e_hora(dados: pd.DataFrame) -> go.Figure:
    figura = px.scatter(
        dados,
        x="hora",
        y="dia_semana",
        size="quantidade_pedidos",
        title="04 · Pedidos por dia e hora",
        color_discrete_sequence=[COR],
        size_max=24,
    )
    figura.update_xaxes(title="Hora do dia")
    figura.update_yaxes(
        title="Dia da semana",
        tickmode="array",
        tickvals=list(range(7)),
        ticktext=list(DIAS_SEMANA),
    )
    return figura


def grafico_intervalo_entre_pedidos(dados: pd.DataFrame) -> go.Figure:
    rotulos = dados["dias_desde_pedido_anterior"].map(
        lambda valor: "Primeira compra" if pd.isna(valor) else f"{numero(valor)} dias"
    )
    figura = px.bar(
        dados.assign(intervalo=rotulos),
        x="intervalo",
        y="quantidade_pedidos",
        title="05 · Intervalo entre pedidos",
        color_discrete_sequence=[COR],
        category_orders={"intervalo": rotulos.tolist()},
    )
    figura.update_xaxes(title="Dias desde o pedido anterior")
    figura.update_yaxes(title="Pedidos")
    return figura


def grafico_tamanho_cestas(dados: pd.DataFrame) -> go.Figure:
    figura = px.line(
        dados,
        x="itens_por_pedido",
        y="quantidade_pedidos",
        markers=True,
        title="06 · Distribuição do tamanho das cestas",
        color_discrete_sequence=[COR],
    )
    figura.update_xaxes(title="Itens por pedido")
    figura.update_yaxes(title="Pedidos")
    return figura


def grafico_produtos_mais_comprados(dados: pd.DataFrame) -> go.Figure:
    figura = px.bar(
        dados.head(10),
        x="vezes_comprado",
        y="product_name",
        orientation="h",
        title="07 · 10 produtos mais comprados",
        color_discrete_sequence=[COR],
    )
    figura.update_xaxes(title="Compras")
    figura.update_yaxes(title="Produto", autorange="reversed")
    return figura


def grafico_departamentos(dados: pd.DataFrame) -> go.Figure:
    figura = px.bar(
        dados,
        x="quantidade_itens",
        y="department",
        orientation="h",
        title="08 · Itens por departamento",
        color_discrete_sequence=[COR],
    )
    figura.update_xaxes(title="Itens")
    figura.update_yaxes(title="Departamento", autorange="reversed")
    return figura


def grafico_corredores(dados: pd.DataFrame) -> go.Figure:
    figura = px.bar(
        dados.head(10),
        x="quantidade_itens",
        y="aisle",
        orientation="h",
        title="09 · 10 corredores com mais itens",
        color_discrete_sequence=[COR],
    )
    figura.update_xaxes(title="Itens")
    figura.update_yaxes(title="Corredor", autorange="reversed")
    return figura


def grafico_recompra_por_posicao(dados: pd.DataFrame) -> go.Figure:
    figura = px.line(
        dados,
        x="posicao_no_carrinho",
        y="percentual_recomprado",
        markers=True,
        title="10 · Recompra por posição no carrinho",
        color_discrete_sequence=[COR],
    )
    figura.update_xaxes(title="Posição no carrinho")
    figura.update_yaxes(title="Itens recomprados (%)")
    return figura
