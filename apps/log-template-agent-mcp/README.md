# log-template-agent-mcp

Drain3 기반 로그 템플릿 추출 엔진과 LangGraph AI 에이전트를 MCP(Model Context Protocol) 서버로 제공하는 프로젝트입니다.

로그 텍스트/파일을 수집하면 Drain3 알고리즘으로 반복 패턴을 자동 템플릿화하고,
자연어 질의를 통해 로그를 분석할 수 있습니다.

---

## 목차

- [구조](#구조)
- [설치](#설치)
- [환경 설정](#환경-설정)
- [MCP 서버 실행](#mcp-서버-실행)
- [MCP 툴 목록 및 사용 예시](#mcp-툴-목록-및-사용-예시)
- [LangGraph 에이전트](#langgraph-에이전트)
- [Python에서 직접 사용](#python에서-직접-사용)
- [테스트 실행](#테스트-실행)

---

## 구조

```
log-template-agent-mcp/
├── core/
│   └── log_engine.py        # 로그 파싱·템플릿화·검색 통합 엔진
├── mcp/
│   ├── tools.py             # MCP 툴 9개 (@mcp.tool() 정의)
│   └── server.py            # MCP 서버 진입점
├── agent/
│   ├── state.py             # LangGraph AgentState 정의
│   ├── prompts.py           # 노드별 프롬프트
│   ├── nodes.py             # 5개 노드 구현 (route/think/execute/chunk_analyze/synthesize)
│   ├── graph.py             # LangGraph StateGraph 빌드
│   └── runner.py            # run_agent() 진입점
├── tests/
│   ├── test_log_engine.py   # LogEngine 단위 테스트 (24개)
│   ├── test_mcp_tools.py    # MCP 툴 테스트 (36개)
│   └── test_agent.py        # 에이전트 테스트 (20개)
├── .env.example
└── requirements.txt
```

---

## 설치

```bash
# 의존성 설치 (프로젝트 루트 기준)
cd apps/log-template-agent-mcp
pip install -r requirements.txt
```

**의존 패키지:**

| 패키지 | 용도 |
|--------|------|
| `drain3` | 로그 템플릿 추출 알고리즘 |
| `pandas` | 로그 데이터프레임 관리 |
| `fastmcp` | MCP 서버 프레임워크 |
| `langchain` / `langchain-anthropic` | LLM 연동 |
| `langgraph` | 에이전트 상태 그래프 |
| `pydantic-settings` | 환경 변수 관리 |

---

## 환경 설정

`.env.example`을 복사하여 `.env`를 생성하고 값을 입력합니다.

```bash
cp .env.example .env
```

```dotenv
# Anthropic API Key (LangGraph 에이전트용, ask_agent 툴 사용 시 필수)
ANTHROPIC_API_KEY=sk-ant-...

# 에이전트 모델 (기본: claude-sonnet-4-6)
AGENT_MODEL=claude-sonnet-4-6

# Drain3 파라미터
DRAIN_SIM_TH=0.4    # 유사도 임계값 (낮을수록 더 많은 템플릿 생성)
DRAIN_DEPTH=4       # 파싱 트리 깊이

# MCP HTTP 서버 설정 (SSE 모드 사용 시)
MCP_HOST=0.0.0.0
MCP_PORT=8000

# 대용량 분석 청크 크기
TEMPLATE_CHUNK_SIZE=50   # 청크당 템플릿 수
LOG_CHUNK_SIZE=200       # 청크당 원본 로그 수
```

---

## MCP 서버 실행

### stdio 모드 (Claude Desktop 등 MCP 클라이언트 연동)

```bash
python -m mcp.server
```

**Claude Desktop `claude_desktop_config.json` 예시:**

```json
{
  "mcpServers": {
    "log-template-agent": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "/path/to/log-template-agent-mcp"
    }
  }
}
```

### SSE 모드 (HTTP 개발·테스트용)

```bash
python -m mcp.server --transport sse --port 8000
```

---

## MCP 툴 목록 및 사용 예시

### 1. `ingest_log_text` — 로그 텍스트 수집

로그 문자열을 파싱하고 Drain3 템플릿을 추출합니다.

```json
{
  "tool": "ingest_log_text",
  "arguments": {
    "log_text": "2024-01-15 09:00:01 ERROR auth Login failed for user alice\n2024-01-15 09:00:02 ERROR auth Login failed for user bob",
    "reset": false
  }
}
```

**응답:**
```json
{ "ingested": 2, "template_count": 1 }
```

---

### 2. `ingest_log_file` — 로그 파일 수집

```json
{
  "tool": "ingest_log_file",
  "arguments": {
    "file_path": "/var/log/app.log",
    "reset": true
  }
}
```

> `reset: true`이면 기존 데이터를 초기화하고 새로 시작합니다.

---

### 3. `list_templates` — 템플릿 전체 목록

학습된 모든 Drain3 템플릿 클러스터를 반환합니다.

```json
{ "tool": "list_templates", "arguments": {} }
```

**응답:**
```json
[
  { "template_id": 1, "template": "Login failed for user <*>", "cluster_size": 42 },
  { "template_id": 2, "template": "Connection timeout to <*>:<*>", "cluster_size": 15 }
]
```

---

### 4. `list_templates_page` — 템플릿 페이지 조회

대용량 환경에서 토큰 초과를 방지하기 위한 페이지네이션 조회입니다.

```json
{
  "tool": "list_templates_page",
  "arguments": { "page": 0, "page_size": 50 }
}
```

**응답:**
```json
{
  "items": [...],
  "page": 0,
  "page_size": 50,
  "total": 230,
  "has_next": true
}
```

> `has_next: true`이면 `page + 1`로 다음 페이지를 요청합니다.

---

### 5. `get_template` — 특정 템플릿 조회

```json
{
  "tool": "get_template",
  "arguments": { "template_id": 1 }
}
```

**응답:**
```json
{ "template_id": 1, "template": "Login failed for user <*>", "cluster_size": 42 }
```

---

### 6. `get_original_logs` — 템플릿 원본 로그 조회

특정 템플릿에 매칭된 모든 원본 로그를 반환합니다.

```json
{
  "tool": "get_original_logs",
  "arguments": { "template_id": 1 }
}
```

---

### 7. `get_original_logs_page` — 원본 로그 페이지 조회

```json
{
  "tool": "get_original_logs_page",
  "arguments": { "template_id": 1, "page": 0, "page_size": 200 }
}
```

---

### 8. `search_logs` — 복합 조건 검색

여러 조건을 AND로 조합하여 로그를 검색합니다. 모든 인자는 선택적입니다.

```json
{
  "tool": "search_logs",
  "arguments": {
    "keyword": "timeout",
    "level": "ERROR",
    "system": "database",
    "start": "2024-01-15 09:00:00",
    "end": "2024-01-15 18:00:00"
  }
}
```

| 파라미터 | 설명 |
|----------|------|
| `keyword` | 메시지/템플릿 키워드 (대소문자 무시) |
| `level` | 로그 레벨 (INFO, WARN, ERROR 등) |
| `system` | 시스템 이름 |
| `category` | 카테고리 |
| `template_id` | 특정 템플릿 ID |
| `start` / `end` | 날짜시간 범위 (`"YYYY-MM-DD HH:MM:SS"`) |

---

### 9. `ask_agent` — 자연어 질의

자연어로 질의하면 LangGraph 에이전트가 적절한 툴을 선택하여 분석하고 요약을 반환합니다.

```json
{
  "tool": "ask_agent",
  "arguments": {
    "query": "어제 발생한 ERROR 로그 중 가장 빈번한 패턴은 무엇인가요?"
  }
}
```

**응답:**
```json
{
  "mode": "template",
  "templates": [
    { "template_id": 3, "template": "DB connection refused at <*>", "cluster_size": 87 }
  ],
  "logs": [],
  "total_count": 1024,
  "summary": "어제 가장 빈번한 ERROR 패턴은 DB 연결 실패(87건)입니다. ..."
}
```

---

## LangGraph 에이전트

`ask_agent`가 내부적으로 실행하는 LangGraph 그래프입니다.

### 실행 흐름

```
질의 입력
    │
    ▼
[route] ─ 복잡도 분류 ──────────────────────────┐
    │                                             │
    ├─ simple ──────────────────► [execute]       │
    │                                 │           │
    ├─ complex ──► [think] ──────► [execute]      │
    │               ▲ (최대 3회)      │           │
    │               └─ rethink ───────┘           │
    │                                             │
    └─ bulk_analysis ──► [chunk_analyze] ◄────────┘
                              │ (페이지 루프)
                              ▼
                         [synthesize] ──► 최종 응답
```

| 복잡도 | 조건 | 경로 |
|--------|------|------|
| `simple` | 단순 키워드 검색 | route → execute → synthesize |
| `complex` | 다단계 분석 필요 | route → think → execute (루프) → synthesize |
| `bulk_analysis` | 전체 템플릿 대규모 분석 | route → chunk_analyze (페이지 루프) → synthesize |

### AgentState 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `query` | str | 사용자 원본 질의 |
| `complexity` | str | `simple` / `complex` / `bulk_analysis` |
| `plan` | dict | think 노드가 수립한 실행 계획 |
| `tool_results` | list | execute 노드가 누적한 툴 결과 |
| `chunk_cursor` | dict | bulk_analysis 페이지 커서 |
| `chunk_summaries` | list | 청크별 LLM 요약 누적 |
| `rethink_count` | int | think 루프 횟수 (최대 3회) |
| `result` | dict | synthesize 노드의 최종 응답 |

---

## Python에서 직접 사용

### LogEngine 직접 사용

```python
from core.log_engine import LogEngine

engine = LogEngine(sim_th=0.4, depth=4)

# 텍스트 수집
result = engine.ingest_text("""
2024-01-15 09:00:01 ERROR auth Login failed for user alice
2024-01-15 09:00:02 ERROR auth Login failed for user bob
2024-01-15 09:00:03 INFO  auth Login succeeded for user carol
""")
print(result)  # {"ingested": 3, "template_count": 2}

# 파일 수집
engine.ingest_file("/var/log/app.log")

# 템플릿 목록 조회
templates = engine.list_templates()
# [{"template_id": 1, "template": "Login failed for user <*>", "cluster_size": 2}, ...]

# 특정 템플릿 원본 로그 조회
logs = engine.get_original_logs(template_id=1)

# 복합 검색
results = engine.search(keyword="timeout", level="ERROR")

# 페이지네이션 (대용량)
page = engine.list_templates_page(page=0, page_size=50)
# {"items": [...], "page": 0, "page_size": 50, "total": 230, "has_next": True}
```

### 에이전트 직접 호출

```python
from core.log_engine import LogEngine
from agent.runner import run_agent

engine = LogEngine()
engine.ingest_file("/var/log/app.log")

result = run_agent("ERROR 로그 중 가장 많은 패턴을 알려줘", engine)
print(result["summary"])
```

---

## 테스트 실행

```bash
cd apps/log-template-agent-mcp

# 전체 테스트
pytest tests/ -v

# 모듈별 실행
pytest tests/test_log_engine.py -v   # LogEngine 24개
pytest tests/test_mcp_tools.py -v    # MCP 툴 36개
pytest tests/test_agent.py -v        # 에이전트 20개
```

> 에이전트 테스트(`test_agent.py`)는 LLM 호출을 mock으로 대체하므로 API 키 없이 실행됩니다.
