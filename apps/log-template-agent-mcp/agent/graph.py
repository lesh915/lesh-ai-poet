"""
agent/graph.py
LangGraph StateGraph 정의

노드 구성:
    route → (simple) → execute → synthesize → END
          → (complex) → think → execute → synthesize → END
          → (bulk_analysis) → chunk_analyze (루프) → synthesize → END

think ↔ execute 사이에 재추론 루프 가능:
    execute → (추가 정보 필요) → think → execute → ...
"""

from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from agent.state import AgentState
from agent.nodes import make_nodes
from core.log_engine import LogEngine


def build_graph(llm: ChatAnthropic, engine: LogEngine):
    """
    LangGraph StateGraph를 빌드하고 컴파일된 그래프를 반환한다.

    Args:
        llm: ChatAnthropic LLM 인스턴스
        engine: LogEngine 인스턴스

    Returns:
        컴파일된 LangGraph StateGraph
    """
    route_node, think_node, execute_node, chunk_analyze_node, synthesize_node = \
        make_nodes(llm, engine)

    builder = StateGraph(AgentState)

    # 노드 등록
    builder.add_node("route",         route_node)
    builder.add_node("think",         think_node)
    builder.add_node("execute",       execute_node)
    builder.add_node("chunk_analyze", chunk_analyze_node)
    builder.add_node("synthesize",    synthesize_node)

    # 시작 → route
    builder.set_entry_point("route")

    # route → 복잡도에 따른 분기
    builder.add_conditional_edges(
        "route",
        _route_decision,
        {
            "simple":        "execute",
            "complex":       "think",
            "bulk_analysis": "chunk_analyze",
        },
    )

    # think → execute (계획 수립 후 실행)
    builder.add_edge("think", "execute")

    # execute → 추가 추론 필요 여부 판단
    builder.add_conditional_edges(
        "execute",
        _needs_rethink,
        {
            "rethink":    "think",       # 추가 정보 필요 → 재추론
            "synthesize": "synthesize",  # 충분한 정보 수집 → 최종화
        },
    )

    # chunk_analyze → 다음 청크 존재 여부 판단
    builder.add_conditional_edges(
        "chunk_analyze",
        _chunk_done,
        {
            "continue":   "chunk_analyze",  # 다음 페이지 존재 → 반복
            "synthesize": "synthesize",     # 모든 청크 완료 → 최종화
        },
    )

    # synthesize → 종료
    builder.add_edge("synthesize", END)

    return builder.compile()


# ── 엣지 조건 함수 ──────────────────────────────────────────────────

def _route_decision(state: AgentState) -> str:
    """route 노드 이후 복잡도에 따라 다음 노드를 결정한다."""
    return state.get("complexity", "simple")


def _needs_rethink(state: AgentState) -> str:
    """
    execute 결과가 불충분하거나 plan에 미실행 step이 남아 있으면 rethink.
    최대 3회 think 루프를 허용한다.
    """
    tool_results = state.get("tool_results", [])
    plan = state.get("plan", {})
    executed_count = len(tool_results)
    planned_count = len(plan.get("steps", []))

    # think 루프 횟수 제한
    rethink_count = state.get("rethink_count", 0)
    if rethink_count >= 3:
        return "synthesize"

    # plan이 있는데 실행 수가 부족한 경우
    if planned_count > 0 and executed_count < planned_count:
        return "rethink"

    return "synthesize"


def _chunk_done(state: AgentState) -> str:
    """chunk_analyze 루프 종료 여부를 판단한다."""
    cursor = state.get("chunk_cursor", {})
    return "synthesize" if cursor.get("done") else "continue"
