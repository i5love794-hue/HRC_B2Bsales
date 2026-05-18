# -*- coding: utf-8 -*-
"""
현대렌탈케어 법인영업팀 대시보드
1단계: 기업별 현황 / 2단계: 월별 설치 실적 비교
"""

import json
import os
import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output, State
import plotly.graph_objects as go
from preprocess import (load_data, get_summary_stats, get_company_summary,
                        get_available_years, get_region_counts, calculate_next_exchange)
from tab2_charts import make_comparison_chart, make_ytd_chart, make_product_stack_chart
from tab4_expiration import (make_expiration_donut, make_product_status_chart, 
                             make_summary_target_table, make_sales_alert)

# ── 데이터 로드 ──
df = load_data()
stats = get_summary_stats(df)

# ── GeoJSON 로드 ──
_GEO_PATH = os.path.join(os.path.dirname(__file__), "data", "korea_provinces.json")
with open(_GEO_PATH, encoding="utf-8") as f:
    KOREA_GEO = json.load(f)
연도_옵션 = get_available_years(df)

# ── 제품구분 고정 순서 ──
제품_순서 = ["정수기", "공기청정기", "비데", "커피머신", "제빙기", "기타"]

# ── 대분류 고정 순서 ──
대분류_순서 = ["현대백화점그룹", "현대자동차그룹", "HD현대", "일반기업",
           "관공서 및 정부기관", "교육시설", "비영리법인"]

# ── 최소교환주기 구간 (개월) ──
교환주기_구간 = ["1개월", "2개월", "3개월", "4개월", "6개월",
            "12개월", "24개월", "36개월", "없음"]

# ── 필터 옵션 (대분류 + 중분류) ──
# 대분류는 고정 순서 우선, 나머지는 뒤에 추가
_existing_groups = set(df["대분류(그룹)"].dropna().unique())
대분류_옵션 = [g for g in 대분류_순서 if g in _existing_groups]
대분류_옵션 += sorted(_existing_groups - set(대분류_순서))
중분류_옵션 = sorted(df["중분류(그룹사)"].dropna().unique())

# ── 렌탈료 커스텀 구간 ──
렌탈료_구간 = [
    ("1만원 이하", 0, 10000),
    ("1만~1.2만", 10000, 12000),
    ("1.2만~1.5만", 12000, 15000),
    ("1.5만~2만", 15000, 20000),
    ("2만~3만", 20000, 30000),
    ("3만~5만", 30000, 50000),
    ("5만~10만", 50000, 100000),
    ("10만원 이상", 100000, float("inf")),
]

# ── 라이트모드 색상 ──
BG_LIGHT = "#f3f4f6"
CARD_BG = "#ffffff"
CARD_BORDER = "#e5e7eb"
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#4b5563"
ACCENT_BLUE = "#2563eb"
ACCENT_GREEN = "#10b981"
ACCENT_ORANGE = "#f59e0b"
ACCENT_RED = "#ef4444"
ACCENT_PURPLE = "#8b5cf6"
CHART_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
                "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#64748b"]

# ── Plotly 다크 템플릿 ──
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT_PRIMARY, family="Pretendard, sans-serif"),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_SECONDARY)
    ),
)

# ── 스타일 정의 ──
CARD_STYLE = {
    "backgroundColor": CARD_BG,
    "border": f"1px solid {CARD_BORDER}",
    "borderRadius": "16px",
    "padding": "24px",
    "marginBottom": "20px",
    "boxShadow": "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
}

KPI_CARD_STYLE = {
    "backgroundColor": CARD_BG,
    "border": f"1px solid {CARD_BORDER}",
    "borderRadius": "16px",
    "padding": "24px 20px",
    "textAlign": "center",
    "flex": "1",
    "minWidth": "200px",
    "boxShadow": "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
    "display": "flex",
    "flexDirection": "column",
    "justifyContent": "center",
}


# ── 헬퍼 함수 ──
def make_kpi_card(title, value, icon, color):
    """KPI 카드 컴포넌트 생성"""
    return html.Div(style=KPI_CARD_STYLE, children=[
        html.Div(icon, style={
            "fontSize": "32px",
            "marginBottom": "12px",
        }),
        html.Div(value, style={
            "fontSize": "30px",
            "fontWeight": "800",
            "color": color,
            "marginBottom": "6px",
            "letterSpacing": "-0.5px"
        }),
        html.Div(title, style={
            "fontSize": "14px",
            "color": TEXT_SECONDARY,
            "fontWeight": "600",
        }),
    ])


