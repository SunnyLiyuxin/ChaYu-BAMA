"""表达生成层（第 3 层）：国内表达 + 跨文化表达，两条同构链路。

国内链与跨文化链地位对等。跨文化表达由国内表达按规则横向翻译派生，
该关系通过 source_expression_id 记录，不进入纵向追溯链。

阶段一：从 seed 预置输出（mock_outputs.yaml）读取表达，不调用 LLM。
规则筛选结果暂挂在返回的 _selected_rules（调试用，不进接口响应），
接 LLM 后改为真正注入 prompt 生成。

seed 存储字段（id / expression_type / strategy_id）为内部字段，
不进接口响应；响应字段名严格对齐 docs/接口文档.md（expression_id / translation_id）。
"""

from app import data_loader
from app.services import rules_service


def get_domestic_expression(
    tea_id: str, audience: dict, style: str | None = None
) -> tuple[dict | None, str]:
    """生成国内中文表达。

    Returns:
        (expression_data, status) — status 为 "ok" / "tea_not_found"
        / "expression_not_found"
    """
    if data_loader.get_tea(tea_id) is None:
        return None, "tea_not_found"

    record = data_loader.get_expression_by_tea(tea_id, "domestic")
    if record is None:
        return None, "expression_not_found"

    # 规则筛选：国内链筛选 domestic_expression 规则
    selected = rules_service.select_rules(
        scope="domestic_expression",
        market="domestic",
        audience_reference="domestic_general",
        tea_id=tea_id,
    )

    data = {
        "expression_id": record["id"],
        "tea_id": record["tea_id"],
        "audience": audience or record.get("audience", {}),
        "outputs": record["outputs"],
        "source_profile_id": record["source_profile_id"],
        "trace_id": record["trace_id"],
    }
    if style:
        data["style"] = style
    data["_selected_rules"] = [r["id"] for r in selected]
    return data, "ok"


def get_cross_cultural_expression(
    tea_id: str,
    target_language: str,
    market: str,
    audience_reference: str,
) -> tuple[dict | None, str]:
    """生成跨文化表达。

    跨文化表达由国内表达横向翻译派生。阶段一从 seed 读取预置表达，
    其中 source_expression_id 已指向国内表达。

    Returns:
        (expression_data, status) — status 为
        "ok" / "tea_not_found" / "expression_not_found"
        / "language_not_supported" / "market_not_supported"
        / "audience_not_supported"
    """
    if data_loader.get_tea(tea_id) is None:
        return None, "tea_not_found"
    if target_language != "en":
        return None, "language_not_supported"
    if market != "western":
        return None, "market_not_supported"
    if audience_reference != "specialty_coffee_lovers":
        return None, "audience_not_supported"

    record = data_loader.get_expression_by_tea(tea_id, "cross_cultural")
    if record is None:
        return None, "expression_not_found"

    # 规则筛选：跨文化链筛选 cross_cultural_expression 规则
    # （含 rule_domestic_to_foreign_translation 翻译规则 + 观音韵保留规则）
    selected = rules_service.select_rules(
        scope="cross_cultural_expression",
        market=market,
        audience_reference=audience_reference,
        tea_id=tea_id,
    )

    data = {
        "translation_id": record["id"],
        "tea_id": record["tea_id"],
        "target_language": target_language,
        "market": market,
        "audience_reference": audience_reference,
        "outputs": record["outputs"],
        "analogy_rules": record.get("analogy_rules", []),
        "source_profile_id": record["source_profile_id"],
        "source_expression_id": record.get("source_expression_id"),
        "trace_id": record["trace_id"],
    }
    data["_selected_rules"] = [r["id"] for r in selected]
    return data, "ok"
