# -*- coding: utf-8 -*-
"""2단계 탭: 월별 렌탈 설치 대수 비교"""
import plotly.graph_objects as go
from preprocess import get_monthly_counts, get_monthly_product_counts

제품_순서 = ["정수기", "공기청정기", "비데", "커피머신", "제빙기", "기타"]
CHART_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
                "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#64748b"]
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#4b5563"
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT_PRIMARY, family="Pretendard, sans-serif"),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_SECONDARY)),
)


def make_comparison_chart(df, year1, year2):
    """두 연도의 월별 설치 대수 비교 라인 차트"""
    m1 = get_monthly_counts(df, year1)
    m2 = get_monthly_counts(df, year2)
    months = [f"{m}월" for m in range(1, 13)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=months, y=m1["건수"], mode="lines+markers+text", name=f"{year1}년",
        line=dict(color="#f0a045", width=3), marker=dict(size=8),
        text=m1["건수"].apply(lambda x: f"{x:,}" if x > 0 else ""),
        textposition="top center", textfont=dict(size=10, color="#f0a045"),
    ))
    fig.add_trace(go.Scatter(
        x=months, y=m2["건수"], mode="lines+markers+text", name=f"{year2}년",
        line=dict(color="#4a90d9", width=3), marker=dict(size=8),
        text=m2["건수"].apply(lambda x: f"{x:,}" if x > 0 else ""),
        textposition="bottom center", textfont=dict(size=10, color="#4a90d9"),
    ))
    fig.update_layout(**PLOT_LAYOUT, height=420)
    fig.update_layout(legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        font=dict(color=TEXT_PRIMARY, size=13),
    ))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#e5e7eb")
    return fig


def make_ytd_chart(df, year1, year2):
    """두 연도의 월별 누적 합계(YTD) 비교 차트"""
    m1 = get_monthly_counts(df, year1)
    m2 = get_monthly_counts(df, year2)
    m1["누적"] = m1["건수"].cumsum()
    m2["누적"] = m2["건수"].cumsum()
    months = [f"{m}월" for m in range(1, 13)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=months, y=m1["누적"], mode="lines+markers+text", name=f"{year1}년",
        line=dict(color="#f0a045", width=3), marker=dict(size=8),
        text=m1["누적"].apply(lambda x: f"{x:,}" if x > 0 else ""),
        textposition="top center", textfont=dict(size=10, color="#f0a045"),
        fill="tozeroy", fillcolor="rgba(240,160,69,0.08)",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=m2["누적"], mode="lines+markers+text", name=f"{year2}년",
        line=dict(color="#4a90d9", width=3), marker=dict(size=8),
        text=m2["누적"].apply(lambda x: f"{x:,}" if x > 0 else ""),
        textposition="bottom center", textfont=dict(size=10, color="#4a90d9"),
        fill="tozeroy", fillcolor="rgba(74,144,217,0.08)",
    ))
    fig.update_layout(**PLOT_LAYOUT, height=420)
    fig.update_layout(legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        font=dict(color=TEXT_PRIMARY, size=13),
    ))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#e5e7eb")
    return fig


def make_product_stack_chart(df, year):
    """제품구분별 월별 스택 바 차트"""
    data = get_monthly_product_counts(df, year)
    months = [f"{m}월" for m in range(1, 13)]
    fig = go.Figure()
    for i, prod in enumerate(제품_순서):
        subset = data[data["제품구분"] == prod]
        fig.add_trace(go.Bar(
            x=months, y=subset["건수"], name=prod,
            marker=dict(color=CHART_COLORS[i], cornerradius=2),
            hovertemplate=f"<b>{prod}</b><br>%{{x}}: %{{y:,}}건<extra></extra>",
        ))
    fig.update_layout(**PLOT_LAYOUT, height=420, barmode="stack")
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                  xanchor="right", x=1,
                                  font=dict(color=TEXT_PRIMARY, size=12)))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#e5e7eb")
    return fig
