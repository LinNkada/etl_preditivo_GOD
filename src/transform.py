"""
transform.py
Etapa de Transformação (T do ETL).

Simula o tratamento que seria necessário caso os dados viessem "crus"
diretamente da API do Notion: parsing de datas, cálculo de campos derivados,
padronização de texto e validação de consistência.

Entrada:  data/raw/obras_ficticias_notion_export.csv
Saída:    data/processed/obras_tratadas.csv
"""

import pandas as pd
from pathlib import Path

CAMINHO_ENTRADA = Path("data/raw/obras_ficticias_notion_export.csv")
CAMINHO_SAIDA = Path("data/processed/obras_tratadas.csv")


def carregar_dados(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, encoding="utf-8-sig")
    return df


def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas do formato 'Notion' para snake_case, padrão de banco."""
    mapa_colunas = {
        "ID Obra": "id_obra",
        "Nome": "nome",
        "Endereço": "endereco",
        "Cidade": "cidade",
        "Estado": "estado",
        "Latitude": "latitude",
        "Longitude": "longitude",
        "Status": "status",
        "Data de Entrada": "data_entrada",
        "Data de Saída": "data_saida",
        "Valor do Contrato (R$)": "valor_contrato",
    }
    return df.rename(columns=mapa_colunas)


def tratar_datas(df: pd.DataFrame) -> pd.DataFrame:
    df["data_entrada"] = pd.to_datetime(df["data_entrada"], errors="coerce")
    df["data_saida"] = pd.to_datetime(df["data_saida"], errors="coerce")
    return df


def calcular_duracao(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula a duração em dias do contrato quando a obra já foi encerrada."""
    df["duracao_dias"] = (df["data_saida"] - df["data_entrada"]).dt.days
    return df


def validar_consistencia(df: pd.DataFrame) -> pd.DataFrame:
    """Remove ou sinaliza registros inconsistentes (ex: saída antes da entrada)."""
    inconsistentes = df["duracao_dias"] < 0
    if inconsistentes.any():
        print(f"[Aviso] {inconsistentes.sum()} registro(s) com datas inconsistentes removidos.")
        df = df[~inconsistentes]
    return df


PREPOSICOES_MINUSCULAS = {"de", "do", "da", "dos", "das", "e"}


def _titulo_com_preposicoes(texto: str) -> str:
    """Como str.title(), mas mantém preposições em minúsculo (ex: 'Mogi das Cruzes')."""
    palavras = texto.split(" ")
    resultado = [
        palavra.lower() if palavra.lower() in PREPOSICOES_MINUSCULAS else palavra.capitalize()
        for palavra in palavras
    ]
    # a primeira palavra nunca deve ficar em minúsculo
    if resultado:
        resultado[0] = resultado[0].capitalize()
    return " ".join(resultado)


def padronizar_texto(df: pd.DataFrame) -> pd.DataFrame:
    df["cidade"] = df["cidade"].str.strip().str.lower().apply(_titulo_com_preposicoes)
    df["estado"] = df["estado"].str.strip().str.upper()
    df["nome"] = df["nome"].str.strip()
    df["endereco"] = df["endereco"].str.strip()
    return df


def formatar_datas_saida(df: pd.DataFrame) -> pd.DataFrame:
    """Converte datas de volta pra string no formato YYYY-MM-DD, mantendo NULL onde não houver."""
    df["data_entrada"] = df["data_entrada"].dt.strftime("%Y-%m-%d")
    df["data_saida"] = df["data_saida"].dt.strftime("%Y-%m-%d")
    return df


def transformar(caminho_entrada: Path = CAMINHO_ENTRADA) -> pd.DataFrame:
    df = carregar_dados(caminho_entrada)
    df = padronizar_colunas(df)
    df = tratar_datas(df)
    df = calcular_duracao(df)
    df = validar_consistencia(df)
    df = padronizar_texto(df)
    df = formatar_datas_saida(df)
    return df


if __name__ == "__main__":
    df_tratado = transformar()
    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    df_tratado.to_csv(CAMINHO_SAIDA, index=False, encoding="utf-8-sig")
    print(f"Dados tratados salvos em: {CAMINHO_SAIDA}")
    print(f"Total de registros: {len(df_tratado)}")
    print(df_tratado.head())
