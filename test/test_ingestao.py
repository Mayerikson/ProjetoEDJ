import contextlib
import gzip
import io
from pathlib import Path

import duckdb
import pytest

from pipeline import ingestao


class CapturedStream(io.StringIO):
    def reconfigure(self, *, encoding: str) -> None:
        self.configured_encoding = encoding


def escrever_arquivos(raw: Path) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    conteudos = {
        # Aisle mínimo para validar o mapa de nomes sem depender do Kaggle.
        "aisles": "aisle_id,aisle\n001,fresh\n",
        # Departamento mínimo para validar a ingestão de texto.
        "departments": "department_id,department\n01,produce\n",
        # Produto com IDs preenchidos para verificar que o raw não os converte.
        "products": "product_id,product_name,aisle_id,department_id\n0001,Apple,001,01\n",
        # Primeiro pedido com intervalo vazio para verificar NULL preservado.
        "orders": (
            "order_id,user_id,eval_set,order_number,order_dow,"
            "order_hour_of_day,days_since_prior_order\n"
            "0001,0002,prior,1,0,9,\n"
        ),
        # Item prior mínimo para conferir as colunas originais.
        "order_products__prior": (
            "order_id,product_id,add_to_cart_order,reordered\n0001,0001,1,0\n"
        ),
        # Item train mínimo para confirmar que a sexta tabela também é ingerida.
        "order_products__train": (
            "order_id,product_id,add_to_cart_order,reordered\n0002,0001,1,1\n"
        ),
    }
    for nome, conteudo in conteudos.items():
        # Cada dataset inventado contém uma linha para provar o mapeamento e a preservação.
        with gzip.open(raw / f"{nome}.csv.gz", "wt", encoding="utf-8") as arquivo:
            arquivo.write(conteudo)


def test_ingestao_preserva_linhas_texto_nulos_e_reexecucao(
    tmp_path: Path, monkeypatch
) -> None:
    raw = tmp_path / "raw"
    escrever_arquivos(raw)
    caminho_banco = tmp_path / "teste.duckdb"
    saidas = []
    monkeypatch.setattr(ingestao, "PASTA_RAW", raw)
    monkeypatch.setattr(
        ingestao, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )

    for _ in range(2):
        stdout, stderr = CapturedStream(), CapturedStream()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            ingestao.main()
        assert stderr.getvalue() == ""
        saidas.append(stdout.getvalue())

    assert saidas[0] == saidas[1]
    con = duckdb.connect(str(caminho_banco), read_only=True)
    assert con.execute("SELECT * FROM raw.pedidos").fetchall() == [
        ("0001", "0002", "prior", "1", "0", "9", None)
    ]
    assert [coluna[1] for coluna in con.execute("DESCRIBE raw.pedidos").fetchall()] == [
        "VARCHAR"
    ] * 7
    assert con.execute("SELECT COUNT(*) FROM raw.itens_pedido_prior").fetchone()[0] == 1
    con.close()


def test_arquivo_ausente_para_antes_de_abrir_o_banco(
    tmp_path: Path, monkeypatch
) -> None:
    raw = tmp_path / "raw"
    escrever_arquivos(raw)
    (raw / "orders.csv.gz").unlink()
    monkeypatch.setattr(ingestao, "PASTA_RAW", raw)

    def conectar_nao_deve_ser_chamado():
        raise AssertionError("A ingestão abriu o banco com arquivo ausente.")

    monkeypatch.setattr(ingestao, "conectar", conectar_nao_deve_ser_chamado)
    stdout, stderr = CapturedStream(), CapturedStream()

    with (
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
        pytest.raises(SystemExit) as erro,
    ):
        ingestao.main()

    assert erro.value.code == 1
    assert stdout.getvalue() == ""
    assert "orders" in stderr.getvalue()
    assert str(raw) in stderr.getvalue()


def test_csv_tem_preferencia_sobre_csv_gz(tmp_path: Path, monkeypatch) -> None:
    raw = tmp_path / "raw"
    escrever_arquivos(raw)
    # O CSV simples tem conteúdo diferente para provar qual extensão foi escolhida.
    (raw / "aisles.csv").write_text(
        "aisle_id,aisle\n002,dry\n", encoding="utf-8"
    )
    caminho_banco = tmp_path / "preferencia.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", raw)
    monkeypatch.setattr(
        ingestao, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )
    stdout, stderr = CapturedStream(), CapturedStream()

    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        ingestao.main()

    assert stderr.getvalue() == ""
    con = duckdb.connect(str(caminho_banco), read_only=True)
    assert con.execute("SELECT * FROM raw.corredores").fetchall() == [("002", "dry")]
    con.close()
