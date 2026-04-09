import streamlit as st
from google.cloud import bigquery
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.oauth2 import service_account
import datetime

st.set_page_config(page_title="Solana Validator Economics", layout="wide")

st.title("Are validator economics a threat to Solana's decentralization?")
st.markdown(
    "Analyzing on-chain data to show how unsustainable validator economics "
    "drove centralization, concentrated block production, and handed control "
    "of transaction ordering to a single MEV infrastructure — Jito. "
)

credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials, project="zoomcamp-test-2")

# ── Solana color palette ──
SOL_PURPLE = "#9945FF"
SOL_DARK_PURPLE = "#7962E7"
SOL_CYAN = "#00D1FF"
SOL_TEAL = "#00BCD4"
SOL_GREEN = "#14F195"
SOL_RED = "#FF6B6B"
SOL_AMBER = "#F59E0B"

group_colors = {
    "Top 10": SOL_PURPLE,
    "Top 11-20": SOL_DARK_PURPLE,
    "Top 21-50": SOL_CYAN,
    "Top 51-100": SOL_TEAL,
    "Remaining 673": SOL_GREEN,
}

price_query = """
    SELECT sol_price_usd FROM `zoomcamp-test-2.solana_validator_economics.raw_sol_price`
    ORDER BY date DESC LIMIT 1
"""
current_sol_price = float(client.query(price_query).to_dataframe().iloc[0]["sol_price_usd"])

# ============================================================
# SECTION 1: VALIDATOR ECONOMICS
# ============================================================
econ_stats_query = """
    WITH block_fees AS (
        SELECT pubkey, daily_block_fees
        FROM `zoomcamp-test-2.solana_validator_economics.validator_daily_block_fees`
    ),
    voting_rewards AS (
        SELECT pubkey, daily_voting_rewards
        FROM `zoomcamp-test-2.solana_validator_economics.validator_daily_voting_rewards`
    ),
    mev_rewards AS (
        SELECT vote_account, ROUND(SUM(mev_rewards_sol) / 4 / 2.5, 4) as daily_mev
        FROM `zoomcamp-test-2.solana_validator_economics.raw_jito_mev`
        WHERE epoch < 950
        GROUP BY vote_account
    )
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN (COALESCE(v.daily_voting_rewards, 0) + COALESCE(b.daily_block_fees, 0) + COALESCE(m.daily_mev, 0)) >= 1.1 THEN 1 ELSE 0 END) as profitable,
        SUM(CASE WHEN (COALESCE(v.daily_voting_rewards, 0) + COALESCE(b.daily_block_fees, 0) + COALESCE(m.daily_mev, 0)) < 1.1 THEN 1 ELSE 0 END) as underwater
    FROM `zoomcamp-test-2.solana_validator_economics.raw_validator_snapshots` s
    LEFT JOIN voting_rewards v ON s.vote_pubkey = v.pubkey
    LEFT JOIN block_fees b ON s.node_pubkey = b.pubkey
    LEFT JOIN mev_rewards m ON s.vote_pubkey = m.vote_account
    WHERE s.snapshot_date = '2026-04-02' AND s.status = 'current'
"""
econ_stats = client.query(econ_stats_query).to_dataframe().iloc[0]