def categorize_rental(val):
    """렌탈료를 커스텀 구간으로 분류합니다."""
    for label, low, high in 렌탈료_구간:
        if low <= val < high:
            return label
    return "10만원 이상"


# ── Dash 앱 생성 ──
app = dash.Dash(
    __name__,
    title="현대렌탈케어 법인영업 대시보드",
    suppress_callback_exceptions=True,
)
server = app.server  # 배포 환경(gunicorn 등)에서 사용하기 위한 변수

# ── 탭 스타일 ──
TAB_STYLE = {"backgroundColor": "#f9fafb", "color": TEXT_SECONDARY,
             "border": f"1px solid {CARD_BORDER}", "padding": "12px 24px",
             "borderRadius": "8px 8px 0 0", "fontSize": "15px", "fontWeight": "600"}
TAB_SELECTED = {**TAB_STYLE, "backgroundColor": CARD_BG, "color": "#111827",
                "borderBottom": "2px solid " + ACCENT_BLUE, "borderTop": "2px solid " + ACCENT_BLUE}

# ── 필터 카드 스타일 (눈에 띄는 색상) ──
FILTER_STYLE = {
    **CARD_STYLE, "display": "flex", "gap": "16px", "flexWrap": "wrap",
    "alignItems": "center", "padding": "16px 24px",
    "borderLeft": f"4px solid {ACCENT_BLUE}",
    "backgroundColor": "#ffffff",
}

