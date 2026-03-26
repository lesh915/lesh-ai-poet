# 개발 가이드: log-template-agent-mcp

## 1. 프로젝트 구조

```
apps/log-template-agent-mcp/
├── PRD.md                        # 제품 요구사항 문서
├── DEV_GUIDE.md                  # 개발 가이드 (이 파일)
├── requirements.txt              # 의존성
├── .env.example                  # 환경변수 예시
│
├── core/
│   ├── __init__.py
│   └── log_engine.py             # 로그 수집·파싱·템플릿화 통합 엔진
│
├── mcp/
│   ├── __init__.py
│   ├── server.py                 # fastmcp 서버 진입점
│   └── tools.py                  # MCP 툴 정의
│
├── agent/
│   ├── __init__.py
│   ├── graph.py                  # LangGraph StateGraph 정의 (노드·엣지)
│   ├── nodes.py                  # 각 노드 구현 (route / think / execute / synthesize / chunk_analyze)
│   ├── state.py                  # AgentState TypedDict 정의
│   └── prompts.py                # 노드별 시스템 프롬프트
│
└── tests/
    ├── test_log_engine.py
    ├── test_mcp_tools.py
    └── test_agent.py
```

---

## 2. 의존성 (requirements.txt)

```text
# 로그 파싱 · 템플릿화
drain3>=0.9.11
pandas>=2.0.0

# MCP 서버
fastmcp>=2.0.0

# LangChain · LangGraph · LLM
langchain>=0.3.0
langchain-anthropic>=0.3.0
langchain-core>=0.3.0
langgraph>=0.2.0

# 설정 관리
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
```

> **참고**: `drain3` 최신 버전은 GitHub에서 직접 설치를 권장합니다.
> ```bash
> pip install git+https://github.com/logpai/Drain3.git
> ```

---

## 3. 환경변수 (.env.example)

```dotenv
# Anthropic API Key (LangChain 에이전트용)
ANTHROPIC_API_KEY=sk-ant-...

# 에이전트에서 사용할 Claude 모델
AGENT_MODEL=claude-sonnet-4-6

# Drain3 기본 파라미터
DRAIN_SIM_TH=0.4
DRAIN_DEPTH=4

# MCP 서버 설정
MCP_HOST=0.0.0.0
MCP_PORT=8000

# 대용량 분석 청크 설정
TEMPLATE_CHUNK_SIZE=50    # 한 번에 처리할 템플릿 수
LOG_CHUNK_SIZE=200        # 한 번에 처리할 원본 로그 수
```

---

## 4. 모듈 상세 구현 가이드

### 4.1 `core/log_engine.py` — 통합 엔진

`drain3-log-matching`의 세 모듈을 조합하여 단일 상태 객체(`LogEngine`)로 관리한다.

