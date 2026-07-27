"""
Extração de séries temporais do SGS (BACEN).

Este script é a camada RAW do pipeline: busca os dados da API pública do
BACEN e salva exatamente como vieram, sem transformação, em CSV.
Isso garante que sempre temos uma cópia fiel da fonte original, caso
precisemos reprocessar algo no futuro.
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from config import SERIES_BACEN, DATA_INICIAL, DATA_FINAL, RAW_DATA_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

# Desde março/2025 a API do BACEN passa a limitar o intervalo por
# requisição a 10 anos. Usamos uma janela um pouco menor por segurança
# e quebramos o período total em pedaços, concatenando o resultado.
JANELA_MAX_DIAS = 3650 - 30


def gerar_janelas(data_inicial: str, data_final: str | None) -> list[tuple[str, str]]:
    """Quebra o intervalo [data_inicial, data_final] em janelas de até ~10 anos."""
    inicio = datetime.strptime(data_inicial, "%d/%m/%Y")
    fim = datetime.strptime(data_final, "%d/%m/%Y") if data_final else datetime.today()

    janelas = []
    cursor = inicio
    while cursor < fim:
        fim_janela = min(cursor + timedelta(days=JANELA_MAX_DIAS), fim)
        janelas.append((cursor.strftime("%d/%m/%Y"), fim_janela.strftime("%d/%m/%Y")))
        cursor = fim_janela + timedelta(days=1)
    return janelas


def montar_url(codigo: int, data_inicial: str, data_final: str) -> str:
    """Monta a URL da API SGS para um código de série e uma janela de datas."""
    return (
        BASE_URL.format(codigo=codigo)
        + f"?formato=json&dataInicial={data_inicial}&dataFinal={data_final}"
    )


def buscar_janela(nome: str, codigo: int, data_inicial: str, data_final: str,
                   tentativas: int = 3) -> pd.DataFrame:
    """Busca uma única janela de datas de uma série, com retry simples."""
    url = montar_url(codigo, data_inicial, data_final)

    for tentativa in range(1, tentativas + 1):
        try:
            logger.info(
                f"Buscando '{nome}' de {data_inicial} a {data_final} - tentativa {tentativa}"
            )
            resposta = requests.get(url, timeout=15)
            resposta.raise_for_status()

            dados = resposta.json()
            if not dados:
                return pd.DataFrame(columns=["data", "valor"])

            df = pd.DataFrame(dados)
            df.columns = ["data", "valor"]
            df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
            return df

        except requests.exceptions.RequestException as erro:
            logger.error(f"Falha ao buscar '{nome}' ({data_inicial}-{data_final}): {erro}")
            if tentativa < tentativas:
                time.sleep(2 * tentativa)  # backoff simples
            else:
                logger.error(f"Desistindo dessa janela de '{nome}' após {tentativas} tentativas.")
                return pd.DataFrame(columns=["data", "valor"])


def buscar_serie(nome: str, codigo: int) -> pd.DataFrame:
    """
    Busca uma série completa do SGS, quebrando automaticamente em janelas
    de até 10 anos e concatenando o resultado.
    """
    janelas = gerar_janelas(DATA_INICIAL, DATA_FINAL)
    partes = []

    for data_inicial, data_final in janelas:
        df_janela = buscar_janela(nome, codigo, data_inicial, data_final)
        if not df_janela.empty:
            partes.append(df_janela)

    if not partes:
        logger.warning(f"Série '{nome}' retornou vazia em todas as janelas.")
        return pd.DataFrame(columns=["data", "valor"])

    df_completo = pd.concat(partes, ignore_index=True)
    df_completo = df_completo.drop_duplicates(subset="data").sort_values("data")
    logger.info(f"Série '{nome}' obtida com sucesso: {len(df_completo)} registros.")
    return df_completo


def salvar_raw(df: pd.DataFrame, nome: str) -> None:
    """Salva o DataFrame bruto em CSV na camada raw."""
    if df.empty:
        logger.warning(f"Nada a salvar para '{nome}' (DataFrame vazio).")
        return

    Path(RAW_DATA_PATH).mkdir(parents=True, exist_ok=True)
    caminho = Path(RAW_DATA_PATH) / f"{nome}.csv"
    df.to_csv(caminho, index=False)
    logger.info(f"Salvo em {caminho}")


def main():
    logger.info("Iniciando extração das séries do BACEN...")
    for nome, codigo in SERIES_BACEN.items():
        df = buscar_serie(nome, codigo)
        salvar_raw(df, nome)
    logger.info("Extração finalizada.")


if __name__ == "__main__":
    main()
