"""Contrato mínimo de conexão e gravação usado pelas etapas do curso.

O caminho de ``raw/`` e do banco é ancorado neste arquivo, não no diretório
corrente, para que executar uma aula de outra pasta não abra ou crie o banco no
lugar errado. Importar o módulo não abre conexão nem cria arquivo; ``conectar``
devolve a conexão aberta para que o chamador controle seu ciclo de vida e
libere o lock ao terminar.

A interface pública tem somente ``PASTA_RAW``, ``conectar``, ``criar_schema``
e ``gravar``. Ela não lê arquivos, escolhe nomes de tabela, imprime mensagens
nem transforma dados, pois essas decisões pertencem a cada etapa e devem ficar
visíveis nela. ``criar_schema`` é idempotente para permitir reexecuções.
``gravar`` substitui a tabela pelos valores e tipos presentes no DataFrame ou
na relação DuckDB, remove o registro temporário usado na operação e consulta
a contagem persistida no banco; assim, nulos e textos não são alterados e a
contagem exibida reflete o conteúdo gravado, não o tamanho do objeto em
memória.
"""

from pathlib import Path as _Path
from uuid import uuid4 as _uuid4

import duckdb as _duckdb
import pandas as _pd

PASTA_RAW = _Path(__file__).resolve().parent.parent / "raw"


def conectar() -> _duckdb.DuckDBPyConnection:
    """Abre o banco na raiz do projeto; quem chama deve fechar a conexão."""
    caminho_banco = PASTA_RAW.parent / "instacart.duckdb"
    return _duckdb.connect(str(caminho_banco))


def criar_schema(con: _duckdb.DuckDBPyConnection, nome: str) -> None:
    """Cria o schema quando necessário, escapando o nome como identificador."""
    nome_sql = '"' + nome.replace('"', '""') + '"'
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {nome_sql}")


def gravar(
    con: _duckdb.DuckDBPyConnection,
    df: _pd.DataFrame | _duckdb.DuckDBPyRelation,
    schema: str,
    tabela: str,
) -> int:
    """Recria a tabela a partir de dados tabulares e retorna a contagem persistida.

    Além de DataFrames, aceita relações DuckDB para que transformações grandes
    possam ser gravadas sem materializar todas as linhas em memória.
    """
    schema_sql = '"' + schema.replace('"', '""') + '"'
    tabela_sql = '"' + tabela.replace('"', '""') + '"'
    registro = f"_dataframe_{_uuid4().hex}"
    con.register(registro, df)
    try:
        con.execute(
            f"CREATE OR REPLACE TABLE {schema_sql}.{tabela_sql} "
            f'AS SELECT * FROM "{registro}"'
        )
        return int(
            con.execute(f"SELECT count(*) FROM {schema_sql}.{tabela_sql}").fetchall()[
                0
            ][0]
        )
    finally:
        con.unregister(registro)
