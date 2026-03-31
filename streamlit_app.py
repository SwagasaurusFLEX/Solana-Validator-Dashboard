import streamlit as st
from google.cloud import bigquery
import pandas as pd
import plotly.express as px
from google.oauth2 import service_account

st.set_page_config(page_title="Solana Validator Economics", layout="wide")

st.title("Are validator economics a threat to Solana's decentralization?")
st.markdown(
    "Analyzing on-chain reward data to determine whether Solana validator "
    "economics are sustainable, and how it affects decentralization. "
    "What happens when Solana becomes too centralized — and how do we go back?"
)

credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials, project="zoomcamp-test-2")

# Get current SOL price
price_query = """
    SELECT sol_price_usd FROM `zoomcamp-test-2.solana_validator_economics.raw_sol_price`
    ORDER BY date DESC LIMIT 1
"""
current_sol_price = client.query(price_query).to_dataframe().iloc[0]["sol_price_usd"]

# --- Scorecards ---
st.header("Network snapshot")

stats_query = """
    SELECT
        COUNT(DISTINCT pubkey) as total_validators,
        SUM(CASE WHEN avg_daily_reward_sol >= 1.1 THEN 1 ELSE 0 END) as profitable_validators,
        SUM(CASE WHEN avg_daily_reward_sol < 1.1 THEN 1 ELSE 0 END) as underwater_validators,
        ROUND(AVG(avg_daily_reward_sol), 4) as network_avg_daily_sol
    FROM `zoomcamp-test-2.solana_validator_economics.fct_validator_profitability`
"""
stats = client.query(stats_query).to_dataframe().iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total validators", f"{int(stats['total_validators']):,}")
col2.metric("Profitable (cover vote costs)", f"{int(stats['profitable_validators']):,}")
col3.metric("Underwater", f"{int(stats['underwater_validators']):,}")
col4.metric("SOL price", f"${float(current_sol_price):,.2f}")

# --- Tile 1: Validator Profit/Loss Distribution ---
st.header("Validator profit & loss distribution")
st.markdown("Validators ranked by daily net SOL after voting costs. Most validators earn less than the 1.1 SOL/day required to participate in consensus.")

dist_query = """
    SELECT net_daily_sol_after_votes,
           ROW_NUMBER() OVER (ORDER BY net_daily_sol_after_votes DESC) as validator_rank
    FROM `zoomcamp-test-2.solana_validator_economics.fct_validator_profitability`
    ORDER BY net_daily_sol_after_votes DESC
"""
dist_df = client.query(dist_query).to_dataframe()
dist_df["net_daily_sol_after_votes"] = dist_df["net_daily_sol_after_votes"].astype(float)

fig = px.line(dist_df, x="validator_rank", y="net_daily_sol_after_votes",
              labels={"validator_rank": "Validators (ranked best to worst)",
                      "net_daily_sol_after_votes": "Net daily SOL (after voting costs)"})
fig.add_hline(y=0, line_dash="solid", line_color="white", line_width=2)
fig.add_hrect(y0=0, y1=20, fillcolor="#1D9E75", opacity=0.08, line_width=0)
fig.add_hrect(y0=-2, y1=0, fillcolor="#E24B4A", opacity=0.08, line_width=0)
fig.update_yaxes(range=[-2, 20], title="Net daily SOL")
fig.update_xaxes(range=[0, 900], title="Validators (ranked best to worst)")
fig.update_layout(margin=dict(t=20, b=20), height=450)
st.plotly_chart(fig, use_container_width=True)

# --- Tile 2: What If Voting Costs Change? ---
st.header("What if voting costs change?")
st.markdown(
    "Solana's upcoming **Alpenglow upgrade** could eliminate voting costs entirely. "
    "Drag the slider to see how many validators become profitable."
)

vote_cost = st.slider("Daily voting cost (SOL)", min_value=0.0, max_value=1.1, value=1.1, step=0.1)

sim_query = """
    SELECT avg_daily_reward_sol
    FROM `zoomcamp-test-2.solana_validator_economics.fct_validator_profitability`
"""
sim_df = client.query(sim_query).to_dataframe()

