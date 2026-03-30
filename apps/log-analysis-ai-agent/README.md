# 로그 분석 AI 에이전트

로그 데이터를 업로드하면 [Drain3](https://github.com/logpai/Drain3)로 자동 템플릿화하고,
세 종류의 pandas DataFrame으로 관리합니다.
사용자가 자연어로 질의하면 OpenAI 기반 LangChain 에이전트가
적절한 테이블을 선택·검색하여 분석 결과를 반환합니다.

---

## 로그 데이터 형식

```
[timestamp] [system] [level] [thread] [category] [message]
```

예시:
```
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:01:10] [DBService] [WARN] [Thread-7] [Database] [Query execution time exceeded 500ms on table orders]
[2024-01-15 09:02:00] [APIGateway] [INFO] [Thread-10] [Network] [Received GET request from client 172.16.0.1 path /api/v1/users]
```

---

## 프로젝트 구조

```
apps/log-analysis-ai-agent/
├── main.py                  # 실행 진입점
├── requirements.txt
├── .env.example
│
├── core/
│   ├── loader.py            # 로그 → 세 DataFrame + template_tree
│   └── search.py            # 세 테이블 컬럼 지정 키워드 검색
│
├── agent/
│   ├── tools.py             # LangChain @tool 등록
│   ├── prompts.py           # 시스템 프롬프트 템플릿
│   └── agent.py             # OpenAI tool-calling 에이전트
│
└── tests/
    ├── test_loader.py
    ├── test_search.py
    └── test_agent.py        # 통합 테스트 (API 필요)
```

**재사용 모듈** (`apps/drain3-log-matching/`):

| 모듈 | 역할 |
|------|------|
| `log_parser.py` | 정규식으로 로그 라인 파싱 → `LogEntry` |
| `drain3_extractor.py` | Drain3로 메시지 → 템플릿 추출 |
| `log_store.py` | DataFrame 구성 함수 |

---

## 설치

```bash
# 1. drain3 (GitHub에서 설치 권장)
pip install "git+https://github.com/logpai/Drain3.git"

# 2. 나머지 의존성
pip install -r requirements.txt
```

---

## 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일에서 OpenAI API Key를 입력합니다:

```dotenv
OPENAI_API_KEY=sk-...
AGENT_MODEL=gpt-4o
DRAIN_SIM_TH=0.4
DRAIN_DEPTH=4
```

---

## 실행

```bash
python main.py
```

출력 예시:
```
[로그 분석 AI 에이전트]

로그 데이터 로딩 중...
  로그: 25건 | 템플릿: 9개 | 통합: 25행

에이전트 초기화 중...
  준비 완료

============================================================
질의 1: ERROR 레벨 로그 중 가장 많이 반복되는 패턴은 무엇인가요?
============================================================
...
[응답]
ERROR 레벨 로그에서 가장 빈번한 패턴은 'Login failed for user <*> from IP <*>' (3건)입니다.
```

---

## 데이터 파이프라인

```
로그 입력 (텍스트 or 파일)
        │
        ▼
  log_parser          → LogEntry 목록
        │
        ▼
  drain3_extractor    → TemplateResult 목록 + template_tree
        │
        ├──▶ log_df       원본 로그 테이블
        ├──▶ template_df  고유 템플릿 테이블
        └──▶ merged_df    통합 테이블 (로그 + 템플릿)
```

### 테이블 컬럼

#### `log_df` — 원본 로그 테이블

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

#### `template_df` — 템플릿 테이블

| 컬럼 | 설명 |
|------|------|
| `template_id` | Drain3 클러스터 ID |
| `template` | 추출된 템플릿 (`<*>` 포함) |
| `cluster_size` | 해당 템플릿에 속한 로그 수 |

#### `merged_df` — 통합 테이블

`log_df` + `template_df` 전체 컬럼 (11개)

---

## Python API 사용법

### 로그 로드

```python
from core.loader import load_from_text, load_from_file

# 텍스트로 로드
log_df, template_df, merged_df, template_tree = load_from_text(log_text)

# 파일로 로드
log_df, template_df, merged_df, template_tree = load_from_file("app.log")
```

### 테이블 검색

```python
from core.search import search_log_table, search_template_table, search_merged_table

# 원본 로그에서 ERROR 레벨 검색
result = search_log_table(log_df, column="level", keyword="ERROR")

# 템플릿에서 패턴 검색
result = search_template_table(template_df, column="template", keyword="Login failed")

# 통합 테이블에서 시스템별 검색
result = search_merged_table(merged_df, column="system", keyword="DBService")

print(result)  # 마크다운 테이블 문자열
```

### AI 에이전트 질의

```python
from core.loader import load_from_text
from agent.agent import create_agent, run_query

log_df, template_df, merged_df, template_tree = load_from_text(log_text)
agent = create_agent(log_df, template_df, merged_df, template_tree)

answer = run_query(agent, "ERROR 로그 중 가장 빈번한 패턴은?")
print(answer)
```

---

## 에이전트 툴 선택 기준

| 질의 유형 | 선택 툴 | 검색 테이블 |
|-----------|---------|------------|
| 패턴·종류·빈도 분석 | `tool_search_template` | `template_df` |
| 원본 로그·상세 내용 | `tool_search_log` | `log_df` |
| 로그 + 패턴 종합 분석 | `tool_search_merged` | `merged_df` |

---

## 테스트

```bash
# 단위 테스트 (OpenAI API 불필요)
python -m pytest tests/test_loader.py tests/test_search.py -v

# 통합 테스트 (OPENAI_API_KEY 필요)
python -m pytest tests/test_agent.py -v -m integration
```

---

## 의존성

| 패키지 | 용도 |
|--------|------|
| [drain3](https://github.com/logpai/Drain3) | 로그 템플릿 자동 추출 |
| [pandas](https://pandas.pydata.org/) | 데이터 저장 및 검색 |
| [tabulate](https://github.com/astanin/python-tabulate) | 마크다운 테이블 출력 |
| [langchain](https://github.com/langchain-ai/langchain) | 에이전트 프레임워크 |
| [langchain-openai](https://github.com/langchain-ai/langchain) | OpenAI LLM 연동 |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 환경변수 관리 |
