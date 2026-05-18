import streamlit as st
import json
import os
import pandas as pd
import plotly.graph_objects as go
from preprocess import (load_data, get_summary_stats, get_company_summary,
                        get_available_years, get_region_counts)
from tab2_charts import make_comparison_chart, make_ytd_chart, make_product_stack_chart
from tab4_expiration import (make_expiration_donut, make_product_status_chart)

# ── 차트 설정 및 상수 ──
제품_순서 = ["정수기", "공기청정기", "비데", "커피머신", "제빙기", "기타"]
대분류_순서 = ["현대백화점그룹", "현대자동차그룹", "HD현대", "일반기업", "관공서 및 정부기관", "교육시설", "비영리법인"]
교환주기_구간 = ["1개월", "2개월", "3개월", "4개월", "6개월", "12개월", "24개월", "36개월", "없음"]
렌탈료_구간 = [
    ("1만원 이하", 0, 10000), ("1만~1.2만", 10000, 12000), ("1.2만~1.5만", 12000, 15000),
    ("1.5만~2만", 15000, 20000), ("2만~3만", 20000, 30000), ("3만~5만", 30000, 50000),
    ("5만~10만", 50000, 100000), ("10만원 이상", 100000, float("inf")),
]
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#4b5563"
ACCENT_BLUE = "#2563eb"
ACCENT_GREEN = "#10b981"
ACCENT_ORANGE = "#f59e0b"
ACCENT_RED = "#ef4444"
ACCENT_PURPLE = "#8b5cf6"
CHART_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#64748b"]

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT_PRIMARY, family="Pretendard, sans-serif"),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_SECONDARY)),
)

st.set_page_config(page_title="현대렌탈케어 대시보드", page_icon="🏢", layout="wide")

# ── 1. 패스워드 인증 ──
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    def password_entered():
        secret_path = os.path.join(os.path.dirname(__file__), "secrets.json")
        try:
            with open(secret_path, "r", encoding="utf-8") as f:
                secrets = json.load(f)
                correct_password = secrets.get("PASSWORD", "")
        except FileNotFoundError:
            st.session_state["password_correct"] = True
            return

        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
            st.error("😕 비밀번호가 일치하지 않습니다.")

    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align: center;'>🔒 보안 시스템</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>대시보드에 접근하려면 비밀번호를 입력하세요.</p>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("비밀번호", type="password", on_change=password_entered, key="password", label_visibility="collapsed")
        return False
    return True

if not check_password():
    st.stop()

