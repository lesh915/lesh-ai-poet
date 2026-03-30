"""
main.py
로그 분석 AI 에이전트 실행 예시.

실행:
    pip install -r requirements.txt
    cp .env.example .env  # OPENAI_API_KEY 설정
    python main.py
"""

from core.loader import load_from_text
from agent.agent import create_agent, run_query

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


def main() -> None:
    print("\n[로그 분석 AI 에이전트]\n")

    # 1. 로그 로드 → 세 DataFrame + template_tree 생성
    print("로그 데이터 로딩 중...")
    log_df, template_df, merged_df, template_tree = load_from_text(SAMPLE_LOGS)
    print(f"  로그: {len(log_df)}건 | 템플릿: {len(template_df)}개 | 통합: {len(merged_df)}행\n")

    # 2. 에이전트 생성
    print("에이전트 초기화 중...")
    agent = create_agent(log_df, template_df, merged_df, template_tree)
    print("  준비 완료\n")

    # 3. 질의 예시
    queries = [
        "ERROR 레벨 로그 중 가장 많이 반복되는 패턴은 무엇인가요?",
        "DBService에서 발생한 WARN 로그를 모두 보여주세요.",
        "전체 로그를 시스템별·레벨별로 요약해주세요.",
    ]

    for i, query in enumerate(queries, 1):
        print(f"{'=' * 60}")
        print(f"질의 {i}: {query}")
        print(f"{'=' * 60}")
        answer = run_query(agent, query)
        print(f"\n[응답]\n{answer}\n")


if __name__ == "__main__":
    main()
