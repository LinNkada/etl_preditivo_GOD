CREATE DATABASE IF NOT EXISTS etl_preditivo
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE etl_preditivo;

CREATE TABLE IF NOT EXISTS obras (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_obra VARCHAR(20) NOT NULL UNIQUE,
    nome VARCHAR(255) NOT NULL,
    endereco VARCHAR(255) NOT NULL,
    cidade VARCHAR(100) NOT NULL,
    estado CHAR(2) NOT NULL,
    latitude DECIMAL(10, 6) NOT NULL,
    longitude DECIMAL(10, 6) NOT NULL,
    status ENUM('Ativa', 'Encerrada') NOT NULL,
    data_entrada DATE NOT NULL,
    data_saida DATE NULL,
    valor_contrato DECIMAL(12, 2) NOT NULL,
    duracao_dias INT NULL COMMENT 'Calculado: dias entre entrada e saída (NULL se ainda ativa)',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Regra de consistência: data de saída não pode ser anterior à de entrada
    CONSTRAINT chk_datas CHECK (data_saida IS NULL OR data_saida >= data_entrada),

    INDEX idx_status (status),
    INDEX idx_cidade (cidade),
    INDEX idx_data_entrada (data_entrada)
);

-- View auxiliar: métricas rápidas de entrada/saída para o dashboard
CREATE OR REPLACE VIEW vw_metricas_obras AS
SELECT
    COUNT(*) AS total_obras,
    SUM(CASE WHEN status = 'Ativa' THEN 1 ELSE 0 END) AS obras_ativas,
    SUM(CASE WHEN status = 'Encerrada' THEN 1 ELSE 0 END) AS obras_encerradas,
    ROUND(SUM(CASE WHEN status = 'Ativa' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_ativas,
    ROUND(SUM(CASE WHEN status = 'Encerrada' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_encerradas,
    ROUND(AVG(valor_contrato), 2) AS ticket_medio,
    ROUND(AVG(duracao_dias), 1) AS duracao_media_dias
FROM obras;
