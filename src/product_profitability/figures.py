"""
Plotly figures shared by the app and the README charts, in the portfolio look: teal margins, one copper highlight
(the biggest selling cost), mist for the other costs, hairline connectors, value labels instead of an axis.
Data and titles come from report.py.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from product_profitability import report
from product_profitability import theme as t

CONFIG = {"displayModeBar": False}
TICK_LABELS = {"list_margin": "Price-list<br>margin", "commission": "Affiliate<br>commission",
               "payment": "Payment<br>fees", "true_margin": "True<br>margin"}


def _num(size: int, color) -> dict:
    """Font of numbers on a chart (value labels, ticks)."""
    return {"family": t.NUM_STACK, "size": size, "color": color}


def _layout(fig: go.Figure, height: int, **extra) -> go.Figure:
    margin = extra.pop("margin", {"l": 8, "r": 8, "t": 12, "b": 8})
    fig.update_layout(
        height=height, margin=margin, paper_bgcolor=t.PAGE, plot_bgcolor=t.PAGE,
        font={"family": t.SANS_STACK, "size": 13, "color": t.TEXT}, showlegend=False,
        hoverlabel={"bgcolor": t.PAGE, "bordercolor": t.LINE,
                    "font": {"family": t.SANS_STACK, "color": t.INK, "size": 13}},
        barcornerradius=4, dragmode=False, **{"bargap": 0.32, **extra},
    )
    return fig


def bar_colors(data: pd.DataFrame) -> list[str]:
    return [t.PRIMARY if kind == "margin" else t.ACCENT if highlight else t.MIST
            for kind, highlight in zip(data["kind"], data["highlight"], strict=True)]


def value_labels(data: pd.DataFrame, language: str = "en") -> list[str]:
    """Margins as they are, costs with a minus sign (a negative cost, such as delivery income, with a plus)."""
    labels = []
    for kind, amount in zip(data["kind"], data["amount"], strict=True):
        if kind == "margin" or amount >= 0:
            labels.append(report.compact(amount if kind == "margin" else -amount, language))
        else:
            labels.append("+" + report.compact(-amount, language))
    return labels


def cascade(data: pd.DataFrame, language: str = "en", height: int = 360) -> go.Figure:
    """The margin cascade: floating bars from the price-list margin down to the true margin."""
    low = data[["start", "end"]].min(axis=1)
    size = (data["end"] - data["start"]).abs()
    ticks = [TICK_LABELS.get(step, label) for step, label in zip(data["step"], data["label"], strict=True)]
    colors = bar_colors(data)
    fig = go.Figure()
    fig.add_bar(
        x=ticks, y=size, base=low, marker={"color": colors}, customdata=data[["label", "share"]],
        text=value_labels(data, language), textposition="outside", cliponaxis=False,
        textfont=_num(13, [t.INK if c != t.MIST else t.TEXT for c in colors]),
        hovertemplate="%{customdata[0]}<br><b>%{text} PLN</b><br>%{customdata[1]:.0%} of the price-list margin"
                      "<extra></extra>",
    )
    for index in range(len(data) - 2):
        level = float(data["end"].iloc[index])
        fig.add_shape(type="line", xref="x", yref="y", x0=index + 0.34, x1=index + 0.66, y0=level, y1=level,
                      line={"color": t.MUTED, "width": 1})
    top = float(data[["start", "end"]].max().max())
    bottom = min(0.0, float(data[["start", "end"]].min().min()))
    fig.update_xaxes(showgrid=False, showline=False, ticks="", tickfont={"color": t.TEXT}, fixedrange=True,
                     ticklabelstandoff=6)
    fig.update_yaxes(visible=False, range=[bottom * 1.15, top * 1.14], fixedrange=True, zeroline=True,
                     zerolinecolor=t.LINE)
    return _layout(fig, height)
