"""
ReACT 로그 분석 에이전트 - Tool 함수 정의
drain3 템플릿 + 원본 로그 맵핑 데이터 기반 분석 도구
"""

import pandas as pd
from typing import Optional
from datetime import datetime


def search_logs(
    df: pd.DataFrame,
    column: str,
    keyword: str,
    top_n: int = 50
) -> pd.DataFrame:
    """
    특정 컬럼에서 키워드로 로그를 검색합니다 (부분 일치, 대소문자 무시).

    Args:
        df: 로그 DataFrame (template, original, level, timestamp 등 포함)
        column: 검색 대상 컬럼명
        keyword: 검색 키워드
        top_n: 최대 반환 행 수

    Returns:
        매칭된 로그 DataFrame (timestamp 오름차순 정렬)

    Example:
        search_logs(df, column="level", keyword="E")
        search_logs(df, column="template", keyword="connection pool")
        search_logs(df, column="original", keyword="user_id=99999")
    """
    if column not in df.columns:
        raise ValueError(f"컬럼 '{column}'이 DataFrame에 존재하지 않습니다. "
                         f"사용 가능한 컬럼: {list(df.columns)}")

    mask = df[column].astype(str).str.contains(keyword, case=False, na=False)
    result = df[mask].sort_values("timestamp").head(top_n)
    return result.reset_index(drop=True)


def get_log_by_id(df: pd.DataFrame, log_id: str) -> pd.Series:
    """
    특정 log_id의 원본 로그 전체 내용을 반환합니다.

    Args:
        df: 로그 DataFrame
        log_id: 조회할 로그 고유 ID

    Returns:
        해당 로그의 전체 컬럼 데이터 (Series)

    Raises:
        KeyError: log_id가 존재하지 않을 경우
    """
    result = df[df["log_id"] == log_id]
    if result.empty:
        raise KeyError(f"log_id '{log_id}'를 찾을 수 없습니다.")
    return result.iloc[0]


def get_logs_by_timerange(
    df: pd.DataFrame,
    start_ts: str,
    end_ts: str,
    level: Optional[str] = None
) -> pd.DataFrame:
    """
    특정 시간 범위의 로그를 필터링합니다.

    Args:
        df: 로그 DataFrame (timestamp 컬럼 필요)
        start_ts: 시작 타임스탬프 (ISO8601 또는 HH:MM:SS)
        end_ts: 종료 타임스탬프
        level: 로그 레벨 필터 (선택, 예: "E", "Q", "S")

    Returns:
        해당 시간대 로그 DataFrame (timestamp 오름차순)
    """
    df_copy = df.copy()
    df_copy["timestamp"] = pd.to_datetime(df_copy["timestamp"])

    start = pd.to_datetime(start_ts)
    end = pd.to_datetime(end_ts)

    mask = (df_copy["timestamp"] >= start) & (df_copy["timestamp"] <= end)
    result = df_copy[mask]

    if level:
        result = result[result["level"].str.upper() == level.upper()]

    return result.sort_values("timestamp").reset_index(drop=True)


def get_stacktrace(df: pd.DataFrame, log_id: str, window_rows: int = 50) -> str:
    """
    특정 에러 로그에 연관된 스택트레이스 전체를 반환합니다.

    S(Stacktrace) 레벨 로그를 에러 로그 직후부터 연속 수집합니다.

    Args:
        df: 로그 DataFrame
        log_id: 기준 에러 로그 ID
        window_rows: 이후 탐색할 최대 행 수

    Returns:
        연결된 스택트레이스 문자열
    """
    df_sorted = df.sort_values("timestamp").reset_index(drop=True)

    try:
        start_idx = df_sorted[df_sorted["log_id"] == log_id].index[0]
    except IndexError:
        raise KeyError(f"log_id '{log_id}'를 찾을 수 없습니다.")

    stacktrace_lines = []
    # 기준 로그 자체의 원본 포함
    base_row = df_sorted.iloc[start_idx]
    stacktrace_lines.append(f"[{base_row['timestamp']}] {base_row['original']}")

    # 이후 S 레벨 로그 연속 수집
    for i in range(start_idx + 1, min(start_idx + 1 + window_rows, len(df_sorted))):
        row = df_sorted.iloc[i]
        if str(row.get("level", "")).upper() == "S":
            stacktrace_lines.append(f"  {row['original']}")
        else:
            # S 레벨이 끊기면 스택트레이스 종료
            break

    return "\n".join(stacktrace_lines)


