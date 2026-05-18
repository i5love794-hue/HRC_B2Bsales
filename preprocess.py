# -*- coding: utf-8 -*-
"""
법인계정 데이터 전처리 모듈
- CSV 로드
- 렌탈료 파싱 ("확인 중" 제외, 쉼표 제거 후 숫자 변환)
- 기업별(중분류 그룹사) 집계
"""

import pandas as pd
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

# 데이터 파일 경로
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CSV_FILENAME = "법인계정리스트_2605 - 법인계정_소유권이전&멤버십x(~26.04까지).csv"
CSV_PATH = os.path.join(DATA_DIR, CSV_FILENAME)


def load_data(file_obj=None) -> pd.DataFrame:
    """CSV 파일을 로드하고 기본 전처리를 수행합니다."""
    if file_obj is not None:
        df = pd.read_csv(file_obj, encoding="utf-8", dtype=str)
    else:
        df = pd.read_csv(CSV_PATH, encoding="utf-8", dtype=str)

    # 컬럼명 앞뒤 공백 제거 및 줄바꿈 제거
    df.columns = [c.strip().replace("\n", "") for c in df.columns]

    # 주요 컬럼 앞뒤 공백 제거
    strip_cols = [
        "대분류(그룹)", "중분류(그룹사)", "지역구분", "지역_1",
        "제품구분", "제품명", "회사명", "법인구분", "납부방법",
        "의무약정만료여부", "렌탈만료여부", "설치일자"
    ]
    for col in strip_cols:
        if col in df.columns:
            df[col] = df[col].str.strip()

    # 렌탈료 파싱: "확인 중" -> NaN, 쉼표 제거 후 숫자 변환
    rental_col = "렌탈료(수정중)"
    if rental_col in df.columns:
        df["렌탈료_숫자"] = pd.to_numeric(
            df[rental_col].str.replace(",", "", regex=False),
            errors="coerce"
        )
    else:
        df["렌탈료_숫자"] = pd.NA

    # 교환예정일 사전 계산 (성능 최적화)
    df = _calculate_exchange_dates(df)
    
    # 약정 만료 상태 사전 계산
    df = _calculate_expiration(df)

    return df

def _calculate_exchange_dates(df: pd.DataFrame) -> pd.DataFrame:
    """설치일자 + 최소교환주기로 다음 교환 예정월을 미리 계산 (수학적 연산으로 최적화)"""
    today = datetime.now()
    df["교환주기"] = pd.to_numeric(df["최소교환주기"], errors="coerce")
    df["설치일"] = pd.to_datetime(df["설치일자"], format="%Y%m%d", errors="coerce")

    def _next_date(row):
        install = row["설치일"]
        cycle = row["교환주기"]
        if pd.isna(install) or pd.isna(cycle) or cycle <= 0:
            return pd.NaT
            
        diff_y = today.year - install.year
        diff_m = today.month - install.month
        total_diff_m = diff_y * 12 + diff_m
        
        if total_diff_m < 0:
            dt = install + relativedelta(months=int(cycle))
        else:
            cycles_passed = total_diff_m // cycle
            dt = install + relativedelta(months=int(cycles_passed * cycle))
            if dt < today:
                dt += relativedelta(months=int(cycle))
            if dt < today:
                dt += relativedelta(months=int(cycle))
        return dt

    df["다음교환예정일"] = df.apply(_next_date, axis=1)
    df["예정년월"] = df["다음교환예정일"].dt.to_period("M").astype(str)
    return df


def _calculate_expiration(df: pd.DataFrame) -> pd.DataFrame:
    """의무약정만료일자를 기준으로 만료 상태를 계산 (벡터화로 최적화)"""
    today = pd.Timestamp(datetime.now().date()) # 시간 제외
    month3 = today + pd.DateOffset(months=3)
    month6 = today + pd.DateOffset(months=6)

    df["약정만료일"] = pd.to_datetime(df["의무약정만료일자"], format="%Y%m%d", errors="coerce")
    
    df["만료상태"] = "이용 중"
    df.loc[df["약정만료일"].isna(), "만료상태"] = "이용 중"
    df.loc[df["약정만료일"] <= month6, "만료상태"] = "6개월 이내 만료 예정"
    df.loc[df["약정만료일"] <= month3, "만료상태"] = "3개월 이내 만료 예정"
    df.loc[df["약정만료일"] < today, "만료상태"] = "의무약정 만료"

    return df


def get_summary_stats(df: pd.DataFrame) -> dict:
    """KPI 카드에 사용할 요약 통계를 반환합니다."""
    total_accounts = len(df)
    total_companies = df["중분류(그룹사)"].nunique()
    valid_rental = df["렌탈료_숫자"].dropna()
    avg_rental = valid_rental.mean() if len(valid_rental) > 0 else 0
    product_types = df["제품구분"].nunique()

    return {
        "총 계정 수": f"{total_accounts:,}",
        "총 그룹사 수": f"{total_companies:,}",
        "평균 렌탈료": f"{avg_rental:,.0f}원",
        "제품군 수": f"{product_types}",
    }


