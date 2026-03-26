# Drain3 로그 템플릿화 및 검색 시스템

[Drain3](https://github.com/logpai/Drain3)를 사용하여 정형 로그 데이터를 템플릿으로 자동 분류하고, pandas DataFrame에 저장하여 다양한 조건으로 검색할 수 있는 Python 프로그램입니다.

---

## 로그 데이터 형식

```
[날짜 시간] [System] [Log Level] [Thread] [Category] [Message Body]
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
apps/drain3-log-matching/
├── log_parser.py        # 로그 파싱 모듈
├── drain3_extractor.py  # Drain3 템플릿 추출 모듈
├── log_store.py         # pandas 저장 및 검색 모듈
├── main.py              # 실행 예시
└── requirements.txt     # 의존성 목록
```

---

## 설치

```bash
pip install -r requirements.txt
```

> **참고**: drain3 최신 버전은 GitHub에서 직접 설치를 권장합니다.
> ```bash
> pip install git+https://github.com/logpai/Drain3.git
> ```

---

## 실행

```bash
python main.py
```

---

## 모듈 설명

### `log_parser.py` - 로그 파싱

정규식을 사용하여 정형 로그 라인을 구조화된 `LogEntry` 객체로 변환합니다.

| 함수 | 설명 |
|------|------|
| `parse_log_line(line, line_number)` | 로그 1줄 파싱 → `LogEntry` |
| `parse_log_lines(lines)` | 여러 라인 일괄 파싱 |
| `parse_log_text(text)` | 멀티라인 문자열 파싱 |
| `parse_log_file(filepath)` | 파일에서 파싱 |

```python
from log_parser import parse_log_text

entries = parse_log_text("""
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
""")
print(entries[0].level)    # ERROR
print(entries[0].message)  # Login failed for user guest from IP 192.168.1.10
```

---

### `drain3_extractor.py` - 템플릿 추출

Drain3 `TemplateMiner`를 래핑하여 로그 메시지에서 패턴을 자동 학습하고 템플릿(`<*>`)을 추출합니다.

| 함수 | 설명 |
|------|------|
| `build_template_miner(**kwargs)` | Drain3 인스턴스 생성 (유사도·깊이 설정 가능) |
| `extract_template(miner, message)` | 메시지 1건 → `TemplateResult` |
| `extract_templates_from_entries(entries, miner)` | 로그 목록 일괄 추출 |
| `get_all_clusters(miner)` | 학습된 전체 클러스터 조회 |

```python
from drain3_extractor import build_template_miner, extract_templates_from_entries

miner = build_template_miner(sim_th=0.4, depth=4)
miner, results = extract_templates_from_entries(entries, miner=miner)

print(results[0].template_id)  # 2
print(results[0].template)     # Login failed for user <*> from IP <*>
```

**`build_template_miner` 주요 파라미터**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `sim_th` | `0.4` | 유사도 임계값 (낮을수록 더 많이 묶음) |
| `depth` | `4` | Drain 트리 깊이 |
| `max_children` | `100` | 노드당 최대 자식 수 |
| `parametrize_numeric_tokens` | `True` | 숫자 토큰을 `<*>`로 대체 |

---

### `log_store.py` - pandas 저장 및 검색

파싱 결과와 템플릿 정보를 DataFrame으로 통합 관리하고 다양한 검색 함수를 제공합니다.

#### DataFrame 구성

| 함수 | 설명 |
|------|------|
| `build_log_dataframe(entries)` | 로그 DataFrame 생성 |
| `build_template_dataframe(results)` | 템플릿 DataFrame 생성 |
| `build_merged_dataframe(log_df, template_df)` | 통합 DataFrame 생성 |
| `build_cluster_summary_dataframe(merged_df)` | 템플릿별 로그 건수 요약 |

#### 검색 함수

| 함수 | 설명 |
|------|------|
| `search_by_keyword(df, keyword)` | 키워드 포함 로그 검색 (대소문자 무시) |
| `search_by_field(df, **filters)` | 필드 값 일치 필터 |
| `search_by_template_id(df, template_id)` | 템플릿 ID로 원본 로그 조회 |
| `search_by_datetime_range(df, start, end)` | 날짜/시간 범위 검색 |
| `search_combined(df, ...)` | 여러 조건 AND 복합 검색 |

#### 통합 DataFrame 컬럼

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
| `template_id` | Drain3 클러스터 ID |
| `template` | 추출된 템플릿 (`<*>` 포함) |
| `cluster_size` | 클러스터에 속한 로그 수 |

---

## 사용 예시

```python
from log_parser import parse_log_text
from drain3_extractor import build_template_miner, extract_templates_from_entries
from log_store import (
    build_log_dataframe, build_template_dataframe, build_merged_dataframe,
    search_by_keyword, search_by_field, search_by_template_id,
    search_by_datetime_range, search_combined, display_results,
)

# 1. 로그 파싱
entries = parse_log_text(log_text)

# 2. 템플릿 추출
miner = build_template_miner(sim_th=0.4)
miner, results = extract_templates_from_entries(entries, miner=miner)

# 3. DataFrame 구성
log_df = build_log_dataframe(entries)
template_df = build_template_dataframe(results)
merged_df = build_merged_dataframe(log_df, template_df)

# 4. 검색 - 키워드
result = search_by_keyword(merged_df, "Login failed")

# 5. 검색 - 필드 필터
result = search_by_field(merged_df, level="ERROR", system="AuthService")

# 6. 검색 - 시간 범위
result = search_by_datetime_range(merged_df, "2024-01-15 09:00:00", "2024-01-15 09:01:00")

# 7. 검색 - 복합 조건
result = search_combined(merged_df, system="APIGateway", level="INFO", keyword="GET")

# 결과 출력
display_results(result)
```

---

## 실행 예시 출력

`main.py` 실행 시 아래 8가지 예시가 순차 실행됩니다.

| 예시 | 검색 조건 |
|------|-----------|
| 1 | 전체 템플릿 클러스터 요약 |
| 2 | 키워드 검색 → `"Login failed"` |
| 3 | 로그 레벨 필터 → `level="ERROR"` |
| 4 | 복합 필드 필터 → `system="DBService", level="WARN"` |
| 5 | 템플릿 ID로 원본 로그 조회 |
| 6 | 시간 범위 검색 → `09:01:00 ~ 09:02:00` |
| 7 | 복합 조건 → `system="APIGateway", level="INFO", keyword="GET"` |
| 8 | 카테고리 필터 → `category="Cache"` |

---

## 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| [drain3](https://github.com/logpai/Drain3) | ≥ 0.9.11 | 로그 템플릿 자동 추출 |
| [pandas](https://pandas.pydata.org/) | ≥ 2.0.0 | 데이터 저장 및 검색 |
