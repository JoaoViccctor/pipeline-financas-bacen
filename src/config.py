"""
Configurações centrais do projeto.
Mantemos os códigos de série e os caminhos em um único lugar para
facilitar manutenção.
"""

from pathlib import Path

# Caminhos calculados a partir da localização deste arquivo, não da
# pasta de onde o script é executado. Isso evita que os dados sejam
# criados em lugares diferentes dependendo de como você roda o script
# (ex: `python extract_bacen.py` de dentro de `src`, ou de outro lugar).
BASE_DIR = Path(__file__).resolve().parent.parent  # raiz do projeto
RAW_DATA_PATH = str(BASE_DIR / "data" / "raw")
PROCESSED_DATA_PATH = str(BASE_DIR / "data" / "processed")
DB_PATH = str(BASE_DIR / "data" / "processed" / "financas.db")

# Códigos das séries no SGS (Sistema Gerenciador de Séries Temporais) do BACEN
# Referência: https://www3.bcb.gov.br/sgspub
SERIES_BACEN = {
    "selic": 11,       # Taxa Selic diária (% a.d.)
    "cdi": 12,         # CDI diário (% a.d.)
    "ipca": 433,       # IPCA mensal (Var. % mensal)
    "poupanca": 196,   # Rendimento da poupança (% mensal)
}

# Tickers do Yahoo Finance
TICKERS_YFINANCE = {
    "ibovespa": "^BVSP",
}

# Período padrão de coleta (formato dd/mm/aaaa, exigido pela API do BACEN)
DATA_INICIAL = "01/01/2015"
DATA_FINAL = None  # None = até a data mais recente disponível
