# PRD: Log Template AI Agent (MCP 기반)

## 1. 개요

### 1.1 프로젝트명
`log-template-agent-mcp`

### 1.2 목적
`drain3-log-matching` 프로젝트에서 확보한 로그 파싱·템플릿화 능력을 확장하여,
LangChain 기반 AI 에이전트와 fastmcp(MCP 서버)로 래핑한다.
클라이언트는 자연어 질의 또는 MCP 툴 호출을 통해 **템플릿 정보**와 **원본 로그** 를
필요에 따라 선택적으로 조회할 수 있다.

### 1.3 범위 (In-Scope)
- 로그 텍스트/파일 수집 및 Drain3 템플릿 자동 추출
- 템플릿 ↔ 원본 로그 양방향 매칭 데이터 관리 (pandas DataFrame)
- MCP 툴로 템플릿/원본 데이터 노출 (fastmcp)
- LangChain 에이전트: 질의 의도를 파악하여 템플릿 전용·원본 전용·혼합 응답 자동 결정

### 1.4 범위 외 (Out-of-Scope)
- 영구 저장소(DB, 파일 스냅샷) 연동 (v1 기준, 메모리 내 운영)
- 실시간 스트리밍 로그 수집
- 인증/권한 관리

---

## 2. 배경 및 문제 정의

기존 `drain3-log-matching` 프로젝트는 다음을 제공한다:
- `log_parser.py` : 정형 로그 → `LogEntry` 변환
- `drain3_extractor.py` : Drain3로 메시지 → 템플릿 추출
- `log_store.py` : DataFrame 빌드 + 키워드·필드·시간 범위 검색

**문제**: 위 기능들이 파이썬 함수로만 존재하며, 외부 시스템(LLM 에이전트, Claude, Copilot 등)이
표준 인터페이스(MCP)로 접근할 수 없다.

**해결**: fastmcp로 MCP 서버를 구성하고, LangChain 에이전트를 내장하여
"템플릿이 필요한지" / "원본 로그가 필요한지"를 에이전트가 스스로 판단·응답한다.

---

## 3. 사용자 및 클라이언트

| 대상 | 설명 |
|------|------|
| MCP 클라이언트 | Claude Desktop, Cursor, 기타 MCP 지원 IDE/도구 |
| LangChain 에이전트 | 자연어 → 툴 선택 → 결과 요약 |
| 개발자 | Python API 직접 호출 또는 CLI 테스트 |

---

## 4. 핵심 기능 요구사항

### FR-01: 로그 수집 및 템플릿화
- 로그 텍스트 문자열 또는 파일 경로를 입력으로 받는다.
- `log_parser`로 파싱 후 `drain3_extractor`로 템플릿을 추출한다.
- 결과를 인메모리 DataFrame에 누적 저장한다.
- 동일 세션 내 여러 번 수집 가능(증분 학습).

### FR-02: MCP 툴 노출 (fastmcp)
아래 툴을 MCP 서버로 노출한다.

| 툴 이름 | 입력 | 출력 |
|---------|------|------|
| `ingest_log_text` | `log_text: str`, `reset: bool = False` | 수집 건수, 템플릿 클러스터 수 |
| `ingest_log_file` | `file_path: str`, `reset: bool = False` | 수집 건수, 템플릿 클러스터 수 |
| `list_templates` | (없음) | 템플릿 ID·패턴·빈도 목록 |
| `get_template` | `template_id: int` | 단일 템플릿 상세 정보 |
| `get_original_logs` | `template_id: int` | 해당 템플릿의 원본 로그 리스트 |
| `search_logs` | `keyword?`, `level?`, `system?`, `category?`, `template_id?`, `start?`, `end?` | 매칭 로그 + 템플릿 정보 |
| `ask_agent` | `query: str` | LangChain 에이전트가 생성한 자연어 응답 |

### FR-03: LangChain AI 에이전트
- `ask_agent` 툴을 통해 자연어 질의를 받는다.
- 에이전트는 위 MCP 툴(FR-02)을 도구(Tool)로 등록하여 ReAct 방식으로 호출한다.
- 다음 판단 로직을 따른다:

```
질의 분석
  ├─ "템플릿", "패턴", "형식" 언급 → 템플릿 정보 위주로 응답
  ├─ "원본", "실제", "raw", "상세" 언급 → 원본 로그 위주로 응답
  └─ 모호한 경우 → 템플릿 요약 + 원본 샘플 함께 응답
```

### FR-04: 응답 데이터 구조
에이전트 및 MCP 툴 응답은 아래 형식을 기본으로 한다.

```json
{
  "mode": "template | original | mixed",
  "templates": [
    {
      "template_id": 3,
      "template": "Login failed for user <*> from IP <*>",
      "cluster_size": 12,
      "sample_logs": []
    }
  ],
  "logs": [
    {
      "line_number": 5,
      "datetime": "2024-01-15 09:00:05",
      "system": "AuthService",
      "level": "ERROR",
      "category": "Security",
      "message": "Login failed for user guest from IP 192.168.1.10",
      "template_id": 3
    }
  ],
  "total_count": 12,
  "summary": "자연어 요약 (에이전트 응답 시)"
}
```

---

## 5. 비기능 요구사항

| 항목 | 요구사항 |
|------|---------|
| 성능 | 10,000줄 로그 수집·템플릿화 5초 이내 |
| 확장성 | 추후 Redis/SQLite 영구 저장 레이어 추가 가능한 구조 |
| 호환성 | Python 3.11+, MCP 1.x 프로토콜 |
| 테스트 | 각 MCP 툴 단위 테스트 + 에이전트 통합 시나리오 테스트 |

---

## 6. 기술 스택

| 구성 요소 | 기술 |
|-----------|------|
| 로그 파싱 | `log_parser` (drain3-log-matching 재사용) |
| 템플릿 추출 | `drain3` + `drain3_extractor` 재사용 |
| 데이터 관리 | `pandas` + `log_store` 재사용 |
| MCP 서버 | `fastmcp` |
| AI 에이전트 | `langchain` + `langchain-anthropic` (Claude) |
| 설정 관리 | `pydantic-settings` (`.env` 기반) |
| 패키징 | `uv` 또는 `pip` + `requirements.txt` |

---

## 7. 제약 사항

- 수집된 데이터는 서버 프로세스 메모리에만 저장된다(재시작 시 초기화).
- LLM 호출은 Anthropic API Key 필요.
- `drain3-log-matching` 패키지를 직접 참조(같은 모노레포 내 상대 경로 import 또는 복사).

---

## 8. 마일스톤

| 단계 | 내용 | 목표 |
|------|------|------|
| M1 | 프로젝트 스캐폴딩 + 의존성 정의 | PRD·가이드 완료 후 즉시 |
| M2 | 로그 수집·템플릿화 코어 모듈 (`log_engine.py`) | M1 + 1일 |
| M3 | MCP 툴 구현 (`mcp_tools.py`) + fastmcp 서버 (`server.py`) | M2 + 1일 |
| M4 | LangChain 에이전트 구현 (`agent.py`) | M3 + 1일 |
| M5 | 단위/통합 테스트 + README | M4 + 1일 |
