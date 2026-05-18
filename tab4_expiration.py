# -*- coding: utf-8 -*-
"""5단계 탭: 의무약정 만료에 따른 영업 활동 지원 알림"""
import plotly.graph_objects as go
import pandas as pd
from dash import dash_table

제품_순서 = ["정수기", "공기청정기", "비데", "커피머신", "제빙기", "기타"]

CHART_COLORS = ["#ef4444", "#f59e0b", "#fbbf24", "#e5e7eb"]
# 만료, 3개월, 6개월, 이용 중 순

TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#4b5563"
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT_PRIMARY, family="Pretendard, sans-serif"),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_SECONDARY)),
)

STATUS_ORDER = ["의무약정 만료", "3개월 이내 만료 예정", "6개월 이내 만료 예정", "이용 중"]


def make_expiration_donut(df):
    """만료 상태 비율 도넛 차트"""
    counts = df["만료상태"].value_counts().reindex(STATUS_ORDER).fillna(0)
    
    fig = go.Figure(data=[go.Pie(
        labels=counts.index,
        values=counts.values,
        hole=0.5,
        marker=dict(colors=CHART_COLORS, line=dict(color="#1a1d29", width=2)),
        textinfo="percent+label",
        textposition="outside",
        textfont=dict(color=TEXT_PRIMARY, size=12),
        hovertemplate="<b>%{label}</b><br>%{value:,}건<extra></extra>"
    )])
    fig.update_layout(**PLOT_LAYOUT, height=350, showlegend=False)
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20))
    # 가운데 총합 텍스트
    total_target = counts["의무약정 만료"] + counts["3개월 이내 만료 예정"] + counts["6개월 이내 만료 예정"]
    fig.add_annotation(text=f"타겟<br><b>{int(total_target):,}</b>건", 
                       x=0.5, y=0.5, font=dict(size=18, color="#e85d5d"), showarrow=False)
    return fig


def make_product_status_chart(df):
    """제품별 만료 상태 스택 바 차트"""
    fig = go.Figure()
    
    # 제품구분 x 만료상태 집계
    grouped = df.groupby(["제품구분", "만료상태"]).size().unstack(fill_value=0)
    
    # 고정 순서 정렬
    prods = [p for p in 제품_순서 if p in grouped.index]
    rest = [p for p in grouped.index if p not in 제품_순서]
    ordered_prods = prods + rest
    grouped = grouped.reindex(ordered_prods)
    
    for i, status in enumerate(STATUS_ORDER):
        if status in grouped.columns:
            values = grouped[status].values
            fig.add_trace(go.Bar(
                name=status, x=grouped.index, y=values,
                marker=dict(color=CHART_COLORS[i], cornerradius=2),
                hovertemplate=f"<b>%{{x}}</b><br>{status}: %{{y:,}}건<extra></extra>",
            ))
            
    fig.update_layout(**PLOT_LAYOUT, height=350, barmode="stack")
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_xaxes(showgrid=False, tickfont=dict(color=TEXT_SECONDARY))
    fig.update_yaxes(showgrid=True, gridcolor="#e5e7eb", tickfont=dict(color=TEXT_SECONDARY))
    return fig