```python
# core/log_engine.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../drain3-log-matching"))

from log_parser import parse_log_text, parse_log_file
from drain3_extractor import build_template_miner, extract_templates_from_entries
from log_store import (
    build_log_dataframe, build_template_dataframe,
    build_merged_dataframe, build_cluster_summary_dataframe,
    search_by_keyword, search_by_field, search_by_template_id,
    search_by_datetime_range, search_combined,
)

class LogEngine:
    """로그 파싱·템플릿화·검색의 단일 상태 관리 객체"""

    def __init__(self, sim_th: float = 0.4, depth: int = 4):
        self.miner = build_template_miner(sim_th=sim_th, depth=depth)
        self.merged_df = None   # pd.DataFrame | None
        self._entries = []
        self._results = []

    def ingest_text(self, log_text: str, reset: bool = False) -> dict:
        """로그 텍스트를 수집·템플릿화하고 상태를 갱신한다."""
        ...

    def ingest_file(self, file_path: str, reset: bool = False) -> dict:
        """로그 파일을 수집·템플릿화하고 상태를 갱신한다."""
        ...

    def list_templates(self) -> list[dict]:
        """학습된 템플릿 클러스터 목록을 반환한다."""
        ...

    def get_template(self, template_id: int) -> dict | None:
        """특정 템플릿 ID의 상세 정보를 반환한다."""
        ...

    def get_original_logs(self, template_id: int) -> list[dict]:
        """특정 템플릿 ID에 매칭된 원본 로그 목록을 반환한다."""
        ...

    def search(self, **kwargs) -> list[dict]:
        """복합 조건 검색 결과를 반환한다."""
        ...

    # ── 청크(페이지) 기반 조회 ─────────────────────────────────────
    def list_templates_page(self, page: int = 0, page_size: int = 50) -> dict:
        """
        템플릿 목록을 페이지 단위로 반환한다 (대용량 데이터 토큰 초과 방지).

        Args:
            page: 0-based 페이지 번호
            page_size: 페이지당 템플릿 수

        Returns:
            {
                "items": [...],        # 이번 페이지 템플릿 목록
                "page": int,
                "page_size": int,
                "total": int,          # 전체 템플릿 수
                "has_next": bool
            }
        """
        ...

    def get_original_logs_page(
        self, template_id: int, page: int = 0, page_size: int = 200
    ) -> dict:
        """
        특정 템플릿의 원본 로그를 페이지 단위로 반환한다.

        Returns:
            {"items": [...], "page": int, "total": int, "has_next": bool}
        """
        ...
```

**설계 포인트**
- `LogEngine`은 싱글턴으로 MCP 서버 프로세스 수명 동안 유지한다.
- `reset=True` 시 miner·DataFrame을 초기화하고 새로 구성한다.
- `merged_df`가 None이면 각 검색 메서드는 빈 결과를 반환한다.
- `list_templates_page` / `get_original_logs_page` 는 대용량 로그 분석 시 에이전트가 청크 단위로 순회하며 토큰 한도 초과를 방지한다.

---

### 4.2 `mcp/tools.py` — MCP 툴 정의

`fastmcp`의 `@mcp.tool()` 데코레이터로 각 툴을 정의한다.

