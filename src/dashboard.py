"""
Dashboard: simula quanto renderia um aporte inicial + aportes mensais em
cada indicador, e destaca quanto poder de compra a poupança "perdeu"
frente à inflação no mesmo período.

Lê a tabela `retorno_acumulado` (retorno mensal já calculado por
transform.py) e faz a simulação de acúmulo com aportes na própria
interface — assim o usuário pode testar seus próprios valores sem
precisar rodar nada de novo.

Rodar com: streamlit run dashboard.py
"""

import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DB_PATH

NOMES_AMIGAVEIS = {
    "selic": "Selic",
    "cdi": "CDI",
    "ipca": "IPCA (inflação)",
    "poupanca": "Poupança",
    "ibovespa": "Ibovespa",
}


@st.cache_data
def carregar_dados() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM retorno_acumulado", conn)
    conn.close()
    df["mes"] = pd.to_datetime(df["mes"])
    df["indicador_nome"] = df["indicador"].map(NOMES_AMIGAVEIS).fillna(df["indicador"])
    return df.sort_values("mes")


def simular_acumulado(retornos_mensais: pd.Series, aporte_inicial: float,
                       aporte_mensal: float) -> pd.Series:
    """
    Simula o valor acumulado mês a mês: no primeiro mês entra o aporte
    inicial, nos seguintes entra o aporte mensal, e tudo rende o retorno
    daquele mês antes do próximo aporte.
    """
    valores = []
    valor = 0.0
    for i, retorno in enumerate(retornos_mensais):
        aporte = aporte_inicial if i == 0 else aporte_mensal
        valor = (valor + aporte) * (1 + retorno)
        valores.append(valor)
    return pd.Series(valores, index=retornos_mensais.index)


st.set_page_config(page_title="Poupança x CDI x Ibovespa x Inflação", layout="wide")
st.title("Quanto poder de compra você perdeu na poupança?")
st.caption("Fontes: BACEN (SGS) e Yahoo Finance — dados desde 2015")

with st.expander("⚠️ Antes de comparar, leia isso"):
    st.markdown(
        """
Os valores abaixo simulam um cenário **idealizado**: aportar todo mês e
render exatamente a taxa do indicador, sem nenhuma fricção. Na prática,
cada produto real tem regras diferentes:

- **Selic e CDI** não são produtos — são taxas de referência. Você
  investe em produtos que rendem *próximo* delas (Tesouro Selic, CDB,
  LCI/LCA), e muitos desses têm carência (ex: resgate só após 90 dias
  ou no vencimento). O Tesouro Selic é a exceção, com liquidez diária.
- **Poupança** é líquida, mas só paga rendimento no "aniversário" do
  depósito — sacar antes de completar o mês daquele aporte específico
  faz você perder o rendimento daquele mês.
- **Ibovespa** não é investível diretamente, mas via ETFs (ex: BOVA11),
  que têm liquidez diária como uma ação.

Este dashboard serve como **referência comparativa entre taxas**, não
como simulação de um produto financeiro específico com suas regras de
carência e tributação.
        """
    )

df = carregar_dados()

# --- Entradas do usuário ---
col1, col2 = st.columns(2)
with col1:
    aporte_inicial = st.number_input("Aporte inicial (R$)", min_value=0.0, value=1000.0, step=100.0)
with col2:
    aporte_mensal = st.number_input("Aporte mensal (R$)", min_value=0.0, value=200.0, step=50.0)

# --- Simulação para cada indicador ---
resultados = {}
for indicador, grupo in df.groupby("indicador"):
    grupo = grupo.set_index("mes")
    resultados[indicador] = simular_acumulado(grupo["retorno_mensal"], aporte_inicial, aporte_mensal)

df_simulado = (
    pd.DataFrame(resultados)
    .reset_index()
    .melt(id_vars="mes", var_name="indicador", value_name="valor_acumulado")
)
df_simulado["indicador_nome"] = df_simulado["indicador"].map(NOMES_AMIGAVEIS)

# --- Headline: poder de compra perdido na poupança ---
total_aportado = aporte_inicial + aporte_mensal * (df["mes"].nunique() - 1)
valor_final_poupanca = resultados["poupanca"].iloc[-1]
valor_final_ipca = resultados["ipca"].iloc[-1]  # quanto precisaria ter para só empatar com a inflação
perda_poder_compra = valor_final_ipca - valor_final_poupanca

st.divider()
m1, m2, m3 = st.columns(3)
m1.metric("Total aportado", f"R$ {total_aportado:,.2f}")
m2.metric("Valor final na poupança", f"R$ {valor_final_poupanca:,.2f}")

# Delta positivo = poupança bateu a inflação (bom, seta verde para cima).
# Delta negativo = poupança perdeu para a inflação (ruim, seta vermelha para baixo).
ganho_ou_perda_pct = -perda_poder_compra / valor_final_ipca
m3.metric(
    "Poder de compra perdido",
    f"R$ {max(perda_poder_compra, 0):,.2f}" if perda_poder_compra > 0 else "R$ 0,00 (bateu a inflação)",
    delta=f"{ganho_ou_perda_pct:.1%}",
    help="Diferença entre o valor final na poupança e o valor que você precisaria ter hoje só para manter o poder de compra do que foi aportado (acompanhando o IPCA). Delta positivo = poupança bateu a inflação.",
)
st.divider()

# --- Gráfico comparativo ---
indicadores_disponiveis = sorted(df_simulado["indicador_nome"].unique())
selecionados = st.multiselect(
    "Indicadores para comparar",
    options=indicadores_disponiveis,
    default=indicadores_disponiveis,
)
df_filtrado = df_simulado[df_simulado["indicador_nome"].isin(selecionados)]

fig = px.line(
    df_filtrado,
    x="mes",
    y="valor_acumulado",
    color="indicador_nome",
    labels={"mes": "Mês", "valor_acumulado": "Valor acumulado (R$)", "indicador_nome": "Indicador"},
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Valor final acumulado por indicador")
resumo = (
    df_filtrado.sort_values("mes")
    .groupby("indicador_nome")
    .last()[["valor_acumulado"]]
    .rename(columns={"valor_acumulado": "Valor final (R$)"})
    .sort_values("Valor final (R$)", ascending=False)
)
st.dataframe(resumo.style.format("R$ {:.2f}"), use_container_width=True)
