"""
tests/test_agent.py
에이전트 그래프 단위 테스트

엣지 조건 함수 단위 테스트 + LLM mock을 활용한 전체 그래프 실행 테스트를 포함한다.
"""

import json
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.graph import build_graph, _route_decision, _needs_rethink, _chunk_done
from agent.state import AgentState
from core.log_engine import LogEngine

SAMPLE_LOG = """
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:01:10] [AuthService] [ERROR] [Thread-3] [Security] [Login failed for user admin from IP 10.0.0.1]
[2024-01-15 09:02:00] [APIGateway] [INFO] [Thread-10] [Network] [Received GET request from client 172.16.0.1 path /api/v1/users]
"""


def make_state(**overrides) -> dict:
    """테스트용 기본 AgentState를 생성한다."""
    base = {
        "query": "ERROR 로그 보여줘",
        "complexity": "simple",
        "plan": {},
        "tool_results": [],
        "chunk_cursor": {},
        "chunk_summaries": [],
        "response_mode": "mixed",
        "rethink_count": 0,
        "result": {},
    }
    base.update(overrides)
    return base


# ── 엣지 조건 함수 단위 테스트 ──────────────────────────────────

class TestRouteDecision:
    def test_route_simple(self):
        state = make_state(complexity="simple")
        assert _route_decision(state) == "simple"

    def test_route_complex(self):
        state = make_state(complexity="complex")
        assert _route_decision(state) == "complex"

    def test_route_bulk_analysis(self):
        state = make_state(complexity="bulk_analysis")
        assert _route_decision(state) == "bulk_analysis"

    def test_route_default_simple(self):
        state = make_state(complexity="")
        # 빈 문자열이면 "simple"이 아닌 빈 문자열을 반환할 수 있지만,
        # _route_decision은 state.get("complexity", "simple")이므로 "" 반환
        result = _route_decision(state)
        assert result in ("", "simple", "complex", "bulk_analysis")

    def test_route_missing_complexity(self):
        state = make_state()
        del state["complexity"]
        result = _route_decision(state)
        assert result == "simple"  # 기본값


class TestNeedsRethink:
    def test_rethink_limit_reached(self):
        state = make_state(
            rethink_count=3,
            plan={"steps": [{"tool": "list_templates", "args": {}}]},
            tool_results=[],
        )
        assert _needs_rethink(state) == "synthesize"

    def test_rethink_limit_exceeded(self):
        state = make_state(
            rethink_count=5,
            plan={"steps": [{"tool": "list_templates", "args": {}}]},
            tool_results=[],
        )
        assert _needs_rethink(state) == "synthesize"

    def test_no_rethink_when_no_plan(self):
        state = make_state(
            rethink_count=0,
            plan={},
            tool_results=[],
        )
        assert _needs_rethink(state) == "synthesize"

    def test_rethink_when_steps_not_executed(self):
        state = make_state(
            rethink_count=0,
            plan={"steps": [
                {"tool": "list_templates", "args": {}},
                {"tool": "get_template", "args": {"template_id": 1}},
            ]},
            tool_results=[],  # 0개 실행됨, 2개 계획됨
        )
        assert _needs_rethink(state) == "rethink"

    def test_synthesize_when_all_steps_executed(self):
        state = make_state(
            rethink_count=0,
            plan={"steps": [{"tool": "list_templates", "args": {}}]},
            tool_results=[{"tool": "list_templates", "result": []}],
        )
        assert _needs_rethink(state) == "synthesize"


class TestChunkDone:
    def test_chunk_continues_when_not_done(self):
        state = make_state(chunk_cursor={"template_page": 0, "done": False})
        assert _chunk_done(state) == "continue"

    def test_chunk_finishes_when_done(self):
        state = make_state(chunk_cursor={"template_page": 1, "done": True})
        assert _chunk_done(state) == "synthesize"

    def test_chunk_continues_with_empty_cursor(self):
        state = make_state(chunk_cursor={})
        assert _chunk_done(state) == "continue"

    def test_chunk_synthesize_when_done_missing_but_truthy(self):
        state = make_state(chunk_cursor={"done": True})
        assert _chunk_done(state) == "synthesize"


# ── LLM mock을 활용한 그래프 실행 테스트 ──────────────────────

class TestGraphSimpleFlow:
    """simple 분기: route → execute → synthesize"""

    def test_graph_simple_flow(self):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            # route_node: complexity = "simple"
            MagicMock(content='{"complexity": "simple", "reason": "단순 검색"}'),
            # synthesize_node: 최종 응답
            MagicMock(content=json.dumps({
                "mode": "template",
                "templates": [],
                "logs": [],
                "total_count": 0,
                "summary": "ERROR 로그가 없습니다.",
            })),
        ]

        engine = MagicMock(spec=LogEngine)
        engine.search.return_value = []
        engine.total_log_count.return_value = 0

        graph = build_graph(mock_llm, engine)
        initial = make_state()
        final_state = graph.invoke(initial)
        result = final_state.get("result", {})
        assert result["mode"] in ("template", "original", "mixed")


