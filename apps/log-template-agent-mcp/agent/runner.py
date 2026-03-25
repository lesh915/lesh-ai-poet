"""
agent/runner.py
에이전트 진입점

자연어 질의를 LangGraph 에이전트로 처리하고 구조화된 결과를 반환한다.
AGENT_PROVIDER 환경 변수로 Anthropic / OpenAI 중 사용할 LLM을 선택한다.
"""

from langchain_core.language_models import BaseChatModel
from pydantic_settings import BaseSettings
from agent.graph import build_graph
from core.log_engine import LogEngine


class Settings(BaseSettings):
    agent_provider: str = "anthropic"   # "anthropic" | "openai"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    agent_model: str = "claude-sonnet-4-6"

    model_config = {"env_file": ".env", "extra": "ignore"}


_settings: Settings | None = None
_llm: BaseChatModel | None = None


def _get_llm() -> BaseChatModel:
    """LLM 인스턴스를 지연 초기화하여 반환한다."""
    global _settings, _llm
    if _llm is None:
        _settings = Settings()
        provider = _settings.agent_provider.lower()

        if provider == "openai":
            from langchain_openai import ChatOpenAI
            _llm = ChatOpenAI(
                model=_settings.agent_model,
                api_key=_settings.openai_api_key,
                temperature=0,
            )
        else:
            from langchain_anthropic import ChatAnthropic
            _llm = ChatAnthropic(
                model=_settings.agent_model,
                api_key=_settings.anthropic_api_key,
                temperature=0,
            )
    return _llm


def run_agent(query: str, engine: LogEngine) -> dict:
    """
    자연어 질의를 LangGraph 에이전트로 처리하고 구조화된 결과를 반환한다.

    Args:
        query: 사용자 자연어 질의
        engine: 공유 LogEngine 인스턴스

    Returns:
        {"mode": str, "templates": list, "logs": list, "total_count": int, "summary": str}
    """
    try:
        llm = _get_llm()
        graph = build_graph(llm, engine)

        initial_state: dict = {
            "query": query,
            "complexity": "",
            "plan": {},
            "tool_results": [],
            "chunk_cursor": {},
            "chunk_summaries": [],
            "response_mode": "mixed",
            "rethink_count": 0,
            "result": {},
        }

        final_state = graph.invoke(initial_state)
        result = final_state.get("result", {})
        if not result:
            result = {
                "mode": "mixed",
                "templates": [],
                "logs": [],
                "total_count": engine.total_log_count(),
                "summary": "응답 생성 실패",
            }
        return result
    except Exception as e:
        return {
            "mode": "mixed",
            "templates": [],
            "logs": [],
            "total_count": 0,
            "summary": f"에이전트 실행 오류: {str(e)}",
        }