```python
# mcp/tools.py
from fastmcp import FastMCP
from core.log_engine import LogEngine

mcp = FastMCP("log-template-agent")
engine = LogEngine()


@mcp.tool()
def ingest_log_text(log_text: str, reset: bool = False) -> dict:
    """
    로그 텍스트를 파싱하고 Drain3 템플릿을 추출합니다.

    Args:
        log_text: 여러 줄의 로그 텍스트 문자열
        reset: True이면 기존 데이터를 초기화하고 새로 시작

    Returns:
        {"ingested": int, "template_count": int}
    """
    return engine.ingest_text(log_text, reset=reset)


@mcp.tool()
def ingest_log_file(file_path: str, reset: bool = False) -> dict:
    """
    로그 파일을 파싱하고 Drain3 템플릿을 추출합니다.

    Args:
        file_path: 로그 파일 절대/상대 경로
        reset: True이면 기존 데이터를 초기화하고 새로 시작

    Returns:
        {"ingested": int, "template_count": int}
    """
    return engine.ingest_file(file_path, reset=reset)


@mcp.tool()
def list_templates() -> list[dict]:
    """
    현재 학습된 모든 Drain3 템플릿 클러스터 목록을 반환합니다.

    Returns:
        [{"template_id": int, "template": str, "cluster_size": int}, ...]
    """
    return engine.list_templates()


@mcp.tool()
def get_template(template_id: int) -> dict:
    """
    특정 템플릿 ID의 상세 정보를 반환합니다.

    Args:
        template_id: 조회할 템플릿(클러스터) ID

    Returns:
        {"template_id": int, "template": str, "cluster_size": int} 또는 빈 dict
    """
    return engine.get_template(template_id) or {}


@mcp.tool()
def get_original_logs(template_id: int) -> list[dict]:
    """
    특정 템플릿 ID에 매칭된 원본 로그 목록을 반환합니다.

    Args:
        template_id: 조회할 템플릿(클러스터) ID

    Returns:
        원본 로그 레코드 리스트 (line_number, datetime, system, level, ...)
    """
    return engine.get_original_logs(template_id)


@mcp.tool()
def search_logs(
    keyword: str | None = None,
    level: str | None = None,
    system: str | None = None,
    category: str | None = None,
    template_id: int | None = None,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    """
    여러 조건을 AND로 조합하여 로그를 검색하고 템플릿 정보를 함께 반환합니다.

    Args:
        keyword: 메시지/템플릿 키워드 (대소문자 무시)
        level: 로그 레벨 (INFO / WARN / ERROR 등)
        system: 시스템 이름
        category: 카테고리
        template_id: 특정 템플릿 ID
        start: 시작 날짜시간 (예: "2024-01-15 09:00:00")
        end: 종료 날짜시간

    Returns:
        매칭 로그 레코드 리스트
    """
    return engine.search(
        keyword=keyword, level=level, system=system,
        category=category, template_id=template_id,
        datetime_start=start, datetime_end=end,
    )


@mcp.tool()
def list_templates_page(page: int = 0, page_size: int = 50) -> dict:
    """
    템플릿 목록을 페이지 단위로 반환합니다 (대용량 데이터 토큰 초과 방지).

    Args:
        page: 0-based 페이지 번호
        page_size: 페이지당 템플릿 수 (기본 50)

    Returns:
        {"items": [...], "page": int, "page_size": int, "total": int, "has_next": bool}
    """
    return engine.list_templates_page(page=page, page_size=page_size)


@mcp.tool()
def get_original_logs_page(
    template_id: int, page: int = 0, page_size: int = 200
) -> dict:
    """
    특정 템플릿의 원본 로그를 페이지 단위로 반환합니다.

    Args:
        template_id: 조회할 템플릿 ID
        page: 0-based 페이지 번호
        page_size: 페이지당 로그 수 (기본 200)

    Returns:
        {"items": [...], "page": int, "total": int, "has_next": bool}
    """
    return engine.get_original_logs_page(
        template_id=template_id, page=page, page_size=page_size
    )


@mcp.tool()
def ask_agent(query: str) -> dict:
    """
    자연어 질의를 LangChain 에이전트에 전달하고 응답을 반환합니다.

    에이전트는 질의 의도에 따라 템플릿 정보 또는 원본 로그 또는
    혼합 결과를 자동으로 선택하여 자연어 요약과 함께 반환합니다.

    Args:
        query: 자연어 질의 문자열

    Returns:
        {
            "mode": "template | original | mixed",
            "templates": [...],
            "logs": [...],
            "total_count": int,
            "summary": str
        }
    """
    from agent.agent import run_agent
    return run_agent(query, engine)
```

---

### 4.3 `mcp/server.py` — fastmcp 서버 진입점

```python
# mcp/server.py
from mcp.tools import mcp

if __name__ == "__main__":
    mcp.run()
```

**실행 방법**

```bash
# stdio 모드 (Claude Desktop 등 MCP 클라이언트용)
python -m mcp.server

# HTTP/SSE 모드 (개발·테스트용)
python -m mcp.server --transport sse --port 8000
```

---

### 4.4 `agent/state.py` — AgentState 정의

```python
# agent/state.py
from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


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
    chunk_cursor: dict          # {"template_page": int, "log_pages": dict[int, int]}
    chunk_summaries: list[str]  # 청크별 중간 요약 누적

    # synthesize 노드가 결정한 최종 응답 모드
    response_mode: str          # "template" | "original" | "mixed"

    # 최종 응답
    result: dict
```

---

### 4.5 `agent/prompts.py` — 노드별 프롬프트

