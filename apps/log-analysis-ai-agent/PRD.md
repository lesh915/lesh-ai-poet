# PRD: 로그 분석 AI 에이전트

## 1. 개요

### 1.1 프로젝트명
`log-analysis-ai-agent`

### 1.2 목적
로그 데이터를 업로드하면 Drain3로 자동 템플릿화하고, 세 종류의 pandas DataFrame으로
관리한다. 사용자가 자연어로 질의하면 LangChain 에이전트가 적절한 테이블을 선택·검색하여
분석 결과를 반환한다.

### 1.3 설계 원칙
- **간단하게**: LangGraph 없이 LangChain ReAct 에이전트 단일 루프
- **재사용**: `drain3-log-matching` 모듈 그대로 활용
- **세 테이블 전략**: 로그 / 템플릿 / 통합 테이블을 각각 독립 검색 툴로 제공

### 1.4 범위 외 (Out-of-Scope)
- MCP 서버 노출
- 영구 저장소(DB) 연동
- 실시간 스트리밍 수집
- 인증/권한 관리

---

## 2. 배경

`drain3-log-matching`은 로그 파싱·템플릿화·검색 기능을 Python 함수로 제공한다.
이를 LangChain 툴로 래핑하여 AI 에이전트가 사용자 질의에 맞게 자율적으로 데이터를
조회·분석하도록 확장한다.

---

## 3. 로그 데이터 형식

```
[timestamp] [system] [level] [thread] [category] [message]
```

예시:
```
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
```

파싱 정규식 (기존 `log_parser.py` 재사용):
```python
PATTERN = r"\[([^\]]+)\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]"
# groups: (timestamp, system, level, thread, category, message)
```

---

## 4. 데이터 파이프라인

```
로그 파일/텍스트 입력
        │
        ▼
  [1] log_parser        → LogEntry 목록
        │
        ▼
  [2] drain3_extractor  → TemplateResult 목록 + print_tree 문자열
        │
        ├──▶ log_df       (로그 테이블)
        ├──▶ template_df  (템플릿 테이블)
        └──▶ merged_df    (통합 테이블)
```

### 4.1 DataFrame 컬럼 정의

#### 로그 테이블 (`log_df`)
| 컬럼 | 설명 |
|------|------|
| `line_number` | 원본 파일 라인 번호 |
| `datetime` | 로그 날짜/시간 |
| `system` | 시스템 이름 |
| `level` | 로그 레벨 (INFO / WARN / ERROR 등) |
| `thread` | 스레드 이름 |
| `category` | 카테고리 |
| `message` | 원본 메시지 |
| `raw` | 원본 로그 라인 전체 |

#### 템플릿 테이블 (`template_df`)
| 컬럼 | 설명 |
|------|------|
| `template_id` | Drain3 클러스터 ID |
| `template` | 추출된 템플릿 (`<*>` 포함) |
| `cluster_size` | 해당 템플릿에 속한 로그 수 |

> **추가 변수** `template_tree: str` — `miner.drain.print_tree()` 전체 출력을 별도 문자열로 저장

#### 통합 테이블 (`merged_df`)
`log_df` + `template_df` 를 `template_id` 기준으로 join한 결과.
모든 컬럼 포함.

---

## 5. 핵심 기능 요구사항

### FR-01: 로그 수집 및 DataFrame 구성
- 파일 경로 또는 텍스트 문자열로 로그 입력
- Drain3 템플릿 마이너 학습 후 세 DataFrame + `template_tree` 생성
- 반환값: `(log_df, template_df, merged_df, template_tree)`

### FR-02: 키워드 검색 함수 (컬럼 지정)
세 테이블 각각에 대해 동일한 시그니처의 검색 함수 제공:

```python
def search_log_table(column: str, keyword: str) -> str:
    """log_df에서 column에 keyword가 포함된 행을 반환"""

def search_template_table(column: str, keyword: str) -> str:
    """template_df에서 column에 keyword가 포함된 행을 반환"""

def search_merged_table(column: str, keyword: str) -> str:
    """merged_df에서 column에 keyword가 포함된 행을 반환"""
```

- `column`이 존재하지 않을 경우 사용 가능한 컬럼 목록을 에러 메시지로 반환
- 결과는 JSON 문자열 또는 마크다운 테이블 형식으로 반환 (최대 50행)

### FR-03: LangChain 툴 등록
FR-02의 세 함수를 `@tool` 데코레이터로 LangChain 툴로 등록:

| 툴 이름 | 설명 |
|---------|------|
| `search_log_table` | 원본 로그 테이블 검색 |
| `search_template_table` | 템플릿 테이블 검색 |
| `search_merged_table` | 통합(로그+템플릿) 테이블 검색 |

### FR-04: ReAct 에이전트 구성
- `langchain` ReAct 에이전트 (단일 루프)
- 시스템 프롬프트에 포함되는 컨텍스트:
  - 로그 테이블 컬럼 목록
  - 템플릿 테이블 컬럼 목록
  - 통합 테이블 컬럼 목록
  - `template_tree` (전체 Drain3 트리 구조)
- 사용자 질의 → 에이전트 → 툴 선택 → 검색 → 분석 응답

#### 시스템 프롬프트 구조
```
당신은 로그 분석 전문가입니다.

[사용 가능한 테이블]
- log_df 컬럼: {log_columns}
- template_df 컬럼: {template_columns}
- merged_df 컬럼: {merged_columns}

[Drain3 템플릿 트리]
{template_tree}

질의에 따라 적합한 테이블을 선택하여 검색하고 결과를 분석하세요.
- 패턴/빈도/종류 질의 → template_table 우선
- 원본 로그/상세 내용 질의 → log_table 우선
- 종합 분석 질의 → merged_table 우선
```

---

## 6. 시나리오 흐름

```
1. 로그 업로드
   load_logs(filepath or text)
   → log_df, template_df, merged_df, template_tree 생성

2. 에이전트 초기화
   agent = create_agent(log_df, template_df, merged_df, template_tree)

3. 사용자 질의
   result = agent.invoke("ERROR 레벨 로그 중 가장 많은 패턴은?")

4. 에이전트 내부 동작
   ① 질의 분석 → "패턴/빈도" → template_table 선택
   ② search_template_table(column="template", keyword="") 또는
      search_merged_table(column="level", keyword="ERROR")
   ③ 결과 취합 → 자연어 응답 생성

5. 응답 반환
   "ERROR 레벨 로그에서 가장 빈번한 패턴은 'Login failed for user <*> from IP <*>' (12건)입니다."
```

---

## 7. 프로젝트 구조

```
apps/log-analysis-ai-agent/
├── PRD.md
├── requirements.txt
├── .env.example
├── main.py                  # 실행 진입점 (예시)
│
├── core/
│   ├── __init__.py
│   ├── loader.py            # 로그 로드 → 세 DataFrame + template_tree 반환
│   └── search.py            # 세 테이블 키워드 검색 함수
│
├── agent/
│   ├── __init__.py
│   ├── tools.py             # LangChain @tool 등록
│   ├── prompts.py           # 시스템 프롬프트 템플릿
│   └── agent.py             # ReAct 에이전트 생성 및 실행
│
└── tests/
    ├── test_loader.py
    ├── test_search.py
    └── test_agent.py
```

---

## 8. 기술 스택

| 구성 요소 | 기술 |
|-----------|------|
| 로그 파싱 | `log_parser.py` (drain3-log-matching 재사용) |
| 템플릿 추출 | `drain3` + `drain3_extractor.py` 재사용 |
| 데이터 관리 | `pandas` + `log_store.py` 재사용 |
| AI 에이전트 | `langchain` ReAct 에이전트 |
| LLM | `langchain-openai` (gpt-4o) |
| 설정 | `.env` + `python-dotenv` |

---

## 9. 의존성 (requirements.txt)

```text
drain3>=0.9.11
pandas>=2.0.0
langchain>=0.3.0
langchain-openai>=0.2.0
langchain-core>=0.3.0
python-dotenv>=1.0.0
```

---

## 10. 비기능 요구사항

| 항목 | 요구사항 |
|------|---------|
| 성능 | 10,000줄 로그 수집·템플릿화 5초 이내 |
| 호환성 | Python 3.11+ |
| 테스트 | 각 모듈 단위 테스트 + 에이전트 시나리오 테스트 1건 이상 |

---

## 11. 마일스톤

| 단계 | 내용 |
|------|------|
| M1 | PRD 완료 + 프로젝트 스캐폴딩 |
| M2 | `core/loader.py` — 로그 로드 및 세 DataFrame 생성 |
| M3 | `core/search.py` — 세 테이블 키워드 검색 함수 |
| M4 | `agent/tools.py` — LangChain @tool 등록 |
| M5 | `agent/agent.py` — ReAct 에이전트 구성 및 테스트 |
