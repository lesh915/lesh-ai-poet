"""tests/test_search.py — core/search.py 단위 테스트"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.loader import load_from_text
from core.search import search_log_table, search_template_table, search_merged_table

SAMPLE = """\
[2024-01-15 09:00:01] [AuthService] [INFO] [Thread-1] [Security] [User admin logged in successfully]
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:00:12] [AuthService] [ERROR] [Thread-3] [Security] [Login failed for user root from IP 10.0.0.5]
[2024-01-15 09:01:00] [DBService] [INFO] [Thread-5] [Database] [Connection established to host db-01 port 5432]
[2024-01-15 09:01:10] [DBService] [WARN] [Thread-7] [Database] [Query execution time exceeded 500ms on table orders]
"""

log_df, template_df, merged_df, _ = load_from_text(SAMPLE)


# --- search_log_table ---

def test_search_log_by_level_error():
    result = search_log_table(log_df, "level", "ERROR")
    assert "ERROR" in result
    assert "Login failed" in result


def test_search_log_by_system():
    result = search_log_table(log_df, "system", "DBService")
    assert "DBService" in result


def test_search_log_no_result():
    result = search_log_table(log_df, "level", "CRITICAL")
    assert "검색 결과 없음" in result


def test_search_log_invalid_column():
    result = search_log_table(log_df, "nonexistent_col", "test")
    assert "오류" in result
    assert "사용 가능한 컬럼" in result


def test_search_log_case_insensitive():
    result_lower = search_log_table(log_df, "level", "error")
    result_upper = search_log_table(log_df, "level", "ERROR")
    # 둘 다 결과를 반환해야 함
    assert "검색 결과 없음" not in result_lower
    assert "검색 결과 없음" not in result_upper


# --- search_template_table ---

def test_search_template_by_keyword():
    result = search_template_table(template_df, "template", "Login")
    assert "template_df" in result


def test_search_template_invalid_column():
    result = search_template_table(template_df, "bad_col", "test")
    assert "오류" in result


# --- search_merged_table ---

def test_search_merged_by_system():
    result = search_merged_table(merged_df, "system", "AuthService")
    assert "AuthService" in result


def test_search_merged_by_level_warn():
    result = search_merged_table(merged_df, "level", "WARN")
    assert "WARN" in result


def test_search_merged_invalid_column():
    result = search_merged_table(merged_df, "unknown", "test")
    assert "오류" in result
    assert "사용 가능한 컬럼" in result


def test_search_merged_returns_markdown_table():
    result = search_merged_table(merged_df, "level", "ERROR")
    # 마크다운 테이블은 | 문자를 포함
    assert "|" in result