# ── 1단계 레이아웃 ──
def tab1_layout():
    return html.Div([
        # 필터
        html.Div(style=FILTER_STYLE, children=[
            html.Span("🔍 필터", style={"fontWeight": "600", "fontSize": "14px",
                                        "color": TEXT_SECONDARY, "marginRight": "8px"}),
            html.Div([html.Label("대분류(그룹)", style={"fontSize": "12px", "color": TEXT_SECONDARY,
                                                      "marginBottom": "4px", "display": "block"}),
                      dcc.Dropdown(id="filter-group",
                                   options=[{"label": g, "value": g} for g in 대분류_옵션],
                                   placeholder="전체", multi=True,
                                   style={"width": "320px", "fontSize": "13px"}, className="dark-dropdown")]),
            html.Div([html.Label("중분류(그룹사)", style={"fontSize": "12px", "color": TEXT_SECONDARY,
                                                       "marginBottom": "4px", "display": "block"}),
                      dcc.Dropdown(id="filter-company",
                                   options=[{"label": c, "value": c} for c in 중분류_옵션],
                                   placeholder="전체", multi=True,
                                   style={"width": "400px", "fontSize": "13px"}, className="dark-dropdown")]),
        ]),
        # KPI
        html.Div(id="kpi-cards", style={"display": "flex", "gap": "20px",
                                        "marginBottom": "24px", "flexWrap": "wrap"}),
        # 차트 Row 1
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                        "gap": "16px", "marginBottom": "16px"}, children=[
            html.Div(style=CARD_STYLE, children=[
                html.H3("제품구분별 설치 현황", style={"fontSize": "15px", "fontWeight": "600",
                                                    "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
                dcc.Graph(id="chart-product", config={"displayModeBar": False})]),
            html.Div(style=CARD_STYLE, children=[
                html.H3("지역별 설치 현황", style={"fontSize": "15px", "fontWeight": "600",
                                                  "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
                dcc.Graph(id="chart-region", config={"displayModeBar": False})]),
        ]),
        # 차트 Row 2
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                        "gap": "16px", "marginBottom": "16px"}, children=[
            html.Div(style=CARD_STYLE, children=[
                html.H3("대분류(그룹)별 설치 현황", style={"fontSize": "15px", "fontWeight": "600",
                                                        "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
                dcc.Graph(id="chart-group", config={"displayModeBar": False})]),
            html.Div(style=CARD_STYLE, children=[
                html.H3("렌탈료 구간별 분포", style={"fontSize": "15px", "fontWeight": "600",
                                                    "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
                dcc.Graph(id="chart-rental", config={"displayModeBar": False})]),
        ]),
        # 차트 Row 3
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                        "gap": "16px", "marginBottom": "16px"}, children=[
            html.Div(style=CARD_STYLE, children=[
                html.H3("의무약정 만료 현황", style={"fontSize": "15px", "fontWeight": "600",
                                                    "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
                dcc.Graph(id="chart-contract", config={"displayModeBar": False})]),
            html.Div(style=CARD_STYLE, children=[
                html.H3("최소교환주기별 현황", style={"fontSize": "15px", "fontWeight": "600",
                                                     "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
                dcc.Graph(id="chart-exchange", config={"displayModeBar": False})]),
        ]),
        # 테이블
        html.Div(style=CARD_STYLE, children=[
            html.H3("기업별 상세 현황", style={"fontSize": "15px", "fontWeight": "600",
                                              "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
            html.Div(id="table-container")]),
        # 3단계: 지도 시각화
        html.Div(style=CARD_STYLE, children=[
            html.H3("🗺️ 시도별 설치 현황 지도", style={"fontSize": "15px", "fontWeight": "600",
                                                    "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
            dcc.Graph(id="chart-map", config={"displayModeBar": False})]),
    ])

# ── 2단계 레이아웃 ──
def tab2_layout():
    yr_opts = [{"label": f"{y}년", "value": y} for y in 연도_옵션]
    default_y1 = 연도_옵션[1] if len(연도_옵션) > 1 else 연도_옵션[0]  # 전년도
    default_y2 = 연도_옵션[0]  # 당해년도
    return html.Div([
        # 필터
        html.Div(style=FILTER_STYLE, children=[
            html.Span("📅 연도 비교", style={"fontWeight": "600", "fontSize": "14px",
                                             "color": TEXT_SECONDARY, "marginRight": "8px"}),
            html.Div([html.Label("비교 연도 1", style={"fontSize": "12px", "color": TEXT_SECONDARY,
                                                      "marginBottom": "4px", "display": "block"}),
                      dcc.Dropdown(id="t2-year1", options=yr_opts, value=default_y1,
                                   style={"width": "160px", "fontSize": "13px"}, className="dark-dropdown")]),
            html.Div([html.Label("비교 연도 2", style={"fontSize": "12px", "color": TEXT_SECONDARY,
                                                      "marginBottom": "4px", "display": "block"}),
                      dcc.Dropdown(id="t2-year2", options=yr_opts, value=default_y2,
                                   style={"width": "160px", "fontSize": "13px"}, className="dark-dropdown")]),
            html.Div([html.Label("대분류(그룹)", style={"fontSize": "12px", "color": TEXT_SECONDARY,
                                                      "marginBottom": "4px", "display": "block"}),
                      dcc.Dropdown(id="t2-filter-group",
                                   options=[{"label": g, "value": g} for g in 대분류_옵션],
                                   placeholder="전체", multi=True,
                                   style={"width": "320px", "fontSize": "13px"}, className="dark-dropdown")]),
        ]),
        # 월별 비교 라인 차트
        html.Div(style=CARD_STYLE, children=[
            html.H3("월별 설치 대수 비교", style={"fontSize": "15px", "fontWeight": "600",
                                                 "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
            dcc.Graph(id="t2-chart-compare", config={"displayModeBar": False})]),
        # 누적 합계 차트
        html.Div(style=CARD_STYLE, children=[
            html.H3("월별 누적 설치 대수 (YTD)", style={"fontSize": "15px", "fontWeight": "600",
                                                       "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
            dcc.Graph(id="t2-chart-ytd", config={"displayModeBar": False})]),
        # 제품별 스택 바 (2개 연도 나란히)
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                        "gap": "16px", "marginBottom": "16px"}, children=[
            html.Div(style=CARD_STYLE, children=[
                html.H3(id="t2-stack-title1", style={"fontSize": "15px", "fontWeight": "600",
                                                      "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
                dcc.Graph(id="t2-chart-stack1", config={"displayModeBar": False})]),
            html.Div(style=CARD_STYLE, children=[
                html.H3(id="t2-stack-title2", style={"fontSize": "15px", "fontWeight": "600",
                                                      "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
                dcc.Graph(id="t2-chart-stack2", config={"displayModeBar": False})]),
        ]),
    ])

# ── 5단계 (약정 만료 알림) 레이아웃 ──
def tab3_layout():
    return html.Div([
        # 필터 영역
        html.Div(style=FILTER_STYLE, children=[
            html.Span("🔔 영업 활동 타겟 필터", style={"fontWeight": "600", "fontSize": "14px",
                                                    "color": TEXT_SECONDARY, "marginRight": "8px"}),
            html.Div([html.Label("대분류(그룹)", style={"fontSize": "12px", "color": TEXT_SECONDARY,
                                                      "marginBottom": "4px", "display": "block"}),
                      dcc.Dropdown(id="t3-filter-group",
                                   options=[{"label": g, "value": g} for g in 대분류_옵션],
                                   placeholder="전체", multi=True,
                                   style={"width": "200px", "fontSize": "13px"}, className="dark-dropdown")]),
            html.Div([html.Label("중분류(그룹사)", style={"fontSize": "12px", "color": TEXT_SECONDARY,
                                                       "marginBottom": "4px", "display": "block"}),
                      dcc.Dropdown(id="t3-filter-company",
                                   options=[{"label": c, "value": c} for c in 중분류_옵션],
                                   placeholder="전체 (대분류 선택 시 연동)", multi=True,
                                   style={"width": "300px", "fontSize": "13px"}, className="dark-dropdown")]),
        ]),
        
        # 차트 영역: 도넛 차트 & 바 차트
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 2fr", "gap": "16px", "marginBottom": "16px"}, children=[
            html.Div(style=CARD_STYLE, children=[
                html.H3("만료 상태 분류", style={"fontSize": "15px", "fontWeight": "600",
                                               "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
                dcc.Graph(id="t3-chart-donut", config={"displayModeBar": False})]),
            html.Div(style=CARD_STYLE, children=[
                html.H3("제품별 상세 만료 현황", style={"fontSize": "15px", "fontWeight": "600",
                                                          "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
                dcc.Graph(id="t3-chart-product-status", config={"displayModeBar": False})]),
        ]),
        
        # 타겟 리스트 테이블
        html.Div(style=CARD_STYLE, children=[
            html.H3("상세 타겟 요약 데이터 (중복 제거)", style={"fontSize": "15px", "fontWeight": "600",
                                                               "margin": "0 0 12px 0", "color": TEXT_SECONDARY}),
            html.Div(id="t3-sales-alert"),
            html.Div(id="t3-table-container")
        ]),
    ])

# ── 보안 시스템 레이아웃 ──
auth_layout = html.Div(
    id="auth-overlay",
    style={
        "position": "fixed",
        "top": 0, "left": 0, "width": "100vw", "height": "100vh",
        "backgroundColor": "rgba(17, 24, 39, 0.85)",
        "zIndex": 9999,
        "display": "flex",
        "justifyContent": "center",
        "alignItems": "center",
        "backdropFilter": "blur(5px)",
    },
    children=[
        html.Div(
            style={
                "backgroundColor": CARD_BG,
                "padding": "40px",
                "borderRadius": "16px",
                "boxShadow": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
                "width": "360px",
                "textAlign": "center",
            },
            children=[
                html.Div("🔒", style={"fontSize": "48px", "marginBottom": "16px"}),
                html.H2("보안 시스템", style={"margin": "0 0 8px 0", "color": TEXT_PRIMARY, "fontSize": "24px"}),
                html.P("대시보드에 접근하려면 비밀번호를 입력하세요.", style={"color": TEXT_SECONDARY, "fontSize": "14px", "marginBottom": "24px"}),
                dcc.Input(
                    id="auth-password-input",
                    type="password",
                    placeholder="비밀번호 입력",
                    style={
                        "width": "100%",
                        "padding": "12px 16px",
                        "borderRadius": "8px",
                        "border": f"1px solid {CARD_BORDER}",
                        "marginBottom": "16px",
                        "fontSize": "15px",
                        "boxSizing": "border-box",
                    },
                    n_submit=0,
                ),
                html.Button(
                    "접속하기",
                    id="auth-submit-btn",
                    n_clicks=0,
                    style={
                        "width": "100%",
                        "padding": "12px",
                        "backgroundColor": ACCENT_BLUE,
                        "color": "white",
                        "border": "none",
                        "borderRadius": "8px",
                        "fontSize": "15px",
                        "fontWeight": "600",
                        "cursor": "pointer",
                    }
                ),
                html.Div(id="auth-error-message", style={"color": ACCENT_RED, "fontSize": "13px", "marginTop": "16px", "minHeight": "20px"}),
            ]
        )
    ]
)

# ── 메인 레이아웃 (탭 구조) ──
dashboard_layout = html.Div(
    id="dashboard-container",
    style={"display": "none", "backgroundColor": BG_LIGHT, "minHeight": "100vh", "color": TEXT_PRIMARY,
           "fontFamily": "Pretendard, -apple-system, 'Segoe UI', sans-serif", "padding": "24px 32px"},
    children=[
        html.Div(style={"marginBottom": "20px"}, children=[
            html.H1("🏢 현대렌탈케어 법인영업 대시보드", style={
                "fontSize": "26px", "fontWeight": "700", "margin": "0", "letterSpacing": "-0.5px"})]),
        dcc.Tabs(id="main-tabs", value="tab-1", children=[
            dcc.Tab(label="📊 기업별 현황", value="tab-1", style=TAB_STYLE, selected_style=TAB_SELECTED),
            dcc.Tab(label="📈 월별 실적 비교", value="tab-2", style=TAB_STYLE, selected_style=TAB_SELECTED),
            dcc.Tab(label="🔔 약정 만료 알림 (영업지원)", value="tab-3", style=TAB_STYLE, selected_style=TAB_SELECTED),
        ], style={"marginBottom": "20px"}),
        html.Div(id="tab-content"),
    ],
)

app.layout = html.Div([
    auth_layout,
    dashboard_layout,
])


# ── 콜백: 대분류 선택 시 중분류 옵션 연동 ──
@app.callback(
    Output("filter-company", "options"),
    Input("filter-group", "value"),
)
def update_company_options(groups):
    """대분류 선택 시 해당 그룹 내 중분류만 표시합니다."""
    if groups:
        filtered_companies = df[df["대분류(그룹)"].isin(groups)]["중분류(그룹사)"].dropna().unique()
        return [{"label": c, "value": c} for c in sorted(filtered_companies)]
    return [{"label": c, "value": c} for c in 중분류_옵션]


# ── 콜백: 필터 → 전체 업데이트 ──
@app.callback(
    [
        Output("kpi-cards", "children"),
        Output("chart-product", "figure"),
        Output("chart-region", "figure"),
        Output("chart-group", "figure"),
        Output("chart-rental", "figure"),
        Output("chart-contract", "figure"),
        Output("chart-exchange", "figure"),
        Output("table-container", "children"),
        Output("chart-map", "figure"),
    ],
    [
        Input("filter-group", "value"),
        Input("filter-company", "value"),
    ],
)
def update_dashboard(groups, companies):
    """필터에 따라 대시보드 전체를 업데이트합니다."""
    filtered = df.copy()

    if groups:
        filtered = filtered[filtered["대분류(그룹)"].isin(groups)]
    if companies:
        filtered = filtered[filtered["중분류(그룹사)"].isin(companies)]

    # ── KPI (총 그룹사 수 → 총 기업수) ──
    total = len(filtered)
    companies_cnt = filtered["중분류(그룹사)"].nunique()
    valid_rental = filtered["렌탈료_숫자"].dropna()
    avg_rental = valid_rental.mean() if len(valid_rental) > 0 else 0
    prod_types = filtered["제품구분"].nunique()

    kpi_cards = [
        make_kpi_card("총 계정 수", f"{total:,}", "📋", ACCENT_BLUE),
        make_kpi_card("총 기업수", f"{companies_cnt:,}", "🏬", ACCENT_GREEN),
        make_kpi_card("평균 렌탈료", f"{avg_rental:,.0f}원", "💰", ACCENT_ORANGE),
        make_kpi_card("제품군 수", f"{prod_types}", "📦", ACCENT_RED),
    ]

    # ── 차트 1: 제품구분별 도넛 (고정 순서) ──
    product_counts = filtered["제품구분"].value_counts()
    # 고정 순서로 정렬, 데이터에 있는 것만
    ordered_labels = [p for p in 제품_순서 if p in product_counts.index]
    ordered_values = [product_counts[p] for p in ordered_labels]

    fig_product = go.Figure(data=[go.Pie(
        labels=ordered_labels,
        values=ordered_values,
        hole=0.55,
        marker=dict(colors=CHART_COLORS[:len(ordered_labels)]),
        textinfo="label+percent",
        textfont=dict(size=12, color=TEXT_PRIMARY),
        hovertemplate="<b>%{label}</b><br>건수: %{value:,}<br>비율: %{percent}<extra></extra>",
        sort=False,  # 순서 고정
    )])
    fig_product.update_layout(**PLOT_LAYOUT, height=400, showlegend=False)
    fig_product.update_layout(
        annotations=[dict(
            text=f"<b>{total:,}</b><br><span style='font-size:11px'>전체</span>",
            x=0.5, y=0.5, font_size=18, showarrow=False,
            font=dict(color=TEXT_PRIMARY),
        )]
    )

    # ── 차트 2: 지역별 바 차트 ──
    region_counts = filtered["지역구분"].value_counts().reset_index()
    region_counts.columns = ["지역구분", "건수"]
    region_counts = region_counts.sort_values("건수", ascending=True)

    fig_region = go.Figure(data=[go.Bar(
        y=region_counts["지역구분"],
        x=region_counts["건수"],
        orientation="h",
        marker=dict(color=ACCENT_BLUE, cornerradius=4),
        text=region_counts["건수"].apply(lambda x: f"{x:,}"),
        textposition="outside",
        textfont=dict(size=12, color=TEXT_SECONDARY),
        hovertemplate="<b>%{y}</b><br>설치 건수: %{x:,}<extra></extra>",
    )])
    fig_region.update_layout(**PLOT_LAYOUT, height=400)
    fig_region.update_xaxes(showgrid=False, showticklabels=False)
    fig_region.update_yaxes(showgrid=False)

    # ── 차트 3: 대분류 그룹별 바 차트 (고정 순서) ──
    group_vc = filtered["대분류(그룹)"].value_counts()
    # 고정 순서로 정렬, 데이터에 있는 것만
    ordered_groups = [g for g in 대분류_순서 if g in group_vc.index]
    rest_groups = [g for g in group_vc.index if g not in 대분류_순서]
    all_groups = ordered_groups + rest_groups
    group_labels = list(reversed(all_groups))  # 가로 바 차트는 위→아래이므로 역순
    group_values = [group_vc[g] for g in group_labels]

    fig_group = go.Figure(data=[go.Bar(
        y=group_labels,
        x=group_values,
        orientation="h",
        marker=dict(color=ACCENT_GREEN, cornerradius=4),
        text=[f"{v:,}" for v in group_values],
        textposition="outside",
        textfont=dict(size=12, color=TEXT_SECONDARY),
        hovertemplate="<b>%{y}</b><br>설치 건수: %{x:,}<extra></extra>",
    )])
    fig_group.update_layout(**PLOT_LAYOUT, height=400)
    fig_group.update_xaxes(showgrid=False, showticklabels=False)
    fig_group.update_yaxes(showgrid=False)

    # ── 차트 4: 렌탈료 커스텀 구간별 바 차트 ──
    rental_valid = filtered["렌탈료_숫자"].dropna()
    구간_labels = [label for label, _, _ in 렌탈료_구간]
    구간_counts = []
    for label, low, high in 렌탈료_구간:
        cnt = ((rental_valid >= low) & (rental_valid < high)).sum()
        구간_counts.append(cnt)

    bar_colors = [ACCENT_ORANGE] * len(구간_labels)

    fig_rental = go.Figure(data=[go.Bar(
        x=구간_labels,
        y=구간_counts,
        marker=dict(
            color=bar_colors,
            cornerradius=4,
            line=dict(color="#1a1d29", width=1),
        ),
        text=[f"{c:,}" for c in 구간_counts],
        textposition="outside",
        textfont=dict(size=12, color=TEXT_SECONDARY),
        hovertemplate="<b>%{x}</b><br>건수: %{y:,}<extra></extra>",
    )])
    fig_rental.update_layout(**PLOT_LAYOUT, height=400)
    fig_rental.update_xaxes(
        tickangle=-30,
        tickfont=dict(size=12),
        showgrid=False,
    )
    fig_rental.update_yaxes(
        title_text="",
        showgrid=False,
        showticklabels=False,
    )

    # ── 차트 5: 의무약정 만료 현황 (추가) ──
    contract_counts = filtered["의무약정만료여부"].value_counts().reset_index()
    contract_counts.columns = ["상태", "건수"]

    status_colors = {
        "만료됨": ACCENT_RED,
        "이용 중": ACCENT_GREEN,
        "만료 예정": ACCENT_ORANGE,
    }
    colors = [status_colors.get(s, ACCENT_BLUE) for s in contract_counts["상태"]]

    fig_contract = go.Figure(data=[go.Pie(
        labels=contract_counts["상태"],
        values=contract_counts["건수"],
        hole=0.55,
        marker=dict(colors=colors),
        textinfo="label+percent",
        textfont=dict(size=12, color=TEXT_PRIMARY),
        hovertemplate="<b>%{label}</b><br>건수: %{value:,}<br>비율: %{percent}<extra></extra>",
    )])
    fig_contract.update_layout(**PLOT_LAYOUT, height=400, showlegend=False)

    # ── 차트 6: 최소교환주기별 현황 (개월 단위 구간) ──
    exchange_raw = pd.to_numeric(filtered["최소교환주기"], errors="coerce")
    # 개월 단위 구간별 집계
    구간_map = {
        "1개월": 1, "2개월": 2, "3개월": 3, "4개월": 4,
        "6개월": 6, "12개월": 12, "24개월": 24, "36개월": 36,
    }
    exchange_labels = []
    exchange_values = []
    for label in 교환주기_구간:
        if label == "없음":
            cnt = int(exchange_raw.isna().sum())
        else:
            val = 구간_map[label]
            cnt = int((exchange_raw == val).sum())
        exchange_labels.append(label)
        exchange_values.append(cnt)

    fig_exchange = go.Figure(data=[go.Bar(
        x=exchange_labels,
        y=exchange_values,
        marker=dict(color=ACCENT_PURPLE, cornerradius=4),
        text=[f"{v:,}" for v in exchange_values],
        textposition="outside",
        textfont=dict(size=12, color=TEXT_SECONDARY),
        hovertemplate="<b>%{x}</b><br>건수: %{y:,}<extra></extra>",
    )])
    fig_exchange.update_layout(**PLOT_LAYOUT, height=400)
    fig_exchange.update_xaxes(showgrid=False, tickangle=-30, tickfont=dict(size=12))
    fig_exchange.update_yaxes(showgrid=False, showticklabels=False)

    # ── 테이블: 모든 중분류 기업 반영, 20개 페이지네이션, 가운데 정렬 ──
    company_df = get_company_summary(filtered)

    table = dash_table.DataTable(
        data=company_df.to_dict("records"),  # 모든 기업 반영 (head 제거)
        columns=[
            {"name": "기업명", "id": "중분류(그룹사)"},
            {"name": "설치대수", "id": "설치대수", "type": "numeric",
             "format": dash_table.Format.Format().group(True)},
            {"name": "평균렌탈료", "id": "평균렌탈료", "type": "numeric",
             "format": dash_table.Format.Format(
                 precision=0, scheme=dash_table.Format.Scheme.fixed
             ).group(True)},
            {"name": "주요지역", "id": "주요지역"},
            {"name": "제품구분", "id": "제품구분목록"},
        ],
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f3f4f6",
            "color": "#111827",
            "fontWeight": "600",
            "fontSize": "13px",
            "border": f"1px solid {CARD_BORDER}",
            "padding": "10px 12px",
            "textAlign": "center",
        },
        style_cell={
            "backgroundColor": CARD_BG,
            "color": "#4b5563",
            "fontSize": "13px",
            "border": f"1px solid {CARD_BORDER}",
            "padding": "8px 12px",
            "textAlign": "center",  # 가운데 정렬
            "maxWidth": "300px",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "#f9fafb",
            },
        ],
        page_size=20,  # 20개씩 페이지네이션
        sort_action="native",
        filter_action="native",
    )

    # ── 3단계: 시도별 지도 ──
    region_data = get_region_counts(filtered)
    fig_map = go.Figure(go.Choroplethmapbox(
        geojson=KOREA_GEO,
        locations=region_data["시도명"],
        z=region_data["건수"],
        featureidkey="properties.name",
        colorscale=[[0, "#e0f2fe"], [0.3, "#7dd3fc"], [0.6, "#0284c7"], [1, "#0369a1"]],
        marker=dict(opacity=0.8, line=dict(width=1, color="#ffffff")),
        hovertemplate="<b>%{location}</b><br>설치 건수: %{z:,}<extra></extra>",
        colorbar=dict(title=dict(text="건수", font=dict(color=TEXT_SECONDARY)),
                      tickfont=dict(color=TEXT_SECONDARY), bgcolor="rgba(0,0,0,0)"),
    ))
    fig_map.update_layout(
        mapbox=dict(style="carto-positron", center=dict(lat=36.5, lon=127.5), zoom=5.5),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_PRIMARY), margin=dict(l=0, r=0, t=10, b=10), height=550,
    )

    return (kpi_cards, fig_product, fig_region, fig_group,
            fig_rental, fig_contract, fig_exchange, table, fig_map)


# ── 콜백: 탭 전환 ──
@app.callback(Output("tab-content", "children"), Input("main-tabs", "value"))
def render_tab(tab):
    if tab == "tab-1":
        return tab1_layout()
    elif tab == "tab-2":
        return tab2_layout()
    elif tab == "tab-3":
        return tab3_layout()


# ── 콜백: 2단계 차트 업데이트 ──
@app.callback(
    [Output("t2-chart-compare", "figure"),
     Output("t2-chart-ytd", "figure"),
     Output("t2-chart-stack1", "figure"),
     Output("t2-chart-stack2", "figure"),
     Output("t2-stack-title1", "children"),
     Output("t2-stack-title2", "children")],
    [Input("t2-year1", "value"),
     Input("t2-year2", "value"),
     Input("t2-filter-group", "value")],
)
def update_tab2(year1, year2, groups):
    filtered = df.copy()
    if groups:
        filtered = filtered[filtered["대분류(그룹)"].isin(groups)]
    fig_compare = make_comparison_chart(filtered, year1, year2)
    fig_ytd = make_ytd_chart(filtered, year1, year2)
    fig_stack1 = make_product_stack_chart(filtered, year1)
    fig_stack2 = make_product_stack_chart(filtered, year2)
    return (fig_compare, fig_ytd, fig_stack1, fig_stack2,
            f"{year1}년 제품구분별 월별 설치", f"{year2}년 제품구분별 월별 설치")


# ── 콜백: 5단계 필터 연동 ──
@app.callback(
    Output("t3-filter-company", "options"),
    Input("t3-filter-group", "value"),
)
def update_t3_company_options(groups):
    if groups:
        filtered_companies = df[df["대분류(그룹)"].isin(groups)]["중분류(그룹사)"].dropna().unique()
        return [{"label": c, "value": c} for c in sorted(filtered_companies)]
    return [{"label": c, "value": c} for c in 중분류_옵션]

# ── 콜백: 5단계 약정 만료 알림 업데이트 ──
@app.callback(
    [Output("t3-chart-donut", "figure"),
     Output("t3-chart-product-status", "figure"),
     Output("t3-sales-alert", "children"),
     Output("t3-table-container", "children")],
    [Input("t3-filter-group", "value"),
     Input("t3-filter-company", "value")],
)
def update_tab3(groups, companies):
    filtered = df.copy()
    if groups:
        filtered = filtered[filtered["대분류(그룹)"].isin(groups)]
        
    fig_donut = make_expiration_donut(filtered)
    
    # 중분류 필터가 걸려있을 때만 상세 차트 및 테이블 렌더링
    if companies:
        filtered_comp = filtered[filtered["중분류(그룹사)"].isin(companies)]
        fig_bar = make_product_status_chart(filtered_comp)
        alert = make_sales_alert(filtered_comp)
        table = make_summary_target_table(filtered_comp)
    else:
        # 필터가 없을 때는 빈 차트와 안내 메시지 반환 (속도 대폭 개선)
        empty_fig = go.Figure()
        empty_fig.update_layout(**PLOT_LAYOUT, height=350)
        empty_fig.add_annotation(text="👆 중분류(그룹사)를 선택하면<br>제품별 만료 현황이 표시됩니다.", 
                                 x=0.5, y=0.5, showarrow=False, font=dict(size=14, color=TEXT_SECONDARY))
        empty_fig.update_xaxes(visible=False)
        empty_fig.update_yaxes(visible=False)
        
        table = html.Div("👆 중분류(그룹사)를 선택하면 상세 요약 데이터를 확인할 수 있습니다.", 
                         style={"textAlign": "center", "color": TEXT_SECONDARY, "padding": "40px 0", "fontSize": "14px"})
        
        fig_bar = empty_fig
        alert = None
        
    return fig_donut, fig_bar, alert, table


# ── 콜백: 로그인 보안 인증 ──
@app.callback(
    [Output("auth-overlay", "style"),
     Output("dashboard-container", "style"),
     Output("auth-error-message", "children")],
    [Input("auth-submit-btn", "n_clicks"),
     Input("auth-password-input", "n_submit")],
    [State("auth-password-input", "value"),
     State("auth-overlay", "style")]
)
def authenticate(n_clicks, n_submit, password, overlay_style):
    if n_clicks == 0 and n_submit == 0:
        return dash.no_update, dash.no_update, dash.no_update
    
    if not password:
        return dash.no_update, dash.no_update, "비밀번호를 입력해주세요."
        
    secret_path = os.path.join(os.path.dirname(__file__), "secrets.json")
    correct_password = ""
    try:
        with open(secret_path, "r", encoding="utf-8") as f:
            secrets = json.load(f)
            correct_password = secrets.get("PASSWORD", "")
    except FileNotFoundError:
        return dash.no_update, dash.no_update, "보안 파일(secrets.json)을 찾을 수 없습니다."
        
    if password == correct_password:
        hidden_overlay = overlay_style.copy()
        hidden_overlay["display"] = "none"
        visible_dashboard = {"display": "block"}
        return hidden_overlay, visible_dashboard, ""
    else:
        return dash.no_update, dash.no_update, "비밀번호가 일치하지 않습니다."


# ── 실행 ──
if __name__ == "__main__":
    app.run(debug=True, port=8050)
