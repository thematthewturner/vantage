# ---
# Notebook: Index vs indicators, and an honest lead-lag look
# Run `make refresh` first.
# ---

# %% [markdown]
# # Does an industry indicator lead or lag the index?
# Overlay an indicator against the VHC index, then run a lead-lag cross-correlation
# on **stationary** (year-over-year) transforms. Read the honesty report before
# believing any number: most of these signals are coincident, and scanning many
# indicators x many lags manufactures spurious correlations.

# %%
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from vantage.storage.db import connect
from vantage.storage.readers import current_series, index_levels
from vantage.transforms.align import asof_align
from vantage.transforms.correlation import honesty_report, lead_lag
from vantage.transforms.signals import yoy

con = connect(read_only=True)

INDICATOR = ("FRED", "CPIMEDSL", "Medical-care CPI")

# %%
# Index (total return) and the indicator, as-of aligned onto trading days.
vhc = index_levels(con, "VHC").set_index("date")["level_tr"]
vhc.index = pd.to_datetime(vhc.index)

ind_df = current_series(con, INDICATOR[0], INDICATOR[1])
indicator = ind_df.set_index("date")["value"]
indicator.index = pd.to_datetime(indicator.index)

aligned = asof_align(vhc, indicator, index_name="VHC", indicator_name=INDICATOR[2])

fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Scatter(x=aligned.index, y=aligned["VHC"], name="VHC (TR)"), secondary_y=False)
fig.add_trace(
    go.Scatter(x=aligned.index, y=aligned[INDICATOR[2]], name=INDICATOR[2]), secondary_y=True
)
fig.update_layout(title=f"VHC vs {INDICATOR[2]}", hovermode="x unified")
fig.show()

# %%
# Lead-lag on monthly YoY transforms (stationary). Positive lag = indicator leads.
vhc_m = vhc.resample("MS").last()
ind_m = indicator.resample("MS").last()
res = lead_lag(yoy(ind_m), yoy(vhc_m), max_lag=12)

fig = go.Figure(go.Bar(x=res["lag"], y=res["corr"]))
fig.update_layout(
    title=f"Lead-lag: {INDICATOR[2]} YoY vs VHC YoY",
    xaxis_title="lag (months; + = indicator leads)",
    yaxis_title="correlation",
)
fig.show()

# %%
# READ THIS before trusting the chart above.
report = honesty_report(res, n_indicators_tested=1)
for warning in report["warnings"]:
    print("⚠ ", warning)
print("\nbest lag:", report["best_lag"], "corr:", report["best_corr"], "n:", report["best_n"])

# %%
con.close()
