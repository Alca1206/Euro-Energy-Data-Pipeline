from datetime import datetime
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st

# Page config
st.set_page_config(
    page_title="Euro Energy Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Database connection function
def get_db_connection():
    """Create a fresh database connection for each use"""

    try:
        return psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5433"),
            database=os.getenv("POSTGRES_DB", "euro_energy"),
            user=os.getenv("POSTGRES_USER", "energy_admin"),
            password=os.getenv("POSTGRES_PASSWORD", "energy_pass"),
        )
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None


# Query functions
@st.cache_data(ttl=300)
def get_consumption_data():
    try:
        conn = get_db_connection()
        query = """
            SELECT date, country, energy_type, energy, source, loaded_at
            FROM raw_energy_consumption
            ORDER BY date DESC, country
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def get_generation_data():
    try:
        conn = get_db_connection()
        query = """
            SELECT date, country, energy_type, energy, source, loaded_at
            FROM raw_energy_generation
            ORDER BY date DESC, country
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def get_db_status():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM raw_energy_consumption")
        con_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM raw_energy_generation")
        gen_count = cursor.fetchone()[0]
        cursor.execute("SELECT MAX(date) FROM raw_energy_consumption")
        latest_con_date = cursor.fetchone()[0]
        cursor.execute("SELECT MAX(date) FROM raw_energy_generation")
        latest_gen_date = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return con_count, gen_count, latest_con_date, latest_gen_date
    except Exception as e:
        st.error(f"Error fetching status: {e}")
        return 0, 0, None, None


# NEW: Optimized helper function to cache CSV conversion
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


# Main Dashboard
st.title("🔋 European Energy Data Dashboard")

# Sidebar
st.sidebar.header("Dashboard Controls")
if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

# Database Status
st.sidebar.subheader("📊 Database Status")
con_count, gen_count, latest_con_date, latest_gen_date = get_db_status()
st.sidebar.metric("Consumption Records", con_count or "-")
st.sidebar.metric("Generation Records", gen_count or "-")
st.sidebar.metric("Latest Consumption Year", latest_con_date or "-")
st.sidebar.metric("Latest Generation Year", latest_gen_date or "-")

# =====================================================================
# REPLACE EVERYTHING FROM "Load data" DOWN TO YOUR "Metrics Row" WITH THIS
# =====================================================================

# Load data
consumption_df = get_consumption_data()
generation_df = get_generation_data()

# -------------------------------------------------------------
# 🌟 UPGRADED: The Master Dictionary
# -------------------------------------------------------------
COUNTRY_LABEL_MAP = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia",
    "CY": "Cyprus", "CZ": "Czech Republic", "DK": "Denmark", "EE": "Estonia",
    "FI": "Finland", "FR": "France", "DE": "Germany", "EL": "Greece",
    "GR": "Greece", "HU": "Hungary", "IE": "Ireland", "IT": "Italy",
    "LV": "Latvia", "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta",
    "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
    "SK": "Slovakia", "SI": "Slovenia", "ES": "Spain", "SE": "Sweden",
    "EU27_2020": "European Union (27)"
}

# Your complete master list of energy sources
GENERATION_SOURCES = {
    "GEP": "Gross Electricity Production (Total)",
    "TOTAL": "Total All Energy Sources",
    "RA000": "Total Renewables",
    "CF": "Combustible Fuels",
    "C0000": "Solid Fossil Fuels",
    "C0100": "Hard Coal",
    "C0200": "Brown Coal / Lignite",
    "O4000": "Oil and Petroleum",
    "O4600": "Diesel / Gas Oil",
    "G3000": "Natural Gas",
    "G3200": "Liquefied Natural Gas (LNG)",
    "N900H": "Nuclear Heat",
    "N9000": "Nuclear Energy",
    "RA100": "Hydroelectric",
    "RA200": "Geothermal",
    "RA300": "Wind",
    "RA400": "Solar",
    "RA500": "Tide, Wave, and Ocean",
    "W6000": "Waste (Non-Renewable)",
    "W6100": "Industrial Waste",
    "W6220": "Municipal Waste (Non-Renewable)",
    "R5110-5150_W6000RI": "Combustible Renewables",
    "R5220B": "Liquid Biofuels",
    "R5300": "Biogases"
}

if not consumption_df.empty:
    consumption_df['country_name'] = consumption_df['country'].map(COUNTRY_LABEL_MAP).fillna(consumption_df['country'])

if not generation_df.empty:
    generation_df['country_name'] = generation_df['country'].map(COUNTRY_LABEL_MAP).fillna(generation_df['country'])
    
    # 🌟 Apply the new master dictionary here!
    generation_df['source'] = generation_df['source'].map(GENERATION_SOURCES).fillna(generation_df['source'])

