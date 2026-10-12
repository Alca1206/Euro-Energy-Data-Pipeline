
# Euro Energy Data Pipeline

## Project Overview

This project collects, stores, processes, and displays European energy generation and consumption data using:
- **Eurostat API** for real-time energy statistics
- **PostgreSQL 15** for data storage
- **Apache Airflow 2.9.1** for orchestration
- **Node.js + Express** REST API backend
- **Streamlit** interactive dashboard

## Quick Start

```bash
# Start all services
docker compose up -d

# Populate historical data (one-time: 2018 to present)
python populate_historical_data.py

# Trigger Airflow DAG
docker exec euroenergydatapipeline-airflow-webserver-1 airflow dags trigger eurostat_energy_pipeline

# Start Streamlit dashboard (new terminal)
streamlit run streamlit_app.py
```

## Services & Access

| Service | URL | Purpose |
|---------|-----|---------|
| Airflow Web UI | `http://localhost:8080` | DAG orchestration & monitoring |
| Streamlit Dashboard | `http://localhost:8501` | Interactive energy analytics |
| PostgreSQL | `localhost:5433` | Database (energy_admin/energy_pass) |

## Database

- **Name**: `euro_energy`
- **Tables**: 
  - `raw_energy_generation` (200+ rows) - Solar, wind, hydro, nuclear, coal, natural gas
  - `raw_energy_consumption` (2500+ rows) - Final energy consumption by country
- **Credentials**: energy_admin / energy_pass

## Sprint Evolution

### Sprint 2 - Initial Pipeline
- Created basic Airflow DAG for sample data ingestion
- Set up PostgreSQL tables for raw and clean data
- Implemented data validation tasks

### Sprint 3 - Dashboard UI
- Added HTML dashboard in `app/index.html`
- Connected to PostgreSQL for real-time metrics
- Created country comparison and trend charts

### Sprint 4 - Eurostat Integration & API Enhancement
- ✅ Integrated **Eurostat Energy API** (multi-dimensional JSON parsing)
- ✅ Implemented `convert_eurostat_json()` function for complex data transformation
- ✅ Updated PostgreSQL schema: energy_type, country, date, energy, source columns
- ✅ Added **retry logic & timeout handling** (3 retries, 60s timeout) for API reliability
- ✅ Developed **Streamlit dashboard** with advanced visualizations:
  - **Year-wise filtering**: Select single or multiple years for analysis
  - **Historical data**: 2018-present (7+ years) with trend analysis
  - **Multi-year comparisons**: Compare consumption/generation across years and countries
  - **Summary statistics**: Aggregated metrics by year

## Data Coverage

- **Countries**: 8 (Germany, France, Spain, Italy, Netherlands, Belgium, Poland, Sweden)
- **Energy Sources**: 6 types (Solar, Wind, Hydro, Nuclear, Coal, Natural Gas)
- **Time Period**: 2018-2024 (annual data)
- **Units**: KTOE (kilotonne oil equivalent)

## Historical Data Population

To populate the database with **7 years of historical data (2018-2024)**, run once:

```bash
python populate_historical_data.py
```

This script:
- Fetches generation data for all countries and energy sources from 2018-present
- Fetches consumption data for all countries from 2018-present
- Inserts data into PostgreSQL tables
- Handles duplicates gracefully (ON CONFLICT DO NOTHING)
- Includes retry logic for API resilience

**Output:**
```
Generation Records Inserted: ~1,000+
Consumption Records Inserted: ~2,500+
```

After population, the Streamlit dashboard will display historical trends across all years.

## Key Features

### Airflow DAG: `eurostat_energy_pipeline`
```
create_tables → [fetch_generation, fetch_consumption] → validate_data
```
- Runs daily at midnight
- Fetches from Eurostat API with retry logic
- Parses multi-dimensional JSON data
- Inserts into PostgreSQL
- Validates row counts before completion

### Streamlit Dashboard Features
- **Year Selection**: Filter data by single or multiple years for focused analysis
- **Country Filters**: Compare energy metrics across selected countries
- **Metrics**: Real-time average/max/min consumption and total generation
- **Year-wise Comparison**: 
  - Trends over selected years (line chart)
  - Consumption by country and year (grouped bar chart)
  - Generation by source (pie chart)
- **Historical Trends**:
  - Total consumption over all years (2018-present)
  - Total generation over all years (2018-present)
- **Data Tables**:
  - Full consumption/generation records with sorting and filtering
  - Year-wise summary statistics (sum, mean, max, min)
- **Refresh Controls**: Manual data refresh to sync with latest database updates

## Verification Queries

```sql
-- Check generation data
SELECT COUNT(*) FROM raw_energy_generation;
SELECT * FROM raw_energy_generation LIMIT 5;

-- Check consumption data
SELECT COUNT(*) FROM raw_energy_consumption;
SELECT * FROM raw_energy_consumption LIMIT 5;

-- Aggregate by country
SELECT country, AVG(energy) AS avg_energy, SUM(energy) AS total_energy
FROM raw_energy_consumption
GROUP BY country
ORDER BY total_energy DESC;
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| DAG fails with timeout | Retry logic handles up to 3 attempts with 60s timeout |
| Empty dashboard | Run: `python populate_historical_data.py` then `airflow dags trigger eurostat_energy_pipeline` |
| Historical data missing | Execute `python populate_historical_data.py` (one-time operation) |
| Connection refused | Check `.env` credentials and docker-compose services running |
| Streamlit won't start | Verify Python packages: `pip install streamlit psycopg2-binary` |

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