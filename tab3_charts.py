# -*- coding: utf-8 -*-
"""4단계 탭: 기업별 최소교환주기에 따른 다음 교환 예정월"""
import plotly.graph_objects as go
import pandas as pd

제품_순서 = ["정수기", "공기청정기", "비데", "커피머신", "제빙기", "기타"]
CHART_COLORS = ["#4a90d9", "#50c878", "#f0a045", "#e85d5d", "#b07ce8",
                "#45c4c9", "#f06292", "#aed581", "#ffb74d", "#90a4ae"]
TEXT_PRIMARY = "#e4e6eb"
TEXT_SECONDARY = "#8b8fa3"
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT_PRIMARY, family="Pretendard, sans-serif"),
    margin=dict(l=40, r=20, t=40, b=60),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_SECONDARY)),
)


def make_exchange_timeline(exchange_df, months_ahead=12):
    """향후 N개월간 월별 교환 예정 건수 바 차트"""
    from datetime import datetime
    now = datetime.now()
    # 향후 months_ahead개월 범위
    future = exchange_df[exchange_df["다음교환예정일"] >= now].copy()
    cutoff = now + pd.DateOffset(months=months_ahead)
    future = future[future["다음교환예정일"] < cutoff]

    monthly = future.groupby("예정년월").size().reset_index(name="건수")
    monthly = monthly.sort_values("예정년월")

    fig = go.Figure(data=[go.Bar(
        x=monthly["예정년월"], y=monthly["건수"],
        marker=dict(color="#4a90d9", cornerradius=4),
        text=monthly["건수"].apply(lambda x: f"{x:,}"),
        textposition="outside",
        textfont=dict(size=11, color=TEXT_SECONDARY),
        hovertemplate="<b>%{x}</b><br>교환 예정: %{y:,}건<extra></extra>",
    )])
    fig.update_layout(**PLOT_LAYOUT, height=400)
    fig.update_xaxes(showgrid=False, tickangle=-30)
    fig.update_yaxes(showgrid=True, gridcolor="#1e2130")
    return fig


def make_exchange_by_product(exchange_df, months_ahead=12):
    """향후 N개월간 제품구분별 월별 교환 예정 스택 바 차트"""
    from datetime import datetime
    now = datetime.now()
    future = exchange_df[exchange_df["다음교환예정일"] >= now].copy()
    cutoff = now + pd.DateOffset(months=months_ahead)
    future = future[future["다음교환예정일"] < cutoff]

    months_sorted = sorted(future["예정년월"].unique())
    fig = go.Figure()
    for i, prod in enumerate(제품_순서):
        subset = future[future["제품구분"] == prod]
        counts = subset.groupby("예정년월").size().reindex(months_sorted, fill_value=0)
        fig.add_trace(go.Bar(
            x=months_sorted, y=counts.values, name=prod,
            marker=dict(color=CHART_COLORS[i], cornerradius=2),
            hovertemplate=f"<b>{prod}</b><br>%{{x}}: %{{y:,}}건<extra></extra>",
        ))
    fig.update_layout(**PLOT_LAYOUT, height=420, barmode="stack")
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                  xanchor="right", x=1,
                                  font=dict(color=TEXT_PRIMARY, size=12)))
    fig.update_xaxes(showgrid=False, tickangle=-30)
    fig.update_yaxes(showgrid=True, gridcolor="#1e2130")
    return fig


def make_exchange_by_company(exchange_df, months_ahead=6):
    """향후 N개월간 기업별(중분류) 교환 예정 TOP 15 바 차트"""
    from datetime import datetime
    now = datetime.now()
    future = exchange_df[exchange_df["다음교환예정일"] >= now].copy()
    cutoff = now + pd.DateOffset(months=months_ahead)
    future = future[future["다음교환예정일"] < cutoff]

    company_counts = future["중분류(그룹사)"].value_counts().head(15)
    labels = list(reversed(company_counts.index))
    values = [company_counts[c] for c in labels]

    fig = go.Figure(data=[go.Bar(
        y=labels, x=values, orientation="h",
        marker=dict(color="#f0a045", cornerradius=4),
        text=[f"{v:,}" for v in values],
        textposition="outside",
        textfont=dict(size=11, color=TEXT_SECONDARY),
        hovertemplate="<b>%{y}</b><br>교환 예정: %{x:,}건<extra></extra>",
    )])
    fig.update_layout(**PLOT_LAYOUT, height=450)
    fig.update_xaxes(showgrid=True, gridcolor="#1e2130")
    fig.update_yaxes(showgrid=False)
    return fig
