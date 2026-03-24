"""
core/log_engine.py
로그 수집·파싱·템플릿화 통합 엔진

drain3-log-matching 프로젝트의 세 모듈(log_parser, drain3_extractor, log_store)을
조합하여 단일 상태 객체(LogEngine)로 관리한다.
"""

import sys
import os

# drain3-log-matching 모듈을 sys.path로 참조
_BASE = os.path.join(os.path.dirname(__file__), "../../drain3-log-matching")
sys.path.insert(0, os.path.abspath(_BASE))

from log_parser import parse_log_text, parse_log_file
from drain3_extractor import build_template_miner, extract_templates_from_entries, get_all_clusters
from log_store import (
    build_log_dataframe,
    build_template_dataframe,
    build_merged_dataframe,
    build_cluster_summary_dataframe,
    search_combined,
    search_by_template_id,
)


class LogEngine:
    """로그 파싱·템플릿화·검색의 단일 상태 관리 객체"""

    def __init__(self, sim_th: float = 0.4, depth: int = 4):
        self._sim_th = sim_th
        self._depth = depth
        self.miner = build_template_miner(sim_th=sim_th, depth=depth)
        self.merged_df = None   # pd.DataFrame | None
        self._entries = []
        self._results = []

    def _reset(self):
        """내부 상태를 초기화한다."""
        self.miner = build_template_miner(sim_th=self._sim_th, depth=self._depth)
        self.merged_df = None
        self._entries = []
        self._results = []

    def _rebuild(self):
        """누적된 entries와 results로 merged_df를 재구성한다."""
        if not self._entries:
            self.merged_df = None
            return

        log_df = build_log_dataframe(self._entries)
        template_df = build_template_dataframe(self._results)
        self.merged_df = build_merged_dataframe(log_df, template_df)

    def ingest_text(self, log_text: str, reset: bool = False) -> dict:
        """
        로그 텍스트를 수집·템플릿화하고 상태를 갱신한다.

        Args:
            log_text: 여러 줄의 로그 텍스트 문자열
            reset: True이면 기존 데이터를 초기화하고 새로 시작

        Returns:
            {"ingested": int, "template_count": int}
        """
        try:
            if reset:
                self._reset()

            entries = parse_log_text(log_text)
            if not entries:
                return {"ingested": 0, "template_count": len(get_all_clusters(self.miner))}

            _, results = extract_templates_from_entries(entries, miner=self.miner)

            self._entries.extend(entries)
            self._results.extend(results)
            self._rebuild()

            template_count = len(get_all_clusters(self.miner))
            return {"ingested": len(entries), "template_count": template_count}
        except Exception as e:
            return {"ingested": 0, "template_count": 0, "error": str(e)}

    def ingest_file(self, file_path: str, reset: bool = False) -> dict:
        """
        로그 파일을 수집·템플릿화하고 상태를 갱신한다.

        Args:
            file_path: 로그 파일 절대/상대 경로
            reset: True이면 기존 데이터를 초기화하고 새로 시작

        Returns:
            {"ingested": int, "template_count": int}
        """
        try:
            if not os.path.exists(file_path):
                return {"ingested": 0, "template_count": 0, "error": f"파일을 찾을 수 없음: {file_path}"}

            if reset:
                self._reset()

            entries = parse_log_file(file_path)
            if not entries:
                return {"ingested": 0, "template_count": len(get_all_clusters(self.miner))}

            _, results = extract_templates_from_entries(entries, miner=self.miner)

            self._entries.extend(entries)
            self._results.extend(results)
            self._rebuild()

            template_count = len(get_all_clusters(self.miner))
            return {"ingested": len(entries), "template_count": template_count}
        except FileNotFoundError:
            return {"ingested": 0, "template_count": 0, "error": f"파일을 찾을 수 없음: {file_path}"}
        except Exception as e:
            return {"ingested": 0, "template_count": 0, "error": str(e)}

    def list_templates(self) -> list[dict]:
        """
        학습된 템플릿 클러스터 목록을 반환한다.

        Returns:
            [{"template_id": int, "template": str, "cluster_size": int}, ...]
        """
        return get_all_clusters(self.miner)

    def get_template(self, template_id: int) -> dict | None:
        """
        특정 템플릿 ID의 상세 정보를 반환한다.

        Args:
            template_id: 조회할 템플릿(클러스터) ID

        Returns:
            {"template_id": int, "template": str, "cluster_size": int} 또는 None
        """
        clusters = get_all_clusters(self.miner)
        for cluster in clusters:
            if cluster["template_id"] == template_id:
                return cluster
        return None

    def get_original_logs(self, template_id: int) -> list[dict]:
        """
        특정 템플릿 ID에 매칭된 원본 로그 목록을 반환한다.

        Args:
            template_id: 조회할 템플릿(클러스터) ID

        Returns:
            원본 로그 레코드 리스트
        """
        if self.merged_df is None:
            return []

        df = search_by_template_id(self.merged_df, template_id)
        return df.to_dict(orient="records")

    def search(self, **kwargs) -> list[dict]:
        """
        복합 조건 검색 결과를 반환한다.

        지원 키워드 인자: keyword, level, system, category, template_id,
                         datetime_start, datetime_end

        Returns:
            매칭 로그 레코드 리스트
        """
        if self.merged_df is None:
            return []

        df = search_combined(self.merged_df, **kwargs)
        return df.to_dict(orient="records")

    def list_templates_page(self, page: int = 0, page_size: int = 50) -> dict:
        """
        템플릿 목록을 페이지 단위로 반환한다 (대용량 데이터 토큰 초과 방지).

        Args:
            page: 0-based 페이지 번호
            page_size: 페이지당 템플릿 수

        Returns:
            {
                "items": [...],        # 이번 페이지 템플릿 목록
                "page": int,
                "page_size": int,
                "total": int,          # 전체 템플릿 수
                "has_next": bool
            }
        """
        all_templates = self.list_templates()
        total = len(all_templates)
        start = page * page_size
        end = start + page_size
        items = all_templates[start:end]
        has_next = end < total

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": has_next,
        }

    def get_original_logs_page(
        self, template_id: int, page: int = 0, page_size: int = 200
    ) -> dict:
        """
        특정 템플릿의 원본 로그를 페이지 단위로 반환한다.

        Args:
            template_id: 조회할 템플릿 ID
            page: 0-based 페이지 번호
            page_size: 페이지당 로그 수

        Returns:
            {"items": [...], "page": int, "page_size": int, "total": int, "has_next": bool}
        """
        all_logs = self.get_original_logs(template_id)
        total = len(all_logs)
        start = page * page_size
        end = start + page_size
        items = all_logs[start:end]
        has_next = end < total

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": has_next,
        }

    def total_log_count(self) -> int:
        """
        수집된 전체 로그 수를 반환한다.

        Returns:
            전체 로그 레코드 수
        """
        if self.merged_df is None:
            return 0
        return len(self.merged_df)
