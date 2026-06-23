"""
Historical Data Population Script
Fetches and populates European energy data from 2018 to present (one-time operation)
Run: python populate_historical_data.py
"""

import itertools
import json
import os
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import psycopg2

# Configuration
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
    "G3000": "Natural Gas"
}

# Database connection
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5433")
DB_NAME = os.getenv("POSTGRES_DB", "euro_energy")
DB_USER = os.getenv("POSTGRES_USER", "energy_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "energy_pass")


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


def convert_eurostat_json(raw_json_str):
    """Convert multi-dimensional Eurostat JSON to flat records"""
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
        siec_code = combo[dimensions.index("siec")] if "siec" in dimensions else None
        year = combo[dimensions.index("time")]
        geo_code = combo[dimensions.index("geo")]

        # Look up human-readable labels from metadata
        country_name = data["dimension"]["geo"]["category"]["label"].get(
            geo_code, geo_code
        )
        
        if siec_code:
            energy_label = data["dimension"]["siec"]["category"]["label"].get(
                siec_code, siec_code
            )
        else:
            energy_label = "Energy"

        # Build the final record
        simplified_list.append(
            {
                "id": entry_id,
                "energy_type": energy_label,
                "country": geo_code,  # Use country code, not name
                "date": year,
                "energy": energy_val,
                "source": siec_code if siec_code else "FC_E",
            }
        )

        entry_id += 1

    return simplified_list


def fetch_and_insert_generation():
    """Fetch generation data for all years from 2018 onwards"""
    geo_params = "&".join([f"geo={c}" for c in COUNTRIES])
    siec_params = "&".join([f"siec={s}" for s in GENERATION_SOURCES.keys()])
    
    url = (
        f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
        f"nrg_bal_c?format=JSON&freq=A&unit=KTOE&nrg_bal=GEP"
        f"&{siec_params}&{geo_params}&sinceTimePeriod=2010&lang=en"
    )
    
    print(f"\n📥 Fetching Generation Data...")
    
    session = get_session_with_retries()
    response = session.get(url, timeout=60)
    response.raise_for_status()
    
    parsed = convert_eurostat_json(response.text)
    print(f"✅ Parsed {len(parsed)} generation records")
    
    if parsed:
        print(f"📋 Sample record: {parsed[0]}")
    
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    inserted_count = 0
    for idx, record in enumerate(parsed):
        energy_val = record.get("energy")
        country = record.get("country")
        year = record.get("date")
        source = record.get("source")
        energy_type = record.get("energy_type", "Unknown")
        
        # Only skip if energy is exactly 0
        if energy_val == 0:
            continue
            
        if country and year and source:
            try:
                insert_query = """
                    INSERT INTO raw_energy_generation 
                    (energy_type, country, date, energy, source)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (energy_type, country, int(year), float(energy_val), source))
                inserted_count += 1
            except Exception as e:
                if idx < 3:  # Print first few errors
                    print(f"⚠️  Error inserting record {idx}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ Inserted {inserted_count} generation records")
    return inserted_count


def fetch_and_insert_consumption():
    """Fetch consumption data for all years from 2018 onwards"""
    geo_params = "&".join([f"geo={c}" for c in COUNTRIES])
    
    url = (
        f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
        f"nrg_bal_c?format=JSON&freq=A&unit=KTOE&nrg_bal=FC_E"
        f"&{geo_params}&sinceTimePeriod=2018&lang=en"
    )
    
    print(f"\n📥 Fetching Consumption Data...")
    
    session = get_session_with_retries()
    response = session.get(url, timeout=60)
    response.raise_for_status()
    
    parsed = convert_eurostat_json(response.text)
    print(f"✅ Parsed {len(parsed)} consumption records")
    
    if parsed:
        print(f"📋 Sample record: {parsed[0]}")
    
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    inserted_count = 0
    for idx, record in enumerate(parsed):
        energy_val = record.get("energy")
        country = record.get("country")
        year = record.get("date")
        energy_type = record.get("energy_type", "Final Energy Consumption")
        
        # Only skip if energy is exactly 0
        if energy_val == 0:
            continue
            
        if country and year:
            try:
                insert_query = """
                    INSERT INTO raw_energy_consumption 
                    (energy_type, country, date, energy, source)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (energy_type, country, int(year), float(energy_val), "FC_E"))
                inserted_count += 1
            except Exception as e:
                if idx < 3:  # Print first few errors
                    print(f"⚠️  Error inserting record {idx}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ Inserted {inserted_count} consumption records")
    return inserted_count


def main():
    print("=" * 60)
    print("🔋 European Energy Data - Historical Population")
    print("=" * 60)
    print(f"⏱️  Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"📅 Data Range: 2018 - Present")
    print(f"🌍 Countries: {', '.join(COUNTRIES)}")
    print("=" * 60)
    
    try:
        # Fetch and populate generation data
        gen_count = fetch_and_insert_generation()
        
        # Fetch and populate consumption data
        con_count = fetch_and_insert_consumption()
        
        print("\n" + "=" * 60)
        print("✅ POPULATION COMPLETE!")
        print("=" * 60)
        print(f"📊 Generation Records Inserted: {gen_count}")
        print(f"📊 Consumption Records Inserted: {con_count}")
        print(f"⏱️  End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