# -------------------------------------------------------------
# 🔍 DEBUG: Prove exactly what is in the database
# -------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.error(f"**Database Audit:** These are the ONLY energy sources currently existing in your raw database rows: {generation_df['source'].unique()}")

# 2. 🌟 PROCEED TO DASHBOARD UI
if consumption_df.empty or generation_df.empty:
    st.warning("⚠️ No data available. Please trigger the Airflow DAG first.")
else:
    # -------------------------------------------------------------
    # 📅 UPGRADED: Year Filter with "Select All"
    # -------------------------------------------------------------
    st.sidebar.subheader("📅 Year Filter")
    
    # Get all available years from your data
    all_years = sorted(
        set(consumption_df["date"].unique()) | set(generation_df["date"].unique()), 
        reverse=True
    )
    
    # 1. Add the Select All checkbox
    select_all_years = st.sidebar.checkbox("Select All Years", value=False, key="all_years_check")
    
    # 2. Configure the multiselect based on the checkbox
    selected_years = st.sidebar.multiselect(
        "Select Years",
        options=all_years,
        default=all_years if select_all_years else all_years[:3], # Auto-fill if checked
        disabled=select_all_years # Lock it if "Select All" is active
    )

    # -------------------------------------------------------------
    # 🌍 UPGRADED: Country Filter with "Select All"
    # -------------------------------------------------------------
    st.sidebar.subheader("🌍 Country Filter")
    
    # Get all available countries from your data
    all_countries = sorted(
        set(consumption_df["country_name"].dropna().unique()) 
        | set(generation_df["country_name"].dropna().unique())
    )
    
    # 1. Add the Select All checkbox
    select_all_countries = st.sidebar.checkbox("Select All Countries", value=False, key="all_countries_check")
    
    # 2. Configure the multiselect based on the checkbox
    selected_countries = st.sidebar.multiselect(
        "Select Countries",
        options=all_countries,
        default=all_countries if select_all_countries else all_countries[:3], # Auto-fill if checked
        disabled=select_all_countries # Lock it if "Select All" is active
    )

    # --- YOUR FILTERING LOGIC CONTINUES BELOW ---
    # Filter data based on the selections...

    # 3. 🌟 FILTER DATA BASED ON SELECTIONS
    # First filter by year
    if selected_years:
        consumption_filtered = consumption_df[consumption_df["date"].isin(selected_years)]
        generation_filtered = generation_df[generation_df["date"].isin(selected_years)]
    else:
        consumption_filtered = consumption_df
        generation_filtered = generation_df

    # Then filter by country_name
    if selected_countries:
        consumption_filtered = consumption_filtered[
            consumption_filtered["country_name"].isin(selected_countries)
        ]
        generation_filtered = generation_filtered[
            generation_filtered["country_name"].isin(selected_countries)
        ]

    # Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    

