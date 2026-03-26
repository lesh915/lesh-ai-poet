"""
mcp/server.py
fastmcp 서버 진입점

stdio 모드를 기본으로 실행하며, Claude Desktop 등 MCP 클라이언트와 연동한다.

실행 방법:
    # stdio 모드 (Claude Desktop 등 MCP 클라이언트용)
    python -m mcp.server

    # HTTP/SSE 모드 (개발·테스트용)
    python -m mcp.server --transport sse --port 8000
"""

from mcp.tools import mcp

if __name__ == "__main__":
    mcp.run()
