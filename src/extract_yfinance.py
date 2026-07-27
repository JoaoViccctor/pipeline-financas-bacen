"""
Extração de dados de mercado via yfinance (camada RAW).
"""

import logging
from pathlib import Path

import yfinance as yf

from config import TICKERS_YFINANCE, DATA_INICIAL, RAW_DATA_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def buscar_ticker(nome: str, ticker: str):
    """Busca o histórico de um ticker desde DATA_INICIAL."""
    try:
        logger.info(f"Buscando ticker '{nome}' ({ticker})")
        # yfinance espera datas no formato aaaa-mm-dd
        dia, mes, ano = DATA_INICIAL.split("/")
        data_inicio = f"{ano}-{mes}-{dia}"

        df = yf.download(ticker, start=data_inicio, progress=False)
        if df.empty:
            logger.warning(f"Ticker '{nome}' retornou vazio.")
            return None

        df = df.reset_index()
        logger.info(f"Ticker '{nome}' obtido com sucesso: {len(df)} registros.")
        return df

    except Exception as erro:
        logger.error(f"Falha ao buscar '{nome}': {erro}")
        return None


def salvar_raw(df, nome: str) -> None:
    if df is None or df.empty:
        logger.warning(f"Nada a salvar para '{nome}'.")
        return

    Path(RAW_DATA_PATH).mkdir(parents=True, exist_ok=True)
    caminho = Path(RAW_DATA_PATH) / f"{nome}.csv"
    df.to_csv(caminho, index=False)
    logger.info(f"Salvo em {caminho}")


def main():
    logger.info("Iniciando extração de dados de mercado (yfinance)...")
    for nome, ticker in TICKERS_YFINANCE.items():
        df = buscar_ticker(nome, ticker)
        salvar_raw(df, nome)
    logger.info("Extração finalizada.")


if __name__ == "__main__":
    main()
