"""
tests/test_mcp_tools.py
MCP 툴 단위 테스트

각 MCP 툴의 응답 형식 검증 및 페이지네이션 경계 테스트를 포함한다.
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
[2024-01-15 09:03:00] [DBService] [WARN] [Thread-5] [Database] [Slow query detected: 3200ms table=orders]
[2024-01-15 09:04:00] [DBService] [WARN] [Thread-6] [Database] [Slow query detected: 4100ms table=users]
"""


@pytest.fixture
def engine_with_data():
    """데이터가 로드된 LogEngine 인스턴스."""
    e = LogEngine()
    e.ingest_text(SAMPLE_LOG)
    return e


@pytest.fixture
def empty_engine():
    """빈 LogEngine 인스턴스."""
    return LogEngine()


# ── ingest_log_text 관련 테스트 ───────────────────────────────────

class TestIngestLogText:
    def test_returns_dict_with_required_keys(self, empty_engine):
        result = empty_engine.ingest_text(SAMPLE_LOG)
        assert isinstance(result, dict)
        assert "ingested" in result
        assert "template_count" in result

    def test_ingested_count_correct(self, empty_engine):
        result = empty_engine.ingest_text(SAMPLE_LOG)
        assert result["ingested"] == 5

    def test_template_count_positive(self, empty_engine):
        result = empty_engine.ingest_text(SAMPLE_LOG)
        assert result["template_count"] >= 1

    def test_reset_true_clears_previous(self, engine_with_data):
        small_log = "[2024-01-15 10:00:00] [SysA] [INFO] [T-1] [General] [Server started successfully]"
        result = engine_with_data.ingest_text(small_log, reset=True)
        assert result["ingested"] == 1
        assert engine_with_data.total_log_count() == 1

    def test_empty_text_returns_zero_ingested(self, empty_engine):
        result = empty_engine.ingest_text("")
        assert result["ingested"] == 0


# ── ingest_log_file 관련 테스트 ──────────────────────────────────

class TestIngestLogFile:
    def test_file_not_found_returns_error(self, empty_engine):
        result = empty_engine.ingest_file("/nonexistent/file.log")
        assert result["ingested"] == 0
        assert "error" in result


# ── list_templates 관련 테스트 ────────────────────────────────────

class TestListTemplates:
    def test_returns_list(self, engine_with_data):
        result = engine_with_data.list_templates()
        assert isinstance(result, list)

    def test_not_empty_after_ingest(self, engine_with_data):
        result = engine_with_data.list_templates()
        assert len(result) >= 1

    def test_each_item_has_required_keys(self, engine_with_data):
        result = engine_with_data.list_templates()
        for item in result:
            assert "template_id" in item
            assert "template" in item
            assert "cluster_size" in item

    def test_empty_engine_returns_empty_list(self, empty_engine):
        result = empty_engine.list_templates()
        assert result == []


# ── get_template 관련 테스트 ─────────────────────────────────────

class TestGetTemplate:
    def test_existing_template_returns_dict(self, engine_with_data):
        templates = engine_with_data.list_templates()
        tid = templates[0]["template_id"]
        result = engine_with_data.get_template(tid)
        assert result is not None
        assert result["template_id"] == tid

    def test_nonexistent_template_returns_none(self, engine_with_data):
        result = engine_with_data.get_template(99999)
        assert result is None


# ── get_original_logs 관련 테스트 ────────────────────────────────

class TestGetOriginalLogs:
    def test_returns_list(self, engine_with_data):
        templates = engine_with_data.list_templates()
        tid = templates[0]["template_id"]
        result = engine_with_data.get_original_logs(tid)
        assert isinstance(result, list)

    def test_each_log_has_message_field(self, engine_with_data):
        templates = engine_with_data.list_templates()
        tid = templates[0]["template_id"]
        result = engine_with_data.get_original_logs(tid)
        assert len(result) > 0
        assert "message" in result[0]

    def test_empty_engine_returns_empty_list(self, empty_engine):
        result = empty_engine.get_original_logs(1)
        assert result == []


# ── search_logs 관련 테스트 ──────────────────────────────────────

class TestSearchLogs:
    def test_search_by_level(self, engine_with_data):
        results = engine_with_data.search(level="ERROR")
        assert len(results) > 0
        assert all(r["level"] == "ERROR" for r in results)

    def test_search_by_keyword(self, engine_with_data):
        results = engine_with_data.search(keyword="Login")
        assert len(results) > 0

    def test_search_no_results(self, engine_with_data):
        results = engine_with_data.search(level="CRITICAL")
        assert results == []

    def test_search_empty_engine(self, empty_engine):
        results = empty_engine.search(keyword="test")
        assert results == []

    def test_search_combined_level_and_system(self, engine_with_data):
        results = engine_with_data.search(level="ERROR", system="AuthService")
        assert len(results) > 0
        assert all(r["level"] == "ERROR" for r in results)
        assert all(r["system"] == "AuthService" for r in results)


