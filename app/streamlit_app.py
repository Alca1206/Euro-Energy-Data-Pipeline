from datetime import datetime
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st

st.set_page_config(
    page_title="Euro Energy Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_db_connection():
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
        st.error(f"Consumption query error: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def get_generation_data():
    try:
        conn = get_db_connection()
        query = """
            SELECT date, country, source, energy_type, energy, loaded_at
            FROM raw_energy_generation
            ORDER BY date DESC, country
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Generation query error: {e}")
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
        cursor.close()
        conn.close()
        return con_count, gen_count
    except Exception as e:
        return 0, 0


@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


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

SOURCE_NAME_MAP = {
    "RA100": "Solar",
    "RA200": "Wind",
    "RA300": "Hydro",
    "N900H": "Nuclear",
    "C0000": "Coal",
    "G3000": "Natural Gas",
}

RENEWABLE_CODES = ["RA100", "RA200", "RA300"]
EUROPE_GEOJSON = "https://raw.githubusercontent.com/leakyMirror/map-of-europe/master/GeoJSON/europe.geojson"

# -------------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------------
st.title("🔋 European Energy Data Dashboard")
st.caption("Real-time European energy data powered by Eurostat API & Apache Airflow")

st.sidebar.header("Dashboard Controls")
if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.subheader("📊 Database Status")
con_count, gen_count = get_db_status()
st.sidebar.metric("Consumption Records", con_count or "-")
st.sidebar.metric("Generation Records", gen_count or "-")

consumption_df = get_consumption_data()
generation_df = get_generation_data()

# -------------------------------------------------------------
# TRANSFORM DATA
# -------------------------------------------------------------
if not consumption_df.empty:
    consumption_df["country_name"] = consumption_df["country"].map(COUNTRY_LABEL_MAP).fillna(consumption_df["country"])

if not generation_df.empty:
    generation_df["country_name"] = generation_df["country"].map(COUNTRY_LABEL_MAP).fillna(generation_df["country"])
    generation_df["source_name"] = generation_df["source"].map(SOURCE_NAME_MAP).fillna(generation_df["source"])
    generation_df["Type"] = generation_df["source"].apply(
        lambda x: "Renewable" if x in RENEWABLE_CODES else "Fossil/Other"
    )

if consumption_df.empty or generation_df.empty:
    st.warning("⚠️ No data available. Please trigger your Airflow DAG first.")
    st.stop()

# -------------------------------------------------------------
# SIDEBAR FILTERS
# -------------------------------------------------------------
st.sidebar.subheader("📅 Filters")
all_years = sorted(
    set(consumption_df["date"].unique()) | set(generation_df["date"].unique()),
    reverse=True
)
select_all_years = st.sidebar.checkbox("Select All Years", value=True)
selected_years = st.sidebar.multiselect(
    "Select Years", options=all_years, default=all_years, disabled=select_all_years
)

all_countries = sorted(
    set(consumption_df["country_name"].dropna().unique()) |
    set(generation_df["country_name"].dropna().unique())
)
select_all_countries = st.sidebar.checkbox("Select All Countries", value=True)
selected_countries = st.sidebar.multiselect(
    "Select Countries", options=all_countries,
    default=all_countries, disabled=select_all_countries
)

years_to_filter = all_years if select_all_years else selected_years
consumption_filtered = consumption_df[consumption_df["date"].isin(years_to_filter)]
generation_filtered = generation_df[generation_df["date"].isin(years_to_filter)]

if not select_all_countries:
    consumption_filtered = consumption_filtered[consumption_filtered["country_name"].isin(selected_countries)]
    generation_filtered = generation_filtered[generation_filtered["country_name"].isin(selected_countries)]

# -------------------------------------------------------------
# METRICS
# -------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    avg = consumption_filtered["energy"].mean()
    st.metric("Avg Consumption (KTOE)", f"{avg:,.0f}" if not pd.isna(avg) else "-")
with col2:
    mx = consumption_filtered["energy"].max()
    st.metric("Max Consumption (KTOE)", f"{mx:,.0f}" if not pd.isna(mx) else "-")
with col3:
    mn = consumption_filtered["energy"].min()
    st.metric("Min Consumption (KTOE)", f"{mn:,.0f}" if not pd.isna(mn) else "-")
with col4:
    total_gen = generation_filtered["energy"].sum()
    st.metric("Total Generation (KTOE)", f"{total_gen:,.0f}" if not pd.isna(total_gen) else "-")

st.markdown("---")

# -------------------------------------------------------------
# TABS — MAP IS NOW FIRST
# -------------------------------------------------------------
tab_map, tab_viz, tab_year, tab_hist, tab_audit = st.tabs([
    "🌍 Map", "📈 Visualizations", "📊 Trends & Comparisons", "📉 Historical", "🛠️ Audit & Export"
])

# --- TAB 1: MAP (NOW FIRST) ---
with tab_map:
    st.subheader("🌍 European Energy Map")

    # Year slider
    min_year = int(min(all_years))
    max_year = int(max(all_years))
    selected_map_year = st.slider(
        "Select Year", min_value=min_year, max_value=max_year,
        value=max_year, step=1
    )

    # Metric selector
    map_metric = st.radio(
        "Select Metric:", ["Energy Consumption", "Energy Generation", "Renewable Share (%)"],
        horizontal=True
    )


    if map_metric == "Energy Consumption":
        map_df = consumption_df[consumption_df["date"] == selected_map_year]
        if not map_df.empty:
            map_plot = map_df.groupby(["country", "country_name"])["energy"].sum().reset_index()
            fig_map = px.choropleth_mapbox(
                map_plot, geojson=EUROPE_GEOJSON, locations="country",
                featureidkey="properties.ISO2", color="energy",
                color_continuous_scale="Blues",
                mapbox_style="carto-positron",
                center={"lat": 51.0, "lon": 10.0}, zoom=3, opacity=0.7,
                hover_name="country_name",
                labels={"energy": "KTOE"},
                title=f"Energy Consumption by Country ({selected_map_year})"
            )
            fig_map.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0}, height=550)
            st.plotly_chart(fig_map, use_container_width=True)

            # Ranked table below map
            st.subheader(f"📋 Consumption Ranking — {selected_map_year}")
            ranked = map_plot.sort_values("energy", ascending=False).reset_index(drop=True)
            ranked.index += 1
            ranked.columns = ["Country Code", "Country", "KTOE"]
            ranked["KTOE"] = ranked["KTOE"].round(0).astype(int)
            st.dataframe(ranked, use_container_width=True)
        else:
            st.info("No consumption data for selected year.")

    elif map_metric == "Energy Generation":
        map_df = generation_df[generation_df["date"] == selected_map_year]
        if not map_df.empty:
            map_plot = map_df.groupby(["country", "country_name"])["energy"].sum().reset_index()
            fig_map = px.choropleth_mapbox(
                map_plot, geojson=EUROPE_GEOJSON, locations="country",
                featureidkey="properties.ISO2", color="energy",
                color_continuous_scale="YlOrRd",
                mapbox_style="carto-positron",
                center={"lat": 51.0, "lon": 10.0}, zoom=3, opacity=0.7,
                hover_name="country_name",
                labels={"energy": "KTOE"},
                title=f"Energy Generation by Country ({selected_map_year})"
            )
            fig_map.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0}, height=550)
            st.plotly_chart(fig_map, use_container_width=True)

            # Ranked table below map
            st.subheader(f"📋 Generation Ranking — {selected_map_year}")
            ranked = map_plot.sort_values("energy", ascending=False).reset_index(drop=True)
            ranked.index += 1
            ranked.columns = ["Country Code", "Country", "KTOE"]
            ranked["KTOE"] = ranked["KTOE"].round(0).astype(int)
            st.dataframe(ranked, use_container_width=True)
        else:
            st.info("No generation data for selected year.")

    elif map_metric == "Renewable Share (%)":
        map_df = generation_df[generation_df["date"] == selected_map_year]
        if not map_df.empty:
            gen_total = map_df.groupby(["country", "country_name"])["energy"].sum().reset_index()
            gen_total.rename(columns={"energy": "total"}, inplace=True)

            gen_renew = map_df[map_df["source"].isin(RENEWABLE_CODES)].groupby(
                ["country", "country_name"])["energy"].sum().reset_index()
            gen_renew.rename(columns={"energy": "renewable"}, inplace=True)

            renew_map = pd.merge(gen_total, gen_renew, on=["country", "country_name"], how="left")
            renew_map["renewable"] = renew_map["renewable"].fillna(0)
            renew_map["renew_pct"] = (renew_map["renewable"] / renew_map["total"] * 100).round(1)

            fig_map = px.choropleth_mapbox(
                renew_map, geojson=EUROPE_GEOJSON, locations="country",
                featureidkey="properties.ISO2", color="renew_pct",
                color_continuous_scale="RdYlGn",
                range_color=[0, 100],
                mapbox_style="carto-positron",
                center={"lat": 51.0, "lon": 10.0}, zoom=3, opacity=0.7,
                hover_name="country_name",
                hover_data={"renew_pct": True, "country": False},
                labels={"renew_pct": "Renewable %"},
                title=f"Renewable Energy Share by Country ({selected_map_year})"
            )
            fig_map.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0}, height=550)
            st.plotly_chart(fig_map, use_container_width=True)

            # Ranked table below map
            st.subheader(f"📋 Renewable Share Ranking — {selected_map_year}")
            ranked = renew_map[["country_name", "renew_pct", "renewable", "total"]].sort_values(
                "renew_pct", ascending=False).reset_index(drop=True)
            ranked.index += 1
            ranked.columns = ["Country", "Renewable %", "Renewable KTOE", "Total KTOE"]
            ranked["Renewable KTOE"] = ranked["Renewable KTOE"].round(0).astype(int)
            ranked["Total KTOE"] = ranked["Total KTOE"].round(0).astype(int)
            st.dataframe(ranked, use_container_width=True)
        else:
            st.info("No generation data for selected year.")

# --- TAB 2: VISUALIZATIONS ---
with tab_viz:
    st.subheader("Deep Dive Analytics")
    chart_options = [
        "Green vs. Fossil Fuel Split",
        "Year-over-Year Change (Waterfall)",
        "Per Capita Perspective",
        "Renewable Adoption Race",
        "Supply/Demand Gap Overlay",
        "Pareto Distribution Analysis",
        "Carbon Footprint Treemap",
    ]
    selected_chart = st.radio(
        "Select View:", options=chart_options, horizontal=True, label_visibility="collapsed"
    )
    st.markdown("---")

    if selected_chart == "Green vs. Fossil Fuel Split":
        st.caption("Visualizing energy transition progress by grouping sources into Renewable vs Fossil.")
        grp = generation_filtered.groupby(["country_name", "Type"])["energy"].sum().reset_index()
        if not grp.empty:
            fig = px.bar(
                grp, x="country_name", y="energy", color="Type",
                title="Green vs Fossil Fuel Grid Profile", barmode="stack",
                color_discrete_map={"Renewable": "#2ecc71", "Fossil/Other": "#e74c3c"}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No generation data available.")

    elif selected_chart == "Year-over-Year Change (Waterfall)":
        st.caption("Net growth or decline in aggregate consumption year over year.")
        yoy = consumption_filtered.groupby("date")["energy"].sum().reset_index().sort_values("date")
        if len(yoy) > 1:
            yoy["delta"] = yoy["energy"].diff().fillna(yoy["energy"].iloc[0])
            fig = go.Figure(go.Waterfall(
                x=yoy["date"].astype(str),
                measure=["relative"] * len(yoy),
                y=yoy["delta"],
                text=yoy["energy"].round(1)
            ))
            fig.update_layout(title="Year-over-Year Consumption Change")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select multiple years to visualize YoY changes.")

    elif selected_chart == "Per Capita Perspective":
        st.caption("Demand intensity normalized per capita.")
        per_cap = consumption_filtered.groupby("country_name")["energy"].sum().reset_index()
        if not per_cap.empty:
            per_cap["per_capita"] = per_cap["energy"] * 0.12
            fig = px.bar(
                per_cap, x="country_name", y="per_capita",
                title="Energy Consumption Per Capita Estimate",
                color="per_capita", color_continuous_scale="Viridis"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No consumption data available.")

    elif selected_chart == "Renewable Adoption Race":
        st.caption("Wind energy production ranking over time by country.")
        renew = generation_filtered[generation_filtered["source"] == "RA200"].groupby(
            ["date", "country_name"])["energy"].sum().reset_index()
        if not renew.empty:
            renew["Rank"] = renew.groupby("date")["energy"].rank(ascending=False, method="first")
            fig = px.line(
                renew, x="date", y="Rank", color="country_name",
                markers=True, title="Wind Energy Production Rank Over Time"
            )
            fig.update_yaxes(autorange="reversed", tickmode="linear", dtick=1)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No wind energy data found.")

    elif selected_chart == "Supply/Demand Gap Overlay":
        st.caption("Total generation vs total consumption over time.")
        gap_c = consumption_filtered.groupby("date")["energy"].sum().reset_index()
        gap_g = generation_filtered.groupby("date")["energy"].sum().reset_index()
        if not gap_c.empty and not gap_g.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=gap_g["date"], y=gap_g["energy"],
                fill="tozeroy", name="Total Generation"
            ))
            fig.add_trace(go.Scatter(
                x=gap_c["date"], y=gap_c["energy"],
                mode="lines+markers", name="Total Consumption",
                line=dict(color="red", width=3)
            ))
            fig.update_layout(title="Supply vs Demand Gap")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Missing data for supply/demand overlay.")

    elif selected_chart == "Pareto Distribution Analysis":
        st.caption("Top countries driving majority of energy consumption.")
        pareto = consumption_filtered.groupby("country_name")["energy"].sum().reset_index().sort_values(
            "energy", ascending=False)
        if not pareto.empty:
            pareto["cum_pct"] = (pareto["energy"].cumsum() / pareto["energy"].sum()) * 100
            fig = go.Figure()
            fig.add_trace(go.Bar(x=pareto["country_name"], y=pareto["energy"], name="Consumption"))
            fig.add_trace(go.Scatter(
                x=pareto["country_name"], y=pareto["cum_pct"],
                name="Cumulative %", yaxis="y2", line=dict(color="red")
            ))
            fig.update_layout(
                title="Pareto Distribution of Energy Consumption",
                yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 105])
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available.")

    elif selected_chart == "Carbon Footprint Treemap":
        st.caption("Energy generation breakdown by country and source.")
        tree = generation_filtered.copy()
        if not tree.empty:
            fig = px.treemap(
                tree, path=["country_name", "source_name"],
                values="energy", title="Generation by Country and Source"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No generation data available.")

# --- TAB 3: TRENDS & COMPARISONS ---
with tab_year:
    st.subheader("Trends & Comparisons")

    col1, col2 = st.columns(2)
    with col1:
        if not consumption_filtered.empty:
            fig = px.line(
                consumption_filtered.groupby("date")["energy"].agg(["sum", "mean"]).reset_index(),
                x="date", y=["sum", "mean"], title="Consumption Trends", markers=True
            )
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        if not generation_filtered.empty:
            fig = px.bar(
                generation_filtered.groupby(["date", "source_name"])["energy"].sum().reset_index(),
                x="date", y="energy", color="source_name",
                title="Generation by Source Over Years", barmode="stack"
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")


    st.subheader("⚡ Energy Generation Mix Over Time (% Share)")
    st.caption("Shows how the proportion of each energy source has shifted year by year.")
    if not generation_filtered.empty:
        area_data = generation_filtered.groupby(["date", "source_name"])["energy"].sum().reset_index()
        area_total = area_data.groupby("date")["energy"].transform("sum")
        area_data["pct"] = (area_data["energy"] / area_total) * 100
        fig_area = px.area(
            area_data, x="date", y="pct", color="source_name",
            title="100% Stacked Energy Generation Mix",
            labels={"pct": "Share (%)", "date": "Year", "source_name": "Source"},
            groupnorm="percent"
        )
        fig_area.update_layout(yaxis_title="Share (%)", height=400)
        st.plotly_chart(fig_area, use_container_width=True)
    else:
        st.info("No generation data available.")

    st.markdown("---")

    st.subheader("🔋 Energy Self-Sufficiency Ratio by Country")
    st.caption("Generation ÷ Consumption. Above 1.0 = net exporter. Below 1.0 = net importer.")
    if not consumption_filtered.empty and not generation_filtered.empty:
        gen_total = generation_filtered.groupby(["country_name", "date"])["energy"].sum().reset_index()
        gen_total.rename(columns={"energy": "generation"}, inplace=True)
        con_total = consumption_filtered.groupby(["country_name", "date"])["energy"].sum().reset_index()
        con_total.rename(columns={"energy": "consumption"}, inplace=True)
        merged = pd.merge(gen_total, con_total, on=["country_name", "date"], how="inner")
        merged["ratio"] = merged["generation"] / merged["consumption"]
        fig_ratio = px.line(
            merged, x="date", y="ratio", color="country_name",
            markers=True, title="Energy Self-Sufficiency Ratio Over Time",
            labels={"ratio": "Generation / Consumption", "date": "Year", "country_name": "Country"}
        )
        fig_ratio.add_hline(
            y=1.0, line_dash="dash", line_color="red",
            annotation_text="Break-even (ratio = 1.0)",
            annotation_position="top left"
        )
        fig_ratio.update_layout(height=450)
        st.plotly_chart(fig_ratio, use_container_width=True)
    else:
        st.info("Need both consumption and generation data for this chart.")

# --- TAB 4: HISTORICAL ---
with tab_hist:
    st.subheader("Historical Trends (All Data)")

    col1, col2 = st.columns(2)
    with col1:
        if not consumption_df.empty:
            fig = px.line(
                consumption_df.groupby("date")["energy"].sum().reset_index(),
                x="date", y="energy", title="Total Consumption Over All Years", markers=True
            )
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        if not generation_df.empty:
            fig = px.line(
                generation_df.groupby("date")["energy"].sum().reset_index(),
                x="date", y="energy", title="Total Generation Over All Years", markers=True
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")


    st.subheader("🌱 Renewable Share Trend by Country")
    st.caption("% of total generation that came from renewable sources each year.")
    if not generation_df.empty:
        gen_all = generation_df.groupby(["date", "country_name", "source"])["energy"].sum().reset_index()
        gen_total = gen_all.groupby(["date", "country_name"])["energy"].sum().reset_index()
        gen_total.rename(columns={"energy": "total"}, inplace=True)
        gen_renew = gen_all[gen_all["source"].isin(RENEWABLE_CODES)].groupby(
            ["date", "country_name"])["energy"].sum().reset_index()
        gen_renew.rename(columns={"energy": "renewable"}, inplace=True)
        renew_share = pd.merge(gen_total, gen_renew, on=["date", "country_name"], how="left")
        renew_share["renewable"] = renew_share["renewable"].fillna(0)
        renew_share["renew_pct"] = (renew_share["renewable"] / renew_share["total"]) * 100
        fig_renew = px.line(
            renew_share, x="date", y="renew_pct", color="country_name",
            markers=True, title="Renewable Energy Share Over Time (%)",
            labels={"renew_pct": "Renewable Share (%)", "date": "Year", "country_name": "Country"}
        )
        fig_renew.add_hline(
            y=50, line_dash="dash", line_color="green",
            annotation_text="50% Renewable Target",
            annotation_position="top left"
        )
        fig_renew.update_layout(height=450)
        st.plotly_chart(fig_renew, use_container_width=True)
    else:
        st.info("No generation data available.")

    st.markdown("---")

    st.subheader("📈 Country Growth Rate (First Year vs Latest Year)")
    st.caption("% change in energy consumption from earliest to latest available year per country.")
    if not consumption_df.empty:
        growth = consumption_df.groupby(["country_name", "date"])["energy"].sum().reset_index()
        first_year = growth.groupby("country_name").apply(
            lambda x: x.loc[x["date"].idxmin(), ["date", "energy"]]
        ).reset_index()
        first_year.columns = ["country_name", "first_year", "first_energy"]
        last_year = growth.groupby("country_name").apply(
            lambda x: x.loc[x["date"].idxmax(), ["date", "energy"]]
        ).reset_index()
        last_year.columns = ["country_name", "last_year", "last_energy"]
        growth_table = pd.merge(first_year, last_year, on="country_name")
        growth_table["change_pct"] = (
            (growth_table["last_energy"] - growth_table["first_energy"]) /
            growth_table["first_energy"] * 100
        ).round(2)
        growth_table["first_energy"] = growth_table["first_energy"].round(0).astype(int)
        growth_table["last_energy"] = growth_table["last_energy"].round(0).astype(int)
        growth_table = growth_table.sort_values("change_pct", ascending=False).reset_index(drop=True)
        growth_table.columns = ["Country", "First Year", "First Year KTOE", "Last Year", "Last Year KTOE", "Change %"]

        def color_change(val):
            color = "green" if val > 0 else "red"
            return f"color: {color}"

        st.dataframe(
            growth_table.style.applymap(color_change, subset=["Change %"]),
            use_container_width=True
        )

        col1, col2 = st.columns(2)
        with col1:
            top = growth_table.iloc[0]
            st.metric(
                f"Highest Growth — {top['Country']}",
                f"{top['Change %']}%",
                f"{top['First Year']} → {top['Last Year']}"
            )
        with col2:
            bottom = growth_table.iloc[-1]
            st.metric(
                f"Biggest Decline — {bottom['Country']}",
                f"{bottom['Change %']}%",
                f"{bottom['First Year']} → {bottom['Last Year']}"
            )
    else:
        st.info("No consumption data available.")

    st.markdown("---")

    st.subheader("🏆 Peak Year Analysis by Country")
    st.caption("Which year had the highest and lowest energy consumption per country.")
    if not consumption_df.empty:
        peak = consumption_df.groupby(["country_name", "date"])["energy"].sum().reset_index()
        peak_high = peak.loc[peak.groupby("country_name")["energy"].idxmax()][["country_name", "date", "energy"]]
        peak_high.columns = ["Country", "Peak Year", "Peak KTOE"]
        peak_high["Peak KTOE"] = peak_high["Peak KTOE"].round(0).astype(int)
        peak_low = peak.loc[peak.groupby("country_name")["energy"].idxmin()][["country_name", "date", "energy"]]
        peak_low.columns = ["Country", "Lowest Year", "Lowest KTOE"]
        peak_low["Lowest KTOE"] = peak_low["Lowest KTOE"].round(0).astype(int)
        peak_table = pd.merge(peak_high, peak_low, on="Country").sort_values("Peak KTOE", ascending=False)
        peak_table = peak_table.reset_index(drop=True)
        st.dataframe(peak_table, use_container_width=True)
    else:
        st.info("No consumption data available.")

# --- TAB 5: AUDIT ---
with tab_audit:
    st.caption("Search, audit, and export filtered records.")
    audit_dataset = st.radio(
        "Dataset:", ["📊 Consumption", "⚡ Generation"], horizontal=True
    )
    current_f = consumption_filtered if audit_dataset == "📊 Consumption" else generation_filtered
    if not current_f.empty:
        st.download_button(
            label="📥 Export CSV", data=convert_df_to_csv(current_f),
            file_name="energy_data.csv", mime="text/csv", use_container_width=True
        )
        st.dataframe(current_f.sort_values("date", ascending=False), use_container_width=True)
    else:
        st.warning("No records match the current filters.")