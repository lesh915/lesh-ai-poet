"""
drain3_extractor.py
Drain3 기반 로그 템플릿 추출 모듈

Drain3(https://github.com/logpai/Drain3)를 사용하여 로그 메시지에서
템플릿을 자동으로 추출합니다.
"""

from dataclasses import dataclass, field
from typing import Optional

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from log_parser import LogEntry


@dataclass
class TemplateResult:
    """Drain3 템플릿 추출 결과"""
    template_id: int
    template: str
    cluster_size: int


def build_template_miner(
    sim_th: float = 0.4,
    depth: int = 4,
    max_children: int = 100,
    max_clusters: Optional[int] = None,
    parametrize_numeric_tokens: bool = True,
) -> TemplateMiner:
    """
    Drain3 TemplateMiner 인스턴스를 설정과 함께 생성합니다.

    Args:
        sim_th: 유사도 임계값 (0~1, 낮을수록 더 많은 로그를 같은 클러스터로 묶음)
        depth: Drain 트리 깊이
        max_children: 각 노드의 최대 자식 수
        max_clusters: 최대 클러스터 수 (None이면 무제한)
        parametrize_numeric_tokens: 숫자 토큰을 <*>로 대체할지 여부

    Returns:
        설정된 TemplateMiner 인스턴스
    """
    config = TemplateMinerConfig()
    config.drain_sim_th = sim_th
    config.drain_depth = depth
    config.drain_max_children = max_children
    config.parametrize_numeric_tokens = parametrize_numeric_tokens
    if max_clusters is not None:
        config.drain_max_clusters = max_clusters

    # 파일 저장 없이 메모리 모드로 실행
    config.snapshot_file_path = None

    return TemplateMiner(config=config)


def extract_template(miner: TemplateMiner, message: str) -> TemplateResult:
    """
    단일 로그 메시지에서 템플릿을 추출합니다.

    Args:
        miner: TemplateMiner 인스턴스
        message: 템플릿을 추출할 로그 메시지 문자열

    Returns:
        TemplateResult (template_id, template, cluster_size)

    Note:
        drain3 add_log_message() 반환 형식:
        {'change_type': str, 'cluster_id': int, 'cluster_size': int,
         'template_mined': str, 'cluster_count': int}
    """
    result = miner.add_log_message(message)
    return TemplateResult(
        template_id=result["cluster_id"],
        template=result["template_mined"],
        cluster_size=result["cluster_size"],
    )


def extract_templates_from_entries(
    entries: list[LogEntry],
    miner: Optional[TemplateMiner] = None,
    **miner_kwargs,
) -> tuple[TemplateMiner, list[TemplateResult]]:
    """
    LogEntry 리스트의 메시지 필드에서 Drain3 템플릿을 일괄 추출합니다.

    Args:
        entries: 파싱된 LogEntry 객체 리스트
        miner: 기존 TemplateMiner 인스턴스 (None이면 새로 생성)
        **miner_kwargs: build_template_miner에 전달할 키워드 인자

    Returns:
        (TemplateMiner 인스턴스, TemplateResult 리스트) 튜플
        - TemplateResult 리스트 순서는 entries와 동일합니다.
    """
    if miner is None:
        miner = build_template_miner(**miner_kwargs)

    results = [extract_template(miner, entry.message) for entry in entries]
    return miner, results


def get_all_clusters(miner: TemplateMiner) -> list[dict]:
    """
    TemplateMiner에 학습된 모든 클러스터(템플릿) 정보를 반환합니다.

    Args:
        miner: 로그를 학습시킨 TemplateMiner 인스턴스

    Returns:
        각 클러스터의 정보를 담은 딕셔너리 리스트
        키: template_id, template, cluster_size
    """
    clusters = []
    for cluster in miner.drain.clusters:
        clusters.append(
            {
                "template_id": cluster.cluster_id,
                "template": cluster.get_template(),
                "cluster_size": cluster.size,
            }
        )
    return clusters
