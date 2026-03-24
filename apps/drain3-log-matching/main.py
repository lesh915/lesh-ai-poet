"""
main.py
Drain3 로그 템플릿화 및 검색 - 실행 예시

실행 방법:
    pip install drain3 pandas
    python main.py
"""

import pandas as pd

from log_parser import parse_log_text
from drain3_extractor import build_template_miner, extract_templates_from_entries, get_all_clusters
from log_store import (
    build_log_dataframe,
    build_template_dataframe,
    build_merged_dataframe,
    build_cluster_summary_dataframe,
    search_by_keyword,
    search_by_field,
    search_by_template_id,
    search_by_datetime_range,
    search_combined,
    display_results,
)

# ---------------------------------------------------------------------------
# 샘플 로그 데이터
# 형식: [날짜 시간] [System] [Log Level] [Thread] [Category] [Message Body]
# ---------------------------------------------------------------------------

SAMPLE_LOGS = """\
[2024-01-15 09:00:01] [AuthService] [INFO] [Thread-1] [Security] [User admin logged in successfully]
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:00:12] [AuthService] [ERROR] [Thread-3] [Security] [Login failed for user root from IP 10.0.0.5]
[2024-01-15 09:00:20] [AuthService] [INFO] [Thread-4] [Security] [User john logged in successfully]
[2024-01-15 09:01:00] [DBService] [INFO] [Thread-5] [Database] [Connection established to host db-01 port 5432]
[2024-01-15 09:01:05] [DBService] [INFO] [Thread-6] [Database] [Connection established to host db-02 port 5432]
[2024-01-15 09:01:10] [DBService] [WARN] [Thread-7] [Database] [Query execution time exceeded 500ms on table orders]
[2024-01-15 09:01:15] [DBService] [WARN] [Thread-8] [Database] [Query execution time exceeded 1200ms on table users]
[2024-01-15 09:01:30] [DBService] [ERROR] [Thread-9] [Database] [Failed to connect to host db-03 port 5432]
[2024-01-15 09:02:00] [APIGateway] [INFO] [Thread-10] [Network] [Received GET request from client 172.16.0.1 path /api/v1/users]
[2024-01-15 09:02:05] [APIGateway] [INFO] [Thread-11] [Network] [Received POST request from client 172.16.0.2 path /api/v1/orders]
[2024-01-15 09:02:10] [APIGateway] [INFO] [Thread-12] [Network] [Received GET request from client 172.16.0.3 path /api/v1/products]
[2024-01-15 09:02:15] [APIGateway] [WARN] [Thread-13] [Network] [Rate limit exceeded for client 172.16.0.99 on path /api/v1/users]
[2024-01-15 09:02:20] [APIGateway] [ERROR] [Thread-14] [Network] [Upstream timeout for request to service payment-svc after 30s]
[2024-01-15 09:03:00] [CacheService] [INFO] [Thread-15] [Cache] [Cache hit for key session:abc123 TTL remaining 3540s]
[2024-01-15 09:03:05] [CacheService] [INFO] [Thread-16] [Cache] [Cache miss for key session:xyz789 TTL remaining 0s]
[2024-01-15 09:03:10] [CacheService] [INFO] [Thread-17] [Cache] [Cache hit for key session:def456 TTL remaining 1200s]
[2024-01-15 09:03:15] [CacheService] [WARN] [Thread-18] [Cache] [Cache eviction triggered memory usage 85 percent]
[2024-01-15 09:04:00] [AuthService] [ERROR] [Thread-19] [Security] [Login failed for user alice from IP 203.0.113.5]
[2024-01-15 09:04:10] [DBService] [WARN] [Thread-20] [Database] [Query execution time exceeded 800ms on table products]
[2024-01-15 09:04:20] [APIGateway] [INFO] [Thread-21] [Network] [Received DELETE request from client 172.16.0.4 path /api/v1/orders/789]
[2024-01-15 09:04:30] [AuthService] [INFO] [Thread-22] [Security] [User bob logged in successfully]
[2024-01-15 09:05:00] [DBService] [INFO] [Thread-23] [Database] [Connection established to host db-04 port 3306]
[2024-01-15 09:05:10] [CacheService] [INFO] [Thread-24] [Cache] [Cache miss for key product:item999 TTL remaining 0s]
[2024-01-15 09:05:20] [APIGateway] [ERROR] [Thread-25] [Network] [Upstream timeout for request to service inventory-svc after 60s]
"""


# ---------------------------------------------------------------------------
# 파이프라인 함수
# ---------------------------------------------------------------------------


