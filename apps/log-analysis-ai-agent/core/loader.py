"""
core/loader.py
로그 파일/텍스트를 받아 세 pandas DataFrame과 template_tree 문자열을 반환한다.

drain3-log-matching 모듈을 재사용한다.
"""

import io
import os
import sys

import pandas as pd

# drain3-log-matching 모듈 경로 추가
_DRAIN3_PATH = os.path.join(os.path.dirname(__file__), "../../drain3-log-matching")
if _DRAIN3_PATH not in sys.path:
    sys.path.insert(0, os.path.abspath(_DRAIN3_PATH))

from log_parser import parse_log_text, parse_log_file  # noqa: E402
from drain3_extractor import build_template_miner, extract_templates_from_entries  # noqa: E402
from log_store import build_log_dataframe, build_template_dataframe, build_merged_dataframe  # noqa: E402


def load_from_text(
    log_text: str,
    sim_th: float = 0.4,
    depth: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """
    로그 텍스트를 받아 세 DataFrame과 template_tree를 반환한다.

    Args:
        log_text: 멀티라인 로그 문자열
        sim_th: Drain3 유사도 임계값 (낮을수록 더 많이 묶음)
        depth: Drain3 트리 깊이

    Returns:
        (log_df, template_df, merged_df, template_tree)
        - log_df      : 원본 로그 테이블 (line_number, datetime, system, level, thread, category, message, raw)
        - template_df : 고유 템플릿 테이블 (template_id, template, cluster_size)
        - merged_df   : 로그 + 템플릿 통합 테이블 (11개 컬럼)
        - template_tree: miner.drain.print_tree() 전체 문자열
    """
    entries = parse_log_text(log_text)
    if not entries:
        empty_log = pd.DataFrame(columns=["line_number", "datetime", "system", "level", "thread", "category", "message", "raw"])
        empty_tmpl = pd.DataFrame(columns=["template_id", "template", "cluster_size"])
        return empty_log, empty_tmpl, pd.DataFrame(), ""

    miner = build_template_miner(sim_th=sim_th, depth=depth)
    miner, results = extract_templates_from_entries(entries, miner=miner)

    log_df = build_log_dataframe(entries)

    # merged_df 는 로그 순서와 동일한 template 결과로 join (인덱스 기반)
    template_df_full = build_template_dataframe(results)
    merged_df = build_merged_dataframe(log_df, template_df_full)

    # template_df 는 고유 템플릿만 (cluster_size 최신값 기준)
    template_df = (
        template_df_full
        .sort_values("cluster_size", ascending=False)
        .drop_duplicates("template_id")
        .reset_index(drop=True)
    )

    # Drain3 트리 전체 구조 문자열 저장
    buf = io.StringIO()
    miner.drain.print_tree(buf)
    template_tree = buf.getvalue()

    return log_df, template_df, merged_df, template_tree


def load_from_file(
    filepath: str,
    sim_th: float = 0.4,
    depth: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """
    로그 파일 경로를 받아 load_from_text와 동일한 결과를 반환한다.

    Args:
        filepath: 로그 파일 경로
        sim_th: Drain3 유사도 임계값
        depth: Drain3 트리 깊이

    Returns:
        (log_df, template_df, merged_df, template_tree)
    """
    entries = parse_log_file(filepath)
    log_text = "\n".join(e.raw for e in entries)
    return load_from_text(log_text, sim_th=sim_th, depth=depth)
