"""
log_store.py
Pandas 기반 로그 저장 및 검색 모듈

파싱된 로그 데이터와 Drain3 템플릿 정보를 DataFrame으로 관리하고,
다양한 조건으로 검색하여 원본 로그와 템플릿을 매칭하여 반환합니다.
"""

import pandas as pd
from typing import Optional

from log_parser import LogEntry
from drain3_extractor import TemplateResult


# ---------------------------------------------------------------------------
# DataFrame 컬럼 정의
# ---------------------------------------------------------------------------

LOG_COLUMNS = [
    "line_number",
    "datetime",
    "system",
    "level",
    "thread",
    "category",
    "message",
    "raw",
]

TEMPLATE_COLUMNS = [
    "template_id",
    "template",
    "cluster_size",
    "level",
]

# MERGED_COLUMNS: level은 LOG_COLUMNS에서 가져오므로 TEMPLATE_COLUMNS의 level은 제외
MERGED_COLUMNS = LOG_COLUMNS + ["template_id", "template", "cluster_size"]


# ---------------------------------------------------------------------------
# 저장 함수
# ---------------------------------------------------------------------------


def build_log_dataframe(entries: list[LogEntry]) -> pd.DataFrame:
    """
    LogEntry 리스트를 pandas DataFrame으로 변환합니다.

    Args:
        entries: 파싱된 LogEntry 객체 리스트

    Returns:
        로그 데이터가 담긴 DataFrame
    """
    rows = [
        {
            "line_number": e.line_number,
            "datetime": e.datetime,
            "system": e.system,
            "level": e.level,
            "thread": e.thread,
            "category": e.category,
            "message": e.message,
            "raw": e.raw,
        }
        for e in entries
    ]
    return pd.DataFrame(rows, columns=LOG_COLUMNS)


def build_template_dataframe(
    results: list[TemplateResult],
    entries: Optional[list[LogEntry]] = None,
) -> pd.DataFrame:
    """
    TemplateResult 리스트를 pandas DataFrame으로 변환합니다.

    Args:
        results: TemplateResult 객체 리스트 (로그와 순서 동일)
        entries: LogEntry 객체 리스트 (results와 순서 동일).
                 전달하면 각 행에 원본 로그의 level 값이 추가됩니다.

    Returns:
        템플릿 데이터가 담긴 DataFrame
        컬럼: template_id, template, cluster_size, level(entries 전달 시)
    """
    levels = [e.level for e in entries] if entries is not None else [None] * len(results)
    rows = [
        {
            "template_id": r.template_id,
            "template": r.template,
            "cluster_size": r.cluster_size,
            "level": lvl,
        }
        for r, lvl in zip(results, levels)
    ]
    return pd.DataFrame(rows, columns=TEMPLATE_COLUMNS)


