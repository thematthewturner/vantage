# ---
# Notebook: Explore healthcare indicators
# Format: "percent" cells (# %%). Opens as a notebook in JupyterLab / VS Code,
# and also runs top-to-bottom as a plain script. Run `make refresh` first so the
# database has data.
# ---

# %% [markdown]
# # Explore healthcare indicators
# Pull a few tailored healthcare trackers from the store and look at their
# year-over-year trends. These are the "CPI-but-for-healthcare" style signals.

# %%
import plotly.graph_objects as go

from vantage.storage.db import connect
from vantage.storage.readers import current_series
from vantage.transforms.signals import yoy

con = connect(read_only=True)

# %%
# What series do we have?
meta = con.execute(
    "SELECT source, series_id, metric_name, frequency, subsector, last_obs "
    "FROM series_meta ORDER BY subsector, series_id"
).df()
meta

# %%
# Year-over-year for a handful of core trackers.
SERIES = {
    "CPIMEDSL": "Medical-care CPI",
    "CES6562000001": "Healthcare employment",
    "JTS6200JOL": "JOLTS health job openings",
    "USPCEHLTHCARE": "PCE health services",
}

fig = go.Figure()
for series_id, label in SERIES.items():
    df = current_series(con, "FRED", series_id)
    if df.empty:
        print(f"(no data yet for {series_id} -- run `make refresh`)")
        continue
    s = df.set_index("date")["value"]
    fig.add_trace(go.Scatter(x=s.index, y=yoy(s) * 100, name=label, mode="lines"))

fig.update_layout(title="Healthcare trackers, YoY %", yaxis_title="YoY %", hovermode="x unified")
fig.show()

# %%
con.close()
