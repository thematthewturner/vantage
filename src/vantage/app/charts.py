"""Plotly chart builders with a single dark "terminal" look.

Every figure routes through ``_style`` so the whole dashboard shares one
black-background, amber-accented theme reminiscent of a trading terminal.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# Terminal palette: amber primary, cyan secondary, green/red for up/down.
AMBER = "#ffb000"
CYAN = "#26c6da"
GREEN = "#26a69a"
RED = "#ef5350"
GRID = "#1c2330"
PAPER = "#0b0f17"
PANEL = "#0e131d"
TEXT = "#c8d0dc"

# A repeating qualitative palette for multi-series charts (sub-sectors, etc.).
PALETTE = [AMBER, CYAN, "#ab47bc", GREEN, "#ff7043", "#5c6bc0", "#d4e157", "#ec407a"]


def _style(fig: go.Figure, *, height: int = 360, title: str | None = None) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        title=title,
        height=height,
        margin=dict(l=48, r=24, t=48 if title else 16, b=32),
        paper_bgcolor=PAPER,
        plot_bgcolor=PANEL,
        font=dict(color=TEXT, family="ui-monospace, SFMono-Regular, Menlo, monospace", size=12),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
        xaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
        yaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
    )
    return fig


def index_chart(track: pd.DataFrame, title: str = "VHC index") -> go.Figure:
    """Total-return and price-return tracks with a range selector."""
    fig = go.Figure()
    if "level_tr" in track:
        fig.add_trace(
            go.Scatter(
                x=track.index,
                y=track["level_tr"],
                name="Total return",
                line=dict(color=AMBER, width=2),
            )
        )
    if "level_pr" in track:
        fig.add_trace(
            go.Scatter(
                x=track.index,
                y=track["level_pr"],
                name="Price return",
                line=dict(color=CYAN, width=1, dash="dot"),
            )
        )
    fig = _style(fig, height=420, title=title)
    fig.update_xaxes(
        rangeselector=dict(
            buttons=[
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all", label="MAX"),
            ],
            bgcolor=PANEL,
            activecolor=AMBER,
            font=dict(color=TEXT),
        ),
        rangeslider=dict(visible=False),
    )
    return fig


def overlay_chart(frame: pd.DataFrame, title: str) -> go.Figure:
    """Several rebased series on one axis (e.g. sub-sectors rebased to 100)."""
    fig = go.Figure()
    for i, col in enumerate(frame.columns):
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[col],
                name=str(col),
                line=dict(color=PALETTE[i % len(PALETTE)], width=1.5),
            )
        )
    return _style(fig, height=420, title=title)


def relative_chart(series: pd.Series, title: str, *, base: float = 100.0) -> go.Figure:
    """Relative-strength line; the dashed baseline marks parity (above = ahead)."""
    s = series.dropna()
    fig = go.Figure(
        go.Scatter(x=s.index, y=s.values, name="relative strength", line=dict(color=AMBER, width=2))
    )
    fig = _style(fig, height=320, title=title)
    fig.add_hline(y=base, line=dict(color=CYAN, width=1, dash="dot"))
    return fig


def sparkline(series: pd.Series) -> go.Figure:
    """Tiny axis-free line for an indicator card; green/red by net direction."""
    s = series.dropna()
    color = GREEN if (len(s) >= 2 and s.iloc[-1] >= s.iloc[0]) else RED
    fig = go.Figure(
        go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(color=color, width=1.5))
    )
    fig.update_layout(
        height=70,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def dual_axis_chart(
    left: pd.Series, right: pd.Series, left_name: str, right_name: str
) -> go.Figure:
    """Index vs indicator on two y-axes (the classic overlay)."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=left.index, y=left.values, name=left_name, line=dict(color=AMBER, width=2))
    )
    fig.add_trace(
        go.Scatter(
            x=right.index,
            y=right.values,
            name=right_name,
            yaxis="y2",
            line=dict(color=CYAN, width=1.5),
        )
    )
    fig = _style(fig, height=420)
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", gridcolor=GRID, showgrid=False, title=right_name)
    )
    return fig


def leadlag_bars(result: pd.DataFrame, title: str) -> go.Figure:
    """Cross-correlation by lag; the peak bar highlighted in amber."""
    corr = result["corr"]
    peak = corr.abs().idxmax() if corr.notna().any() else None
    colors = [AMBER if i == peak else "#3a4456" for i in result.index]
    fig = go.Figure(go.Bar(x=result["lag"], y=result["corr"], marker_color=colors))
    fig = _style(fig, height=320, title=title)
    fig.update_xaxes(title="lag (periods; + = indicator leads)")
    fig.update_yaxes(title="correlation", range=[-1, 1])
    return fig


def correlation_heatmap(matrix: pd.DataFrame, title: str) -> go.Figure:
    """Indicators (rows) x lag (cols) correlation matrix."""
    fig = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=[str(c) for c in matrix.columns],
            y=list(matrix.index),
            colorscale="RdBu",
            zmid=0,
            zmin=-1,
            zmax=1,
            colorbar=dict(title="corr"),
        )
    )
    fig = _style(fig, height=max(320, 26 * len(matrix) + 120), title=title)
    fig.update_xaxes(title="lag (periods; + = indicator leads)")
    return fig


def movers_bar(movers: pd.DataFrame, title: str) -> go.Figure:
    """Horizontal %-return bars per constituent; green for up, red for down."""
    m = movers.sort_values("return_pct")
    colors = [GREEN if v >= 0 else RED for v in m["return_pct"]]
    fig = go.Figure(go.Bar(x=m["return_pct"], y=m["ticker"], orientation="h", marker_color=colors))
    fig = _style(fig, height=max(240, 20 * len(m) + 80), title=title)
    fig.update_xaxes(title="return (%)")
    return fig


def forecast_chart(backtest: pd.DataFrame, title: str) -> go.Figure:
    """Walk-forward predicted vs actual next-month return (%), out of sample."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=backtest.index,
            y=backtest["actual"] * 100.0,
            name="actual",
            line=dict(color=CYAN, width=1.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=backtest.index,
            y=backtest["pred"] * 100.0,
            name="predicted",
            line=dict(color=AMBER, width=1.5),
        )
    )
    fig = _style(fig, height=380, title=title)
    fig.update_yaxes(title="next-month return (%)")
    return fig


def weights_bar(weights: pd.DataFrame, title: str) -> go.Figure:
    """Horizontal constituent-weight bars at the latest rebalance."""
    w = weights.sort_values("weight")
    label = w["ticker"] if "ticker" in w else w.index
    fig = go.Figure(go.Bar(x=w["weight"] * 100.0, y=label, orientation="h", marker_color=AMBER))
    fig = _style(fig, height=max(320, 18 * len(w) + 80), title=title)
    fig.update_xaxes(title="weight (%)")
    return fig
