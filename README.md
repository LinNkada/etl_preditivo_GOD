# ETL-Preditivo

Pipeline de ETL (Extração, Transformação e Carga) com análise preditiva de receita, desenvolvido como projeto de portfólio para a área de Análise de Dados. Simula o fluxo de dados de contratos de obras de uma empresa de portas de proteção para elevadores.

> ⚠️ **Nota sobre os dados**: todos os dados utilizados neste projeto são **fictícios/sintéticos**, gerados artificialmente por questões de confidencialidade. Não representam informações reais de nenhuma empresa.

## Objetivo

Simular um pipeline completo de dados — desde a extração de uma fonte externa (API do Notion) até a análise preditiva de receita — alimentando um dashboard interativo no Power BI com um recurso de simulação what-if.

## Arquitetura do pipeline

```
Notion (fonte simulada)
        │
        ▼
   [Extract]  →  src/extract.py
        │
        ▼
  [Transform]  →  src/transform.py
        │
        ▼
    [Load]     →  src/load.py  →  MySQL
        │
        ▼
[Predictive]   →  src/predictive_model.py
        │
        ▼
   Power BI (dashboard + slider what-if)
```

## Estrutura 

```
etl-preditivo/
├── data/
│   ├── raw/              # dados brutos simulados (saída "crua" da extração)
│   └── processed/        # dados tratados e saídas do modelo preditivo
├── src/
│   ├── extract.py        # extração via API do Notion (simulada)
│   ├── transform.py      # limpeza, padronização e cálculo de campos derivados
│   ├── load.py            # carga dos dados tratados no MySQL
│   └── predictive_model.py # projeção de receita e geração de cenários what-if
├── notebooks/
│   └── analise_exploratoria.ipynb
├── sql/
│   └── schema.sql         # criação das tabelas e view no MySQL
├── .env.example
├── requirements.txt
└── README.md
```

## Tecnologias utilizadas

| Etapa | Ferramentas |
|---|---|
| Extração | Python, API do Notion |
| Transformação | Pandas |
| Carga | MySQL, SQLAlchemy |
| Análise preditiva | Pandas, NumPy, Scikit-learn |
| Visualização | Matplotlib |
| Dashboard | Power BI |
| Versionamento | Git, GitHub |

## O banco de dados

O `sql/schema.sql` cria o banco `etl_preditivo` com as seguintes tabelas:

- **`obras`** — dados granulares de cada obra/contrato (endereço, coordenadas, status, datas, valor)
- **`cenarios_whatif`** — receita projetada para uma faixa de variações (-50% a +50%) na taxa de saída (churn), usada pelo slider what-if do dashboard
- **`previsao_baseline`** — projeção de receita mês a mês, sem variação de cenário

E uma view auxiliar:

- **`vw_metricas_obras`** — métricas agregadas prontas: total de obras, % ativas/encerradas, ticket médio, duração média de contrato

## O modelo preditivo

O `predictive_model.py`:

1. Constrói uma série temporal mensal de **receita ativa** (soma do valor dos contratos vigentes em cada mês)
2. Ajusta um modelo de regressão linear sobre essa série para projetar a tendência de receita
3. Simula cenários variando a taxa de churn (-50% a +50%, em passos de 5%) e calcula a receita projetada resultante para cada cenário
4. Grava os resultados tanto em CSV (`data/processed/`) quanto diretamente nas tabelas do MySQL

Essa tabela de cenários é consumida no Power BI através de um parâmetro **What-if** nativo, permitindo simular o impacto de diferentes taxas de rotatividade de contratos na receita futura sem precisar rodar o modelo novamente.

## Como rodar o projeto

### 1. Pré-requisitos
- Python 3.10+
- MySQL instalado localmente (ou acessível remotamente)

### 2. Configuração do ambiente

```bash
python -m venv venv
source venv/Scripts/activate   # Windows (Git Bash)
# ou venv\Scripts\Activate.ps1 no PowerShell

pip install -r requirements.txt
```

### 3. Configuração do banco de dados

Renomeie `.env.example` para `.env` e preencha com suas credenciais:

```
DB_USER=root
DB_PASSWORD=sua_senha_aqui
DB_HOST=localhost
DB_PORT=3306
DB_NAME=etl_preditivo
```

Execute o `sql/schema.sql` no MySQL Workbench (ou outro cliente MySQL) para criar o banco e as tabelas.

### 4. Executando o pipeline

```bash
python src/transform.py         # trata os dados brutos
python src/load.py              # carrega os dados na tabela `obras`
python src/predictive_model.py  # gera a projeção e os cenários what-if
```

### 5. Conectando ao Power BI

No Power BI Desktop: `Get Data` → `MySQL database` → informe servidor (`localhost:3306`) e banco (`etl_preditivo`) → selecione as tabelas `obras`, `cenarios_whatif`, `previsao_baseline` e a view `vw_metricas_obras`.

## Dashboard (Power BI)

- Mapa geográfico das obras (latitude/longitude)
- Percentual de obras ativas vs. encerradas
- Slider de simulação what-if para variação da taxa de saída de contratos, refletindo o impacto na receita projetada

## Autor

Lincoln — Estudante de Análise e Desenvolvimento de Sistemas, em transição de carreira para Análise de Dados.
