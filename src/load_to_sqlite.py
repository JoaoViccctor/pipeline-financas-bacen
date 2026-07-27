"""
Carga dos dados da camada RAW (CSV) para o banco SQLite (camada de
armazenamento estruturado).

Modelagem:
- tabela `indicadores`: formato longo (data, indicador, valor) — junta
  selic, cdi, ipca e poupanca, já que todas têm a mesma estrutura.
- tabela `mercado`: dados de preço do Ibovespa (abertura, máxima,
  mínima, fechamento, volume).

Rodar este script várias vezes é seguro: cada carga substitui o
conteúdo anterior da tabela (idempotente), evitando duplicar dados.
"""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from config import SERIES_BACEN, TICKERS_YFINANCE, RAW_DATA_PATH, DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def carregar_indicadores(conn: sqlite3.Connection) -> None:
    """Lê os CSVs de séries do BACEN e monta a tabela `indicadores` (formato longo)."""
    partes = []

    for nome in SERIES_BACEN.keys():
        caminho = Path(RAW_DATA_PATH) / f"{nome}.csv"
        if not caminho.exists():
            logger.warning(f"Arquivo não encontrado, pulando: {caminho}")
            continue

        df = pd.read_csv(caminho, parse_dates=["data"])
        df["indicador"] = nome
        partes.append(df[["data", "indicador", "valor"]])

    if not partes:
        logger.error("Nenhum indicador encontrado para carregar. Abortando.")
        return

    df_final = pd.concat(partes, ignore_index=True)
    df_final.to_sql("indicadores", conn, if_exists="replace", index=False)
    logger.info(f"Tabela 'indicadores' carregada: {len(df_final)} registros.")


def carregar_mercado(conn: sqlite3.Connection) -> None:
    """Lê os CSVs de tickers do yfinance e monta a tabela `mercado`."""
    partes = []

    for nome in TICKERS_YFINANCE.keys():
        caminho = Path(RAW_DATA_PATH) / f"{nome}.csv"
        if not caminho.exists():
            logger.warning(f"Arquivo não encontrado, pulando: {caminho}")
            continue

        df = pd.read_csv(caminho)
        # yfinance salva a data na primeira coluna (nome pode variar: Date, Price...)
        df = df.rename(columns={df.columns[0]: "data"})
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.dropna(subset=["data"])

        # Padroniza nomes de colunas esperadas, ignorando as que não existirem
        renomear = {
            "Open": "abertura",
            "High": "maxima",
            "Low": "minima",
            "Close": "fechamento",
            "Adj Close": "fechamento_ajustado",
            "Volume": "volume",
        }
        df = df.rename(columns=renomear)
        df["ticker"] = nome

        colunas_numericas = [c for c in renomear.values() if c in df.columns]
        for coluna in colunas_numericas:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

        # O yfinance às vezes grava uma linha extra de cabeçalho (com o
        # nome do ticker) no meio do CSV. Após forçar conversão numérica,
        # essa linha vira NaN em todas as colunas de preço — descartamos.
        df = df.dropna(subset=colunas_numericas, how="all")

        colunas_finais = ["data", "ticker"] + colunas_numericas
        partes.append(df[colunas_finais])

    if not partes:
        logger.warning("Nenhum dado de mercado encontrado para carregar.")
        return

    df_final = pd.concat(partes, ignore_index=True)
    df_final.to_sql("mercado", conn, if_exists="replace", index=False)
    logger.info(f"Tabela 'mercado' carregada: {len(df_final)} registros.")


def main():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        logger.info(f"Conectado ao banco: {DB_PATH}")
        carregar_indicadores(conn)
        carregar_mercado(conn)
        conn.commit()
        logger.info("Carga finalizada com sucesso.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