sim_df["avg_daily_reward_sol"] = sim_df["avg_daily_reward_sol"].astype(float)
sim_df["net_sol"] = sim_df["avg_daily_reward_sol"] - vote_cost
profitable_count = int((sim_df["net_sol"] > 0).sum())
underwater_count = int((sim_df["net_sol"] <= 0).sum())
total = profitable_count + underwater_count
profitable_pct = round(profitable_count / total * 100, 1)

col1, col2, col3 = st.columns(3)
col1.metric("Profitable", f"{profitable_count:,}", f"{profitable_pct}%")
col2.metric("Underwater", f"{underwater_count:,}")
col3.metric("Daily vote cost", f"{vote_cost} SOL", f"${vote_cost * float(current_sol_price):,.0f}/day" if vote_cost > 0 else "$0/day")

# --- Tile 3: Nakamoto Coefficient Over Time ---
st.header("Nakamoto coefficient over time")
st.markdown(
    "The minimum number of validators needed to control 33% of rewards. "
    "Higher = more decentralized. Below 20 is concerning. "
    "Solana is currently more centralized than it has been in years."
)

nakamoto_query = """
    SELECT reward_date, nakamoto_coefficient, total_validators
    FROM `zoomcamp-test-2.solana_validator_economics.fct_reward_concentration`
    WHERE total_validators < 10000
    ORDER BY reward_date
"""
nakamoto_df = client.query(nakamoto_query).to_dataframe()

fig2 = px.line(nakamoto_df, x="reward_date", y="nakamoto_coefficient",
               labels={"reward_date": "Date", "nakamoto_coefficient": "Nakamoto coefficient"})
fig2.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="Concerning threshold")
fig2.update_layout(margin=dict(t=20, b=20), height=350)
st.plotly_chart(fig2, use_container_width=True)

# --- Tile 4: Reward Concentration ---
st.header("Reward concentration")
st.markdown("What percentage of total rewards go to the top validators?")

concentration_query = """
    SELECT reward_date,
           ROUND(pct_rewards_top_10, 1) as top_10,
           ROUND(pct_rewards_top_50, 1) as top_50,
           ROUND(pct_rewards_top_100, 1) as top_100
    FROM `zoomcamp-test-2.solana_validator_economics.fct_reward_concentration`
    WHERE total_validators < 10000
    ORDER BY reward_date
"""
conc_df = client.query(concentration_query).to_dataframe()

fig3 = px.line(conc_df, x="reward_date", y=["top_10", "top_50", "top_100"],
               labels={"reward_date": "Date", "value": "% of total rewards", "variable": "Group"})
fig3.update_layout(margin=dict(t=20, b=20), height=350, legend_title_text="Validator group")
st.plotly_chart(fig3, use_container_width=True)

# --- Tile 5: Active Validators Over Time ---
st.header("Active validator count")
st.markdown("Number of unique validators earning rewards per day.")

active_query = """
    SELECT reward_date, active_validators
    FROM `zoomcamp-test-2.solana_validator_economics.int_daily_network_stats`
    WHERE active_validators < 10000
    ORDER BY reward_date
"""
active_df = client.query(active_query).to_dataframe()

fig4 = px.line(active_df, x="reward_date", y="active_validators",
               labels={"reward_date": "Date", "active_validators": "Active validators"})
fig4.update_layout(margin=dict(t=20, b=20), height=350)
st.plotly_chart(fig4, use_container_width=True)

# --- Key Findings ---
st.header("Key findings")
st.markdown(f"""
- **Over half of validators are underwater** — {int(stats['underwater_validators'])} out of {int(stats['total_validators'])} don't earn enough SOL to cover the 1.1 SOL/day voting cost.
- **Only ~750 active validators remain**, down from ~2,500 in 2023 — a 68% decline.
- **Solana is more centralized than it has been in years.** The Nakamoto coefficient sits at 15-19, meaning fewer than 20 validators could collude to control a third of the network.
- **Reward concentration is high** — the top 100 validators capture over 70% of all rewards, leaving 650+ validators to share the remaining 27%.
- **At current SOL price (${float(current_sol_price):,.2f})**, voting alone costs ~${1.1 * float(current_sol_price):,.0f}/day before hardware expenses.
- **The upcoming Alpenglow upgrade** could change this by moving voting off-chain, eliminating the ~1.1 SOL/day voting cost that makes small validators unprofitable.
""")
