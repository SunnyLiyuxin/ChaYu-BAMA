"""营销物料层（第 4 层）：国内物料 + 跨文化物料，同等重要、相同生成方式。

language=zh → 读取国内表达生成中文物料，source_expression_id 指向国内表达。
language=en → 读取跨文化表达生成英文物料，source_translation_id 指向跨文化表达。
两者均为纵向追溯链上一级；横向翻译关系不在物料层处理。

阶段一：从 seed 预置输出（mock_outputs.yaml）读取物料，不调用真实生图 API
（meta.image_generation_enabled=false）。

seed 存储字段（id / tea_id / asset_type）为内部字段，响应字段名严格对齐
docs/接口文档.md（asset_id）。
"""

from app import data_loader
from app.services import rules_service


def get_marketing_asset(
    tea_id: str,
    language: str,
    asset_type: str = "poster",
    platform: str | None = None,
    route_id: str | None = None,
    style: str | None = None,
) -> tuple[dict | None, str]:
    """生成营销物料。

    Returns:
        (asset_data, status) — status 为
        "ok" / "tea_not_found" / "language_not_supported"
        / "asset_not_found"
    """
    if data_loader.get_tea(tea_id) is None:
        return None, "tea_not_found"
    if language not in ("zh", "en"):
        return None, "language_not_supported"

    record = data_loader.get_asset_by_language(tea_id, language)
    if record is None:
        return None, "asset_not_found"

    # 规则筛选：物料层筛选 marketing_asset 规则（如事实边界）
    selected = rules_service.select_rules(
        scope="marketing_asset",
        market="domestic" if language == "zh" else "western",
        audience_reference="domestic_general" if language == "zh" else "specialty_coffee_lovers",
        tea_id=tea_id,
    )

    data = {
        "asset_id": record["id"],
        "tea_id": record["tea_id"],
        "asset_type": record["asset_type"],
        "platform": platform or record.get("platform", ""),
        "language": language,
        "copy": record["copy"],
        "visual_data": record["visual_data"],
        "image_prompt": record["image_prompt"],
        # 国内物料纵向上一级 = 国内表达；跨文化物料纵向上一级 = 跨文化表达
        "source_expression_id": record.get("source_expression_id"),
        "source_translation_id": record.get("source_translation_id"),
        "trace_id": record["trace_id"],
    }
    if route_id:
        data["route_id"] = route_id
    if style:
        data["style"] = style
    data["_selected_rules"] = [r["id"] for r in selected]
    return data, "ok"
