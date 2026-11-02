"""Serve a interface web do DuckDB sobre o banco já ingerido.

O banco é resolvido a partir deste arquivo para que a UI encontre o mesmo
arquivo que a ingestão mesmo se iniciada de outra pasta. A extensão ``ui`` é
instalada e carregada e ``CALL start_ui()`` inicia a interface em
``http://localhost:4213``. O arquivo não é criado se estiver ausente: abrir um
banco vazio faria uma ingestão inexistente parecer um dashboard quebrado.

A conexão fica viva enquanto o servidor é usado e é fechada no Ctrl+C, que
encerra o processo sem traceback e libera o lock para uma próxima ingestão.
Esta ferramenta não importa o módulo de ingestão, para que iniciar o navegador
nunca execute uma carga de dados. stdout e stderr usam UTF-8 para que URL e
mensagens com acentos sejam legíveis no Prompt de Comando do Windows.
"""

import sys
import time
from pathlib import Path

import duckdb


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    caminho_banco = Path(__file__).resolve().parent / "instacart.duckdb"
    if not caminho_banco.is_file():
        print(
            f"Banco não encontrado em {caminho_banco}. "
            "Execute a ingestão antes de abrir a interface.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    con = duckdb.connect(str(caminho_banco))
    try:
        con.execute("INSTALL ui")
        con.execute("LOAD ui")
        con.execute("CALL start_ui()")
        print("Interface disponível em http://localhost:4213")
        print("Ctrl+C para encerrar")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterface encerrada.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