st.header("1. Validator economics are unsustainable")
st.markdown(
    "Solana went from 5,400 validators in October 2024 to under 800 today — an 85% collapse. "
    f"Validators must pay ~1.1 SOL/day (${1.1 * current_sol_price:,.0f}/day) in voting fees just to participate. "
    "Thousands of validators couldn't cover the cost and shut down. "
    f"Of the {int(econ_stats['total'])} that remain, {int(econ_stats['underwater'])} are still underwater while profits concentrate at the top."
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total validators", f"{int(econ_stats['total']):,}")
col2.metric("Profitable", f"{int(econ_stats['profitable']):,}")
col3.metric("Underwater", f"{int(econ_stats['underwater']):,}")
col4.metric("SOL price", f"${current_sol_price:,.2f}")

dist_query = """
    WITH block_fees AS (
        SELECT pubkey, daily_block_fees
        FROM `zoomcamp-test-2.solana_validator_economics.validator_daily_block_fees`
    ),
    voting_rewards AS (
        SELECT pubkey, daily_voting_rewards
        FROM `zoomcamp-test-2.solana_validator_economics.validator_daily_voting_rewards`
    ),
    mev_rewards AS (
        SELECT vote_account, ROUND(SUM(mev_rewards_sol) / 4 / 2.5, 4) as daily_mev
        FROM `zoomcamp-test-2.solana_validator_economics.raw_jito_mev`
        WHERE epoch < 950
        GROUP BY vote_account
    )
    SELECT 
        (COALESCE(v.daily_voting_rewards, 0) + COALESCE(b.daily_block_fees, 0) + COALESCE(m.daily_mev, 0) - 1.1) as net_daily_sol,
        ROW_NUMBER() OVER (ORDER BY (COALESCE(v.daily_voting_rewards, 0) + COALESCE(b.daily_block_fees, 0) + COALESCE(m.daily_mev, 0)) DESC) as rank
    FROM `zoomcamp-test-2.solana_validator_economics.raw_validator_snapshots` s
    LEFT JOIN voting_rewards v ON s.vote_pubkey = v.pubkey
    LEFT JOIN block_fees b ON s.node_pubkey = b.pubkey
    LEFT JOIN mev_rewards m ON s.vote_pubkey = m.vote_account
    WHERE s.snapshot_date = '2026-04-02' AND s.status = 'current'
    ORDER BY net_daily_sol DESC
"""
dist_df = client.query(dist_query).to_dataframe()
dist_df["net_daily_sol"] = dist_df["net_daily_sol"].astype(float)

import numpy as np

dist_df = client.query(dist_query).to_dataframe()
dist_df["net_daily_sol"] = dist_df["net_daily_sol"].astype(float)

# Split data for shading
dist_df["positive"] = dist_df["net_daily_sol"].clip(lower=0)

fig = go.Figure()

# Main line
fig.add_trace(go.Scatter(
    x=dist_df["rank"],
    y=dist_df["net_daily_sol"],
    mode="lines",
    line=dict(color=SOL_PURPLE, width=2),
    name="Net Daily SOL"
))

# ✅ Green shaded area ONLY under profitable portion
fig.add_trace(go.Scatter(
    x=dist_df["rank"],
    y=dist_df["positive"],
    fill='tozeroy',
    mode='none',
    fillcolor='rgba(20, 241, 149, 0.15)',  # soft green
    name="Profitable Zone"
))

# Zero line
fig.add_hline(y=0, line_dash="solid", line_color="white", line_width=2)

# Axis limits
fig.update_yaxes(range=[-5, 45], title="Net daily SOL")
fig.update_xaxes(range=[-8, 800], title="Validators (ranked best to worst)")

# ✅ Axis break marker — LOCKED to y-axis
fig.add_annotation(
    x=-7,  # aligns to y-axis
    y=45,  # where the cutoff is
    xref="x",
    yref="y",
    text="//",
    showarrow=False,
    font=dict(size=16, color="white"),
    xanchor="right",  # pushes it ONTO the axis line
    yanchor="middle"
)

# Optional: label for clipped values
fig.add_annotation(
    x=700,
    y=40,
    text="Top validators earn 500+ SOL/day",
    showarrow=False,
    font=dict(size=11, color="gray")
)

fig.update_layout(
    margin=dict(t=20, b=20),
    height=400
)

st.plotly_chart(fig, use_container_width=True)

st.markdown(
    f"**Just 98 validators (12%) earn over 500 SOL/day.** "
    f"The remaining 675 average under 14 SOL/day — and {int(econ_stats['underwater'])} of those lose money after voting costs."
)

# Alpenglow slider
st.subheader("What if voting costs change?")
st.markdown("The upcoming **Alpenglow upgrade** could eliminate voting costs.")

vote_cost = st.slider("Daily voting cost (SOL)", min_value=0.0, max_value=1.1, value=1.1, step=0.1)

sim_df = dist_df.copy()
sim_df["adjusted_net"] = sim_df["net_daily_sol"] + 1.1 - vote_cost
profitable_count = int((sim_df["adjusted_net"] > 0).sum())
underwater_count = int((sim_df["adjusted_net"] <= 0).sum())
total_count = profitable_count + underwater_count
profitable_pct = round(profitable_count / total_count * 100, 1)

col1, col2, col3 = st.columns(3)
col1.metric("Profitable", f"{profitable_count:,}", f"{profitable_pct}%")
col2.metric("Underwater", f"{underwater_count:,}")
col3.metric("Daily vote cost", f"{vote_cost} SOL", f"${vote_cost * current_sol_price:,.0f}/day" if vote_cost > 0 else "$0/day")

# ============================================================
# SECTION 2: DECENTRALIZATION IS DECLINING
# ============================================================
st.header("2. Decentralization is declining")
st.markdown(
    "When validators can't afford to operate, they shut down. "
    "The network is losing validators at an alarming rate."
)

st.subheader("Active validator count (2024 - present)")

hist_val_query = """
    SELECT day, validators
    FROM `zoomcamp-test-2.solana_validator_economics.historical_validator_count`
    ORDER BY day
"""
hist_val_df = client.query(hist_val_query).to_dataframe()

fig_hist = px.area(hist_val_df, x="day", y="validators",
                   labels={"day": "Date", "validators": "Active validators"})
fig_hist.update_traces(line_color=SOL_GREEN, fillcolor="rgba(20,241,149,0.15)")
fig_hist.update_layout(margin=dict(t=20, b=20), height=400)
st.plotly_chart(fig_hist, use_container_width=True)

st.markdown("**From 5,400 validators in October 2024 to under 800 today — an 85% decline.** "
            "The crash accelerated as memecoin trading volume dried up and MEV revenue collapsed, "
            "leaving thousands of validators unable to cover the 1.1 SOL/day voting cost.")

st.subheader("Nakamoto coefficient")
st.markdown(
    "The minimum number of validators needed to control 33% of rewards. "
    "Lower = more centralized. Below 20 is concerning."
)

nakamoto_query = """
    SELECT reward_date, nakamoto_coefficient, total_validators
    FROM `zoomcamp-test-2.solana_validator_economics.fct_reward_concentration`
    WHERE total_validators < 10000
    ORDER BY reward_date
"""
nakamoto_df = client.query(nakamoto_query).to_dataframe()

fig_nak = px.line(nakamoto_df, x="reward_date", y="nakamoto_coefficient",
                  labels={"reward_date": "Date", "nakamoto_coefficient": "Nakamoto coefficient"})
fig_nak.update_traces(line_color=SOL_CYAN)
fig_nak.add_hline(y=20, line_dash="dash", line_color=SOL_RED, annotation_text="Concerning threshold")
fig_nak.update_layout(margin=dict(t=20, b=20), height=350)
st.plotly_chart(fig_nak, use_container_width=True)

# ============================================================
# SECTION 3: REVENUE BREAKDOWN
# ============================================================
st.header("3. Where does validator revenue come from?")
st.markdown(
    "Revenue broken down into four sources using Jito's official fee data. "
    "Block fees are split into base fees and priority fees using Jito's reported ratio (18% base / 65% priority / 17% tips)."
)

revenue_query = """
    WITH block_fees AS (
        SELECT pubkey, daily_block_fees
        FROM `zoomcamp-test-2.solana_validator_economics.validator_daily_block_fees`
    ),
    voting_rewards AS (
        SELECT pubkey, daily_voting_rewards
        FROM `zoomcamp-test-2.solana_validator_economics.validator_daily_voting_rewards`
    ),
    mev_tips AS (
        SELECT vote_account, ROUND(SUM(mev_rewards_sol) / 4 / 2.5, 4) as daily_mev_tips
        FROM `zoomcamp-test-2.solana_validator_economics.raw_jito_mev`
        WHERE epoch < 950
        GROUP BY vote_account
    )
    SELECT 
        CASE 
            WHEN (COALESCE(v.daily_voting_rewards, 0) + COALESCE(b.daily_block_fees, 0) + COALESCE(m.daily_mev_tips, 0)) < 1.1 
                THEN '4. Underwater'
            WHEN s.activated_stake_sol >= 1000000 THEN '1. Top tier (1M+ SOL)'
            WHEN s.activated_stake_sol >= 100000 THEN '2. Mid tier (100k-1M)'
            ELSE '3. Small profitable'
        END as tier,
        COUNT(*) as validators,
        ROUND(AVG(COALESCE(v.daily_voting_rewards, 0)), 4) as avg_voting,
        ROUND(AVG(COALESCE(b.daily_block_fees, 0) * 0.218), 4) as avg_base_fees,
        ROUND(AVG(COALESCE(b.daily_block_fees, 0) * 0.782), 4) as avg_priority_fees,
        ROUND(AVG(COALESCE(m.daily_mev_tips, 0)), 4) as avg_jito_tips
    FROM `zoomcamp-test-2.solana_validator_economics.raw_validator_snapshots` s
    LEFT JOIN voting_rewards v ON s.vote_pubkey = v.pubkey
    LEFT JOIN block_fees b ON s.node_pubkey = b.pubkey
    LEFT JOIN mev_tips m ON s.vote_pubkey = m.vote_account
    WHERE s.snapshot_date = '2026-04-02' AND s.status = 'current'
    GROUP BY tier
    ORDER BY tier
"""
rev_df = client.query(revenue_query).to_dataframe()
rev_df["total"] = (rev_df["avg_voting"].astype(float) + rev_df["avg_base_fees"].astype(float) 
                   + rev_df["avg_priority_fees"].astype(float) + rev_df["avg_jito_tips"].astype(float))
rev_df["mev_related"] = rev_df["avg_priority_fees"].astype(float) + rev_df["avg_jito_tips"].astype(float)
rev_df["mev_pct"] = round(rev_df["mev_related"] / rev_df["total"].clip(lower=0.001) * 100, 1)

# Metric cards
st.subheader("Average daily revenue per validator")
cols = st.columns(len(rev_df))
for i, row in rev_df.iterrows():
    total_sol = float(row['total'])
    mev_pct = float(row['mev_pct'])
    with cols[i]:
        tier_name = row['tier'].split('. ', 1)[1]
        st.metric(
            label=f"{tier_name} ({int(row['validators'])})",
            value=f"{total_sol:,.1f} SOL/day",
            delta="Underwater" if "Underwater" in row['tier'] else f"{mev_pct:.0f}% MEV-related"
        )

# Horizontal 100% stacked bar
rev_df["pct_voting"] = round(rev_df["avg_voting"].astype(float) / rev_df["total"].clip(lower=0.001) * 100, 1)
rev_df["pct_base"] = round(rev_df["avg_base_fees"].astype(float) / rev_df["total"].clip(lower=0.001) * 100, 1)
rev_df["pct_priority"] = round(rev_df["avg_priority_fees"].astype(float) / rev_df["total"].clip(lower=0.001) * 100, 1)
rev_df["pct_tips"] = round(rev_df["avg_jito_tips"].astype(float) / rev_df["total"].clip(lower=0.001) * 100, 1)

rev_df = rev_df.sort_values("total", ascending=True)

fig_rev = go.Figure()

for col_name, label, color in [
    ("pct_voting", "Voting / Inflation Rewards", SOL_DARK_PURPLE),
    ("pct_base", "Base & Vote Fees", SOL_TEAL),
    ("pct_priority", "Priority Fees", SOL_CYAN),
    ("pct_tips", "Jito Tips", SOL_AMBER),
]:
    fig_rev.add_trace(go.Bar(
        y=rev_df["tier"].str.split('. ', expand=True)[1],
        x=rev_df[col_name].astype(float),
        name=label,
        orientation='h',
        marker_color=color,
        text=rev_df[col_name].astype(float).apply(lambda x: f"{x:.0f}%" if x >= 5 else ""),
        textposition="inside",
        textfont=dict(size=11, color="white"),
    ))

for idx, row in rev_df.iterrows():
    total_sol = float(row['total'])
    tier_label = row['tier'].split('. ', 1)[1]
    fig_rev.add_annotation(
        x=108, y=tier_label,
        text=f"<b>{total_sol:,.1f} SOL/day</b>",
        showarrow=False,
        font=dict(size=12, color="white"),
        xanchor="left",
    )

fig_rev.update_layout(
    barmode='stack',
    margin=dict(t=20, b=20, l=20, r=140),
    height=320,
    legend=dict(x=0.01, y=-0.3, orientation="h"),
    xaxis=dict(title="% of revenue", range=[0, 120]),
    yaxis=dict(title=""),
)
st.plotly_chart(fig_rev, use_container_width=True)

st.markdown(
    "**Top tier validators earn 551 SOL/day. Underwater validators earn 0.6 SOL/day — a 920x difference.** "
    "For mid-tier validators, about 25% of income is MEV-related (priority fees + Jito tips). "
    "For underwater validators, it's 65% — the smallest validators are the most dependent on extraction revenue, "
    "and it's still not enough."
)
st.caption(
    "Source: Block fee split derived from Jito's official fee breakdown (March 2026). "
    "During peak memecoin season (late 2024), Jito tips alone accounted for over 50% of all block revenue. "
    "The ratio shifts dramatically with market activity."
)

# ============================================================
# SECTION 4: BLOCK PRODUCTION & MEV CONCENTRATION
# ============================================================
st.header("4. Block production and MEV are concentrated in few hands")
st.markdown(
    "Block production is stake-weighted — more stake means more blocks means more control "
    "over transaction ordering. MEV revenue is even more concentrated than block production itself."
)

st.subheader("Block production share")

block_conc_query = """
    SELECT 
        CASE 
            WHEN rank <= 10 THEN 'Top 10'
            WHEN rank <= 20 THEN 'Top 11-20'
            WHEN rank <= 50 THEN 'Top 21-50'
            WHEN rank <= 100 THEN 'Top 51-100'
            ELSE 'Remaining 673'
        END as group_name,
        SUM(blocks_produced) as total_blocks,
        ROUND(SUM(blocks_produced) * 100.0 / (SELECT COUNT(*) FROM `zoomcamp-test-2.solana_validator_economics.raw_blocks` WHERE block_timestamp >= TIMESTAMP('2026-03-01')), 1) as pct_of_blocks
    FROM (
        SELECT leader, COUNT(*) as blocks_produced,
               ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) as rank
        FROM `zoomcamp-test-2.solana_validator_economics.raw_blocks`
        WHERE block_timestamp >= TIMESTAMP('2026-03-01')
        GROUP BY leader
    )
    GROUP BY group_name
    ORDER BY MIN(rank)
"""
block_df = client.query(block_conc_query).to_dataframe()

fig2 = px.bar(block_df, x="pct_of_blocks", y="group_name",
              orientation='h', text="pct_of_blocks",
              color="group_name", color_discrete_map=group_colors,
              labels={"pct_of_blocks": "% of all blocks", "group_name": ""})
fig2.update_traces(texttemplate='%{text}%', textposition='outside')
fig2.update_layout(margin=dict(t=20, b=20), height=280, showlegend=False,
                   yaxis=dict(categoryorder='array',
                              categoryarray=['Remaining 673', 'Top 51-100', 'Top 21-50', 'Top 11-20', 'Top 10']),
                   xaxis=dict(range=[0, 35]))
st.plotly_chart(fig2, use_container_width=True)

st.subheader("MEV revenue share")

mev_conc_query = """
    SELECT 
        CASE 
            WHEN rank <= 10 THEN 'Top 10'
            WHEN rank <= 20 THEN 'Top 11-20'
            WHEN rank <= 50 THEN 'Top 21-50'
            WHEN rank <= 100 THEN 'Top 51-100'
            ELSE 'Remaining 673'
        END as group_name,
        ROUND(SUM(total_mev_sol), 2) as total_mev_sol,
        ROUND(SUM(total_mev_sol) * 100.0 / (SELECT SUM(mev_rewards_sol) FROM `zoomcamp-test-2.solana_validator_economics.raw_jito_mev` WHERE epoch < 950), 1) as pct_of_mev
    FROM (
        SELECT vote_account, SUM(mev_rewards_sol) as total_mev_sol,
               ROW_NUMBER() OVER (ORDER BY SUM(mev_rewards_sol) DESC) as rank
        FROM `zoomcamp-test-2.solana_validator_economics.raw_jito_mev`
        WHERE epoch < 950
        GROUP BY vote_account
    )
    GROUP BY group_name
    ORDER BY MIN(rank)
"""
mev_df = client.query(mev_conc_query).to_dataframe()
mev_df["group_name"] = mev_df["group_name"].replace({"Rest": "Remaining 673"})

fig_mev = px.bar(mev_df, x="pct_of_mev", y="group_name",
                 orientation='h', text="pct_of_mev",
                 color="group_name", color_discrete_map=group_colors,
                 labels={"pct_of_mev": "% of all MEV revenue", "group_name": ""})
fig_mev.update_traces(texttemplate='%{text}%', textposition='outside')
fig_mev.update_layout(margin=dict(t=20, b=20), height=280, showlegend=False,
                      yaxis=dict(categoryorder='array',
                                 categoryarray=['Remaining 673', 'Top 51-100', 'Top 21-50', 'Top 11-20', 'Top 10']),
                      xaxis=dict(range=[0, 40]))
st.plotly_chart(fig_mev, use_container_width=True)

st.markdown(
    "**The top 10 produce 22.8% of blocks but capture 33.2% of MEV revenue.** "
    "The top 50 produce 54% of blocks but take 62% of MEV. "
    "The largest validators don't just make more blocks — they extract more value per block."
)

# ============================================================
# SECTION 5: REWARD CONCENTRATION
# ============================================================
st.header("5. Rewards are flowing to the top")
st.markdown("How do validator rewards flow across the network?")

conc_latest_query = """
    SELECT 
        ROUND(AVG(pct_rewards_top_10), 1) as top_10,
        ROUND(AVG(pct_rewards_top_50), 1) as top_50,
        ROUND(AVG(pct_rewards_top_100), 1) as top_100
    FROM `zoomcamp-test-2.solana_validator_economics.fct_reward_concentration`
    WHERE total_validators < 10000
      AND reward_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
"""
conc_latest = client.query(conc_latest_query).to_dataframe().iloc[0]

top_10_val = float(conc_latest['top_10'])
top_11_50_val = float(conc_latest['top_50']) - float(conc_latest['top_10'])
top_51_100_val = float(conc_latest['top_100']) - float(conc_latest['top_50'])
rest_val = 100 - float(conc_latest['top_100'])

fig_sankey = go.Figure(data=[go.Sankey(
    node=dict(
        pad=20, thickness=30,
        line=dict(color="rgba(0,0,0,0.3)", width=1),
        label=["Total Network Rewards", 
               f"Top 10 ({top_10_val:.0f}%)", f"Top 11-50 ({top_11_50_val:.0f}%)", 
               f"Top 51-100 ({top_51_100_val:.0f}%)", f"Remaining 673+ ({rest_val:.0f}%)"],
        color=[SOL_DARK_PURPLE, SOL_PURPLE, SOL_CYAN, SOL_TEAL, SOL_GREEN],
    ),
    link=dict(
        source=[0, 0, 0, 0], target=[1, 2, 3, 4],
        value=[top_10_val, top_11_50_val, top_51_100_val, rest_val],
        color=["rgba(153,69,255,0.4)", "rgba(0,209,255,0.4)", "rgba(0,188,212,0.4)", "rgba(20,241,149,0.4)"],
    )
)])
fig_sankey.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=400)
st.plotly_chart(fig_sankey, use_container_width=True)