def build_pipeline(log_text: str, **miner_kwargs) -> tuple:
    """
    로그 텍스트를 입력받아 전체 파이프라인을 실행합니다.
    파싱 -> Drain3 템플릿 추출 -> DataFrame 구성

    Args:
        log_text: 원본 로그 텍스트 (멀티라인)
        **miner_kwargs: Drain3 TemplateMiner 옵션

    Returns:
        (merged_df, miner, log_df, template_df) 튜플
    """
    # 1단계: 로그 파싱
    entries = parse_log_text(log_text)
    print(f"[1] 로그 파싱 완료: {len(entries)}건")

    # 2단계: Drain3 템플릿 추출
    miner = build_template_miner(**miner_kwargs)
    miner, results = extract_templates_from_entries(entries, miner=miner)
    clusters = get_all_clusters(miner)
    print(f"[2] 템플릿 추출 완료: {len(clusters)}개 클러스터 발견")

    # 3단계: DataFrame 구성
    log_df = build_log_dataframe(entries)
    template_df = build_template_dataframe(results)
    merged_df = build_merged_dataframe(log_df, template_df)
    print(f"[3] DataFrame 구성 완료: {len(merged_df)}행 x {len(merged_df.columns)}열\n")

    return merged_df, miner, log_df, template_df


# ---------------------------------------------------------------------------
# 실행 예시
# ---------------------------------------------------------------------------


def example_show_all_clusters(merged_df: pd.DataFrame) -> None:
    """예시 1: 발견된 전체 템플릿(클러스터) 요약 출력"""
    print("=" * 70)
    print("예시 1: 발견된 전체 로그 템플릿 목록")
    print("=" * 70)
    summary = build_cluster_summary_dataframe(merged_df)
    with pd.option_context("display.max_colwidth", 60, "display.width", 200):
        print(summary.to_string(index=False))
    print()


def example_search_keyword(merged_df: pd.DataFrame) -> None:
    """예시 2: 키워드 검색 - 'Login failed' 포함 로그"""
    print("=" * 70)
    print("예시 2: 키워드 검색 → 'Login failed'")
    print("=" * 70)
    result = search_by_keyword(merged_df, keyword="Login failed")
    display_results(result)


def example_search_by_level(merged_df: pd.DataFrame) -> None:
    """예시 3: 로그 레벨 필터링 - ERROR 레벨 로그"""
    print("=" * 70)
    print("예시 3: 로그 레벨 필터 → level='ERROR'")
    print("=" * 70)
    result = search_by_field(merged_df, level="ERROR")
    display_results(result)


def example_search_by_system_and_level(merged_df: pd.DataFrame) -> None:
    """예시 4: 시스템 + 레벨 복합 필터 - DBService의 WARN 로그"""
    print("=" * 70)
    print("예시 4: 복합 필드 필터 → system='DBService', level='WARN'")
    print("=" * 70)
    result = search_by_field(merged_df, system="DBService", level="WARN")
    display_results(result)


def example_search_by_template_id(merged_df: pd.DataFrame) -> None:
    """예시 5: 특정 템플릿 ID로 원본 로그 검색"""
    print("=" * 70)
    # 가장 많이 등장하는 템플릿 ID를 자동 선택
    summary = build_cluster_summary_dataframe(merged_df)
    top_template_id = int(summary.iloc[0]["template_id"])
    top_template = summary.iloc[0]["template"]
    print(f"예시 5: 템플릿 ID로 검색 → template_id={top_template_id}")
    print(f"        템플릿: {top_template}")
    print("=" * 70)
    result = search_by_template_id(merged_df, template_id=top_template_id)
    display_results(result)


def example_search_datetime_range(merged_df: pd.DataFrame) -> None:
    """예시 6: 날짜/시간 범위 검색"""
    print("=" * 70)
    print("예시 6: 시간 범위 검색 → 09:01:00 ~ 09:02:00")
    print("=" * 70)
    result = search_by_datetime_range(
        merged_df,
        start="2024-01-15 09:01:00",
        end="2024-01-15 09:02:00",
    )
    display_results(result)


def example_search_combined(merged_df: pd.DataFrame) -> None:
    """예시 7: 다중 조건 복합 검색"""
    print("=" * 70)
    print("예시 7: 복합 조건 검색 → system='APIGateway', level='INFO', keyword='GET'")
    print("=" * 70)
    result = search_combined(
        merged_df,
        system="APIGateway",
        level="INFO",
        keyword="GET",
    )
    display_results(result)


def example_search_category(merged_df: pd.DataFrame) -> None:
    """예시 8: 카테고리 필터 검색"""
    print("=" * 70)
    print("예시 8: 카테고리 필터 → category='Cache'")
    print("=" * 70)
    result = search_by_field(merged_df, category="Cache")
    display_results(result)


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------


def main() -> None:
    print("\n[Drain3 로그 템플릿화 및 검색 시스템]\n")

    # 파이프라인 실행 (sim_th: 유사도 임계값 - 낮을수록 더 잘 묶임)
    merged_df, miner, log_df, template_df = build_pipeline(
        SAMPLE_LOGS,
        sim_th=0.4,
        depth=4,
    )

    # 실행 예시 순차 실행
    example_show_all_clusters(merged_df)
    example_search_keyword(merged_df)
    example_search_by_level(merged_df)
    example_search_by_system_and_level(merged_df)
    example_search_by_template_id(merged_df)
    example_search_datetime_range(merged_df)
    example_search_combined(merged_df)
    example_search_category(merged_df)

    print("[완료] 모든 예시 실행 완료.")


if __name__ == "__main__":
    main()
