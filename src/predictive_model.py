"""
predictive_model.py
Etapa de Análise Preditiva.

Objetivo: projetar a receita futura (soma do valor de contratos ativos)
e gerar uma tabela de cenários "what-if" que alimenta o slider de
simulação no dashboard Power BI.

Lógica do what-if:
    O usuário simula "e se a taxa de saída (churn) das obras fosse X% maior/menor?"
    Esse script pré-calcula a receita projetada para uma faixa de variações
    (-50% a +50%, em passos de 5%) e salva numa tabela. No Power BI, um
    parâmetro What-if nativo (mesma faixa) é usado para buscar (LOOKUPVALUE)
    a linha correspondente nessa tabela — assim o slider funciona sem
    precisar rodar Python em tempo real.

Entrada:  MySQL (tabela `obras`, via .env) — ou, na ausência de conexão,
          data/processed/obras_tratadas.csv como fallback
Saída:    data/processed/previsao_baseline.csv
          data/processed/cenarios_whatif.csv
          data/processed/tendencia_receita.png
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

# ── Configurações ────────────────────────────────────────────────────────
MESES_PROJECAO = 6
VARIACAO_MIN_PCT = -50
VARIACAO_MAX_PCT = 50
PASSO_PCT = 5

CAMINHO_CSV_TRATADO = Path("data/processed/obras_tratadas.csv")
CAMINHO_SAIDA_BASELINE = Path("data/processed/previsao_baseline.csv")
CAMINHO_SAIDA_CENARIOS = Path("data/processed/cenarios_whatif.csv")
CAMINHO_GRAFICO = Path("data/processed/tendencia_receita.png")


# ── Carga dos dados ──────────────────────────────────────────────────────
def carregar_dados() -> pd.DataFrame:
    """Tenta ler do MySQL; se não conseguir, usa o CSV tratado como fallback."""
    try:
        from dotenv import load_dotenv
        from sqlalchemy import create_engine

        load_dotenv()
        url = (
            f"mysql+mysqlconnector://{os.getenv('DB_USER', 'root')}:"
            f"{os.getenv('DB_PASSWORD', '')}@{os.getenv('DB_HOST', 'localhost')}:"
            f"{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME', 'etl_preditivo')}"
        )
        engine = create_engine(url)
        df = pd.read_sql("SELECT * FROM obras", con=engine)
        print("Dados carregados do MySQL.")
    except Exception as e:
        print(f"[Aviso] Não foi possível conectar ao MySQL ({e}). Usando CSV tratado.")
        df = pd.read_csv(CAMINHO_CSV_TRATADO, encoding="utf-8-sig")

    df["data_entrada"] = pd.to_datetime(df["data_entrada"])
    df["data_saida"] = pd.to_datetime(df["data_saida"], errors="coerce")
    return df


# ── Construção da série temporal ─────────────────────────────────────────
def construir_serie_receita_ativa(df: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada mês, calcula a receita ativa: soma do valor_contrato de todas
    as obras que estavam vigentes no fechamento daquele mês
    (entrou até o mês, e não saiu ainda ou saiu depois do mês).
    """
    inicio = df["data_entrada"].min().to_period("M")
    fim = pd.Timestamp.today().to_period("M")
    meses = pd.period_range(inicio, fim, freq="M")

    registros = []
    for mes in meses:
        fim_mes = mes.to_timestamp(how="end")
        ativas = df[
            (df["data_entrada"] <= fim_mes)
            & (df["data_saida"].isna() | (df["data_saida"] > fim_mes))
        ]
        registros.append({
            "mes": mes.to_timestamp(),
            "receita_ativa": ativas["valor_contrato"].sum(),
            "qtd_obras_ativas": len(ativas),
        })

    return pd.DataFrame(registros)