st.markdown(f"""
**The top 10 validators capture {top_10_val:.0f}% of all rewards.** The top 100 take {float(conc_latest['top_100']):.0f}%. 
The remaining 673+ validators — the vast majority of the network — split just {rest_val:.0f}%.
""")

# ============================================================
# SECTION 6: JITO DOMINANCE
# ============================================================
st.header("6. Jito controls transaction ordering on 98% of blocks")
st.markdown(
    "Almost every validator runs Jito — software that sells transaction ordering to the highest bidder. "
    "Snipers and bundlers pay tips to guarantee their transactions land first."
)

col1, col2, col3 = st.columns(3)
col1.metric("Blocks by Jito validators", "98.1%")
col2.metric("Validators running Jito", "770 / 773")
col3.metric("MEV captured by top 10", "33.2%")

st.subheader("Total MEV earned vs Jito validator adoption")
st.markdown(
    "Validators don't have enough incentives to operate. When Jito offered MEV revenue as a lifeline, "
    "adoption was inevitable — and irreversible. Today 770 out of 773 validators run Jito. "
    "Without viable alternatives to profit and operating costs so high, Solana's entire validator network "
    "became dependent on MEV extraction."
)

hist_query = """
    SELECT epoch, total_mev_sol, jito_validator_count
    FROM `zoomcamp-test-2.solana_validator_economics.raw_jito_historical`
    WHERE jito_validator_count > 0
    ORDER BY epoch
"""
hist_df = client.query(hist_query).to_dataframe()

