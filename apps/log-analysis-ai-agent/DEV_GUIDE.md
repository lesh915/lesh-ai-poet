# 개발 가이드: log-analysis-ai-agent

## 1. 프로젝트 구조

```
apps/log-analysis-ai-agent/
├── PRD.md                   # 제품 요구사항 문서
├── DEV_GUIDE.md             # 개발 가이드 (이 파일)
├── requirements.txt         # 의존성
├── .env.example             # 환경변수 예시
├── main.py                  # 실행 진입점
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

**재사용 모듈 경로** (drain3-log-matching):
```
apps/drain3-log-matching/
├── log_parser.py            # 로그 파싱 (재사용)
├── drain3_extractor.py      # Drain3 템플릿 추출 (재사용)
└── log_store.py             # DataFrame 구성 (재사용)
```

---

## 2. 의존성 (requirements.txt)

```text
# 로그 파싱 · 템플릿화
drain3>=0.9.11
pandas>=2.0.0

# LangChain · LLM
langchain>=0.3.0
langchain-anthropic>=0.3.0
langchain-core>=0.3.0

# 설정
python-dotenv>=1.0.0
```

> **참고**: drain3 최신 버전은 GitHub에서 직접 설치를 권장합니다.
> ```bash
> pip install git+https://github.com/logpai/Drain3.git
> ```

---

## 3. 환경변수 (.env.example)

```dotenv
# Anthropic API Key
ANTHROPIC_API_KEY=sk-ant-...

# 에이전트에서 사용할 Claude 모델
AGENT_MODEL=claude-sonnet-4-6

# Drain3 기본 파라미터
DRAIN_SIM_TH=0.4
DRAIN_DEPTH=4
```

---

## 4. 모듈 구현 가이드

### 4.1 `core/loader.py` — 로그 로드 및 DataFrame 구성

`drain3-log-matching`의 세 모듈을 조합하여 세 DataFrame과 `template_tree`를 반환한다.

```python
# core/loader.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../drain3-log-matching"))

import pandas as pd
from log_parser import parse_log_text, parse_log_file
from drain3_extractor import build_template_miner, extract_templates_from_entries
from log_store import build_log_dataframe, build_template_dataframe, build_merged_dataframe


