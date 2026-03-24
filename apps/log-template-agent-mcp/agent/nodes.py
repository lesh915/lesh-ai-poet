"""
agent/nodes.py
LangGraph 각 노드 구현

route / think / execute / chunk_analyze / synthesize 노드를 make_nodes 팩토리로 생성한다.
"""

import json
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState
from agent.prompts import (
    ROUTE_PROMPT,
    THINK_PROMPT,
    CHUNK_ANALYZE_PROMPT,
    SYNTHESIZE_PROMPT,
)
from core.log_engine import LogEngine


def make_nodes(llm: ChatAnthropic, engine: LogEngine):
    """각 노드 함수를 생성하여 반환한다."""

    # ── route_node ─────────────────────────────────────────────────
    def route_node(state: AgentState) -> AgentState:
        """
        질의 복잡도를 분류한다.
        단순 질의는 think를 건너뛰고 execute로 바로 이동한다.
        """
        try:
            response = llm.invoke([
                SystemMessage(content=ROUTE_PROMPT),
                HumanMessage(content=state["query"]),
            ])
            parsed = json.loads(response.content)
            complexity = parsed.get("complexity", "simple")
        except (json.JSONDecodeError, Exception):
            complexity = "simple"

        return {**state, "complexity": complexity}

    # ── think_node ─────────────────────────────────────────────────
    def think_node(state: AgentState) -> AgentState:
        """
        현재 수집 결과를 바탕으로 다음 실행 계획을 수립한다.
        complex 질의 또는 execute 후 추가 추론이 필요할 때 호출된다.
        """
        context = json.dumps({
            "query": state["query"],
            "collected_so_far": state.get("tool_results", []),
        }, ensure_ascii=False)

        try:
            response = llm.invoke([
                SystemMessage(content=THINK_PROMPT),
                HumanMessage(content=context),
            ])
            plan = json.loads(response.content)
        except (json.JSONDecodeError, Exception):
            plan = {"steps": [], "response_mode": "mixed"}

        rethink_count = state.get("rethink_count", 0) + 1
        return {
            **state,
            "plan": plan,
            "response_mode": plan.get("response_mode", "mixed"),
            "rethink_count": rethink_count,
        }

    # ── execute_node ────────────────────────────────────────────────
    def execute_node(state: AgentState) -> AgentState:
        """
        plan의 steps를 순서대로 실행하고 결과를 tool_results에 누적한다.
        simple 복잡도인 경우 plan이 없으면 기본 검색을 수행한다.
        """
        plan = state.get("plan", {})
        steps = plan.get("steps", [])
        tool_results = list(state.get("tool_results", []))

        # simple 분기: plan 없이 기본 동작
        if not steps:
            keyword = _extract_keyword(state["query"])
            results = engine.search(keyword=keyword)
            tool_results.append({"tool": "search_logs", "result": results})
            return {**state, "tool_results": tool_results}

        for step in steps:
            tool_name = step["tool"]
            args = step.get("args", {})
            result = _call_engine_tool(engine, tool_name, args)
            tool_results.append({"tool": tool_name, "args": args, "result": result})

        return {**state, "tool_results": tool_results}

    # ── chunk_analyze_node ──────────────────────────────────────────
    def chunk_analyze_node(state: AgentState) -> AgentState:
        """
        대용량 분석 전용 노드.
        템플릿을 TEMPLATE_CHUNK_SIZE 단위로 순회하며 LLM으로 청크별 요약을 생성한다.
        모든 페이지를 처리할 때까지 반복 (LangGraph 루프).
        """
        cursor = state.get("chunk_cursor", {})
        # 최초 진입 시 초기화
        if not cursor:
            cursor = {"template_page": 0, "done": False}

        page = cursor.get("template_page", 0)
        chunk_summaries = list(state.get("chunk_summaries", []))

        page_result = engine.list_templates_page(page=page, page_size=50)
        items = page_result["items"]
        has_next = page_result["has_next"]

        if not items:
            return {**state, "chunk_cursor": {**cursor, "done": True}}

        # 청크 데이터를 LLM으로 요약
        try:
            response = llm.invoke([
                SystemMessage(content=CHUNK_ANALYZE_PROMPT.format(
                    previous_summaries="\n".join(chunk_summaries[-3:]) if chunk_summaries else "없음",
                    chunk_data=json.dumps(items, ensure_ascii=False),
                )),
            ])
            chunk_summaries.append(response.content.strip())
        except Exception as e:
            chunk_summaries.append(f"청크 분석 오류: {str(e)}")

        new_cursor = {**cursor, "template_page": page + 1, "done": not has_next}
        return {**state, "chunk_cursor": new_cursor, "chunk_summaries": chunk_summaries}

    # ── synthesize_node ─────────────────────────────────────────────
    def synthesize_node(state: AgentState) -> AgentState:
        """
        모든 수집 결과(tool_results + chunk_summaries)를 통합하여 최종 응답을 생성한다.
        """
        # bulk_analysis는 청크 요약을 직접 종합
        if state.get("complexity") == "bulk_analysis":
            combined_summary = "\n".join(state.get("chunk_summaries", []))
            result = {
                "mode": "mixed",
                "templates": [],
                "logs": [],
                "total_count": engine.total_log_count(),
                "summary": combined_summary or "분석 결과가 없습니다.",
            }
            return {**state, "result": result}

        # tool_results가 너무 크면 축약
        raw_results = state.get("tool_results", [])
        truncated_results = []
        for item in raw_results:
            item_copy = dict(item)
            result_data = item_copy.get("result", [])
            if isinstance(result_data, list) and len(str(result_data)) > 5000:
                item_copy["result"] = result_data[:10]
                item_copy["result_truncated"] = True
            elif isinstance(result_data, str) and len(result_data) > 5000:
                item_copy["result"] = result_data[:5000] + "...(truncated)"
            truncated_results.append(item_copy)

        context = json.dumps({
            "query": state["query"],
            "tool_results": truncated_results,
        }, ensure_ascii=False)

        try:
            response = llm.invoke([
                SystemMessage(content=SYNTHESIZE_PROMPT.format(
                    response_mode=state.get("response_mode", "mixed"),
                )),
                HumanMessage(content=context),
            ])
            result = json.loads(response.content)
        except (json.JSONDecodeError, Exception) as e:
            result = {
                "mode": state.get("response_mode", "mixed"),
                "templates": [],
                "logs": [],
                "total_count": engine.total_log_count(),
                "summary": f"응답 생성 중 오류 발생: {str(e)}",
            }

        return {**state, "result": result}

    return route_node, think_node, execute_node, chunk_analyze_node, synthesize_node


# ── 내부 유틸 ─────────────────────────────────────────────────────

def _call_engine_tool(engine: LogEngine, tool_name: str, args: dict):
    """tool_name 문자열로 LogEngine 메서드를 동적 호출한다."""
    dispatch = {
        "list_templates":         lambda: engine.list_templates(),
        "list_templates_page":    lambda: engine.list_templates_page(**args),
        "get_template":           lambda: engine.get_template(**args),
        "get_original_logs":      lambda: engine.get_original_logs(**args),
        "get_original_logs_page": lambda: engine.get_original_logs_page(**args),
        "search_logs":            lambda: engine.search(**args),
    }
    fn = dispatch.get(tool_name)
    if fn:
        try:
            return fn()
        except Exception as e:
            return {"error": str(e)}
    return {"error": f"Unknown tool: {tool_name}"}


def _extract_keyword(query: str) -> str | None:
    """질의에서 핵심 키워드를 단순 추출한다 (simple 분기 전용)."""
    stop_words = {"의", "을", "를", "이", "가", "은", "는", "로", "에서", "알려줘", "보여줘"}
    tokens = [t for t in query.split() if t not in stop_words and len(t) > 1]
    return tokens[0] if tokens else None
