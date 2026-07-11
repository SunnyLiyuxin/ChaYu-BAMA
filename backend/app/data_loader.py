"""YAML seed 加载器：启动时把 data/seeds/*.yaml 读进内存 registry 并缓存。

阶段一不接 SQLite：seed 文件即数据源（可提交 Git、可复现）。
启动时加载一次、全局共享；修改 seed 后重启即可。
接 SQLite 后，本加载器可由 seed.py 调用，把同样的数据灌进 DB。

所有 services 通过 data_loader 提供的查询函数取数据，不再直接 import mock_data。
"""

from functools import lru_cache
from pathlib import Path

import yaml

# backend/app/data_loader.py → backend/data/seeds
SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"


def _load(name: str) -> dict:
    """读取单个 seed 文件为 dict。"""
    path = SEEDS_DIR / f"{name}.yaml"
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=None)
def all_seeds() -> dict:
    """一次性加载全部 seed，返回带命名键的 registry。后续查询函数都基于它。"""
    return {
        "teas": _load("teas").get("teas", []),
        "evidence_sources": _load("evidence").get("evidence_sources", []),
        "tea_knowledge": _load("knowledge").get("tea_knowledge", []),
        "flavor_profiles": _load("flavor_profiles").get("flavor_profiles", []),
        "demo_routes": _load("demo_routes").get("demo_routes", []),
        "rules": _load("generation_rules").get("rules", []),
        "cross_cultural_terms": _load("cross_cultural_terms").get("cross_cultural_terms", []),
        "expression_strategies": _load("expression_strategies").get("expression_strategies", []),
        "expressions": _load("mock_outputs").get("expressions", []),
        "assets": _load("mock_outputs").get("assets", []),
        "trace_nodes": _load("trace_links").get("trace_nodes", []),
        "tea_terms": _load("trace_links").get("tea_terms", {}),
    }


# 优先级排序权重：规则筛选后按 high > medium > low 排序
PRIORITY_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


# ---------------------------------------------------------------------------
# 查询函数（services 用）
# ---------------------------------------------------------------------------


def list_teas() -> list[dict]:
    return all_seeds()["teas"]


def get_tea(tea_id: str) -> dict | None:
    for t in all_seeds()["teas"]:
        if t["id"] == tea_id:
            return t
    return None


def list_demo_routes() -> list[dict]:
    return all_seeds()["demo_routes"]


def get_knowledge(tea_id: str) -> dict | None:
    for k in all_seeds()["tea_knowledge"]:
        if k["tea_id"] == tea_id:
            return _build_knowledge_card(tea_id, k)
    return None


def _build_knowledge_card(tea_id: str, knowledge: dict) -> dict:
    """组装知识卡片：tea 基础信息 + 产地 + 工艺 + 故事 + 证据明细。"""
    tea = get_tea(tea_id) or {}
    evidence_map = {e["id"]: e for e in all_seeds()["evidence_sources"]}
    evidence = [
        {
            "id": eid,
            "source_type": evidence_map[eid]["source_type"],
            "title": evidence_map[eid]["source"],
            "source": evidence_map[eid]["source"],
            "confidence": evidence_map[eid]["confidence"],
            "note": evidence_map[eid].get("notes", ""),
        }
        for eid in knowledge.get("evidence_ids", [])
        if eid in evidence_map
    ]
    return {
        "tea": {
            "id": tea.get("id", tea_id),
            "name": tea.get("name", ""),
            "category": tea.get("category", ""),
            "origin": tea.get("origin", ""),
            "brand": tea.get("brand", ""),
        },
        "origin": knowledge.get("origin", {}),
        "process": knowledge.get("process", {}),
        "story": knowledge.get("story", {}),
        "evidence": evidence,
    }


def get_flavor_profile(tea_id: str) -> dict | None:
    for p in all_seeds()["flavor_profiles"]:
        if p["tea_id"] == tea_id:
            return p
    return None


def get_expression(expression_id: str) -> dict | None:
    for e in all_seeds()["expressions"]:
        if e["id"] == expression_id:
            return e
    return None


def get_expression_by_tea(tea_id: str, expression_type: str) -> dict | None:
    """按茶品 + 类型（domestic / cross_cultural）取预置表达。"""
    for e in all_seeds()["expressions"]:
        if e["tea_id"] == tea_id and e.get("expression_type") == expression_type:
            return e
    return None


def get_asset_by_language(tea_id: str, language: str) -> dict | None:
    """按茶品 + 语言取预置物料（zh→国内物料，en→跨文化物料）。"""
    for a in all_seeds()["assets"]:
        if a["tea_id"] == tea_id and a.get("language") == language:
            return a
    return None


def get_asset(asset_id: str) -> dict | None:
    for a in all_seeds()["assets"]:
        if a["id"] == asset_id:
            return a
    return None


def get_trace_node(output_id: str) -> dict | None:
    for n in all_seeds()["trace_nodes"]:
        if n["id"] == output_id:
            return n
    return None


def get_tea_terms(tea_id: str) -> list[str]:
    return all_seeds()["tea_terms"].get(tea_id, [])


def all_rules() -> list[dict]:
    return all_seeds()["rules"]