# ── 2. 파일 업로드 및 데이터 로드 ──
st.title("🏢 현대렌탈케어 법인영업 대시보드")
st.sidebar.header("📁 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("최신 CSV 파일을 업로드하세요", type=["csv"])

@st.cache_data
def load_processed_data(file_obj):
    return load_data(file_obj)

try:
    if uploaded_file is not None:
        df = load_processed_data(uploaded_file)
    else:
        df = load_processed_data(None)
except Exception as e:
    st.info("데이터 파일을 찾을 수 없습니다. 좌측 사이드바에서 CSV 파일을 업로드해주세요.")
    st.stop()

# GeoJSON 로드
KOREA_GEO = None
geo_error_msg = ""
possible_paths = [
    os.path.join(os.path.dirname(__file__), "data", "korea_provinces.json"),
    "data/korea_provinces.json",
    "korea_provinces.json"
]

for path in possible_paths:
    try:
        with open(path, encoding="utf-8") as f:
            KOREA_GEO = json.load(f)
            break
    except Exception as e:
        geo_error_msg = str(e)
        continue

if KOREA_GEO is None:
    st.sidebar.warning(f"지도 데이터를 찾을 수 없습니다: {geo_error_msg}")

# 필터 옵션 추출
대분류_옵션 = sorted(df["대분류(그룹)"].dropna().unique())
중분류_옵션 = sorted(df["중분류(그룹사)"].dropna().unique())
연도_옵션 = get_available_years(df)

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 필터 (전체 탭 적용)")
selected_groups = st.sidebar.multiselect("대분류(그룹)", options=대분류_옵션)

if selected_groups:
    filtered_companies = df[df["대분류(그룹)"].isin(selected_groups)]["중분류(그룹사)"].dropna().unique()
    company_options = sorted(filtered_companies)
else:
    company_options = 중분류_옵션

selected_companies = st.sidebar.multiselect("중분류(그룹사)", options=company_options)

# 데이터 필터링 적용
filtered_df = df.copy()
if selected_groups:
    filtered_df = filtered_df[filtered_df["대분류(그룹)"].isin(selected_groups)]
if selected_companies:
    filtered_df = filtered_df[filtered_df["중분류(그룹사)"].isin(selected_companies)]

# ── 3. 탭 구성 ──
tab1, tab2, tab3 = st.tabs(["📊 기업별 현황", "📈 월별 실적 비교", "🔔 약정 만료 알림 (영업지원)"])

with tab1:
    stats = get_summary_stats(filtered_df)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 계정 수", stats["총 계정 수"])
    col2.metric("총 기업수", stats["총 그룹사 수"])
    col3.metric("평균 렌탈료", stats["평균 렌탈료"])
    col4.metric("제품군 수", stats["제품군 수"])
    
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("제품구분별 설치 현황")
        product_counts = filtered_df["제품구분"].value_counts()
        ordered_labels = [p for p in 제품_순서 if p in product_counts.index]
        ordered_values = [product_counts[p] for p in ordered_labels]
        fig_product = go.Figure(data=[go.Pie(
            labels=ordered_labels, values=ordered_values, hole=0.55,
            marker=dict(colors=CHART_COLORS[:len(ordered_labels)]),
            textinfo="label+percent", textfont=dict(size=12, color=TEXT_PRIMARY), sort=False
        )])
        fig_product.update_layout(**PLOT_LAYOUT, height=400, showlegend=False)
        st.plotly_chart(fig_product, use_container_width=True)

    with c2:
        st.subheader("지역별 설치 현황")
        region_counts = filtered_df["지역구분"].value_counts().reset_index()
        region_counts.columns = ["지역구분", "건수"]
        region_counts = region_counts.sort_values("건수", ascending=True)
        fig_region = go.Figure(data=[go.Bar(
            y=region_counts["지역구분"], x=region_counts["건수"], orientation="h",
            marker=dict(color=ACCENT_BLUE, cornerradius=4),
            text=region_counts["건수"].apply(lambda x: f"{x:,}"),
            textposition="outside", textfont=dict(size=12, color=TEXT_SECONDARY)
        )])
        fig_region.update_layout(**PLOT_LAYOUT, height=400)
        fig_region.update_xaxes(showgrid=False, showticklabels=False)
        fig_region.update_yaxes(showgrid=False)
        st.plotly_chart(fig_region, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("대분류(그룹)별 설치 현황")
        group_vc = filtered_df["대분류(그룹)"].value_counts()
        ordered_groups = [g for g in 대분류_순서 if g in group_vc.index]
        rest_groups = [g for g in group_vc.index if g not in 대분류_순서]
        all_groups = ordered_groups + rest_groups
        group_labels = list(reversed(all_groups))
        group_values = [group_vc[g] for g in group_labels]
        fig_group = go.Figure(data=[go.Bar(
            y=group_labels, x=group_values, orientation="h",
            marker=dict(color=ACCENT_GREEN, cornerradius=4),
            text=[f"{v:,}" for v in group_values],
            textposition="outside", textfont=dict(size=12, color=TEXT_SECONDARY)
        )])
        fig_group.update_layout(**PLOT_LAYOUT, height=400)
        fig_group.update_xaxes(showgrid=False, showticklabels=False)
        fig_group.update_yaxes(showgrid=False)
        st.plotly_chart(fig_group, use_container_width=True)

    with c4:
        st.subheader("렌탈료 구간별 분포")
        rental_valid = filtered_df["렌탈료_숫자"].dropna()
        구간_labels = [label for label, _, _ in 렌탈료_구간]
        구간_counts = [((rental_valid >= low) & (rental_valid < high)).sum() for label, low, high in 렌탈료_구간]
        fig_rental = go.Figure(data=[go.Bar(
            x=구간_labels, y=구간_counts, marker=dict(color=[ACCENT_ORANGE]*len(구간_labels), cornerradius=4),
            text=[f"{c:,}" for c in 구간_counts], textposition="outside", textfont=dict(size=12, color=TEXT_SECONDARY)
        )])
        fig_rental.update_layout(**PLOT_LAYOUT, height=400)
        fig_rental.update_xaxes(tickangle=-30, tickfont=dict(size=12), showgrid=False)
        fig_rental.update_yaxes(showgrid=False, showticklabels=False)
        st.plotly_chart(fig_rental, use_container_width=True)
        
    st.markdown("---")
    st.subheader("기업별 상세 현황")
    company_df = get_company_summary(filtered_df)
    st.dataframe(company_df, use_container_width=True)

    st.markdown("---")
    st.subheader("🗺️ 시도별 설치 현황 지도")
    if KOREA_GEO:
        region_data = get_region_counts(filtered_df)
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
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.warning("지도 데이터(korea_provinces.json)를 불러올 수 없어 지도를 표시할 수 없습니다.")

with tab2:
    st.subheader("📈 월별 실적 비교")
    if len(연도_옵션) >= 2:
        default_y1, default_y2 = 연도_옵션[1], 연도_옵션[0]
    else:
        default_y1 = default_y2 = 연도_옵션[0] if 연도_옵션 else "2024"
        
    y1, y2 = st.columns(2)
    year1 = y1.selectbox("비교 연도 1", 연도_옵션, index=연도_옵션.index(default_y1) if default_y1 in 연도_옵션 else 0)
    year2 = y2.selectbox("비교 연도 2", 연도_옵션, index=연도_옵션.index(default_y2) if default_y2 in 연도_옵션 else 0)
    
    fig_compare = make_comparison_chart(filtered_df, year1, year2)
    st.plotly_chart(fig_compare, use_container_width=True)
    
    fig_ytd = make_ytd_chart(filtered_df, year1, year2)
    st.plotly_chart(fig_ytd, use_container_width=True)

with tab3:
    st.subheader("🔔 약정 만료 알림 (영업지원)")
    if selected_companies:
        # 영업 알림 텍스트 표시
        total_count = len(filtered_df)
        expired_count = len(filtered_df[filtered_df["만료상태"] == "의무약정 만료"])
        expiring_3m = len(filtered_df[filtered_df["만료상태"] == "3개월 이내 만료 예정"])
        expiring_6m = len(filtered_df[filtered_df["만료상태"] == "6개월 이내 만료 예정"])
        target_count = expired_count + expiring_3m + expiring_6m
        
        if total_count > 0:
            alert_text = (f"선택하신 기업은 총 **{total_count:,}**개의 제품을 사용 중이며, "
                          f"그 중 **{expired_count:,}**개가 의무기간 만료, "
                          f"**{expiring_3m + expiring_6m:,}**개가 만료 예정입니다. ")
            if target_count > 0:
                alert_text += "따라서 재렌탈(또는 신규 교환) 영업이 필요합니다!"
                st.error(f"🔔 {alert_text}")
            else:
                alert_text += "현재 만료 또는 만료 예정인 대상이 없습니다. 지속적인 관리가 필요합니다."
                st.success(f"🔔 {alert_text}")
                
        c1, c2 = st.columns([1, 2])
        with c1:
            st.plotly_chart(make_expiration_donut(filtered_df), use_container_width=True)
        with c2:
            st.plotly_chart(make_product_status_chart(filtered_df), use_container_width=True)
        
        # DataFrame 직접 생성 (Dash Table 대신)
        group_cols = ["제품구분", "제품명", "의무약정만료일자", "만료상태", "렌탈료(수정중)"]
        STATUS_ORDER = ["의무약정 만료", "3개월 이내 만료 예정", "6개월 이내 만료 예정", "이용 중"]
        table_df = filtered_df[group_cols].copy()
        table_df["만료상태"] = pd.Categorical(table_df["만료상태"], categories=STATUS_ORDER, ordered=True)
        summary_df = table_df.groupby(group_cols, dropna=False).size().reset_index(name="수량")
        summary_df = summary_df[summary_df["수량"] > 0]
        summary_df = summary_df.sort_values(by=["만료상태", "의무약정만료일자", "수량"], ascending=[True, True, False])
        summary_df["만료상태"] = summary_df["만료상태"].astype(str)
        st.dataframe(summary_df, use_container_width=True)
    else:
        st.info("👆 좌측 사이드바에서 중분류(그룹사)를 선택하시면 상세 만료 현황이 표시됩니다.")