def build_merged_dataframe(
    log_df: pd.DataFrame,
    template_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    로그 DataFrame과 템플릿 DataFrame을 인덱스 기준으로 병합합니다.

    Args:
        log_df: build_log_dataframe()으로 생성한 DataFrame
        template_df: build_template_dataframe()으로 생성한 DataFrame

    Returns:
        원본 로그 + 템플릿 정보가 합쳐진 통합 DataFrame
    """
    # template_df의 level 컬럼은 log_df에 이미 존재하므로 중복 제거 후 병합
    tmpl = template_df.drop(columns=["level"], errors="ignore")
    merged = pd.concat(
        [log_df.reset_index(drop=True), tmpl.reset_index(drop=True)],
        axis=1,
    )
    return merged[MERGED_COLUMNS]


def build_cluster_summary_dataframe(merged_df: pd.DataFrame) -> pd.DataFrame:
    """
    통합 DataFrame에서 템플릿(클러스터) 별 요약 정보를 생성합니다.

    Args:
        merged_df: build_merged_dataframe()으로 생성한 통합 DataFrame

    Returns:
        template_id, template, log_count, levels, level_counts를 컬럼으로 하는 요약 DataFrame
        - levels      : 해당 템플릿에 속한 원본 로그의 고유 레벨 목록 (쉼표 구분, 알파벳 정렬)
        - level_counts: 레벨별 로그 건수 딕셔너리 문자열 (예: "ERROR:5, WARN:3")
    """
    base = (
        merged_df.groupby(["template_id", "template"], as_index=False)
        .agg(log_count=("line_number", "count"))
    )

    # 템플릿별 레벨 집계
    level_info = (
        merged_df.groupby(["template_id", "level"])
        .size()
        .reset_index(name="cnt")
    )

    def _levels(tid: int) -> str:
        lvls = level_info.loc[level_info["template_id"] == tid, "level"].tolist()
        return ", ".join(sorted(set(lvls)))

    def _level_counts(tid: int) -> str:
        rows = level_info[level_info["template_id"] == tid].sort_values("level")
        return ", ".join(f"{row.level}:{row.cnt}" for row in rows.itertuples())

    base["levels"] = base["template_id"].apply(_levels)
    base["level_counts"] = base["template_id"].apply(_level_counts)

    return (
        base.sort_values("log_count", ascending=False)
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# 검색 함수
# ---------------------------------------------------------------------------


def search_by_keyword(
    merged_df: pd.DataFrame,
    keyword: str,
    columns: Optional[list[str]] = None,
    case_sensitive: bool = False,
) -> pd.DataFrame:
    """
    키워드로 로그를 검색하고 템플릿 정보를 함께 반환합니다.

    Args:
        merged_df: 통합 DataFrame
        keyword: 검색할 키워드 문자열
        columns: 검색할 컬럼 목록 (None이면 모든 문자열 컬럼 대상)
        case_sensitive: 대소문자 구분 여부 (기본값 False)

    Returns:
        키워드가 포함된 행들의 DataFrame
    """
    if columns is None:
        # pandas 3.x에서는 문자열 컬럼 dtype이 'object' 대신 'str'(StringDtype)으로 저장됨
        columns = [
            col
            for col in MERGED_COLUMNS
            if col in merged_df.columns
            and not pd.api.types.is_numeric_dtype(merged_df[col])
        ]

    mask = pd.Series(False, index=merged_df.index)
    for col in columns:
        if col in merged_df.columns:
            mask |= merged_df[col].astype(str).str.contains(
                keyword, case=case_sensitive, na=False, regex=False
            )

    return merged_df[mask].reset_index(drop=True)


def search_by_field(
    merged_df: pd.DataFrame,
    **field_filters,
) -> pd.DataFrame:
    """
    특정 필드 값으로 정확히 일치하는 로그를 검색합니다.

    Args:
        merged_df: 통합 DataFrame
        **field_filters: 컬럼명=값 형식의 필터 조건
            지원 컬럼: datetime, system, level, thread, category,
                       template_id, template

    Returns:
        조건에 맞는 행들의 DataFrame

    Example:
        search_by_field(df, level="ERROR", system="AuthService")
    """
    mask = pd.Series(True, index=merged_df.index)
    for col, value in field_filters.items():
        if col not in merged_df.columns:
            raise ValueError(f"존재하지 않는 컬럼: '{col}'. 사용 가능: {MERGED_COLUMNS}")
        mask &= merged_df[col].astype(str).str.lower() == str(value).lower()

    return merged_df[mask].reset_index(drop=True)


def search_by_template_id(
    merged_df: pd.DataFrame,
    template_id: int,
) -> pd.DataFrame:
    """
    특정 템플릿 ID에 해당하는 원본 로그를 모두 반환합니다.

    Args:
        merged_df: 통합 DataFrame
        template_id: 조회할 Drain3 클러스터 ID

    Returns:
        해당 템플릿 ID의 모든 로그 행 DataFrame
    """
    return merged_df[merged_df["template_id"] == template_id].reset_index(drop=True)


def search_by_datetime_range(
    merged_df: pd.DataFrame,
    start: str,
    end: str,
) -> pd.DataFrame:
    """
    날짜/시간 범위로 로그를 검색합니다.

    Args:
        merged_df: 통합 DataFrame
        start: 시작 날짜시간 문자열 (예: "2024-01-15 09:00:00")
        end: 종료 날짜시간 문자열 (예: "2024-01-15 10:00:00")

    Returns:
        해당 범위 내 로그 행 DataFrame
    """
    dt_series = pd.to_datetime(merged_df["datetime"], errors="coerce")
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    mask = (dt_series >= start_dt) & (dt_series <= end_dt)
    return merged_df[mask].reset_index(drop=True)


def search_combined(
    merged_df: pd.DataFrame,
    keyword: Optional[str] = None,
    level: Optional[str] = None,
    system: Optional[str] = None,
    category: Optional[str] = None,
    thread: Optional[str] = None,
    template_id: Optional[int] = None,
    datetime_start: Optional[str] = None,
    datetime_end: Optional[str] = None,
) -> pd.DataFrame:
    """
    여러 조건을 조합하여 로그를 검색합니다 (AND 조건).

    Args:
        merged_df: 통합 DataFrame
        keyword: 메시지/템플릿에서 검색할 키워드
        level: 로그 레벨 (예: "ERROR", "WARN", "INFO")
        system: 시스템 이름 필터
        category: 카테고리 필터
        thread: 스레드 이름 필터
        template_id: 템플릿 ID 필터
        datetime_start: 시작 날짜시간
        datetime_end: 종료 날짜시간

    Returns:
        모든 조건을 만족하는 로그 행 DataFrame
    """
    result = merged_df.copy()

    if level is not None:
        result = search_by_field(result, level=level)
    if system is not None:
        result = search_by_field(result, system=system)
    if category is not None:
        result = search_by_field(result, category=category)
    if thread is not None:
        result = search_by_field(result, thread=thread)
    if template_id is not None:
        result = search_by_template_id(result, template_id)
    if datetime_start is not None or datetime_end is not None:
        start = datetime_start or "1900-01-01"
        end = datetime_end or "9999-12-31"
        result = search_by_datetime_range(result, start, end)
    if keyword is not None:
        result = search_by_keyword(result, keyword, columns=["message", "raw", "template"])

    return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 출력 유틸리티
# ---------------------------------------------------------------------------


def display_results(df: pd.DataFrame, max_rows: int = 20) -> None:
    """
    검색 결과를 보기 좋게 출력합니다.

    Args:
        df: 출력할 DataFrame
        max_rows: 최대 출력 행 수
    """
    if df.empty:
        print("검색 결과가 없습니다.")
        return

    print(f"[검색 결과: {len(df)}건]\n")
    display_cols = ["line_number", "datetime", "system", "level", "category", "message", "template_id", "template"]
    available = [c for c in display_cols if c in df.columns]

    with pd.option_context(
        "display.max_colwidth", 60,
        "display.width", 200,
        "display.max_rows", max_rows,
    ):
        print(df[available].to_string(index=False))
    print()