def load_from_text(
    log_text: str,
    sim_th: float = 0.4,
    depth: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """
    로그 텍스트를 받아 세 DataFrame과 template_tree를 반환한다.

    Returns:
        (log_df, template_df, merged_df, template_tree)
    """
    entries = parse_log_text(log_text)
    miner = build_template_miner(sim_th=sim_th, depth=depth)
    miner, results = extract_templates_from_entries(entries, miner=miner)

    log_df = build_log_dataframe(entries)
    template_df = build_template_dataframe(results).drop_duplicates("template_id")
    merged_df = build_merged_dataframe(log_df, template_df)

    # Drain3 트리 전체 구조를 문자열로 저장
    import io
    buf = io.StringIO()
    miner.drain.print_tree(buf)
    template_tree = buf.getvalue()

    return log_df, template_df, merged_df, template_tree


def load_from_file(
    filepath: str,
    sim_th: float = 0.4,
    depth: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """파일 경로를 받아 load_from_text와 동일한 결과를 반환한다."""
    entries = parse_log_file(filepath)
    log_text = "\n".join(e.raw for e in entries)
    return load_from_text(log_text, sim_th=sim_th, depth=depth)
```

**반환값 요약**

| 변수 | 타입 | 설명 |
|------|------|------|
| `log_df` | `pd.DataFrame` | 파싱된 원본 로그 (8개 컬럼) |
| `template_df` | `pd.DataFrame` | 고유 템플릿 목록 (3개 컬럼) |
| `merged_df` | `pd.DataFrame` | 로그 + 템플릿 join (11개 컬럼) |
| `template_tree` | `str` | `miner.drain.print_tree()` 전체 문자열 |

---

### 4.2 `core/search.py` — 세 테이블 키워드 검색

컬럼 이름과 키워드를 받아 해당 테이블을 검색하고 문자열로 반환한다.

```python
# core/search.py
import pandas as pd

MAX_ROWS = 50  # 최대 반환 행 수


def _search(df: pd.DataFrame, column: str, keyword: str, table_name: str) -> str:
    """공통 검색 로직. 결과를 마크다운 테이블 문자열로 반환한다."""
    if column not in df.columns:
        available = ", ".join(df.columns.tolist())
        return f"[오류] '{column}' 컬럼이 {table_name}에 존재하지 않습니다. 사용 가능한 컬럼: {available}"

    mask = df[column].astype(str).str.contains(keyword, case=False, na=False)
    result = df[mask].head(MAX_ROWS)

    if result.empty:
        return f"[{table_name}] '{column}' 컬럼에서 '{keyword}' 검색 결과 없음"

    return f"[{table_name}] '{column}' 컬럼에서 '{keyword}' 검색 결과 ({len(result)}건):\n\n" \
           + result.to_markdown(index=False)


# --- 세 테이블 검색 함수 ---

def search_log_table(df: pd.DataFrame, column: str, keyword: str) -> str:
    """log_df에서 column에 keyword가 포함된 행을 반환한다."""
    return _search(df, column, keyword, "log_df")


def search_template_table(df: pd.DataFrame, column: str, keyword: str) -> str:
    """template_df에서 column에 keyword가 포함된 행을 반환한다."""
    return _search(df, column, keyword, "template_df")


def search_merged_table(df: pd.DataFrame, column: str, keyword: str) -> str:
    """merged_df에서 column에 keyword가 포함된 행을 반환한다."""
    return _search(df, column, keyword, "merged_df")
```

**검색 함수 규칙**

| 조건 | 동작 |
|------|------|
| 컬럼이 존재하지 않을 때 | 에러 메시지 + 사용 가능 컬럼 목록 반환 |
| 결과가 없을 때 | "검색 결과 없음" 메시지 반환 |
| 결과가 MAX_ROWS 초과 | 상위 50행만 반환 |
| 키워드 대소문자 | 무시 (case-insensitive) |

---

### 4.3 `agent/tools.py` — LangChain @tool 등록

`core/search.py`의 함수를 클로저로 감싸 LangChain 툴로 등록한다.
DataFrame은 툴 생성 시 바인딩된다.

```python
# agent/tools.py
from langchain_core.tools import tool
import pandas as pd
from core.search import search_log_table, search_template_table, search_merged_table


def create_tools(
    log_df: pd.DataFrame,
    template_df: pd.DataFrame,
    merged_df: pd.DataFrame,
) -> list:
    """세 DataFrame을 바인딩한 LangChain 툴 목록을 반환한다."""

    @tool
    def tool_search_log(column: str, keyword: str) -> str:
        """원본 로그 테이블(log_df)에서 지정한 컬럼에 키워드가 포함된 행을 검색한다.
        컬럼 예시: line_number, datetime, system, level, thread, category, message, raw"""
        return search_log_table(log_df, column, keyword)

    @tool
    def tool_search_template(column: str, keyword: str) -> str:
        """템플릿 테이블(template_df)에서 지정한 컬럼에 키워드가 포함된 행을 검색한다.
        컬럼 예시: template_id, template, cluster_size"""
        return search_template_table(template_df, column, keyword)

    @tool
    def tool_search_merged(column: str, keyword: str) -> str:
        """통합 테이블(merged_df)에서 지정한 컬럼에 키워드가 포함된 행을 검색한다.
        로그와 템플릿 정보가 모두 포함되어 있다.
        컬럼 예시: system, level, category, message, template, cluster_size 등"""
        return search_merged_table(merged_df, column, keyword)

    return [tool_search_log, tool_search_template, tool_search_merged]
```

**툴 선택 가이드 (시스템 프롬프트에 반영)**

| 질의 유형 | 추천 툴 |
|-----------|---------|
| 패턴·종류·빈도 분석 | `tool_search_template` |
| 원본 로그·상세 내용 조회 | `tool_search_log` |
| 로그 + 패턴 종합 분석 | `tool_search_merged` |

---

### 4.4 `agent/prompts.py` — 시스템 프롬프트

```python
# agent/prompts.py

SYSTEM_PROMPT_TEMPLATE = """\
당신은 로그 분석 전문가입니다. 사용자의 질의에 맞게 적절한 툴을 선택하여 로그를 분석하세요.

[사용 가능한 테이블 컬럼]
- log_df     : {log_columns}
- template_df: {template_columns}
- merged_df  : {merged_columns}

[툴 선택 기준]
- 패턴·종류·빈도 분석     → tool_search_template (template_df 사용)
- 원본 로그·상세 내용 조회 → tool_search_log (log_df 사용)
- 로그 + 패턴 종합 분석   → tool_search_merged (merged_df 사용)

[Drain3 템플릿 트리]
{template_tree}

분석 결과는 한국어로 간결하게 답변하세요.
"""


def build_system_prompt(
    log_columns: list[str],
    template_columns: list[str],
    merged_columns: list[str],
    template_tree: str,
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        log_columns=", ".join(log_columns),
        template_columns=", ".join(template_columns),
        merged_columns=", ".join(merged_columns),
        template_tree=template_tree,
    )
```

---

### 4.5 `agent/agent.py` — ReAct 에이전트

```python
# agent/agent.py
import os
import pandas as pd
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from agent.tools import create_tools
from agent.prompts import build_system_prompt

load_dotenv()


def create_agent(
    log_df: pd.DataFrame,
    template_df: pd.DataFrame,
    merged_df: pd.DataFrame,
    template_tree: str,
) -> AgentExecutor:
    """세 DataFrame과 template_tree를 받아 ReAct 에이전트를 생성한다."""

    tools = create_tools(log_df, template_df, merged_df)

    system_prompt = build_system_prompt(
        log_columns=log_df.columns.tolist(),
        template_columns=template_df.columns.tolist(),
        merged_columns=merged_df.columns.tolist(),
        template_tree=template_tree,
    )

    llm = ChatAnthropic(
        model=os.getenv("AGENT_MODEL", "claude-sonnet-4-6"),
        api_key=os.getenv("ANTHROPIC_API_KEY"),
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=5)


def run_query(agent_executor: AgentExecutor, query: str) -> str:
    """에이전트에 질의하고 응답 문자열을 반환한다."""
    result = agent_executor.invoke({"input": query})
    return result["output"]
```

---

## 5. main.py — 실행 진입점

```python
# main.py
from core.loader import load_from_text
from agent.agent import create_agent, run_query

SAMPLE_LOGS = """\
[2024-01-15 09:00:01] [AuthService] [INFO] [Thread-1] [Security] [User admin logged in successfully]
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:00:12] [AuthService] [ERROR] [Thread-3] [Security] [Login failed for user root from IP 10.0.0.5]
[2024-01-15 09:01:00] [DBService] [INFO] [Thread-5] [Database] [Connection established to host db-01 port 5432]
[2024-01-15 09:01:10] [DBService] [WARN] [Thread-7] [Database] [Query execution time exceeded 500ms on table orders]
[2024-01-15 09:02:00] [APIGateway] [INFO] [Thread-10] [Network] [Received GET request from client 172.16.0.1 path /api/v1/users]
[2024-01-15 09:02:15] [APIGateway] [WARN] [Thread-13] [Network] [Rate limit exceeded for client 172.16.0.99 on path /api/v1/users]
"""


def main():
    # 1. 로그 로드 → 세 DataFrame + template_tree 생성
    log_df, template_df, merged_df, template_tree = load_from_text(SAMPLE_LOGS)
    print(f"로그: {len(log_df)}건 / 템플릿: {len(template_df)}개 / 통합: {len(merged_df)}행")

    # 2. 에이전트 생성
    agent = create_agent(log_df, template_df, merged_df, template_tree)

    # 3. 질의 예시
    queries = [
        "ERROR 레벨 로그 중 가장 많이 반복되는 패턴은 무엇인가요?",
        "DBService에서 발생한 WARN 로그를 보여주세요.",
        "전체 로그를 시스템별로 요약해주세요.",
    ]

    for query in queries:
        print(f"\n질의: {query}")
        answer = run_query(agent, query)
        print(f"응답: {answer}")


if __name__ == "__main__":
    main()
```

---

## 6. 테스트 가이드

### 6.1 `tests/test_loader.py`

```python
# tests/test_loader.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.loader import load_from_text

SAMPLE = """\
[2024-01-15 09:00:01] [AuthService] [INFO] [Thread-1] [Security] [User admin logged in successfully]
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:00:12] [AuthService] [ERROR] [Thread-3] [Security] [Login failed for user root from IP 10.0.0.5]
"""


def test_load_returns_four_values():
    result = load_from_text(SAMPLE)
    assert len(result) == 4


def test_log_df_columns():
    log_df, _, _, _ = load_from_text(SAMPLE)
    assert set(["datetime", "system", "level", "message"]).issubset(set(log_df.columns))


def test_log_df_row_count():
    log_df, _, _, _ = load_from_text(SAMPLE)
    assert len(log_df) == 3


def test_template_df_has_unique_templates():
    _, template_df, _, _ = load_from_text(SAMPLE)
    assert template_df["template_id"].is_unique


def test_merged_df_has_all_columns():
    log_df, template_df, merged_df, _ = load_from_text(SAMPLE)
    for col in log_df.columns:
        assert col in merged_df.columns
    for col in template_df.columns:
        assert col in merged_df.columns


def test_template_tree_is_string():
    _, _, _, template_tree = load_from_text(SAMPLE)
    assert isinstance(template_tree, str)
    assert len(template_tree) > 0
```

### 6.2 `tests/test_search.py`

```python
# tests/test_search.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.loader import load_from_text
from core.search import search_log_table, search_template_table, search_merged_table

SAMPLE = """\
[2024-01-15 09:00:01] [AuthService] [INFO] [Thread-1] [Security] [User admin logged in successfully]
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:00:12] [DBService] [WARN] [Thread-3] [Database] [Query execution time exceeded 500ms on table orders]
"""

log_df, template_df, merged_df, _ = load_from_text(SAMPLE)


def test_search_log_by_level():
    result = search_log_table(log_df, "level", "ERROR")
    assert "ERROR" in result
    assert "Login failed" in result


def test_search_log_invalid_column():
    result = search_log_table(log_df, "nonexistent", "test")
    assert "오류" in result
    assert "사용 가능한 컬럼" in result


def test_search_template_by_keyword():
    result = search_template_table(template_df, "template", "Login")
    assert "template_df" in result


def test_search_merged_by_system():
    result = search_merged_table(merged_df, "system", "DBService")
    assert "DBService" in result


def test_search_no_result():
    result = search_log_table(log_df, "level", "CRITICAL")
    assert "검색 결과 없음" in result
```

### 6.3 `tests/test_agent.py`

```python
# tests/test_agent.py — 통합 테스트 (실제 LLM 호출)
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.loader import load_from_text
from agent.agent import create_agent, run_query

SAMPLE = """\
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:00:12] [AuthService] [ERROR] [Thread-3] [Security] [Login failed for user root from IP 10.0.0.5]
[2024-01-15 09:01:10] [DBService] [WARN] [Thread-7] [Database] [Query execution time exceeded 500ms on table orders]
"""


@pytest.mark.integration
def test_agent_error_query():
    """ERROR 패턴 질의에 대한 에이전트 응답 확인"""
    log_df, template_df, merged_df, template_tree = load_from_text(SAMPLE)
    agent = create_agent(log_df, template_df, merged_df, template_tree)
    answer = run_query(agent, "ERROR 로그 패턴을 알려주세요")
    assert isinstance(answer, str)
    assert len(answer) > 0
```

테스트 실행:
```bash
# 단위 테스트만 실행 (LLM 호출 없음)
pytest tests/test_loader.py tests/test_search.py -v

# 통합 테스트 포함 (ANTHROPIC_API_KEY 필요)
pytest tests/ -v -m integration
```

---

## 7. 설치 및 실행

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에서 ANTHROPIC_API_KEY 입력

# 3. 실행
python main.py
```

---

## 8. 구현 순서 체크리스트

- [ ] M1: 프로젝트 스캐폴딩 (`__init__.py`, `.env.example`, `requirements.txt`)
- [ ] M2: `core/loader.py` 구현 + `tests/test_loader.py` 통과
- [ ] M3: `core/search.py` 구현 + `tests/test_search.py` 통과
- [ ] M4: `agent/tools.py` + `agent/prompts.py` 구현
- [ ] M5: `agent/agent.py` 구현 + `tests/test_agent.py` 통과 + `main.py` 동작 확인

---

## 9. 주요 의존 관계

```
main.py
  └── core/loader.py
  │     ├── (drain3-log-matching) log_parser.py
  │     ├── (drain3-log-matching) drain3_extractor.py
  │     └── (drain3-log-matching) log_store.py
  │
  └── agent/agent.py
        ├── agent/tools.py
        │     └── core/search.py
        └── agent/prompts.py
```

---

## 10. 참고 — `template_tree` 출력 예시

```
Root
├── [2] (size 3)
│   └── Login failed for user <*> from IP <*>
├── [3] (size 2)
│   └── Query execution time exceeded <*> on table <*>
└── [4] (size 1)
    └── Rate limit exceeded for client <*> on path <*>
```

`template_tree`는 시스템 프롬프트에 그대로 포함되어
에이전트가 전체 로그 패턴 구조를 파악하는 데 활용된다.
