"""
agent/tools.py
core/search.py 함수를 LangChain @tool로 등록한다.

DataFrame은 create_tools() 호출 시 클로저로 바인딩되므로
툴 함수 자체는 column, keyword 두 인자만 받는다.
"""

import pandas as pd
from langchain_core.tools import tool

from core.search import search_log_table, search_template_table, search_merged_table


def create_tools(
    log_df: pd.DataFrame,
    template_df: pd.DataFrame,
    merged_df: pd.DataFrame,
) -> list:
    """
    세 DataFrame을 바인딩한 LangChain 툴 목록을 반환한다.

    Args:
        log_df: 원본 로그 테이블
        template_df: 고유 템플릿 테이블
        merged_df: 로그 + 템플릿 통합 테이블

    Returns:
        LangChain Tool 객체 리스트 [tool_search_log, tool_search_template, tool_search_merged]
    """

    @tool
    def tool_search_log(column: str, keyword: str) -> str:
        """원본 로그 테이블(log_df)에서 지정한 컬럼에 키워드가 포함된 행을 검색한다.
        사용 가능한 컬럼: line_number, datetime, system, level, thread, category, message, raw
        예시: column='level', keyword='ERROR'"""
        return search_log_table(log_df, column, keyword)

    @tool
    def tool_search_template(column: str, keyword: str) -> str:
        """템플릿 테이블(template_df)에서 지정한 컬럼에 키워드가 포함된 행을 검색한다.
        사용 가능한 컬럼: template_id, template, cluster_size
        패턴·빈도·종류 분석에 적합하다.
        예시: column='template', keyword='Login failed'"""
        return search_template_table(template_df, column, keyword)

    @tool
    def tool_search_merged(column: str, keyword: str) -> str:
        """통합 테이블(merged_df)에서 지정한 컬럼에 키워드가 포함된 행을 검색한다.
        로그 정보와 템플릿 정보가 모두 포함되어 있어 종합 분석에 적합하다.
        사용 가능한 컬럼: line_number, datetime, system, level, thread, category, message, raw, template_id, template, cluster_size
        예시: column='system', keyword='DBService'"""
        return search_merged_table(merged_df, column, keyword)

    return [tool_search_log, tool_search_template, tool_search_merged]