def get_query_stats(df: pd.DataFrame, slow_threshold_ms: int = 1000) -> dict:
    """
    Q 레벨 로그에서 DB 쿼리 통계를 집계합니다.

    Args:
        df: 로그 DataFrame
        slow_threshold_ms: 슬로우 쿼리 판단 기준 (밀리초, 기본값: 1000ms)

    Returns:
        쿼리 통계 딕셔너리:
            - total_queries: 총 쿼리 수
            - slow_queries: 슬로우 쿼리 목록 (DataFrame)
            - avg_duration_ms: 평균 실행 시간
            - max_duration_ms: 최대 실행 시간
            - template_distribution: 템플릿별 쿼리 빈도
            - error_queries: 에러 포함 쿼리 수
    """
    q_logs = df[df["level"].str.upper() == "Q"].copy()

    if q_logs.empty:
        return {"total_queries": 0, "message": "Q 레벨 로그가 없습니다."}

    stats = {
        "total_queries": len(q_logs),
        "template_distribution": q_logs["template"].value_counts().to_dict(),
    }

    # duration_ms 컬럼이 있는 경우 성능 통계 추가
    if "duration_ms" in q_logs.columns:
        q_logs["duration_ms"] = pd.to_numeric(q_logs["duration_ms"], errors="coerce")
        stats["avg_duration_ms"] = round(q_logs["duration_ms"].mean(), 2)
        stats["max_duration_ms"] = q_logs["duration_ms"].max()
        slow = q_logs[q_logs["duration_ms"] >= slow_threshold_ms]
        stats["slow_query_count"] = len(slow)
        stats["slow_queries"] = slow.sort_values("duration_ms", ascending=False)

    # 에러 포함 쿼리 (original에 error/exception 포함)
    error_q = q_logs[
        q_logs["original"].str.contains("error|exception|fail", case=False, na=False)
    ]
    stats["error_queries_count"] = len(error_q)

    return stats


def get_error_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    E 레벨 로그의 에러 유형별 요약을 반환합니다.

    Args:
        df: 로그 DataFrame

    Returns:
        에러 요약 DataFrame:
            - template: drain3 에러 템플릿
            - count: 발생 횟수
            - first_occurrence: 최초 발생 시각
            - last_occurrence: 마지막 발생 시각
    """
    e_logs = df[df["level"].str.upper() == "E"].copy()

    if e_logs.empty:
        return pd.DataFrame(columns=["template", "count", "first_occurrence", "last_occurrence"])

    e_logs["timestamp"] = pd.to_datetime(e_logs["timestamp"])

    summary = (
        e_logs.groupby("template")
        .agg(
            count=("log_id", "count"),
            first_occurrence=("timestamp", "min"),
            last_occurrence=("timestamp", "max"),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )

    return summary


def get_log_overview(df: pd.DataFrame) -> dict:
    """
    전체 로그의 기본 통계를 반환합니다 (Phase 1 Step 1 전용).

    Args:
        df: 로그 DataFrame

    Returns:
        전체 로그 개요 딕셔너리
    """
    df_copy = df.copy()
    df_copy["timestamp"] = pd.to_datetime(df_copy["timestamp"])

    return {
        "total_logs": len(df_copy),
        "time_range": {
            "start": str(df_copy["timestamp"].min()),
            "end": str(df_copy["timestamp"].max()),
            "duration_minutes": round(
                (df_copy["timestamp"].max() - df_copy["timestamp"].min()).total_seconds() / 60, 2
            ),
        },
        "level_distribution": df_copy["level"].value_counts().to_dict(),
        "unique_templates": df_copy["template"].nunique(),
        "unique_sources": df_copy.get("source", pd.Series()).nunique(),
    }


# ─── Tool 메타데이터 (에이전트 프레임워크 연동용) ───────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_logs",
        "description": "특정 컬럼에서 키워드로 로그를 검색합니다. 부분 일치, 대소문자 무시.",
        "parameters": {
            "column": "검색 대상 컬럼명 (예: level, template, original, source, session_id)",
            "keyword": "검색 키워드",
            "top_n": "최대 반환 행 수 (기본값: 50)",
        },
    },
    {
        "name": "get_log_by_id",
        "description": "특정 log_id의 원본 로그 전체 내용을 반환합니다.",
        "parameters": {"log_id": "조회할 로그 고유 ID"},
    },
    {
        "name": "get_logs_by_timerange",
        "description": "특정 시간 범위의 로그를 필터링합니다.",
        "parameters": {
            "start_ts": "시작 타임스탬프 (ISO8601)",
            "end_ts": "종료 타임스탬프",
            "level": "로그 레벨 필터 (선택, 예: E, Q, S)",
        },
    },
    {
        "name": "get_stacktrace",
        "description": "특정 에러 로그에 연관된 스택트레이스 전체를 반환합니다.",
        "parameters": {
            "log_id": "기준 에러 로그 ID",
            "window_rows": "이후 탐색할 최대 행 수 (기본값: 50)",
        },
    },
    {
        "name": "get_query_stats",
        "description": "Q 레벨 로그에서 DB 쿼리 통계를 집계합니다.",
        "parameters": {
            "slow_threshold_ms": "슬로우 쿼리 판단 기준 밀리초 (기본값: 1000)"
        },
    },
    {
        "name": "get_error_summary",
        "description": "E 레벨 로그의 에러 유형별 요약을 반환합니다.",
        "parameters": {},
    },
    {
        "name": "get_log_overview",
        "description": "전체 로그의 기본 통계를 반환합니다 (총 건수, 시간 범위, 레벨 분포 등).",
        "parameters": {},
    },
]
