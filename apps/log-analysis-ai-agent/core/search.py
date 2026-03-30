"""
core/search.py
세 pandas DataFrame에 대한 컬럼 지정 키워드 검색 함수.

각 함수는 결과를 마크다운 테이블 문자열로 반환한다.
컬럼이 존재하지 않을 경우 사용 가능한 컬럼 목록을 포함한 에러 메시지를 반환한다.
"""

import pandas as pd

MAX_ROWS = 50


def _search(df: pd.DataFrame, column: str, keyword: str, table_name: str) -> str:
    """공통 검색 로직."""
    if column not in df.columns:
        available = ", ".join(df.columns.tolist())
        return (
            f"[오류] '{column}' 컬럼이 {table_name}에 존재하지 않습니다.\n"
            f"사용 가능한 컬럼: {available}"
        )

    mask = df[column].astype(str).str.contains(keyword, case=False, na=False, regex=False)
    result = df[mask].head(MAX_ROWS)

    if result.empty:
        return f"[{table_name}] '{column}' 컬럼에서 '{keyword}' 검색 결과 없음"

    header = f"[{table_name}] '{column}' 컬럼에서 '{keyword}' 검색 결과 ({len(result)}건)"
    return header + "\n\n" + result.to_markdown(index=False)


def search_log_table(df: pd.DataFrame, column: str, keyword: str) -> str:
    """
    log_df에서 지정한 column에 keyword가 포함된 행을 검색한다.

    Args:
        df: 로그 테이블 DataFrame
        column: 검색 대상 컬럼 (line_number, datetime, system, level, thread, category, message, raw)
        keyword: 검색 키워드 (대소문자 무시)

    Returns:
        마크다운 테이블 문자열 또는 에러/결과없음 메시지
    """
    return _search(df, column, keyword, "log_df")


def search_template_table(df: pd.DataFrame, column: str, keyword: str) -> str:
    """
    template_df에서 지정한 column에 keyword가 포함된 행을 검색한다.

    Args:
        df: 템플릿 테이블 DataFrame
        column: 검색 대상 컬럼 (template_id, template, cluster_size)
        keyword: 검색 키워드 (대소문자 무시)

    Returns:
        마크다운 테이블 문자열 또는 에러/결과없음 메시지
    """
    return _search(df, column, keyword, "template_df")


def search_merged_table(df: pd.DataFrame, column: str, keyword: str) -> str:
    """
    merged_df에서 지정한 column에 keyword가 포함된 행을 검색한다.

    Args:
        df: 통합 테이블 DataFrame
        column: 검색 대상 컬럼 (system, level, category, message, template, cluster_size 등)
        keyword: 검색 키워드 (대소문자 무시)

    Returns:
        마크다운 테이블 문자열 또는 에러/결과없음 메시지
    """
    return _search(df, column, keyword, "merged_df")
