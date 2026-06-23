from __future__ import annotations

import itertools
import json
import os
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import psycopg2
from airflow.decorators import dag, task


def get_session_with_retries():
    """Create a requests session with retry logic"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


CREATE_TABLES_SQL = """

CREATE TABLE IF NOT EXISTS eurostat_energy_data (
    id SERIAL PRIMARY KEY,
    energy_type VARCHAR(100),
    country VARCHAR(10),
    date INT,
    energy NUMERIC,
    source VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_energy_generation (
    id SERIAL PRIMARY KEY,
    energy_type VARCHAR(100),
    country VARCHAR(10),
    date INT,
    energy NUMERIC,
    source VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_energy_consumption (
    id SERIAL PRIMARY KEY,
    energy_type VARCHAR(100),
    country VARCHAR(10),
    date INT,
    energy NUMERIC,
    source VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

COUNTRIES = ["DE", "FR", "ES", "IT", "NL", "BE", "PL", "SE"]

GENERATION_SOURCES = {
    "RA100": "Solar",
    "RA200": "Wind",
    "RA300": "Hydro",
    "N900H": "Nuclear",
    "C0000": "Coal",
    "G3000": "Natural Gas",
}


def convert_eurostat_json(raw_json_str):
    data = json.loads(raw_json_str)

    dimensions = data["id"]  # ['freq', 'nrg_bal', 'siec', 'unit', 'geo', 'time']
    sizes = data["size"]  # [1, 1, 72, 1, 1, 5]
    values = data["value"]
    source_name = data.get("source", "ESTAT")

    # 1. Extract category keys for each dimension in their exact indexed order
    dim_lists = []
    for dim in dimensions:
        cat_index = data["dimension"][dim]["category"]["index"]
        sorted_cats = sorted(cat_index.keys(), key=lambda k: cat_index[k])
        dim_lists.append(sorted_cats)

    # 2. Compute index multipliers for the multi-dimensional flattening math
    multipliers = []
    for i in range(len(sizes)):
        mult = 1
        for j in range(i + 1, len(sizes)):
            mult *= sizes[j]
        multipliers.append(mult)

    simplified_list = []
    entry_id = 1  # Initialize sequential ID counter

    # 3. Loop through every possible combination of dimensions
    for combo in itertools.product(*dim_lists):
        # Calculate the unique flat index for this specific combination
        flat_index = 0
        for i, cat in enumerate(combo):
            dim_name = dimensions[i]
            cat_idx = data["dimension"][dim_name]["category"]["index"][cat]
            flat_index += cat_idx * multipliers[i]

        str_index = str(flat_index)

        # Handle missing data points gracefully
        if str_index in values:
            energy_val = values[str_index]
        else:
            energy_val = 0.0

        # Extract dimensions for mapping
        siec_code = combo[dimensions.index("siec")]
        year = combo[dimensions.index("time")]
        geo_code = combo[dimensions.index("geo")]

        # Look up human-readable labels from metadata
        country_name = data["dimension"]["geo"]["category"]["label"].get(
            geo_code, geo_code
        )
        energy_label = data["dimension"]["siec"]["category"]["label"].get(
            siec_code, siec_code
        )

        # Build the final record
        simplified_list.append(
            {
                "id": entry_id,  # 1, 2, 3...
                "energy_type": energy_label,  # E.g., 'Natural gas', 'Electricity'
                "country": country_name,
                "date": year,
                "energy": energy_val,
                "source": source_name,
            }
        )

        entry_id += 1  # Increment the counter for the next record

    return json.dumps(simplified_list, indent=4)


def get_postgres_dsn() -> str:
    airflow_dsn = os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"]
    return airflow_dsn.replace("postgresql+psycopg2://", "postgresql://", 1)


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
        f"&{siec_params}&{geo_params}&sinceTimePeriod=2020&lang=en"
    )
        print(f"Fetching: {url}")
        session = get_session_with_retries()
        response = session.get(url, timeout=60)
        response.raise_for_status()
        data = response.json()

        dimensions = data.get("dimension", {})
        geo_dim = dimensions.get("geo", {}).get("category", {}).get("index", {})
        time_dim = dimensions.get("time", {}).get("category", {}).get("index", {})
        siec_dim = dimensions.get("siec", {}).get("category", {}).get("index", {})
        values = data.get("value", {})

        print(f"Geo keys: {list(geo_dim.keys())}")
        print(f"Time keys: {list(time_dim.keys())[:5]}")
        print(f"Siec keys: {list(siec_dim.keys())}")
        print(f"Total values: {len(values)}")

        geo_by_id = {v: k for k, v in geo_dim.items()}
        time_by_id = {v: k for k, v in time_dim.items()}
        siec_by_id = {v: k for k, v in siec_dim.items()}

        n_siec = len(siec_dim)
        n_time = len(time_dim)
        n_geo = len(geo_dim)

        rows = []
        for str_idx, value in values.items():
            idx = int(str_idx)
            siec_i = idx % n_siec
            time_i = (idx // n_siec) % n_time
            geo_i = (idx // (n_siec * n_time)) % n_geo

            country = geo_by_id.get(geo_i)
            year_str = time_by_id.get(time_i)
            siec_code = siec_by_id.get(siec_i)
            source_name = GENERATION_SOURCES.get(siec_code, siec_code)

            if country and year_str and value is not None:
                rows.append((source_name, country, int(year_str), float(value), "GEP"))

        print(f"Rows parsed: {len(rows)}")

        with psycopg2.connect(get_postgres_dsn()) as conn:
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE raw_energy_generation RESTART IDENTITY;")
                cursor.executemany(
                    "INSERT INTO raw_energy_generation (energy_type, country, date, energy, source) VALUES (%s, %s, %s, %s, %s);",
                    rows,
                )
        print(f"Generation rows inserted: {len(rows)}")
        return len(rows)

    @task
    def fetch_consumption() -> int:
        geo_params = "&".join([f"geo={c}" for c in COUNTRIES])

        url = (
        f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
        f"nrg_bal_c?format=JSON&freq=A&unit=KTOE&nrg_bal=FC_E"
        f"&{geo_params}&sinceTimePeriod=2020&lang=en"
    )
        print(f"Fetching: {url}")
        session = get_session_with_retries()
        response = session.get(url, timeout=60)
        response.raise_for_status()
        data = response.json()

        print(f"API Response keys: {data.keys()}")
        print(f"Dimensions: {data.get('id', [])}")
        print(f"Sizes: {data.get('size', [])}")

        dimensions = data.get("dimension", {})
        geo_dim = dimensions.get("geo", {}).get("category", {}).get("index", {})
        time_dim = dimensions.get("time", {}).get("category", {}).get("index", {})
        values = data.get("value", {})

        print(f"Geo keys: {list(geo_dim.keys())}")
        print(f"Time keys: {list(time_dim.keys())[:5]}")
        print(f"Total values: {len(values)}")

        # If no values found with old parsing, try convert_eurostat_json
        if len(values) == 0:
            print("No values found with old parsing method, trying convert_eurostat_json...")
            json_str = json.dumps(data)
            result_json = convert_eurostat_json(json_str)
            result_list = json.loads(result_json)
            
            rows = []
            for record in result_list:
                if record["energy"] is not None:
                    rows.append((
                        record["energy_type"],
                        record["country"],
                        record["date"],
                        record["energy"],
                        record["source"]
                    ))
            
            print(f"Rows parsed: {len(rows)}")
            
            with psycopg2.connect(get_postgres_dsn()) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("TRUNCATE TABLE raw_energy_consumption RESTART IDENTITY;")
                    cursor.executemany(
                        "INSERT INTO raw_energy_consumption (energy_type, country, date, energy, source) VALUES (%s, %s, %s, %s, %s);",
                        rows,
                    )
            print(f"Consumption rows inserted: {len(rows)}")
            return len(rows)

        # Old parsing method for backwards compatibility
        geo_by_id = {v: k for k, v in geo_dim.items()}
        time_by_id = {v: k for k, v in time_dim.items()}

        n_time = len(time_dim)
        n_geo = len(geo_dim)

        rows = []
        for str_idx, value in values.items():
            idx = int(str_idx)
            time_i = idx % n_time
            geo_i = (idx // n_time) % n_geo

            country = geo_by_id.get(geo_i)
            year_str = time_by_id.get(time_i)

            if country and year_str and value is not None:
                rows.append(("Final Consumption - Energy", country, int(year_str), float(value), "ESTAT"))

        print(f"Rows parsed: {len(rows)}")

        with psycopg2.connect(get_postgres_dsn()) as conn:
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE raw_energy_consumption RESTART IDENTITY;")
                cursor.executemany(
                    "INSERT INTO raw_energy_consumption (energy_type, country, date, energy, source) VALUES (%s, %s, %s, %s, %s);",
                    rows,
                )
        print(f"Consumption rows inserted: {len(rows)}")
        return len(rows)

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