```python
# agent/prompts.py

ROUTE_PROMPT = """
당신은 로그 분석 요청을 분류하는 전문가입니다.
사용자 질의를 보고 아래 세 가지 중 하나로 분류하세요.

- simple    : 단일 툴 호출로 해결 가능 (특정 레벨 검색, 템플릿 목록 조회 등)
- complex   : 여러 툴을 순서대로 호출해야 하며 중간 추론이 필요한 경우
- bulk_analysis : "전체 분석", "모든 로그", "전체 패턴" 처럼
                  데이터 전체를 순회해야 하는 경우 (청크 분석 필요)

응답은 반드시 JSON만 출력하세요:
{{"complexity": "simple|complex|bulk_analysis", "reason": "한 줄 이유"}}
"""

THINK_PROMPT = """
당신은 로그 분석 계획을 수립하는 전문가입니다.
사용자 질의와 현재까지 수집된 결과를 보고 다음 단계를 계획하세요.

사용 가능한 툴:
- list_templates          : 전체 템플릿 목록
- list_templates_page     : 템플릿 목록 페이지 조회 (대용량)
- get_template            : 특정 템플릿 상세
- get_original_logs       : 특정 템플릿의 원본 로그
- get_original_logs_page  : 원본 로그 페이지 조회 (대용량)
- search_logs             : 복합 조건 검색

응답은 반드시 JSON만 출력하세요:
{{
  "steps": [
    {{"tool": "툴명", "args": {{...}}, "reason": "이유"}},
    ...
  ],
  "response_mode": "template|original|mixed"
}}
"""

CHUNK_ANALYZE_PROMPT = """
당신은 로그 템플릿 분석가입니다.
아래는 전체 데이터의 일부(청크)입니다. 이 청크만을 분석하여 핵심 패턴과 이상 징후를 요약하세요.
이전 청크 요약이 있다면 그것도 참고하여 일관된 분석을 유지하세요.

이전 청크 요약:
{previous_summaries}

현재 청크 데이터:
{chunk_data}

응답은 2-5문장의 한국어 요약으로만 출력하세요.
"""

SYNTHESIZE_PROMPT = """
당신은 로그 분석 결과를 정리하는 전문가입니다.
수집된 모든 결과를 종합하여 사용자 질의에 대한 최종 응답을 생성하세요.

응답 모드: {response_mode}
- template  : 템플릿 패턴 위주로 요약
- original  : 원본 로그 상세 내용 위주로 요약
- mixed     : 템플릿 요약 + 대표 원본 로그 샘플 함께 제공

응답은 반드시 JSON만 출력하세요:
{{
  "mode": "template|original|mixed",
  "templates": [...],
  "logs": [...],
  "total_count": 0,
  "summary": "자연어 최종 요약"
}}
"""
```

---

### 4.6 `agent/nodes.py` — 노드 구현

```python
# agent/nodes.py
import json
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState
from agent.prompts import (
    ROUTE_PROMPT, THINK_PROMPT,
    CHUNK_ANALYZE_PROMPT, SYNTHESIZE_PROMPT,
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
        response = llm.invoke([
            SystemMessage(content=ROUTE_PROMPT),
            HumanMessage(content=state["query"]),
        ])
        parsed = json.loads(response.content)
        return {**state, "complexity": parsed["complexity"]}

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

        response = llm.invoke([
            SystemMessage(content=THINK_PROMPT),
            HumanMessage(content=context),
        ])
        plan = json.loads(response.content)
        return {**state, "plan": plan, "response_mode": plan.get("response_mode", "mixed")}

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
            results = engine.search(keyword=_extract_keyword(state["query"]))
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
        cursor = state.get("chunk_cursor", {"template_page": 0})
        page = cursor.get("template_page", 0)
        chunk_summaries = list(state.get("chunk_summaries", []))

        page_result = engine.list_templates_page(page=page, page_size=50)
        items = page_result["items"]
        has_next = page_result["has_next"]

        if not items:
            return {**state, "chunk_cursor": {**cursor, "done": True}}

        # 청크 데이터를 LLM으로 요약
        response = llm.invoke([
            SystemMessage(content=CHUNK_ANALYZE_PROMPT.format(
                previous_summaries="\n".join(chunk_summaries[-3:]) or "없음",
                chunk_data=json.dumps(items, ensure_ascii=False),
            )),
        ])
        chunk_summaries.append(response.content.strip())

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
                "summary": combined_summary,
            }
            return {**state, "result": result}

        context = json.dumps({
            "query": state["query"],
            "tool_results": state.get("tool_results", []),
        }, ensure_ascii=False)

        response = llm.invoke([
            SystemMessage(content=SYNTHESIZE_PROMPT.format(
                response_mode=state.get("response_mode", "mixed"),
            )),
            HumanMessage(content=context),
        ])
        result = json.loads(response.content)
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
    return fn() if fn else {"error": f"Unknown tool: {tool_name}"}


def _extract_keyword(query: str) -> str | None:
    """질의에서 핵심 키워드를 단순 추출한다 (simple 분기 전용)."""
    stop_words = {"의", "을", "를", "이", "가", "은", "는", "로", "에서", "알려줘", "보여줘"}
    tokens = [t for t in query.split() if t not in stop_words and len(t) > 1]
    return tokens[0] if tokens else None
```

