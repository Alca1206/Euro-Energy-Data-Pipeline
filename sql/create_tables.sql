CREATE TABLE IF NOT EXISTS energy_prices (
    id SERIAL PRIMARY KEY,
    country VARCHAR(100),
    date DATE,
    price_eur_mwh NUMERIC,
    source VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_energy_prices (
    id SERIAL PRIMARY KEY,
    country VARCHAR(100),
    price_date DATE,
    price_eur_mwh NUMERIC,
    source VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clean_energy_prices (
    id SERIAL PRIMARY KEY,
    country VARCHAR(100),
    price_date DATE,
    price_eur_mwh NUMERIC,
    source VARCHAR(100),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);