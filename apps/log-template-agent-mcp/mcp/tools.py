"""
mcp/tools.py
MCP 툴 정의

fastmcp의 @mcp.tool() 데코레이터로 각 툴을 정의한다.
LogEngine 싱글턴을 공유하여 모든 툴이 동일한 상태를 참조한다.
"""

from fastmcp import FastMCP
from core.log_engine import LogEngine

mcp = FastMCP("log-template-agent")
engine = LogEngine()


@mcp.tool()
def ingest_log_text(log_text: str, reset: bool = False) -> dict:
    """
    로그 텍스트를 파싱하고 Drain3 템플릿을 추출합니다.

    Args:
        log_text: 여러 줄의 로그 텍스트 문자열
        reset: True이면 기존 데이터를 초기화하고 새로 시작

    Returns:
        {"ingested": int, "template_count": int}
    """
    return engine.ingest_text(log_text, reset=reset)


@mcp.tool()
def ingest_log_file(file_path: str, reset: bool = False) -> dict:
    """
    로그 파일을 파싱하고 Drain3 템플릿을 추출합니다.

    Args:
        file_path: 로그 파일 절대/상대 경로
        reset: True이면 기존 데이터를 초기화하고 새로 시작

    Returns:
        {"ingested": int, "template_count": int}
    """
    return engine.ingest_file(file_path, reset=reset)


@mcp.tool()
def list_templates() -> list[dict]:
    """
    현재 학습된 모든 Drain3 템플릿 클러스터 목록을 반환합니다.

    Returns:
        [{"template_id": int, "template": str, "cluster_size": int}, ...]
    """
    return engine.list_templates()


@mcp.tool()
def get_template(template_id: int) -> dict:
    """
    특정 템플릿 ID의 상세 정보를 반환합니다.

    Args:
        template_id: 조회할 템플릿(클러스터) ID

    Returns:
        {"template_id": int, "template": str, "cluster_size": int} 또는 빈 dict
    """
    return engine.get_template(template_id) or {}


@mcp.tool()
def get_original_logs(template_id: int) -> list[dict]:
    """
    특정 템플릿 ID에 매칭된 원본 로그 목록을 반환합니다.

    Args:
        template_id: 조회할 템플릿(클러스터) ID

    Returns:
        원본 로그 레코드 리스트 (line_number, datetime, system, level, ...)
    """
    return engine.get_original_logs(template_id)


@mcp.tool()
def search_logs(
    keyword: str | None = None,
    level: str | None = None,
    system: str | None = None,
    category: str | None = None,
    template_id: int | None = None,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    """
    여러 조건을 AND로 조합하여 로그를 검색하고 템플릿 정보를 함께 반환합니다.

    Args:
        keyword: 메시지/템플릿 키워드 (대소문자 무시)
        level: 로그 레벨 (INFO / WARN / ERROR 등)
        system: 시스템 이름
        category: 카테고리
        template_id: 특정 템플릿 ID
        start: 시작 날짜시간 (예: "2024-01-15 09:00:00")
        end: 종료 날짜시간

    Returns:
        매칭 로그 레코드 리스트
    """
    return engine.search(
        keyword=keyword,
        level=level,
        system=system,
        category=category,
        template_id=template_id,
        datetime_start=start,
        datetime_end=end,
    )


@mcp.tool()
def list_templates_page(page: int = 0, page_size: int = 50) -> dict:
    """
    템플릿 목록을 페이지 단위로 반환합니다 (대용량 데이터 토큰 초과 방지).

    Args:
        page: 0-based 페이지 번호
        page_size: 페이지당 템플릿 수 (기본 50)

    Returns:
        {"items": [...], "page": int, "page_size": int, "total": int, "has_next": bool}
    """
    return engine.list_templates_page(page=page, page_size=page_size)


@mcp.tool()
def get_original_logs_page(
    template_id: int, page: int = 0, page_size: int = 200
) -> dict:
    """
    특정 템플릿의 원본 로그를 페이지 단위로 반환합니다.

    Args:
        template_id: 조회할 템플릿 ID
        page: 0-based 페이지 번호
        page_size: 페이지당 로그 수 (기본 200)

    Returns:
        {"items": [...], "page": int, "page_size": int, "total": int, "has_next": bool}
    """
    return engine.get_original_logs_page(
        template_id=template_id, page=page, page_size=page_size
    )


@mcp.tool()
def ask_agent(query: str) -> dict:
    """
    자연어 질의를 LangChain 에이전트에 전달하고 응답을 반환합니다.

    에이전트는 질의 의도에 따라 템플릿 정보 또는 원본 로그 또는
    혼합 결과를 자동으로 선택하여 자연어 요약과 함께 반환합니다.

    Args:
        query: 자연어 질의 문자열

    Returns:
        {
            "mode": "template | original | mixed",
            "templates": [...],
            "logs": [...],
            "total_count": int,
            "summary": str
        }
    """
    from agent.runner import run_agent
    return run_agent(query, engine)
