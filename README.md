# ProjetoEDJ · análise de compras Instacart

Pipeline de dados criado como desafio final do curso: da fonte pública aos
indicadores, usando Python, SQL, DuckDB, testes e Git. O projeto explora
comportamentos de compra — frequência, tamanho das cestas, produtos e
recompras — em vez de reproduzir os indicadores do pipeline Spec do curso.

## Fonte e licença

- **Dataset:** [Instacart Market Basket Analysis no Kaggle](https://www.kaggle.com/datasets/psparks/instacart-market-basket-analysis).
- **Origem dos dados:** Instacart; a página Kaggle disponibiliza os arquivos
  usados neste projeto e declara a licença **CC0: Public Domain**. Consulte
  também a [licença CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
- **Download:** acesse a página Kaggle, baixe e extraia os arquivos CSV para
  `raw/` na raiz do repositório. É necessário ter uma conta Kaggle e aceitar
  os termos apresentados pela plataforma, se solicitado.

Os CSVs e o banco DuckDB são arquivos locais e não fazem parte deste
repositório. O pipeline espera os seis arquivos abaixo; `sample_submission`
não é usado:

```text
raw/
├── aisles.csv
├── departments.csv
├── products.csv
├── orders.csv
├── order_products__prior.csv
└── order_products__train.csv
```

## O que representa uma linha

| Arquivo de origem | Tabela `raw` / `refined` | Granularidade e chave de relacionamento |
|---|---|---|
| `aisles.csv` | `corredores` | Um corredor; chave `aisle_id`. |
| `departments.csv` | `departamentos` | Um departamento; chave `department_id`. |
| `products.csv` | `produtos` | Um produto; chave `product_id`, ligado a `corredores` e `departamentos`. |
| `orders.csv` | `pedidos` | Um pedido; chave `order_id`, com `user_id`, conjunto (`eval_set`), dia e hora. |
| `order_products__prior.csv` | `itens_pedido_prior` | Um produto em um pedido do conjunto `prior`; chave composta `order_id`, `product_id`. |
| `order_products__train.csv` | `itens_pedido_treino` | Um produto em um pedido do conjunto `train`; chave composta `order_id`, `product_id`. |

Os itens se ligam aos pedidos por `order_id` e aos produtos por `product_id`.
Produtos se ligam a corredores por `aisle_id` e a departamentos por
`department_id`. As consultas de desempenho usam esses relacionamentos com
`JOIN`.

## Camadas e indicadores

O arquivo `instacart.duckdb` é criado na raiz do projeto e contém três schemas:

1. **`raw` — dado bruto.** `pipeline.ingestao` carrega os seis CSVs sem
   conversão ou renomeação de valores; campos vazios são armazenados como
   `NULL`. Esta etapa recria as tabelas a cada execução.
2. **`refined` — dado transformado.** `pipeline.transformacao` mantém os nomes
   originais, conserva IDs como texto, converte contagens e horários para
   tipos numéricos, converte valores inválidos em `NULL`, remove duplicatas
   exatas e avisa sobre chaves com conteúdos conflitantes sem descartar essas
   linhas.
3. **`marts` — indicadores.** `pipeline.marts` materializa uma tabela por
   arquivo em `sql/marts/`. Cada arquivo é a fonte SQL da regra de negócio;
   o schema é atualizado em uma transação e um mart vazio causa erro.

| SQL | Tabela em `marts` | Pergunta respondida |
|---|---|---|
| [`01_indicadores_gerais.sql`](sql/marts/01_indicadores_gerais.sql) | `indicadores_gerais` | Quantos pedidos, usuários, itens e produtos foram observados? Qual a taxa de recompra e a média de itens por pedido? |
| [`02_pedidos_por_dia_semana.sql`](sql/marts/02_pedidos_por_dia_semana.sql) | `pedidos_por_dia_semana` | Como o volume de pedidos se distribui pelos dias da semana? |
| [`03_pedidos_por_hora.sql`](sql/marts/03_pedidos_por_hora.sql) | `pedidos_por_hora` | Como o volume se distribui pelas horas do dia? |
| [`04_pedidos_por_dia_e_hora.sql`](sql/marts/04_pedidos_por_dia_e_hora.sql) | `pedidos_por_dia_e_hora` | Como dia da semana e hora se combinam no volume de pedidos? |
| [`05_intervalo_entre_pedidos.sql`](sql/marts/05_intervalo_entre_pedidos.sql) | `intervalo_entre_pedidos` | Qual a distribuição dos dias entre pedidos consecutivos? |
| [`06_distribuicao_tamanho_cestas.sql`](sql/marts/06_distribuicao_tamanho_cestas.sql) | `distribuicao_tamanho_cestas` | Quantos pedidos têm cada tamanho de cesta? |
| [`07_produtos_mais_comprados.sql`](sql/marts/07_produtos_mais_comprados.sql) | `produtos_mais_comprados` | Quais produtos aparecem mais vezes nos itens observados? |
| [`08_desempenho_departamentos.sql`](sql/marts/08_desempenho_departamentos.sql) | `desempenho_departamentos` | Como itens, pedidos e recompra se distribuem por departamento? |
| [`09_desempenho_corredores.sql`](sql/marts/09_desempenho_corredores.sql) | `desempenho_corredores` | Como itens, pedidos e recompra se distribuem por corredor? |
| [`10_recompra_por_posicao_carrinho.sql`](sql/marts/10_recompra_por_posicao_carrinho.sql) | `recompra_por_posicao_carrinho` | Como a recompra varia conforme a posição do item no carrinho? |

Os dados não contêm preço, receita, endereço/UF, avaliação, data de calendário
nem horário de entrega. Por isso, o projeto não apresenta faturamento,
ticket, localização geográfica, avaliações ou indicadores de entrega. As
consultas combinam `prior` e `train` quando analisam itens; pedidos `test` não
possuem itens rotulados neste dataset.

## Reproduzir do zero

Requisitos: Python 3.13 e [uv](https://docs.astral.sh/uv/).

Com os seis CSVs já extraídos em `raw/`, execute na raiz do repositório:

```powershell
uv sync
uv run python -m pipeline.ingestao
uv run python -m pipeline.transformacao
uv run python -m pipeline.marts
```

Para abrir o dashboard:

```powershell
uv run streamlit run app.py
```

Para exportar uma prévia HTML autocontida do dashboard:

```powershell
uv run python -m relatorio
```

O comando cria `dashboard_preview.html` na raiz, que pode ser aberto no
navegador e compartilhado para revisão. O arquivo é ignorado pelo Git, pois é
uma saída gerada localmente.

Para executar os testes unitários e medir a cobertura:

```powershell
uv run pytest --cov
```

Os testes usam bancos DuckDB temporários e dados inventados; não abrem o banco
nem os CSVs locais do projeto. A configuração exige cobertura total mínima de
60%.

## Histórico e conferência

O histórico Git registra as etapas em commits separados: configuração,
ingestão, transformação, consultas SQL, dashboard e testes. Cada mart tem sua
consulta versionada em `sql/marts/`, e os motivos das decisões de ingestão e
transformação estão documentados nas docstrings dos módulos.

### Uso de IA e conferência

A IA inicialmente recebeu especificações de exemplo feitas para a Olist,
com conceitos como receita, entrega e localização que não existem neste
dataset. A conferência das seis tabelas e das colunas disponíveis mostrou
essa diferença; os indicadores foram então adaptados para cestas, horários,
produtos e recompra. A ausência de preço e data de calendário também foi
verificada antes de excluir receita e filtros por mês do dashboard.

As regras foram conferidas com testes de entradas inventadas: por exemplo,
uma duplicata idêntica reduz a contagem em uma linha, enquanto uma chave com
conteúdo conflitante é preservada; as consultas de cesta e de hora também
foram executadas sobre tabelas sintéticas. Para repetir essa conferência,
rode `uv run pytest --cov`.