reference_epoch = 950
reference_date = datetime.date(2026, 4, 2)
hist_df["approx_date"] = hist_df["epoch"].apply(
    lambda e: reference_date - datetime.timedelta(days=(reference_epoch - e) * 2.5)
)

fig5 = go.Figure()
fig5.add_trace(go.Scatter(
    x=hist_df["approx_date"], y=hist_df["total_mev_sol"],
    name="Total SOL earned from MEV (per epoch)", yaxis="y1",
    line=dict(color=SOL_RED, width=2),
))
fig5.add_trace(go.Scatter(
    x=hist_df["approx_date"], y=hist_df["jito_validator_count"],
    name="Validators running Jito", yaxis="y2",
    line=dict(color=SOL_PURPLE, width=2),
))
fig5.update_layout(
    xaxis_title="Date",
    yaxis=dict(title="SOL earned from MEV (per epoch, ~2.5 days)", side="left", showgrid=False),
    yaxis2=dict(title="Validators running Jito", side="right", overlaying="y", showgrid=False),
    margin=dict(t=20, b=20), height=400,
    legend=dict(x=0.01, y=0.99),
)
st.plotly_chart(fig5, use_container_width=True)

st.markdown(
    "**During peak memecoin season (mid-2024), 116,070 SOL was extracted in a single epoch with only 441 Jito validators.** "
    "Today MEV has dropped 97% but 770 validators run Jito — nearly double. "
    "The extraction infrastructure is embedded in 98% of blocks and waiting for the next wave of volume."
)

