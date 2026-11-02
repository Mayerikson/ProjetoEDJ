"""Ingestão fiel dos seis CSVs principais para o schema ``raw``.

O mapeamento literal é aisles→corredores, departments→departamentos,
products→produtos, orders→pedidos, order_products__prior→itens_pedido_prior e
order_products__train→itens_pedido_treino; ``sample_submission`` é excluído
porque não faz parte da ingestão. Se houver ambas as extensões, ``.csv`` tem
preferência sobre ``.csv.gz``.

Todos os arquivos são verificados antes de abrir o banco para não deixar cinco
tabelas gravadas e produzir um resultado aparentemente completo. CSV e gzip
são lidos diretamente com UTF-8 e ``dtype=str``: IDs, nomes de colunas, linhas
e valores não são descartados, deduplicados, renomeados nem convertidos, pois
a limpeza pertence à etapa ``refined``. Somente campos vazios viram nulos;
marcadores não vazios como ``NA`` permanecem texto. Cada tabela é recriada ao
reexecutar, para que uma nova execução não acrescente dados à anterior.

A saída informa cada nome qualificado e a contagem consultada no banco, além
do total, com milhares separados por ponto para facilitar a conferência.
stdout e stderr usam UTF-8 para que os nomes e mensagens com acentos sejam
legíveis no Prompt de Comando do Windows.
"""

import sys

import pandas as pd

from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar

TABELAS = (
    ("aisles", "corredores"),
    ("departments", "departamentos"),
    ("products", "produtos"),
    ("orders", "pedidos"),
    ("order_products__prior", "itens_pedido_prior"),
    ("order_products__train", "itens_pedido_treino"),
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    arquivos = {}
    faltantes = []
    for nome_base, _ in TABELAS:
        caminho_csv = PASTA_RAW / f"{nome_base}.csv"
        caminho_gzip = PASTA_RAW / f"{nome_base}.csv.gz"
        if caminho_csv.is_file():
            arquivos[nome_base] = caminho_csv
        elif caminho_gzip.is_file():
            arquivos[nome_base] = caminho_gzip
        else:
            faltantes.append(nome_base)

    if faltantes:
        lista_faltantes = ", ".join(faltantes)
        print(
            f"Arquivos ausentes em {PASTA_RAW}: {lista_faltantes} "
            "(esperado .csv ou .csv.gz).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    con = conectar()
    try:
        criar_schema(con, "raw")
        total = 0
        for nome_base, tabela in TABELAS:
            df = pd.read_csv(
                arquivos[nome_base],
                encoding="utf-8",
                dtype=str,
                keep_default_na=False,
                na_values=[""],
                skip_blank_lines=False,
            )
            contagem = gravar(con, df, "raw", tabela)
            print(f"raw.{tabela}: {contagem:,}".replace(",", "."))
            total += contagem
            del df

        print(f"Total: {total:,}".replace(",", "."))
    finally:
        con.close()


if __name__ == "__main__":
    main()
