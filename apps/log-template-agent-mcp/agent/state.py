"""
agent/state.py
LangGraph AgentState TypedDict 정의

에이전트의 각 노드는 이 상태를 읽고 갱신된 상태를 반환한다.
"""

from typing import Any
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # 사용자 원본 질의
    query: str

    # route 노드가 분류한 복잡도: "simple" | "complex" | "bulk_analysis"
    complexity: str

    # think 노드가 생성한 실행 계획 (툴 호출 순서, 예상 mode)
    plan: dict

    # execute 노드가 수집한 툴 결과 누적
    tool_results: list[dict]

    # 대용량 청크 분석 전용 커서
    chunk_cursor: dict          # {"template_page": int, "log_pages": dict[int, int], "done": bool}
    chunk_summaries: list[str]  # 청크별 중간 요약 누적

    # synthesize 노드가 결정한 최종 응답 모드
    response_mode: str          # "template" | "original" | "mixed"

    # think 루프 횟수 (최대 3회 제한)
    rethink_count: int

    # 최종 응답
    result: dict
