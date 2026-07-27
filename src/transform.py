"""
Transformação: calcula o retorno mensal e o valor acumulado de R$ 1.000
investidos em cada indicador desde o início da série.

Regras de conversão para retorno mensal (necessário porque as fontes têm
frequências diferentes):
- Selic e CDI: taxas diárias (% a.d.) -> juros compostos dentro do mês.
- IPCA e Poupança: já vêm como variação % mensal -> usados diretamente.
- Ibovespa: preço de fechamento diário -> retorno mensal = variação do
  fechamento do último dia do mês em relação ao mês anterior.

Resultado salvo na tabela `retorno_acumulado`, com uma linha por
mês/indicador, pronta para o dashboard plotar.
"""

import logging
import sqlite3

import pandas as pd

from config import DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

VALOR_INICIAL = 1000  # R$ investidos no início da série, para a comparação


def retorno_mensal_diario(df_serie: pd.DataFrame) -> pd.Series:
    """Composição de juros diários dentro de cada mês (Selic, CDI)."""
    df_serie = df_serie.copy()
    df_serie["mes"] = df_serie["data"].dt.to_period("M")
    return df_serie.groupby("mes")["valor"].apply(lambda x: (1 + x / 100).prod() - 1)


def retorno_mensal_direto(df_serie: pd.DataFrame) -> pd.Series:
    """Série já mensal (IPCA, Poupança) -> só converte % para decimal."""
    df_serie = df_serie.copy()
    df_serie["mes"] = df_serie["data"].dt.to_period("M")
    return df_serie.groupby("mes")["valor"].mean() / 100


def retorno_mensal_mercado(df_mercado: pd.DataFrame) -> pd.Series:
    """Retorno mensal do Ibovespa a partir do fechamento do último dia útil do mês."""
    df_mercado = df_mercado.copy()
    df_mercado["mes"] = df_mercado["data"].dt.to_period("M")
    fechamento_mensal = df_mercado.groupby("mes")["fechamento"].last()
    return fechamento_mensal.pct_change()


def montar_tabela_final(retornos: dict[str, pd.Series]) -> pd.DataFrame:
    """Junta os retornos mensais de todos os indicadores e calcula o acumulado."""
    partes = []
    for nome, serie in retornos.items():
        df = serie.rename("retorno_mensal").reset_index()
        df.columns = ["mes", "retorno_mensal"]
        df["indicador"] = nome
        df["retorno_mensal"] = df["retorno_mensal"].fillna(0)  # 1º mês sem retorno anterior
        df = df.sort_values("mes")
        df["valor_acumulado"] = VALOR_INICIAL * (1 + df["retorno_mensal"]).cumprod()
        partes.append(df)

    df_final = pd.concat(partes, ignore_index=True)
    df_final["mes"] = df_final["mes"].astype(str)
    return df_final[["mes", "indicador", "retorno_mensal", "valor_acumulado"]]


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        logger.info("Lendo dados das tabelas 'indicadores' e 'mercado'...")
        df_indicadores = pd.read_sql("SELECT * FROM indicadores", conn, parse_dates=["data"])
        df_mercado = pd.read_sql("SELECT * FROM mercado", conn, parse_dates=["data"])

        retornos = {}

        for nome in ["selic", "cdi"]:
            df_serie = df_indicadores[df_indicadores["indicador"] == nome]
            if not df_serie.empty:
                retornos[nome] = retorno_mensal_diario(df_serie)
                logger.info(f"Retorno mensal calculado para '{nome}'.")

        for nome in ["ipca", "poupanca"]:
            df_serie = df_indicadores[df_indicadores["indicador"] == nome]
            if not df_serie.empty:
                retornos[nome] = retorno_mensal_direto(df_serie)
                logger.info(f"Retorno mensal calculado para '{nome}'.")

        df_ibov = df_mercado[df_mercado["ticker"] == "ibovespa"]
        if not df_ibov.empty:
            retornos["ibovespa"] = retorno_mensal_mercado(df_ibov)
            logger.info("Retorno mensal calculado para 'ibovespa'.")

        df_final = montar_tabela_final(retornos)
        df_final.to_sql("retorno_acumulado", conn, if_exists="replace", index=False)
        conn.commit()
        logger.info(f"Tabela 'retorno_acumulado' salva: {len(df_final)} registros.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