def calcular_taxas_medias(df: pd.DataFrame, serie: pd.DataFrame) -> dict:
    """Taxa média mensal de entrada (R$ novos/mês) e taxa de churn (% que sai/mês)."""
    receita_entrada_por_mes = (
        df.groupby(df["data_entrada"].dt.to_period("M"))["valor_contrato"].sum()
    )
    media_entrada_mensal = receita_entrada_por_mes.mean()

    obras_saida_por_mes = (
        df.dropna(subset=["data_saida"])
        .groupby(df["data_saida"].dt.to_period("M"))
        .size()
    )
    media_obras_ativas = serie["qtd_obras_ativas"].mean()
    taxa_churn_mensal = (
        obras_saida_por_mes.mean() / media_obras_ativas if media_obras_ativas > 0 else 0
    )

    return {
        "media_entrada_mensal_rs": media_entrada_mensal,
        "taxa_churn_mensal": taxa_churn_mensal,
    }


# ── Modelo de tendência (baseline) ───────────────────────────────────────
def ajustar_tendencia(serie: pd.DataFrame):
    serie = serie.reset_index(drop=True)
    X = np.arange(len(serie)).reshape(-1, 1)
    y = serie["receita_ativa"].values

    modelo = LinearRegression()
    modelo.fit(X, y)
    r2 = modelo.score(X, y)
    print(f"Modelo de tendência ajustado — R² = {r2:.3f}, inclinação = {modelo.coef_[0]:.2f} R$/mês")
    return modelo, r2


def projetar_baseline(serie: pd.DataFrame, modelo, meses_futuro: int) -> pd.DataFrame:
    ultimo_indice = len(serie) - 1
    indices_futuros = np.arange(ultimo_indice + 1, ultimo_indice + 1 + meses_futuro).reshape(-1, 1)
    previsoes = modelo.predict(indices_futuros)

    ultimo_mes = serie["mes"].max()
    meses_futuros = pd.date_range(ultimo_mes + pd.DateOffset(months=1), periods=meses_futuro, freq="MS")

    return pd.DataFrame({
        "mes": meses_futuros,
        "receita_projetada": np.clip(previsoes, a_min=0, a_max=None),
    })


# ── Cenários what-if ──────────────────────────────────────────────────────
def simular_cenario(
    receita_atual: float,
    media_entrada_mensal: float,
    taxa_churn_mensal: float,
    variacao_churn_pct: float,
    meses_futuro: int,
) -> float:
    """
    Simula a receita ativa após `meses_futuro`, aplicando uma variação
    percentual sobre a taxa de churn histórica.

    Lógica: a cada mês, soma-se a entrada média de receita nova e
    subtrai-se a fração da receita ativa correspondente ao churn ajustado.
    """
    churn_ajustado = taxa_churn_mensal * (1 + variacao_churn_pct / 100)
    churn_ajustado = min(max(churn_ajustado, 0), 1)  # limita entre 0% e 100%

    receita = receita_atual
    for _ in range(meses_futuro):
        receita = receita * (1 - churn_ajustado) + media_entrada_mensal
        receita = max(receita, 0)

    return receita


def gerar_tabela_cenarios(
    receita_atual: float,
    taxas: dict,
    meses_futuro: int,
) -> pd.DataFrame:
    variacoes = np.arange(VARIACAO_MIN_PCT, VARIACAO_MAX_PCT + PASSO_PCT, PASSO_PCT)

    registros = []
    for variacao in variacoes:
        receita_projetada = simular_cenario(
            receita_atual=receita_atual,
            media_entrada_mensal=taxas["media_entrada_mensal_rs"],
            taxa_churn_mensal=taxas["taxa_churn_mensal"],
            variacao_churn_pct=variacao,
            meses_futuro=meses_futuro,
        )
        registros.append({
            "variacao_taxa_saida_pct": int(variacao),
            "receita_projetada": round(receita_projetada, 2),
        })

    return pd.DataFrame(registros)