# ── list_templates_page 페이지네이션 테스트 ──────────────────────

class TestListTemplatesPage:
    def test_returns_required_keys(self, engine_with_data):
        result = engine_with_data.list_templates_page(page=0, page_size=50)
        assert "items" in result
        assert "page" in result
        assert "page_size" in result
        assert "total" in result
        assert "has_next" in result

    def test_page_zero(self, engine_with_data):
        result = engine_with_data.list_templates_page(page=0, page_size=50)
        assert result["page"] == 0

    def test_page_size_respected(self, engine_with_data):
        result = engine_with_data.list_templates_page(page=0, page_size=1)
        assert len(result["items"]) <= 1

    def test_has_next_false_when_all_fit(self, engine_with_data):
        result = engine_with_data.list_templates_page(page=0, page_size=1000)
        assert result["has_next"] is False

    def test_has_next_true_when_more_pages(self, engine_with_data):
        all_templates = engine_with_data.list_templates()
        if len(all_templates) >= 2:
            result = engine_with_data.list_templates_page(page=0, page_size=1)
            assert result["has_next"] is True

    def test_out_of_range_page_returns_empty(self, engine_with_data):
        result = engine_with_data.list_templates_page(page=9999, page_size=50)
        assert result["items"] == []
        assert result["has_next"] is False

    def test_total_consistent(self, engine_with_data):
        all_templates = engine_with_data.list_templates()
        result = engine_with_data.list_templates_page(page=0, page_size=50)
        assert result["total"] == len(all_templates)

    def test_empty_engine_pagination(self, empty_engine):
        result = empty_engine.list_templates_page(page=0, page_size=50)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["has_next"] is False

    def test_pagination_covers_all_items(self, engine_with_data):
        """페이지 단위로 순회하면 전체 아이템을 커버해야 한다."""
        all_templates = engine_with_data.list_templates()
        page_size = 1
        collected = []
        page = 0
        while True:
            result = engine_with_data.list_templates_page(page=page, page_size=page_size)
            collected.extend(result["items"])
            if not result["has_next"]:
                break
            page += 1

        assert len(collected) == len(all_templates)

    def test_last_page_has_next_false(self, engine_with_data):
        """마지막 페이지의 has_next는 반드시 False여야 한다."""
        all_templates = engine_with_data.list_templates()
        total = len(all_templates)
        if total == 0:
            pytest.skip("No templates to paginate")

        page_size = 1
        last_page_idx = total - 1
        result = engine_with_data.list_templates_page(page=last_page_idx, page_size=page_size)
        assert result["has_next"] is False

    def test_boundary_exact_page_size(self, engine_with_data):
        """총 개수와 page_size가 정확히 같을 때 has_next는 False여야 한다."""
        all_templates = engine_with_data.list_templates()
        total = len(all_templates)
        if total == 0:
            pytest.skip("No templates to paginate")

        result = engine_with_data.list_templates_page(page=0, page_size=total)
        assert len(result["items"]) == total
        assert result["has_next"] is False


# ── get_original_logs_page 페이지네이션 테스트 ───────────────────

class TestGetOriginalLogsPage:
    def test_returns_required_keys(self, engine_with_data):
        templates = engine_with_data.list_templates()
        tid = templates[0]["template_id"]
        result = engine_with_data.get_original_logs_page(tid, page=0, page_size=200)
        assert "items" in result
        assert "page" in result
        assert "total" in result
        assert "has_next" in result

    def test_empty_engine_returns_empty(self, empty_engine):
        result = empty_engine.get_original_logs_page(999, page=0, page_size=200)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["has_next"] is False

    def test_out_of_range_page(self, engine_with_data):
        templates = engine_with_data.list_templates()
        tid = templates[0]["template_id"]
        result = engine_with_data.get_original_logs_page(tid, page=9999, page_size=200)
        assert result["items"] == []
        assert result["has_next"] is False

    def test_has_next_false_when_all_fit(self, engine_with_data):
        templates = engine_with_data.list_templates()
        tid = templates[0]["template_id"]
        result = engine_with_data.get_original_logs_page(tid, page=0, page_size=10000)
        assert result["has_next"] is False

    def test_pagination_page_size_one(self, engine_with_data):
        """page_size=1로 여러 로그를 가진 템플릿을 순회한다."""
        templates = engine_with_data.list_templates()
        # 2개 이상의 로그를 가진 템플릿 찾기
        target_tid = None
        for t in templates:
            logs = engine_with_data.get_original_logs(t["template_id"])
            if len(logs) >= 2:
                target_tid = t["template_id"]
                break

        if target_tid is None:
            pytest.skip("No template with 2+ logs")

        page0 = engine_with_data.get_original_logs_page(target_tid, page=0, page_size=1)
        page1 = engine_with_data.get_original_logs_page(target_tid, page=1, page_size=1)
        assert len(page0["items"]) == 1
        assert len(page1["items"]) == 1
        assert page0["items"] != page1["items"]
        assert page0["has_next"] is True
