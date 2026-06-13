# ---
# Notebook: Build and view the custom healthcare index
# Run `make refresh` first to ingest prices and build indices, or call
# build_all_indices() here against already-ingested prices.
# ---

# %% [markdown]
# # The custom healthcare stock index (VHC)
# A market-cap-weighted, quarterly-rebalanced index of the healthcare universe
# in `config/universe.toml`, normalized to 100 at inception. Plus per-sub-sector
# sub-indices (pharma, payers, providers, devices, biotech, tools, distributors).

# %%
import plotly.graph_objects as go

from vantage.index.subsectors import build_all_indices
from vantage.index.universe import SUBSECTORS, index_id_for
from vantage.storage.db import connect
from vantage.storage.readers import index_levels

con = connect()

# %%
# (Re)build all indices from whatever prices are already stored.
built = build_all_indices(con)
print("built:", built)

# %%
# Whole-universe index: price vs total return.
vhc = index_levels(con, "VHC")
fig = go.Figure()
fig.add_trace(go.Scatter(x=vhc["date"], y=vhc["level_pr"], name="VHC price return"))
fig.add_trace(go.Scatter(x=vhc["date"], y=vhc["level_tr"], name="VHC total return"))
fig.update_layout(title="VHC healthcare index (base = 100)", yaxis_title="Level",
                  hovermode="x unified")
fig.show()

# %%
# Sub-sectors on one chart (total return) -- watch them diverge.
fig = go.Figure()
for sub in SUBSECTORS:
    lv = index_levels(con, index_id_for(sub))
    if lv.empty:
        continue
    fig.add_trace(go.Scatter(x=lv["date"], y=lv["level_tr"], name=sub))
fig.update_layout(title="Healthcare sub-sector indices (total return, base = 100)",
                  yaxis_title="Level", hovermode="x unified")
fig.show()

# %%
con.close()