---

### 4.7 `agent/graph.py` — LangGraph StateGraph 정의

```python
# agent/graph.py
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from agent.state import AgentState
from agent.nodes import make_nodes
from core.log_engine import LogEngine


def build_graph(llm: ChatAnthropic, engine: LogEngine):
    """
    LangGraph StateGraph를 빌드하고 컴파일된 그래프를 반환한다.

    노드 구성:
        route → (simple) → execute → synthesize → END
              → (complex) → think → execute → synthesize → END
              → (bulk_analysis) → chunk_analyze (루프) → synthesize → END

    think ↔ execute 사이에 재추론 루프 가능:
        execute → (추가 정보 필요) → think → execute → ...
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
            "rethink":    "think",      # 추가 정보 필요 → 재추론
            "synthesize": "synthesize", # 충분한 정보 수집 → 최종화
        },
    )

    # chunk_analyze → 다음 청크 존재 여부 판단
    builder.add_conditional_edges(
        "chunk_analyze",
        _chunk_done,
        {
            "continue":  "chunk_analyze",  # 다음 페이지 존재 → 반복
            "synthesize": "synthesize",    # 모든 청크 완료 → 최종화
        },
    )

    # synthesize → 종료
    builder.add_edge("synthesize", END)

    return builder.compile()


# ── 엣지 조건 함수 ──────────────────────────────────────────────────

def _route_decision(state: AgentState) -> str:
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

    # plan이 있는데 실행 수가 부족한 경우
    if planned_count > 0 and executed_count < planned_count:
        return "rethink"

    # think 루프 횟수 제한 (state에 rethink_count 저장)
    rethink_count = state.get("rethink_count", 0)
    if rethink_count >= 3:
        return "synthesize"

    return "synthesize"


def _chunk_done(state: AgentState) -> str:
    cursor = state.get("chunk_cursor", {})
    return "synthesize" if cursor.get("done") else "continue"
```

---

### 4.8 `agent/runner.py` — 에이전트 진입점