# =====================================================================
# YOUR EXISTING METRICS AND CHARTS CONTINUE NORMALLY BELOW THIS POINT
# =====================================================================

    with col1:
        avg_consumption = consumption_filtered["energy"].mean()
        st.metric(
            "Avg Consumption (KTOE)",
            f"{avg_consumption:.2f}" if not pd.isna(avg_consumption) else "-",
        )

    with col2:
        max_consumption = consumption_filtered["energy"].max()
        st.metric(
            "Max Consumption (KTOE)",
            f"{max_consumption:.2f}" if not pd.isna(max_consumption) else "-",
        )

    with col3:
        min_consumption = consumption_filtered["energy"].min()
        st.metric(
            "Min Consumption (KTOE)",
            f"{min_consumption:.2f}" if not pd.isna(min_consumption) else "-",
        )

    with col4:
        total_generation = generation_filtered["energy"].sum()
        st.metric(
            "Total Generation (KTOE)",
            f"{total_generation:.2f}" if not pd.isna(total_generation) else "-",
        )

    # Charts Section
    st.markdown("---")
    st.subheader("📈 Energy Visualizations")

    # Consumption by Country
    col1, col2 = st.columns(2)

    with col1:
        if not consumption_filtered.empty:
            con_by_country = (
                consumption_filtered.groupby(["date", "country"])["energy"]
                .sum()
                .reset_index()
            )
            fig_con = px.bar(
                con_by_country,
                x="country",
                y="energy",
                color="date",
                title="Energy Consumption by Country & Year",
                labels={"energy": 'Energy (KTOE)', "country": "Country"},
                barmode="group",
            )
            st.plotly_chart(fig_con, use_container_width=True)

    with col2:
        if not generation_filtered.empty:
            # -------------------------------------------------------------
            # 🌟 FIX 1: Group ONLY by source (Remove 'date')
            # -------------------------------------------------------------
            gen_by_source = generation_filtered.groupby(['source'])['energy'].sum().reset_index()
            
            # 🌟 FIX 2: Filter out ALL aggregate totals
            aggregates_to_remove = [
                "Gross Electricity Production (Total)", 
                "Total All Energy Sources", 
                "Total Renewables",
                "Combustible Fuels" 
            ]
            
            pie_data = gen_by_source[~gen_by_source['source'].isin(aggregates_to_remove)]
            
            # 🌟 FIX 3: Remove sources with 0 energy so they don't clutter the legend
            pie_data = pie_data[pie_data['energy'] > 0]
            
            fig_gen = px.pie(
                pie_data,
                values='energy',
                names='source',
                title="Generation by Energy Source",
                hole=0.3
            )
            
            # Force the legend to show everything that survives the filter
            fig_gen.update_layout(showlegend=True)
            
            st.plotly_chart(fig_gen, use_container_width=True)

    # Year-wise Comparison
    st.subheader("📊 Year-wise Analysis")
    col1, col2 = st.columns(2)

    with col1:
        if not consumption_filtered.empty:
            con_by_year = (
                consumption_filtered.groupby("date")["energy"]
                .agg(["sum", "mean", "max"])
                .reset_index()
            )
            fig_year_con = px.line(
                con_by_year,
                x="date",
                y=["sum", "mean"],
                title="Consumption Trends Over Years",
                labels={"value": "Energy (KTOE)", "date": "Year"},
                markers=True,
            )
            st.plotly_chart(fig_year_con, use_container_width=True)

    with col2:
        if not generation_filtered.empty:
            gen_by_year_source = (
                generation_filtered.groupby(["date", "source"])["energy"]
                .sum()
                .reset_index()
            )
            fig_gen_stack = px.bar(
                gen_by_year_source,
                x="date",
                y="energy",
                color="source",
                title="Generation by Source Over Years",
                labels={"energy": "Energy (KTOE)", "date": "Year"},
                barmode="stack",
            )
            st.plotly_chart(fig_gen_stack, use_container_width=True)

    # Historical Trends
    st.markdown("---")
    st.subheader("📉 Historical Trends (All Years)")

    col1, col2 = st.columns(2)

    with col1:
        if not consumption_df.empty:
            all_con_by_year = (
                consumption_df.groupby("date")["energy"]
                .agg(["sum", "mean"])
                .reset_index()
            )
            fig_all_con = px.line(
                all_con_by_year,
                x="date",
                y="sum",
                title="Total Consumption Over All Years",
                labels={"sum": "Total Energy (KTOE)", "date": "Year"},
                markers=True,
            )
            st.plotly_chart(fig_all_con, use_container_width=True)

    with col2:
        if not generation_df.empty:
            all_gen_by_year = (
                generation_df.groupby("date")["energy"].sum().reset_index()
            )
            fig_all_gen = px.line(
                all_gen_by_year,
                x="date",
                y="energy",
                title="Total Generation Over All Years",
                labels={"energy": "Total Energy (KTOE)", "date": "Year"},
                markers=True,
                line_shape="spline",
            )
            st.plotly_chart(fig_all_gen, use_container_width=True)

    # Data Tables & Downloads Section
    st.markdown("---")
    st.subheader("🛠️ Data Audit & Export Center")
    st.caption("The main charts above show your high-level trends. Use the vaults below to search, audit, and extract granular ledger records.")

    # Create clean tabs for the two datasets
    tab1, tab2 = st.tabs(["📊 Consumption Records", "⚡ Generation Records"])

    with tab1:
        # Main action button is visible right away
        csv_con = convert_df_to_csv(consumption_filtered)
        st.download_button(
            label="📥 Export Filtered Consumption Dataset (CSV)",
            data=csv_con,
            file_name=f"energy_consumption_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="download_btn_consumption",
            use_container_width=True
        )

        # 🌟 IDEA 3: The Explanatory Dropdown (Collapsible Vault)
        with st.expander("🔍 Click to open Raw Consumption Ledger Vault", expanded=False):
            st.markdown("### 🗄️ Internal Audit Ledger")
            st.write("This vault contains the exact rows pulled from `raw_energy_consumption`. Use the search box below to find specific records instantly.")
            
            # Local search filter inside the expander
            search_con = st.text_input("⚡ Quick search by Energy Type (e.g., 'Natural gas', 'Electricity'):", key="search_con_input")
            
            # Apply local search filter if text is typed
            display_con_df = consumption_filtered.sort_values('date', ascending=False)
            if search_con:
                display_con_df = display_con_df[display_con_df['energy_type'].str.contains(search_con, case=False, na=False)]
            
            # Display rows found
            st.dataframe(display_con_df, use_container_width=True)
            st.caption(f"Showing {len(display_con_df)} of {len(consumption_filtered)} filtered ledger rows.")

    with tab2:
        # Main action button visible right away
        csv_gen = convert_df_to_csv(generation_filtered)
        st.download_button(
            label="📥 Export Filtered Generation Dataset (CSV)",
            data=csv_gen,
            file_name=f"energy_generation_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="download_btn_generation",
            use_container_width=True
        )

        # 🌟 IDEA 3: The Explanatory Dropdown (Collapsible Vault)
        with st.expander("🔍 Click to open Raw Generation Ledger Vault", expanded=False):
            st.markdown("### 🗄️ Internal Generation Ledger")
            st.write("This vault contains the exact rows pulled from `raw_energy_generation` based on your global sidebar filters.")
            
            # Local search filter inside the expander
            search_gen = st.text_input("🔌 Quick search by Energy Source Name:", key="search_gen_input")
            
            # Apply local search filter if text is typed
            display_gen_df = generation_filtered.sort_values('date', ascending=False)
            if search_gen:
                display_gen_df = display_gen_df[display_gen_df['source'].str.contains(search_gen, case=False, na=False)]
            
            # Display rows found
            st.dataframe(display_gen_df, use_container_width=True)
            st.caption(f"Showing {len(display_gen_df)} of {len(generation_filtered)} filtered ledger rows.")


