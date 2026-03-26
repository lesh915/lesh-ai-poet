"""
tests/test_log_engine.py
LogEngine 단위 테스트
"""

import pytest
import sys
import os

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.log_engine import LogEngine

SAMPLE_LOG = """
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:01:10] [AuthService] [ERROR] [Thread-3] [Security] [Login failed for user admin from IP 10.0.0.1]
[2024-01-15 09:02:00] [APIGateway] [INFO] [Thread-10] [Network] [Received GET request from client 172.16.0.1 path /api/v1/users]
"""

SAMPLE_LOG_2 = """
[2024-01-15 10:00:00] [DBService] [WARN] [Thread-5] [Database] [Slow query detected: 3200ms table=orders]
[2024-01-15 10:01:00] [DBService] [WARN] [Thread-6] [Database] [Slow query detected: 4100ms table=users]
"""


@pytest.fixture
def engine():
    e = LogEngine()
    e.ingest_text(SAMPLE_LOG)
    return e


@pytest.fixture
def empty_engine():
    return LogEngine()


def test_ingest_returns_count(engine):
    result = engine.ingest_text(SAMPLE_LOG, reset=True)
    assert result["ingested"] == 3


def test_ingest_text_incremental():
    e = LogEngine()
    r1 = e.ingest_text(SAMPLE_LOG)
    assert r1["ingested"] == 3

    r2 = e.ingest_text(SAMPLE_LOG_2)
    assert r2["ingested"] == 2
    assert e.total_log_count() == 5


def test_ingest_text_reset():
    e = LogEngine()
    e.ingest_text(SAMPLE_LOG)
    r = e.ingest_text(SAMPLE_LOG_2, reset=True)
    assert r["ingested"] == 2
    assert e.total_log_count() == 2


def test_ingest_empty_text():
    e = LogEngine()
    result = e.ingest_text("")
    assert result["ingested"] == 0


def test_ingest_file_not_found():
    e = LogEngine()
    result = e.ingest_file("/nonexistent/path/log.txt")
    assert result["ingested"] == 0
    assert "error" in result


def test_list_templates_not_empty(engine):
    templates = engine.list_templates()
    assert len(templates) >= 1


def test_list_templates_structure(engine):
    templates = engine.list_templates()
    for t in templates:
        assert "template_id" in t
        assert "template" in t
        assert "cluster_size" in t


def test_get_original_logs_by_template(engine):
    templates = engine.list_templates()
    tid = templates[0]["template_id"]
    logs = engine.get_original_logs(tid)
    assert len(logs) > 0
    assert "message" in logs[0]


def test_get_original_logs_empty_engine(empty_engine):
    logs = empty_engine.get_original_logs(999)
    assert logs == []


def test_get_template_found(engine):
    templates = engine.list_templates()
    tid = templates[0]["template_id"]
    t = engine.get_template(tid)
    assert t is not None
    assert t["template_id"] == tid


def test_get_template_not_found(engine):
    result = engine.get_template(99999)
    assert result is None


def test_search_by_level(engine):
    results = engine.search(level="ERROR")
    assert len(results) > 0
    assert all(r["level"] == "ERROR" for r in results)


def test_search_by_system(engine):
    results = engine.search(system="AuthService")
    assert len(results) > 0
    assert all(r["system"] == "AuthService" for r in results)


def test_search_by_keyword(engine):
    results = engine.search(keyword="Login")
    assert len(results) > 0


def test_search_empty_engine(empty_engine):
    results = empty_engine.search(keyword="test")
    assert results == []


def test_search_no_match(engine):
    results = engine.search(level="CRITICAL")
    assert results == []


def test_list_templates_page_basic(engine):
    result = engine.list_templates_page(page=0, page_size=50)
    assert "items" in result
    assert "page" in result
    assert "page_size" in result
    assert "total" in result
    assert "has_next" in result
    assert result["page"] == 0
    assert result["page_size"] == 50


def test_list_templates_page_first_page(engine):
    all_templates = engine.list_templates()
    result = engine.list_templates_page(page=0, page_size=1)
    assert len(result["items"]) == 1
    assert result["total"] == len(all_templates)
    assert result["has_next"] == (len(all_templates) > 1)


def test_list_templates_page_out_of_range(engine):
    result = engine.list_templates_page(page=9999, page_size=50)
    assert result["items"] == []
    assert result["has_next"] is False


def test_list_templates_page_last_page(engine):
    """마지막 페이지에서 has_next가 False여야 한다."""
    all_templates = engine.list_templates()
    total = len(all_templates)
    last_page = max(0, (total - 1) // 1)
    result = engine.list_templates_page(page=last_page, page_size=1)
    assert result["has_next"] is False


def test_get_original_logs_page_basic(engine):
    templates = engine.list_templates()
    tid = templates[0]["template_id"]
    result = engine.get_original_logs_page(tid, page=0, page_size=200)
    assert "items" in result
    assert "page" in result
    assert "total" in result
    assert "has_next" in result


def test_get_original_logs_page_pagination(engine):
    """페이지네이션이 올바르게 동작해야 한다."""
    templates = engine.list_templates()
    # 가장 많은 로그를 가진 템플릿 선택
    tid = templates[0]["template_id"]
    all_logs = engine.get_original_logs(tid)
    total = len(all_logs)

    if total >= 2:
        page0 = engine.get_original_logs_page(tid, page=0, page_size=1)
        page1 = engine.get_original_logs_page(tid, page=1, page_size=1)
        assert page0["items"] != page1["items"]
        assert page0["has_next"] is True
    else:
        page0 = engine.get_original_logs_page(tid, page=0, page_size=200)
        assert page0["has_next"] is False


def test_total_log_count(engine):
    count = engine.total_log_count()
    assert count == 3


def test_total_log_count_empty(empty_engine):
    count = empty_engine.total_log_count()
    assert count == 0