```python
# agent/runner.py
from langchain_anthropic import ChatAnthropic
from pydantic_settings import BaseSettings
from agent.graph import build_graph
from core.log_engine import LogEngine


class Settings(BaseSettings):
    anthropic_api_key: str
    agent_model: str = "claude-sonnet-4-6"

    class Config:
        env_file = ".env"


_settings = Settings()
_llm = ChatAnthropic(
    model=_settings.agent_model,
    api_key=_settings.anthropic_api_key,
    temperature=0,
)


def run_agent(query: str, engine: LogEngine) -> dict:
    """
    자연어 질의를 LangGraph 에이전트로 처리하고 구조화된 결과를 반환한다.

    Args:
        query: 사용자 자연어 질의
        engine: 공유 LogEngine 인스턴스

    Returns:
        {"mode": str, "templates": list, "logs": list, "total_count": int, "summary": str}
    """
    graph = build_graph(_llm, engine)

    initial_state: dict = {
        "query": query,
        "complexity": "",
        "plan": {},
        "tool_results": [],
        "chunk_cursor": {},
        "chunk_summaries": [],
        "response_mode": "mixed",
        "result": {},
    }

    final_state = graph.invoke(initial_state)
    return final_state.get("result", {"summary": "응답 생성 실패", "mode": "mixed"})

---

## 5. MCP 클라이언트 설정 예시

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "log-template-agent": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "/path/to/apps/log-template-agent-mcp",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

### Cursor / VSCode (`.cursor/mcp.json` 또는 `mcp.json`)

```json
{
  "servers": {
    "log-template-agent": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "/path/to/apps/log-template-agent-mcp"
    }
  }
}
```

---

## 6. 데이터 흐름

```
[클라이언트 / MCP 호스트]
        │
        │ MCP 툴 호출 (JSON-RPC over stdio or SSE)
        ▼
[mcp/server.py  ←  mcp/tools.py]
        │
        ├─ ingest_* ──► core/log_engine.py
        │                   ├─ log_parser        (파싱)
        │                   ├─ drain3_extractor  (템플릿 추출)
        │                   └─ log_store         (DataFrame 관리)
        │
        ├─ list_templates / get_template / get_original_logs
        │       └─► LogEngine 상태 조회
        │
        ├─ search_logs ──► log_store.search_combined()
        │
        └─ ask_agent ──► agent/runner.py
                            └─ LangGraph StateGraph
                                ├─ route_node        (복잡도 분류)
                                │     ├─ simple       → execute_node
                                │     ├─ complex      → think_node → execute_node
                                │     └─ bulk_analysis→ chunk_analyze_node (루프)
                                ├─ think_node        (실행 계획 수립)
                                ├─ execute_node      (툴 순차 실행)
                                │     └─ (추가 추론 필요 시) → think_node (재루프)
                                ├─ chunk_analyze_node(청크별 LLM 요약, 루프)
                                └─ synthesize_node   (최종 응답 통합)
```

---

## 7. 테스트 전략

### 7.1 단위 테스트 (`tests/test_log_engine.py`)

```python
import pytest
from core.log_engine import LogEngine

SAMPLE_LOG = """
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:01:10] [AuthService] [ERROR] [Thread-3] [Security] [Login failed for user admin from IP 10.0.0.1]
[2024-01-15 09:02:00] [APIGateway] [INFO] [Thread-10] [Network] [Received GET request from client 172.16.0.1 path /api/v1/users]
"""

@pytest.fixture
def engine():
    e = LogEngine()
    e.ingest_text(SAMPLE_LOG)
    return e

def test_ingest_returns_count(engine):
    result = engine.ingest_text(SAMPLE_LOG, reset=True)
    assert result["ingested"] == 3

def test_list_templates_not_empty(engine):
    templates = engine.list_templates()
    assert len(templates) >= 1

def test_get_original_logs_by_template(engine):
    templates = engine.list_templates()
    tid = templates[0]["template_id"]
    logs = engine.get_original_logs(tid)
    assert len(logs) > 0
    assert "message" in logs[0]

def test_search_by_level(engine):
    results = engine.search(level="ERROR")
    assert all(r["level"] == "ERROR" for r in results)
```

### 7.2 MCP 툴 테스트 (`tests/test_mcp_tools.py`)

- fastmcp의 `Client` 또는 `in_memory` 모드로 각 툴 응답 형식 검증
- `list_templates_page` / `get_original_logs_page` 페이지네이션 경계 테스트

### 7.3 에이전트 그래프 단위 테스트 (`tests/test_agent.py`)

```python
from unittest.mock import MagicMock, patch
from agent.graph import build_graph, _route_decision, _needs_rethink, _chunk_done
from agent.state import AgentState