# -------------------------------------------------------------
    # 🌟 PREMIUM TILE MAP: Mapbox Carto-Positron Integration
    # -------------------------------------------------------------
    st.markdown("---")
    st.subheader("🌍 Spatial Distribution (Interactive Tile Map)")
    
    # Lightweight GeoJSON containing European boundaries matched by ISO2 codes
    EUROPE_GEOJSON = "https://raw.githubusercontent.com/leakyMirror/map-of-europe/master/GeoJSON/europe.geojson"
    
    # 1. Map Controls Card
    map_col1, map_col2, map_col3 = st.columns([2, 2, 4])
    
    with map_col1:
        map_metric = st.radio(
            "Select Metric to Map:",
            options=["Energy Consumption", "Energy Generation"],
            horizontal=True,
            key="mapbox_metric"
        )
        
    with map_col2:
        map_years = selected_years if selected_years else available_years
        selected_map_year = st.selectbox("Select Map Year:", options=map_years, key="mapbox_year")

    # 2. Extract and Filter Map Data safely
    if map_metric == "Energy Consumption":
        map_df = consumption_df[consumption_df['date'] == selected_map_year]
        color_scale = "Blues"
        legend_title = "Consumption (KTOE)"
    else:
        map_df = generation_df[generation_df['date'] == selected_map_year]
        
        with map_col3:
            available_sources = ["All Sources"] + list(map_df['source'].unique())
            selected_map_source = st.selectbox("Filter Map by Energy Source:", options=available_sources, key="mapbox_source")
            
        if selected_map_source != "All Sources":
            map_df = map_df[map_df['source'] == selected_map_source]
            
        color_scale = "YlOrRd"
        legend_title = "Generation (KTOE)"

    # Aggregate using the raw country ISO codes ('country') while carrying over 'country_name' for tooltips
    map_plot_data = map_df.groupby(['country', 'country_name'])['energy'].sum().reset_index()

    # 3. Draw Plotly Mapbox Choropleth
    if not map_plot_data.empty:
        fig_map = px.choropleth_mapbox(
            map_plot_data,
            geojson=EUROPE_GEOJSON,
            locations="country",             # Links to your 2-letter codes (e.g. 'DE', 'FR')
            featureidkey="properties.ISO2",  # Points to matching keys in the GeoJSON file
            color="energy",
            color_continuous_scale=color_scale,
            labels={'energy': legend_title},
            hover_name="country_name",       # Displays full clean country names on hover!
            mapbox_style="carto-positron",   # 🌟 THE MAGIC: Beautiful minimalist base map!
            center={"lat": 51.0, "lon": 10.0}, # Center coordinates exactly over Europe
            zoom=3,                          # Perfect default zoom level for the EU
            opacity=0.7                      # Slight transparency so the underlying roads/cities show through
        )
        
        fig_map.update_layout(
            margin={"r":0,"t":10,"l":0,"b":0},
            height=600 # Slightly taller to give the beautiful map room to breathe
        )
        
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("No matching records found to display on the map for this selection.")