def make_summary_target_table(df):
    """영업 활동 지원을 위한 제품별 요약 리스트 (DataTable) - 중복 제거 및 수량 표시"""
    group_cols = ["제품구분", "제품명", "의무약정만료일자", "만료상태", "렌탈료(수정중)"]
    table_df = df[group_cols].copy()
    
    # 지정된 정렬 순서를 위해 Categorical 타입 적용
    table_df["만료상태"] = pd.Categorical(
        table_df["만료상태"], 
        categories=STATUS_ORDER, 
        ordered=True
    )
    
    # groupby로 수량(건수) 계산
    # dropna=False를 통해 결측치 그룹도 보존 (필요 시 fillna 처리 가능)
    summary_df = table_df.groupby(group_cols, dropna=False).size().reset_index(name="수량")
    summary_df = summary_df[summary_df["수량"] > 0]
    
    # 정렬: 만료상태 -> 만료일자(가까운순) -> 수량(많은순)
    summary_df = summary_df.sort_values(by=["만료상태", "의무약정만료일자", "수량"], ascending=[True, True, False])
    summary_df["만료상태"] = summary_df["만료상태"].astype(str)
    
    cols = group_cols + ["수량"]
    
    # 데이터가 너무 많을 경우 프론트엔드 렌더링이 느려지므로 가상화 옵션 추가
    table = dash_table.DataTable(
        data=summary_df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in cols],
        virtualization=True, # 렌더링 속도 최적화
        page_action="none",  # 가상화를 위해 페이지네이션 대신 스크롤 사용
        fixed_rows={'headers': True},
        style_table={'height': '400px', 'overflowY': 'auto'},
        style_header={
            "backgroundColor": "#f3f4f6", "color": "#111827",
            "fontWeight": "700", "border": "none", "borderBottom": "1px solid #e5e7eb",
            "textAlign": "center", "padding": "12px"
        },
        style_cell={
            "backgroundColor": "#ffffff", "color": TEXT_SECONDARY,
            "border": "none", "borderBottom": "1px solid #f3f4f6",
            "textAlign": "center", "padding": "12px",
            "fontFamily": "Pretendard, sans-serif", "fontSize": "13px",
            "overflow": "hidden", "textOverflow": "ellipsis", "maxWidth": 0,
        },
        style_data_conditional=[
            {
                "if": {"filter_query": "{만료상태} = '의무약정 만료'", "column_id": "만료상태"},
                "color": "#ef4444", "fontWeight": "bold"
            },
            {
                "if": {"filter_query": "{만료상태} = '3개월 이내 만료 예정'", "column_id": "만료상태"},
                "color": "#f59e0b", "fontWeight": "bold"
            },
            {
                "if": {"filter_query": "{만료상태} = '6개월 이내 만료 예정'", "column_id": "만료상태"},
                "color": "#fbbf24", "fontWeight": "bold"
            },
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "#f9fafb",
            },
        ],
        sort_action="native",
        filter_action="native",
    )
    return table

def make_sales_alert(df):
    """영업 활동을 위한 커스텀 알림 텍스트 생성"""
    from dash import html
    total_count = len(df)
    expired_count = len(df[df["만료상태"] == "의무약정 만료"])
    expiring_3m = len(df[df["만료상태"] == "3개월 이내 만료 예정"])
    expiring_6m = len(df[df["만료상태"] == "6개월 이내 만료 예정"])
    
    target_count = expired_count + expiring_3m + expiring_6m
    
    if total_count == 0:
        return html.Div()
        
    text = (f"🔔 선택하신 기업은 총 {total_count:,}개의 제품을 사용 중이며, "
            f"그 중 {expired_count:,}개가 의무기간 만료, "
            f"{expiring_3m + expiring_6m:,}개가 만료 예정입니다. ")
            
    if target_count > 0:
        text += "따라서 재렌탈(또는 신규 교환) 영업이 필요합니다!"
        color = "#b91c1c" # 붉은 계열 텍스트
        bg = "#fee2e2"    # 연한 붉은 배경
        border = "1px solid #fca5a5"
    else:
        text += "현재 만료 또는 만료 예정인 대상이 없습니다. 지속적인 관리가 필요합니다."
        color = "#047857" # 초록 계열 텍스트
        bg = "#d1fae5"    # 연한 초록 배경
        border = "1px solid #6ee7b7"
        
    return html.Div(
        text,
        style={
            "padding": "16px 20px",
            "backgroundColor": bg,
            "border": border,
            "borderRadius": "8px",
            "color": color,
            "fontWeight": "600",
            "fontSize": "15px",
            "marginBottom": "16px",
            "display": "flex",
            "alignItems": "center",
            "lineHeight": "1.5"
        }
    )