# ============================================================
# SECTION 7: THE FULL STORY
# ============================================================
st.header("The full picture")
st.markdown(f"""
**Solana's consensus layer is decentralized in name, but its execution layer is centralized through Jito.**

1. **Bad economics are killing validators.** {int(econ_stats['underwater'])} out of {int(econ_stats['total'])} validators can't cover the 1.1 SOL/day voting cost. Just 98 validators (12%) earn over 500 SOL/day — the rest fight for scraps.

2. **Validator count has collapsed.** From 5,400 in October 2024 to under 800 today — an 85% decline. Thousands couldn't cover the cost and shut down.

3. **Validators depend on MEV-related revenue.** Priority fees and Jito tips make up 25% of mid-tier income and 65% of underwater validator income. During peak memecoin season, Jito tips alone were over 50% of all block revenue.

4. **Block production is concentrated.** The top 50 validators produce 54% of all blocks. The top 100 produce 71%. The remaining 673 split just 29%.

5. **MEV is even more concentrated than block production.** The top 10 capture 33.2% of MEV despite producing only 22.8% of blocks.

6. **Jito controls 98.1% of block production.** Every sniper, every bundler, every sandwich bot has guaranteed access to nearly every block.

7. **The extraction infrastructure has nearly doubled — and it's waiting.** During peak memecoin season, only 441 validators ran Jito and $14.7M was extracted in a single day. Today 770 run it. The machine is built. When the next wave hits, there won't be a single block where a sniper can't buy priority.

**Right now, volume is dead and the trenches are nothing but bundled rugs.** Every launch is fake volume manufactured by bundlers. The few retail traders left are exit liquidity. Nothing survives. Trust is gone.

**When the next wave comes — and it will — it's going to be worse.** 770 Jito validators instead of 441. 98% block coverage. Every sniper more efficient and more embedded than last cycle. If retail gets burned worse than before, they won't come back. Not to memecoins. Not to Solana. Maybe not to crypto.

**The fix isn't just better economics. It's competing infrastructure.** Validator software that doesn't sell transaction ordering. Systems that protect users instead of extracting from them. The market is wide open. Whoever builds it doesn't just build a business — they fix the trenches. And they might save crypto's shot at mainstream adoption.
""")