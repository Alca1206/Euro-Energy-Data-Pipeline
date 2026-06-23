
# Euro Energy Data Pipeline

## Project Overview

This project collects, stores, processes, and displays European energy data using PostgreSQL, Apache Airflow, and a lightweight dashboard UI.

## Local Setup

1. Create `.env` from `.env.example`.
2. Start the project:

```bash
docker compose up -d
```

3. Open Airflow:

```text
http://localhost:8080
```

## Services

- PostgreSQL: `localhost:5433`
- Airflow: `http://localhost:8080`
- Dashboard UI: `app/index.html`

## Database

Database name: `euro_energy`

## Sprint 2 Pipeline

The Airflow DAG `energy_ingestion_pipeline` performs four steps:

1. Create raw and clean database tables.
2. Load sample European energy price data.
3. Clean the data by removing invalid rows and standardizing country names.
4. Validate that clean data contains usable positive price values.

## Sprint 3 Dashboard

Sprint 3 adds a user interface in the `app` folder.

Open this file in a browser:

```text
app/index.html
```

The dashboard shows:

- Average energy price
- Highest-price market
- Loaded record count
- Country comparison chart
- Selected-country trend
- Pipeline status summary

## Verification Queries

Run these queries after triggering the DAG in Airflow:

```sql
SELECT * FROM raw_energy_prices;
SELECT * FROM clean_energy_prices;
SELECT country, AVG(price_eur_mwh) AS average_price
FROM clean_energy_prices
GROUP BY country
ORDER BY average_price DESC;
```

# Euro Energy Data Pipeline

## Project Overview

This project collects, stores, processes, and displays European energy data using PostgreSQL, Apache Airflow, and a lightweight dashboard UI.

## Local Setup

1. Create `.env` from `.env.example`.
2. Start the project:

```bash
docker compose up -d
```

3. Open Airflow:

```text
http://localhost:8080
```

## Services

- PostgreSQL: `localhost:5433`
- Airflow: `http://localhost:8080`
- Dashboard UI: `app/index.html`

## Database

Database name: `euro_energy`

## Sprint 2 Pipeline

The Airflow DAG `energy_ingestion_pipeline` performs four steps:

1. Create raw and clean database tables.
2. Load sample European energy price data.
3. Clean the data by removing invalid rows and standardizing country names.
4. Validate that clean data contains usable positive price values.

## Sprint 3 Dashboard

Sprint 3 adds a user interface in the `app` folder.

Open this file in a browser:

```text
app/index.html
```

The dashboard shows:

- Average energy price
- Highest-price market
- Loaded record count
- Country comparison chart
- Selected-country trend
- Pipeline status summary

## Verification Queries

Run these queries after triggering the DAG in Airflow:

```sql
SELECT * FROM raw_energy_prices;
SELECT * FROM clean_energy_prices;
SELECT country, AVG(price_eur_mwh) AS average_price
FROM clean_energy_prices
GROUP BY country
ORDER BY average_price DESC;
```

## Sprint 5 Dashboard Improvements

Sprint 5 improves the dashboard with country filtering, summary statistics, comparison table, and report summary section.