# ── Visualização de apoio ────────────────────────────────────────────────
def plotar_tendencia(serie: pd.DataFrame, baseline: pd.DataFrame, caminho: Path):
    plt.figure(figsize=(10, 5))
    plt.plot(serie["mes"], serie["receita_ativa"], label="Histórico", marker="o")
    plt.plot(baseline["mes"], baseline["receita_projetada"], label="Projeção (baseline)", marker="o", linestyle="--")
    plt.title("Receita Ativa — Histórico e Projeção")
    plt.xlabel("Mês")
    plt.ylabel("Receita Ativa (R$)")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(caminho)
    print(f"Gráfico salvo em: {caminho}")


# ── Gravação no MySQL ─────────────────────────────────────────────────────
def salvar_no_mysql(serie: pd.DataFrame, baseline: pd.DataFrame, cenarios: pd.DataFrame):
    """Insere (substituindo) as tabelas receita_mensal_historico, previsao_baseline
    e cenarios_whatif no MySQL."""
    try:
        from dotenv import load_dotenv
        from sqlalchemy import create_engine, text

        load_dotenv()
        url = (
            f"mysql+mysqlconnector://{os.getenv('DB_USER', 'root')}:"
            f"{os.getenv('DB_PASSWORD', '')}@{os.getenv('DB_HOST', 'localhost')}:"
            f"{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME', 'etl_preditivo')}"
        )
        engine = create_engine(url)

        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE cenarios_whatif"))
            conn.execute(text("TRUNCATE TABLE previsao_baseline"))
            conn.execute(text("TRUNCATE TABLE receita_mensal_historico"))

        serie_bd = serie.copy()
        serie_bd["mes"] = pd.to_datetime(serie_bd["mes"]).dt.date
        serie_bd.to_sql("receita_mensal_historico", con=engine, if_exists="append", index=False)

        cenarios.to_sql("cenarios_whatif", con=engine, if_exists="append", index=False)
        baseline_bd = baseline.rename(columns={"mes": "mes"}).copy()
        baseline_bd["mes"] = pd.to_datetime(baseline_bd["mes"]).dt.date
        baseline_bd.to_sql("previsao_baseline", con=engine, if_exists="append", index=False)

        print("Tabelas 'receita_mensal_historico', 'cenarios_whatif' e 'previsao_baseline' gravadas no MySQL.")
    except Exception as e:
        print(f"[Aviso] Não foi possível gravar no MySQL ({e}). Os CSVs locais ainda foram salvos normalmente.")


# ── Execução principal ────────────────────────────────────────────────────
if __name__ == "__main__":
    df = carregar_dados()

    print("Construindo série mensal de receita ativa...")
    serie = construir_serie_receita_ativa(df)

    taxas = calcular_taxas_medias(df, serie)
    print(f"Entrada média mensal: R$ {taxas['media_entrada_mensal_rs']:,.2f}")
    print(f"Taxa de churn mensal média: {taxas['taxa_churn_mensal']:.2%}")

    modelo, r2 = ajustar_tendencia(serie)
    baseline = projetar_baseline(serie, modelo, MESES_PROJECAO)

    receita_atual = serie["receita_ativa"].iloc[-1]
    cenarios = gerar_tabela_cenarios(receita_atual, taxas, MESES_PROJECAO)

    CAMINHO_SAIDA_BASELINE.parent.mkdir(parents=True, exist_ok=True)
    baseline.to_csv(CAMINHO_SAIDA_BASELINE, index=False, encoding="utf-8-sig")
    cenarios.to_csv(CAMINHO_SAIDA_CENARIOS, index=False, encoding="utf-8-sig")

    plotar_tendencia(serie, baseline, CAMINHO_GRAFICO)
    salvar_no_mysql(serie, baseline, cenarios)

    print("\n=== Resumo ===")
    print(f"Receita ativa atual: R$ {receita_atual:,.2f}")
    print(f"Receita projetada em {MESES_PROJECAO} meses (baseline): R$ {baseline['receita_projetada'].iloc[-1]:,.2f}")
    print(f"\nTabela de cenários salva em: {CAMINHO_SAIDA_CENARIOS}")
    print(cenarios.to_string(index=False))