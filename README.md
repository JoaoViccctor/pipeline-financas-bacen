# Quanto poder de compra você perdeu na poupança?

Pipeline de dados financeiros que extrai, armazena, transforma e
disponibiliza séries históricas de indicadores brasileiros (BACEN +
mercado) para responder uma pergunta concreta: **se você tivesse
investido um valor inicial + aportes mensais desde 2015 em Poupança,
CDI, Selic ou Ibovespa, quanto teria hoje — e teria ao menos empatado
com a inflação?**

Projeto de portfólio em engenharia de dados. O foco não é a conclusão
financeira em si, mas o pipeline por trás dela: extração resiliente,
armazenamento estruturado, transformação versionada e um pipeline que
se atualiza sozinho (ver seção Automação).

## Demo

Dashboard interativo em Streamlit, com aporte inicial e mensal
editáveis pelo usuário:

- Headline: quanto de poder de compra a poupança ganhou ou perdeu
  frente à inflação, dado o valor real aportado
- Gráfico comparativo entre Selic, CDI, IPCA, Poupança e Ibovespa
- Aviso de transparência: os números são *benchmarks* teóricos (taxas),
  não simulam produtos financeiros reais com carência/tributação

## Arquitetura

```
Fontes públicas (BACEN SGS, Yahoo Finance)
        │
        ▼
Extração (Python, com retry e quebra automática de período)
        │
        ▼
Armazenamento local (SQLite) — tabelas indicadores e mercado
        │
        ▼
Transformação (SQL/pandas) — retorno mensal e acumulado
        │
        ▼
Dashboard (Streamlit) — simulação com aportes dinâmicos
```

## Fontes de dados

| Série | Fonte | Código/Ticker | Frequência |
|---|---|---|---|
| Selic diária | BACEN SGS | 11 | Diária |
| CDI diário | BACEN SGS | 12 | Diária |
| IPCA mensal | BACEN SGS | 433 | Mensal |
| Poupança (rendimento) | BACEN SGS | 196 | Mensal |
| Ibovespa | Yahoo Finance | ^BVSP | Diária |

## Decisões técnicas (e problemas reais resolvidos no caminho)

- **Quebra automática de período**: a API do BACEN limita consultas a
  10 anos por requisição desde 2025. `extract_bacen.py` quebra o
  período em janelas automaticamente e concatena o resultado.
- **Retry com backoff**: chamadas de API falham. Cada requisição tenta
  até 3 vezes antes de desistir, com espera crescente entre tentativas.
- **Validação de tipos na carga**: o `yfinance` ocasionalmente grava
  uma linha de cabeçalho extra no meio do CSV, contaminando colunas
  numéricas com texto. `load_to_sqlite.py` força conversão numérica e
  descarta linhas inválidas.
- **Formato longo para indicadores do BACEN**: uma única tabela
  (`indicadores`) com colunas `data, indicador, valor`, em vez de uma
  tabela por série — facilita filtrar, agregar e adicionar novas
  séries sem alterar o schema.
- **Retorno mensal como base comum**: como as fontes têm frequências
  diferentes (diária vs. mensal), tudo é convertido para retorno
  mensal antes de comparar — séries diárias são compostas dentro do
  mês (juros compostos), séries mensais são usadas diretamente.

## Status

- [x] Extração (BACEN + Yahoo Finance)
- [x] Armazenamento em SQLite
- [x] Transformação e cálculo de retorno mensal/acumulado
- [x] Dashboard interativo (Streamlit) com aportes dinâmicos
- [x] Automação (GitHub Actions, atualização semanal — [workflow](.github/workflows/atualizar-dados.yml))
- [ ] Migração para cloud (Supabase) — avaliado, não priorizado no MVP

## Setup

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Como rodar o pipeline completo

```bash
cd src
python extract_bacen.py       # extrai séries do BACEN -> data/raw/
python extract_yfinance.py    # extrai Ibovespa -> data/raw/
python load_to_sqlite.py      # carrega os CSVs no SQLite -> data/processed/financas.db
python transform.py           # calcula retorno mensal/acumulado
streamlit run dashboard.py    # abre o dashboard
```

## Limitações conhecidas

Os indicadores comparados são **taxas de referência**, não produtos
financeiros específicos. Na prática, produtos reais têm regras que este
projeto não modela: carência (CDB, LCI/LCA), regra de aniversário
(poupança), tributação (IR regressivo, IOF). Ver aviso dentro do próprio
dashboard para detalhes.

## Próximos passos

- Modelar produtos reais com carência (ex: CDB 1 ano) como opção
  alternativa de simulação
- Avaliar migração da camada de armazenamento para Supabase (Postgres
  gerenciado gratuito), permitindo acesso ao dashboard sem depender do
  ambiente local