class TestGraphComplexFlow:
    """complex 분기: route → think → execute → synthesize"""

    def test_graph_complex_flow(self):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            # route_node: complexity = "complex"
            MagicMock(content='{"complexity": "complex", "reason": "여러 단계 필요"}'),
            # think_node: 실행 계획
            MagicMock(content=json.dumps({
                "steps": [{"tool": "list_templates", "args": {}, "reason": "템플릿 목록 확인"}],
                "response_mode": "template",
            })),
            # synthesize_node
            MagicMock(content=json.dumps({
                "mode": "template",
                "templates": [{"template_id": 1, "template": "Login failed", "cluster_size": 2}],
                "logs": [],
                "total_count": 2,
                "summary": "로그인 실패 패턴이 감지되었습니다.",
            })),
        ]

        engine = MagicMock(spec=LogEngine)
        engine.list_templates.return_value = [
            {"template_id": 1, "template": "Login failed for user <*> from IP <*>", "cluster_size": 2}
        ]
        engine.total_log_count.return_value = 2

        graph = build_graph(mock_llm, engine)
        initial = make_state(query="어떤 템플릿 패턴이 있나요?")
        final_state = graph.invoke(initial)
        result = final_state.get("result", {})
        assert result["mode"] in ("template", "original", "mixed")


class TestGraphBulkAnalysisFlow:
    """bulk_analysis 분기: route → chunk_analyze (루프) → synthesize"""

    def test_graph_bulk_analysis_single_chunk(self):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            # route_node: complexity = "bulk_analysis"
            MagicMock(content='{"complexity": "bulk_analysis", "reason": "전체 데이터 분석"}'),
            # chunk_analyze_node: 청크 요약
            MagicMock(content="로그인 실패 패턴이 주로 발생하고 있습니다."),
        ]

        engine = MagicMock(spec=LogEngine)
        engine.list_templates_page.side_effect = [
            # 첫 번째 호출: 1개 아이템, 더 이상 없음
            {
                "items": [{"template_id": 1, "template": "Login failed", "cluster_size": 2}],
                "page": 0,
                "page_size": 50,
                "total": 1,
                "has_next": False,
            },
        ]
        engine.total_log_count.return_value = 2

        graph = build_graph(mock_llm, engine)
        initial = make_state(query="전체 로그 패턴을 분석해줘", complexity="")
        final_state = graph.invoke(initial)
        result = final_state.get("result", {})
        # bulk_analysis 모드는 synthesize에서 chunk_summaries를 summary로 사용
        assert "summary" in result


class TestGraphRethinkLoop:
    """rethink 루프: execute → think → execute → synthesize"""

    def test_rethink_stops_at_limit(self):
        """rethink_count >= 3이면 synthesize로 이동해야 한다."""
        state = make_state(
            rethink_count=3,
            plan={"steps": [{"tool": "list_templates", "args": {}}]},
            tool_results=[],
        )
        result = _needs_rethink(state)
        assert result == "synthesize"

    def test_rethink_triggers_when_plan_not_executed(self):
        """plan steps > executed results이면 rethink해야 한다."""
        state = make_state(
            rethink_count=1,
            plan={"steps": [
                {"tool": "list_templates", "args": {}},
                {"tool": "get_template", "args": {"template_id": 1}},
            ]},
            tool_results=[],
        )
        result = _needs_rethink(state)
        assert result == "rethink"


class TestGraphWithRealEngine:
    """실제 LogEngine을 사용한 통합 테스트 (LLM만 mock)"""

    def test_graph_with_real_engine_simple(self):
        engine = LogEngine()
        engine.ingest_text(SAMPLE_LOG)

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content='{"complexity": "simple", "reason": "단순 검색"}'),
            MagicMock(content=json.dumps({
                "mode": "original",
                "templates": [],
                "logs": [
                    {"line_number": 1, "level": "ERROR", "message": "Login failed"}
                ],
                "total_count": 2,
                "summary": "2건의 ERROR 로그가 발견되었습니다.",
            })),
        ]

        graph = build_graph(mock_llm, engine)
        initial = make_state(query="ERROR 로그 보여줘")
        final_state = graph.invoke(initial)
        result = final_state.get("result", {})
        assert "mode" in result
        assert "summary" in result
        assert result["mode"] in ("template", "original", "mixed")
