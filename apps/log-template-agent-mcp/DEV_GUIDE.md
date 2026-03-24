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
│   ├── agent.py                  # LangChain ReAct 에이전트
│   └── prompts.py                # 시스템 프롬프트·Few-shot 예시
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

# LangChain · LLM
langchain>=0.3.0
langchain-anthropic>=0.3.0
langchain-core>=0.3.0

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
```

**설계 포인트**
- `LogEngine`은 싱글턴으로 MCP 서버 프로세스 수명 동안 유지한다.
- `reset=True` 시 miner·DataFrame을 초기화하고 새로 구성한다.
- `merged_df`가 None이면 각 검색 메서드는 빈 결과를 반환한다.

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

### 4.4 `agent/prompts.py` — 시스템 프롬프트

```python
# agent/prompts.py

SYSTEM_PROMPT = """
당신은 로그 분석 전문가 AI입니다. 사용자의 질의를 분석하여 적절한 도구를 호출하고
로그 패턴과 원본 데이터를 효과적으로 제공합니다.

## 응답 결정 규칙

1. **템플릿 중심 응답** (mode: "template")
   - 사용자가 "패턴", "템플릿", "어떤 종류", "형식" 등을 언급할 때
   - 로그 유형 분류·통계가 필요할 때

2. **원본 중심 응답** (mode: "original")
   - 사용자가 "원본", "실제", "상세", "전체 내용" 을 언급할 때
   - 특정 IP, 사용자, 값 등 구체적 파라미터를 요청할 때

3. **혼합 응답** (mode: "mixed")
   - 위 두 경우가 모두 해당하거나 의도가 모호할 때
   - 템플릿 요약 + 대표 원본 로그 샘플(최대 5건)을 함께 제공

## 도구 호출 순서 (권장)
1. 데이터가 없으면 먼저 ingest_log_text / ingest_log_file 호출
2. 필요에 따라 list_templates → get_template / get_original_logs 순서로 호출
3. 복합 조건이면 search_logs 단독 사용
"""
```

---

### 4.5 `agent/agent.py` — LangChain ReAct 에이전트

```python
# agent/agent.py
import json
from langchain_anthropic import ChatAnthropic
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.tools import StructuredTool
from langchain_core.prompts import PromptTemplate
from agent.prompts import SYSTEM_PROMPT
from core.log_engine import LogEngine


def _make_langchain_tools(engine: LogEngine) -> list:
    """LogEngine 메서드를 LangChain Tool로 변환한다."""

    def search_logs_fn(
        keyword=None, level=None, system=None,
        category=None, template_id=None, start=None, end=None,
    ):
        return engine.search(
            keyword=keyword, level=level, system=system,
            category=category, template_id=template_id,
            datetime_start=start, datetime_end=end,
        )

    return [
        StructuredTool.from_function(engine.list_templates, name="list_templates",
            description="학습된 Drain3 템플릿 클러스터 목록 조회"),
        StructuredTool.from_function(engine.get_template, name="get_template",
            description="template_id로 특정 템플릿 상세 조회"),
        StructuredTool.from_function(engine.get_original_logs, name="get_original_logs",
            description="template_id에 해당하는 원본 로그 목록 조회"),
        StructuredTool.from_function(search_logs_fn, name="search_logs",
            description="키워드·레벨·시스템·시간 범위 등 복합 조건 검색"),
    ]


def run_agent(query: str, engine: LogEngine) -> dict:
    """
    자연어 질의를 받아 LangChain ReAct 에이전트로 처리하고 구조화된 결과를 반환한다.

    Args:
        query: 사용자 자연어 질의
        engine: 공유 LogEngine 인스턴스

    Returns:
        {"mode": str, "templates": list, "logs": list, "total_count": int, "summary": str}
    """
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        anthropic_api_key: str
        agent_model: str = "claude-sonnet-4-6"

        class Config:
            env_file = ".env"

    settings = Settings()

    llm = ChatAnthropic(
        model=settings.agent_model,
        api_key=settings.anthropic_api_key,
        temperature=0,
    )

    tools = _make_langchain_tools(engine)

    # ReAct 프롬프트 템플릿
    prompt = PromptTemplate.from_template(
        SYSTEM_PROMPT + """

사용 가능한 도구: {tools}
도구 이름: {tool_names}

질의: {input}
{agent_scratchpad}
"""
    )

    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=10)

    result = executor.invoke({"input": query})

    # 에이전트 출력을 구조화된 형식으로 변환
    return _parse_agent_output(result.get("output", ""), query)


def _parse_agent_output(output: str, query: str) -> dict:
    """에이전트 자연어 출력을 표준 응답 형식으로 변환한다."""
    # 기본 응답 구조 (에이전트가 채운 내용을 그대로 반환)
    return {
        "mode": _infer_mode(query),
        "templates": [],
        "logs": [],
        "total_count": 0,
        "summary": output,
    }


def _infer_mode(query: str) -> str:
    """질의 텍스트에서 응답 모드를 추론한다."""
    query_lower = query.lower()
    template_keywords = ["패턴", "템플릿", "종류", "형식", "pattern", "template"]
    original_keywords = ["원본", "실제", "상세", "raw", "original", "detail"]

    has_template = any(k in query_lower for k in template_keywords)
    has_original = any(k in query_lower for k in original_keywords)

    if has_template and not has_original:
        return "template"
    if has_original and not has_template:
        return "original"
    return "mixed"
```

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
        └─ ask_agent ──► agent/agent.py
                            └─ LangChain ReAct
                                ├─ list_templates tool
                                ├─ get_template tool
                                ├─ get_original_logs tool
                                └─ search_logs tool
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

### 7.3 에이전트 통합 테스트 (`tests/test_agent.py`)

- 실제 LLM 호출 대신 `ChatAnthropic` mock으로 에이전트 분기 로직 검증
- `_infer_mode` 함수 파라미터화 테스트

---

## 8. 개발 순서 (권장)

```
1. requirements.txt 설치 및 .env 구성
2. core/log_engine.py 구현 → test_log_engine.py 통과
3. mcp/tools.py + mcp/server.py 구현 → MCP Inspector로 툴 확인
4. agent/prompts.py + agent/agent.py 구현 → ask_agent 동작 확인
5. tests/ 전체 통과 확인
6. README.md 작성 후 PR 생성
```

---

## 9. 자주 묻는 질문

**Q. drain3-log-matching 모듈을 어떻게 참조하나요?**
A. 같은 모노레포 내에 있으므로 `sys.path`에 상대 경로를 추가하거나,
`pyproject.toml`의 `[tool.uv.sources]`로 로컬 경로를 패키지로 설정합니다.

**Q. fastmcp 버전 선택 기준은?**
A. fastmcp 2.x 이상을 권장합니다. `@mcp.tool()` 데코레이터와 타입 힌트 기반 스키마 자동 생성을 지원합니다.

**Q. LangChain 에이전트가 어떤 모델을 사용하나요?**
A. 기본값은 `claude-sonnet-4-6`이며 `.env`의 `AGENT_MODEL` 값으로 변경할 수 있습니다.

**Q. MCP 서버를 HTTP 모드로 실행하려면?**
A. fastmcp는 `--transport sse` 옵션으로 SSE 기반 HTTP 서버를 지원합니다.
개발·디버깅 시 `--port 8000` 과 함께 사용하면 브라우저나 curl로 확인할 수 있습니다.
