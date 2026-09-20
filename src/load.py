"""
load.py
Etapa de Carga (L do ETL).

Lê os dados já tratados (data/processed/obras_tratadas.csv) e insere
na tabela `obras` do MySQL (schema criado por sql/schema.sql).

Credenciais de conexão vêm do arquivo .env (nunca hardcode senha no código).
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

CAMINHO_DADOS_TRATADOS = Path("data/processed/obras_tratadas.csv")

load_dotenv()

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "etl_preditivo")


def criar_engine():
    url = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url)


def carregar_dados_tratados(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, encoding="utf-8-sig")
    return df


def preparar_para_insercao(df: pd.DataFrame) -> pd.DataFrame:
    """Ajustes finais de tipo antes de mandar pro MySQL."""
    df = df.copy()
    df["data_entrada"] = pd.to_datetime(df["data_entrada"]).dt.date
    df["data_saida"] = pd.to_datetime(df["data_saida"], errors="coerce").dt.date
    # pandas NaT/NaN não é entendido pelo MySQL -> converte pra None
    df = df.where(pd.notnull(df), None)
    return df


def inserir_dados(engine, df: pd.DataFrame, tabela: str = "obras"):
    df.to_sql(tabela, con=engine, if_exists="append", index=False, method="multi", chunksize=200)


def validar_carga(engine, tabela: str = "obras"):
    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {tabela}")).scalar()
        print(f"Total de registros na tabela '{tabela}': {total}")

        metricas = conn.execute(text("SELECT * FROM vw_metricas_obras")).fetchone()
        if metricas:
            print("Métricas (view vw_metricas_obras):")
            print(dict(metricas._mapping))


if __name__ == "__main__":
    print("Conectando ao MySQL...")
    engine = criar_engine()

    print(f"Lendo dados tratados de: {CAMINHO_DADOS_TRATADOS}")
    df = carregar_dados_tratados(CAMINHO_DADOS_TRATADOS)
    df = preparar_para_insercao(df)

    print(f"Inserindo {len(df)} registros na tabela 'obras'...")
    inserir_dados(engine, df)

    print("Carga concluída. Validando...")
    validar_carga(engine)