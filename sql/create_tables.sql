CREATE TABLE IF NOT EXISTS energy_prices (
    id SERIAL PRIMARY KEY,
    country VARCHAR(100),
    date DATE,
    price_eur_mwh NUMERIC,
    source VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);