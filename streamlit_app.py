import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# Page configuration
st.set_page_config(page_title="Euro Energy Pipeline", layout="wide", initial_sidebar_state="expanded")

# Database connection
@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5433'),
        database=os.getenv('POSTGRES_DB', 'euro_energy'),
        user=os.getenv('POSTGRES_USER', 'energy_admin'),
        password=os.getenv('POSTGRES_PASSWORD', 'energy_pass')
    )

@st.cache_data(ttl=300)
def fetch_consumption_data():
    try:
        conn = get_connection()
        query = """
            SELECT country, date, energy, energy_type 
            FROM raw_energy_consumption 
            ORDER BY date DESC, country
        """
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"Error fetching consumption data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_generation_data():
    try:
        conn = get_connection()
        query = """
            SELECT country, date, energy, energy_type 
            FROM raw_energy_generation 
            ORDER BY date DESC, country, energy_type
        """
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"Error fetching generation data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_db_status():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM raw_energy_consumption")
        consumption_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM raw_energy_generation")
        generation_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT MAX(date) FROM raw_energy_consumption")
        latest_consumption = cursor.fetchone()[0]
        
        cursor.execute("SELECT MAX(date) FROM raw_energy_generation")
        latest_generation = cursor.fetchone()[0]
        
        cursor.close()
        
        return {
            'consumption_rows': consumption_count,
            'generation_rows': generation_count,
            'latest_consumption': latest_consumption,
            'latest_generation': latest_generation
        }
    except Exception as e:
        st.error(f"Error fetching DB status: {e}")
        return None

# Header
st.title("🌍 European Energy Pipeline Dashboard")
st.markdown("Real-time energy consumption and generation data from Eurostat")

# Sidebar
with st.sidebar:
    st.header("Dashboard Controls")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    
    # Database status
    status = get_db_status()
    if status:
        st.subheader("Database Status")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Consumption Rows", status['consumption_rows'])
            st.metric("Latest Year", status['latest_consumption'])
        with col2:
            st.metric("Generation Rows", status['generation_rows'])
            st.metric("Latest Year", status['latest_generation'])
    
    st.divider()
    st.markdown("**Data Source:** Eurostat API  \n**Updated:** Every hour")

# Main content
cons_df = fetch_consumption_data()
gen_df = fetch_generation_data()

if cons_df.empty or gen_df.empty:
    st.warning("⚠️ No data available. Please ensure the Airflow DAG has run successfully.")
else:
    # Get latest year
    latest_year = max(cons_df['date'].max(), gen_df['date'].max())
    
    # Filter to latest year
    cons_latest = cons_df[cons_df['date'] == latest_year]
    gen_latest = gen_df[gen_df['date'] == latest_year]
    
    # Metrics row
    st.subheader(f"📊 Energy Metrics - {latest_year}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_consumption = cons_latest['energy'].mean()
        st.metric("Avg Consumption", f"{avg_consumption:,.0f}", "ktoe")
    
    with col2:
        max_consumption = cons_latest['energy'].max()
        st.metric("Max Consumption", f"{max_consumption:,.0f}", "ktoe")
    
    with col3:
        min_consumption = cons_latest['energy'].min()
        st.metric("Min Consumption", f"{min_consumption:,.0f}", "ktoe")
    
    with col4:
        total_generation = gen_latest['energy'].sum()
        st.metric("Total Generation", f"{total_generation:,.0f}", "ktoe")
    
    st.divider()
    
    # Charts
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("🔴 Energy Consumption by Country")
        cons_chart = cons_latest.sort_values('energy', ascending=False)
        fig = px.bar(
            cons_chart,
            x='country',
            y='energy',
            color='energy',
            color_continuous_scale='Reds',
            labels={'energy': 'Energy (ktoe)', 'country': 'Country'},
            height=400
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col_right:
        st.subheader("⚡ Energy Generation by Type")
        gen_by_type = gen_latest.groupby('energy_type')['energy'].sum().sort_values(ascending=False)
        fig = px.pie(
            values=gen_by_type.values,
            names=gen_by_type.index,
            color_discrete_sequence=px.colors.qualitative.Set2,
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Generation by country
    st.subheader("🏭 Generation Mix by Country")
    
    countries = st.multiselect(
        "Select countries to compare:",
        sorted(gen_latest['country'].unique()),
        default=sorted(gen_latest['country'].unique())[:3]
    )
    
    if countries:
        gen_filtered = gen_latest[gen_latest['country'].isin(countries)]
        fig = px.bar(
            gen_filtered,
            x='country',
            y='energy',
            color='energy_type',
            barmode='stack',
            labels={'energy': 'Energy (ktoe)', 'country': 'Country', 'energy_type': 'Type'},
            height=400,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Data tables
    st.divider()
    
    tab1, tab2 = st.tabs(["📋 Consumption Data", "📋 Generation Data"])
    
    with tab1:
        st.dataframe(cons_latest.sort_values('energy', ascending=False), use_container_width=True)
    
    with tab2:
        st.dataframe(gen_latest.sort_values(['country', 'energy'], ascending=[True, False]), use_container_width=True)
    
    # Time series (if multiple years)
    if len(cons_df['date'].unique()) > 1:
        st.divider()
        st.subheader("📈 Historical Trends")
        
        selected_country = st.selectbox(
            "Select country for trend analysis:",
            sorted(cons_df['country'].unique())
        )
        
        cons_trend = cons_df[cons_df['country'] == selected_country].sort_values('date')
        gen_trend = gen_df[gen_df['country'] == selected_country].sort_values('date')
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.line(
                cons_trend,
                x='date',
                y='energy',
                title=f"Consumption Trend - {selected_country}",
                labels={'energy': 'Energy (ktoe)', 'date': 'Year'},
                height=400,
                markers=True
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            gen_by_year = gen_trend.groupby('date')['energy'].sum().reset_index()
            fig = px.line(
                gen_by_year,
                x='date',
                y='energy',
                title=f"Generation Trend - {selected_country}",
                labels={'energy': 'Energy (ktoe)', 'date': 'Year'},
                height=400,
                markers=True
            )
            st.plotly_chart(fig, use_container_width=True)
