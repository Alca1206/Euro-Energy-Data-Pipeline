from __future__ import annotations

import os
import itertools
import json
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import psycopg2
from airflow.decorators import dag, task


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS raw_energy_generation (
    id SERIAL PRIMARY KEY,
    energy_type VARCHAR(200),
    country VARCHAR(10),
    date INT,
    energy NUMERIC,
    source VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_energy_consumption (
    id SERIAL PRIMARY KEY,
    energy_type VARCHAR(200),
    country VARCHAR(10),
    date INT,
    energy NUMERIC,
    source VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

COUNTRIES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "EL", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE"
]

GENERATION_SOURCES = {
    "RA100": "Solar",
    "RA200": "Wind",
    "RA300": "Hydro",
    "N900H": "Nuclear",
    "C0000": "Coal",
    "G3000": "Natural Gas",
}


def get_postgres_dsn() -> str:
    airflow_dsn = os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"]
    return airflow_dsn.replace("postgresql+psycopg2://", "postgresql://", 1)


def get_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def convert_eurostat_json(raw_json_str):
    data = json.loads(raw_json_str)
    dimensions = data["id"]
    sizes = data["size"]
    values = data["value"]

    dim_lists = []
    for dim in dimensions:
        cat_index = data["dimension"][dim]["category"]["index"]
        sorted_cats = sorted(cat_index.keys(), key=lambda k: cat_index[k])
        dim_lists.append(sorted_cats)

    multipliers = []
    for i in range(len(sizes)):
        mult = 1
        for j in range(i + 1, len(sizes)):
            mult *= sizes[j]
        multipliers.append(mult)

    records = []
    for combo in itertools.product(*dim_lists):
        flat_index = 0
        for i, cat in enumerate(combo):
            dim_name = dimensions[i]
            cat_idx = data["dimension"][dim_name]["category"]["index"][cat]
            flat_index += cat_idx * multipliers[i]

        energy_val = values.get(str(flat_index), 0.0)
        if energy_val == 0:
            continue

        siec_code = combo[dimensions.index("siec")] if "siec" in dimensions else None
        year = combo[dimensions.index("time")]
        geo_code = combo[dimensions.index("geo")]

        energy_label = (
            data["dimension"]["siec"]["category"]["label"].get(siec_code, siec_code)
            if siec_code else "Energy"
        )

        records.append({
            "energy_type": energy_label,
            "country": geo_code,
            "date": int(year),
            "energy": float(energy_val),
            "source": siec_code if siec_code else "FC_E",
        })

    return records


@dag(
    dag_id="eurostat_energy_pipeline",
    description="Fetch European energy generation and consumption from Eurostat API.",
    start_date=datetime(2026, 6, 1),
    schedule="@daily",
    catchup=False,
    tags=["euro-energy", "eurostat", "sprint-4"],
)
def eurostat_energy_pipeline():

    @task
    def create_tables() -> None:
        with psycopg2.connect(get_postgres_dsn()) as conn:
            with conn.cursor() as cursor:
                cursor.execute(CREATE_TABLES_SQL)
        print("Tables created successfully.")

    @task
    def fetch_generation() -> int:
        geo_params = "&".join([f"geo={c}" for c in COUNTRIES])
        siec_params = "&".join([f"siec={s}" for s in GENERATION_SOURCES.keys()])
        url = (
            f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
            f"nrg_bal_c?format=JSON&freq=A&unit=KTOE&nrg_bal=GEP"
            f"&{siec_params}&{geo_params}&sinceTimePeriod=2010&lang=en"
        )
        print(f"Fetching generation: {url}")
        session = get_session()
        response = session.get(url, timeout=60)
        response.raise_for_status()

        records = convert_eurostat_json(response.text)
        print(f"Parsed {len(records)} generation records")

        with psycopg2.connect(get_postgres_dsn()) as conn:
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE raw_energy_generation RESTART IDENTITY;")
                cursor.executemany(
                    """INSERT INTO raw_energy_generation
                       (energy_type, country, date, energy, source)
                       VALUES (%s, %s, %s, %s, %s)""",
                    [(r["energy_type"], r["country"], r["date"], r["energy"], r["source"]) for r in records],
                )
        print(f"Generation rows inserted: {len(records)}")
        return len(records)

    @task
    def fetch_consumption() -> int:
        geo_params = "&".join([f"geo={c}" for c in COUNTRIES])
        url = (
            f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
            f"nrg_bal_c?format=JSON&freq=A&unit=KTOE&nrg_bal=FC_E"
            f"&{geo_params}&sinceTimePeriod=2010&lang=en"
        )
        print(f"Fetching consumption: {url}")
        session = get_session()
        response = session.get(url, timeout=60)
        response.raise_for_status()

        records = convert_eurostat_json(response.text)
        print(f"Parsed {len(records)} consumption records")

        with psycopg2.connect(get_postgres_dsn()) as conn:
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE raw_energy_consumption RESTART IDENTITY;")
                cursor.executemany(
                    """INSERT INTO raw_energy_consumption
                       (energy_type, country, date, energy, source)
                       VALUES (%s, %s, %s, %s, %s)""",
                    [(r["energy_type"], r["country"], r["date"], r["energy"], r["source"]) for r in records],
                )
        print(f"Consumption rows inserted: {len(records)}")
        return len(records)

    @task
    def validate(gen_count: int, con_count: int) -> None:
        print(f"Generation rows: {gen_count}")
        print(f"Consumption rows: {con_count}")
        if gen_count == 0:
            raise ValueError("No generation data fetched.")
        if con_count == 0:
            raise ValueError("No consumption data fetched.")
        print("Validation passed.")

    tables = create_tables()
    gen = fetch_generation()
    con = fetch_consumption()
    tables >> [gen, con]
    validate(gen, con)


eurostat_energy_pipeline()