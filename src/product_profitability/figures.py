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


def axis_labels(data: pd.DataFrame) -> list[str]:
    """Step names on the axis; no hyphen, which tabular figures in chart text space out."""
    return [label.replace("Price-list", "Price list") for label in data["label"]]


def cascade(data: pd.DataFrame, language: str = "en", height: int | None = None) -> go.Figure:
    """
    The margin cascade, read from top to bottom: the price-list margin, each selling cost as a floating bar from the
    running margin, the true margin. Horizontal, so the step names stay readable on a 390 px phone.
    """
    low = data[["start", "end"]].min(axis=1)
    size = (data["end"] - data["start"]).abs()
    colors = bar_colors(data)
    fig = go.Figure()
    fig.add_bar(
        y=axis_labels(data), x=size, base=low, orientation="h", marker={"color": colors},
        customdata=data[["label", "share"]], text=value_labels(data, language), textposition="outside",
        cliponaxis=False, textfont=_num(13, [t.INK if c != t.MIST else t.TEXT for c in colors]),
        hovertemplate="%{customdata[0]}<br><b>%{text} PLN</b><br>%{customdata[1]:.0%} of the price-list margin"
                      "<extra></extra>",
    )
    for index in range(len(data) - 2):
        level = float(data["end"].iloc[index])
        fig.add_shape(type="line", xref="x", yref="y", x0=level, x1=level, y0=index + 0.34, y1=index + 0.66,
                      line={"color": t.MUTED, "width": 1})
    left = min(0.0, float(data[["start", "end"]].min().min()))
    right = max(0.0, float(data[["start", "end"]].max().max()))
    span = (right - left) or 1.0
    if left < 0:
        fig.add_shape(type="line", xref="x", yref="paper", x0=0, x1=0, y0=0, y1=1, line={"color": t.LINE, "width": 1})
    fig.update_yaxes(autorange="reversed", showgrid=False, showline=False, ticks="", tickfont={"color": t.TEXT},
                     fixedrange=True, ticklabelstandoff=8)
    fig.update_xaxes(visible=False, range=[left - span * (0.14 if left < 0 else 0), right + span * 0.04],
                     fixedrange=True)
    # Value labels sit outside the bars: keep room for them in pixels, so they fit on a 390 px phone too.
    return _layout(fig, height or 44 * len(data) + 24, bargap=0.32,
                   margin={"l": 8, "r": 64, "t": 12, "b": 8})