def get_company_summary(df: pd.DataFrame) -> pd.DataFrame:
    """중분류(그룹사) 기준 기업별 요약 테이블을 생성합니다."""
    valid = df.copy()

    # 제품구분 고정 순서
    _제품순서 = ["정수기", "공기청정기", "비데", "커피머신", "제빙기", "기타"]

    def _sort_products(products):
        unique = set(products.dropna().unique())
        ordered = [p for p in _제품순서 if p in unique]
        # 순서에 없는 항목은 뒤에 추가
        rest = sorted(unique - set(_제품순서))
        return ", ".join(ordered + rest)

    grouped = valid.groupby("중분류(그룹사)").agg(
        설치대수=("주문번호", "count"),
        평균렌탈료=("렌탈료_숫자", "mean"),
        주요지역=("지역구분", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else ""),
        제품구분목록=("제품구분", _sort_products),
    ).reset_index()

    grouped["평균렌탈료"] = grouped["평균렌탈료"].round(0)
    grouped = grouped.sort_values("설치대수", ascending=False)

    return grouped


# 지역_1 → GeoJSON 정식 명칭 매핑
_REGION_MAP = {
    "서울": "서울특별시", "경기": "경기도", "인천": "인천광역시",
    "부산": "부산광역시", "대구": "대구광역시", "대전": "대전광역시",
    "광주": "광주광역시", "울산": "울산광역시", "세종": "세종특별자치시",
    "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
    "전북": "전라북도", "전남": "전라남도", "경북": "경상북도",
    "경남": "경상남도", "제주": "제주특별자치도",
}


def get_region_counts(df: pd.DataFrame) -> pd.DataFrame:
    """지역_1 기준 시도별 설치 건수를 집계합니다."""
    counts = df["지역_1"].str.strip().value_counts().reset_index()
    counts.columns = ["지역", "건수"]
    counts["시도명"] = counts["지역"].map(_REGION_MAP)
    return counts.dropna(subset=["시도명"])


def get_available_years(df: pd.DataFrame) -> list:
    """설치일자에서 사용 가능한 연도 목록을 반환합니다."""
    years = df["설치일자"].str[:4]
    return sorted(years.dropna().unique(), reverse=True)


def calculate_next_exchange(df: pd.DataFrame) -> pd.DataFrame:
    """기존 호환성을 위한 래퍼 함수 (미리 계산된 df를 그대로 반환)"""
    valid = df.dropna(subset=["교환주기", "설치일"]).copy()
    return valid


def get_monthly_counts(df: pd.DataFrame, year: str) -> pd.DataFrame:
    """특정 연도의 월별 설치 건수를 반환합니다."""
    mask = df["설치일자"].str[:4] == str(year)
    subset = df[mask].copy()
    subset["월"] = subset["설치일자"].str[4:6].astype(int)

    monthly = subset.groupby("월").size().reset_index(name="건수")
    # 1~12월 전체 보장
    all_months = pd.DataFrame({"월": range(1, 13)})
    monthly = all_months.merge(monthly, on="월", how="left").fillna(0)
    monthly["건수"] = monthly["건수"].astype(int)
    return monthly


def get_monthly_product_counts(df: pd.DataFrame, year: str) -> pd.DataFrame:
    """특정 연도의 제품구분별 월별 설치 건수를 반환합니다."""
    제품순서 = ["정수기", "공기청정기", "비데", "커피머신", "제빙기", "기타"]

    mask = df["설치일자"].str[:4] == str(year)
    subset = df[mask].copy()
    subset["월"] = subset["설치일자"].str[4:6].astype(int)

    pivot = subset.groupby(["월", "제품구분"]).size().reset_index(name="건수")
    # 1~12월 × 전체 제품구분 보장
    all_months = pd.DataFrame({"월": range(1, 13)})
    result = pd.DataFrame()
    for prod in 제품순서:
        prod_data = pivot[pivot["제품구분"] == prod][["월", "건수"]]
        merged = all_months.merge(prod_data, on="월", how="left").fillna(0)
        merged["건수"] = merged["건수"].astype(int)
        merged["제품구분"] = prod
        result = pd.concat([result, merged], ignore_index=True)

    return result


if __name__ == "__main__":
    # 테스트 실행
    data = load_data()
    print(f"데이터 로드 완료: {len(data)}건")
    print(f"컬럼: {list(data.columns)}")
    print()

    stats = get_summary_stats(data)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print()

    company_df = get_company_summary(data)
    print(f"기업별 집계: {len(company_df)}개 그룹사")
    print(company_df.head(10).to_string(index=False))
