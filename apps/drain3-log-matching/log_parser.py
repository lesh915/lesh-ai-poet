"""
log_parser.py
로그 파싱 모듈 - 정형화된 로그 데이터를 파싱합니다.

로그 형식: [날짜 시간] [System] [Log Level(Type)] [Thread] [Category] [Message Body]
예시: [2024-01-15 09:23:11] [AuthService] [ERROR] [Thread-12] [Security] [Login failed for user admin]
"""

import re
from dataclasses import dataclass
from typing import Optional


# 로그 라인 파싱 정규식
LOG_PATTERN = re.compile(
    r"\[(?P<datetime>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]"
    r"\s+\[(?P<system>[^\]]+)\]"
    r"\s+\[(?P<level>[^\]]+)\]"
    r"\s+\[(?P<thread>[^\]]+)\]"
    r"\s+\[(?P<category>[^\]]+)\]"
    r"\s+\[(?P<message>.+)\]"
)


@dataclass
class LogEntry:
    """파싱된 로그 엔트리 데이터 클래스"""
    raw: str
    datetime: str
    system: str
    level: str
    thread: str
    category: str
    message: str
    line_number: int


def parse_log_line(line: str, line_number: int = 0) -> Optional[LogEntry]:
    """
    단일 로그 라인을 파싱하여 LogEntry 객체를 반환합니다.

    Args:
        line: 파싱할 로그 라인 문자열
        line_number: 로그 파일 내 라인 번호 (기본값 0)

    Returns:
        LogEntry 객체 또는 파싱 실패 시 None
    """
    line = line.strip()
    if not line:
        return None

    match = LOG_PATTERN.match(line)
    if not match:
        return None

    return LogEntry(
        raw=line,
        datetime=match.group("datetime"),
        system=match.group("system"),
        level=match.group("level"),
        thread=match.group("thread"),
        category=match.group("category"),
        message=match.group("message"),
        line_number=line_number,
    )


def parse_log_lines(lines: list[str]) -> list[LogEntry]:
    """
    여러 로그 라인을 파싱하여 LogEntry 리스트를 반환합니다.

    Args:
        lines: 파싱할 로그 라인 리스트

    Returns:
        파싱에 성공한 LogEntry 객체 리스트
    """
    entries = []
    for i, line in enumerate(lines, start=1):
        entry = parse_log_line(line, line_number=i)
        if entry is not None:
            entries.append(entry)
    return entries


def parse_log_file(filepath: str) -> list[LogEntry]:
    """
    로그 파일을 읽어 파싱된 LogEntry 리스트를 반환합니다.

    Args:
        filepath: 로그 파일 경로

    Returns:
        파싱된 LogEntry 객체 리스트
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return parse_log_lines(lines)


def parse_log_text(text: str) -> list[LogEntry]:
    """
    멀티라인 로그 텍스트 문자열을 파싱합니다.

    Args:
        text: 줄바꿈으로 구분된 로그 텍스트

    Returns:
        파싱된 LogEntry 객체 리스트
    """
    return parse_log_lines(text.splitlines())
