"""
tests/test_agent.py — 에이전트 통합 테스트 (실제 OpenAI API 호출)

실행:
    pytest tests/test_agent.py -v -m integration
    (OPENAI_API_KEY 환경변수 필요)
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.loader import load_from_text
from agent.agent import create_agent, run_query

SAMPLE = """\
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:00:12] [AuthService] [ERROR] [Thread-3] [Security] [Login failed for user root from IP 10.0.0.5]
[2024-01-15 09:01:00] [DBService] [INFO] [Thread-5] [Database] [Connection established to host db-01 port 5432]
[2024-01-15 09:01:10] [DBService] [WARN] [Thread-7] [Database] [Query execution time exceeded 500ms on table orders]
[2024-01-15 09:02:00] [APIGateway] [ERROR] [Thread-14] [Network] [Upstream timeout for request to service payment-svc after 30s]
"""


@pytest.mark.integration
def test_agent_error_pattern_query():
    """ERROR 패턴 질의에 대한 에이전트 응답이 문자열로 반환되는지 확인"""
    log_df, template_df, merged_df, template_tree = load_from_text(SAMPLE)
    agent = create_agent(log_df, template_df, merged_df, template_tree)
    answer = run_query(agent, "ERROR 로그 패턴을 알려주세요")
    assert isinstance(answer, str)
    assert len(answer) > 10


@pytest.mark.integration
def test_agent_system_summary_query():
    """시스템별 요약 질의에 대한 에이전트 응답 확인"""
    log_df, template_df, merged_df, template_tree = load_from_text(SAMPLE)
    agent = create_agent(log_df, template_df, merged_df, template_tree)
    answer = run_query(agent, "각 시스템별 로그 건수를 알려주세요")
    assert isinstance(answer, str)
    assert len(answer) > 10