# 엣지 조건 함수 단위 테스트
def test_route_simple():
    state = AgentState(complexity="simple", ...)
    assert _route_decision(state) == "simple"

def test_route_bulk():
    state = AgentState(complexity="bulk_analysis", ...)
    assert _route_decision(state) == "bulk_analysis"

def test_chunk_done_continues():
    state = AgentState(chunk_cursor={"done": False}, ...)
    assert _chunk_done(state) == "continue"

def test_chunk_done_finishes():
    state = AgentState(chunk_cursor={"done": True}, ...)
    assert _chunk_done(state) == "synthesize"

def test_rethink_limit():
    # think 루프 3회 초과 시 강제 synthesize
    state = AgentState(rethink_count=3, plan={"steps": [...]}, tool_results=[], ...)
    assert _needs_rethink(state) == "synthesize"

# LLM mock으로 전체 그래프 실행 테스트
@patch("agent.nodes.ChatAnthropic")
def test_graph_simple_flow(mock_llm):
    mock_llm.return_value.invoke.side_effect = [
        MagicMock(content='{"complexity": "simple", "reason": "단순 검색"}'),
        MagicMock(content='{"mode": "template", "templates": [], "logs": [], "total_count": 0, "summary": "ok"}'),
    ]
    engine = MagicMock()
    engine.search.return_value = []
    graph = build_graph(mock_llm(), engine)
    result = graph.invoke({"query": "ERROR 로그 보여줘", ...})
    assert result["result"]["mode"] in ("template", "original", "mixed")
```

---

## 8. 개발 순서 (권장)

```
1. requirements.txt 설치 및 .env 구성
2. core/log_engine.py 구현 (list_templates_page 포함) → test_log_engine.py 통과
3. mcp/tools.py + mcp/server.py 구현 → MCP Inspector로 툴 확인
4. agent/state.py → agent/prompts.py → agent/nodes.py 순서로 구현
5. agent/graph.py 구현 → 엣지 조건 단위 테스트 통과
6. agent/runner.py 구현 → ask_agent E2E 동작 확인
7. tests/ 전체 통과 확인
8. README.md 작성 후 PR 생성
```

---

## 9. 자주 묻는 질문

**Q. drain3-log-matching 모듈을 어떻게 참조하나요?**
A. 같은 모노레포 내에 있으므로 `sys.path`에 상대 경로를 추가하거나,
`pyproject.toml`의 `[tool.uv.sources]`로 로컬 경로를 패키지로 설정합니다.

**Q. fastmcp 버전 선택 기준은?**
A. fastmcp 2.x 이상을 권장합니다. `@mcp.tool()` 데코레이터와 타입 힌트 기반 스키마 자동 생성을 지원합니다.

**Q. LangGraph think 루프가 무한히 반복되지 않나요?**
A. `_needs_rethink` 엣지 함수에서 `rethink_count >= 3` 조건으로 최대 3회로 제한합니다.
또한 LangGraph `compile()`에 `recursion_limit`을 설정하면 그래프 수준에서도 제어할 수 있습니다.

**Q. 대용량 분석 시 chunk_analyze가 몇 번 루프를 도나요?**
A. `TEMPLATE_CHUNK_SIZE=50` 기준으로 템플릿 500개라면 10회 루프합니다.
각 루프에서 LLM 호출 1회 + `list_templates_page` 1회가 발생합니다.

**Q. LangChain 에이전트가 어떤 모델을 사용하나요?**
A. 기본값은 `claude-sonnet-4-6`이며 `.env`의 `AGENT_MODEL` 값으로 변경할 수 있습니다.

**Q. MCP 서버를 HTTP 모드로 실행하려면?**
A. fastmcp는 `--transport sse` 옵션으로 SSE 기반 HTTP 서버를 지원합니다.
개발·디버깅 시 `--port 8000` 과 함께 사용하면 브라우저나 curl로 확인할 수 있습니다.
