"""工作台自由提问路由：POST /api/chat。

前端文案 / 物料工作台的自由输入框统一走本入口。此前输入框是装饰性的——
用户敲的文本不进后端，domestic-expression / cross-cultural-expression /
marketing-asset 都按预设 copySel / matSel 生成一大段。本入口前置一次意义评判
LLM，拒绝无意义输入（如「？」），有意义输入把原文作为 directive 透传到 mode
对应的生成链路，让自由提问真正影响生成。

响应 shape 与对应链路一致（domestic→5.1 / overseas→5.2 / material→6.1），
meta 额外含 chat 子对象（judge_llm_generated / judge_fallback / mode）。
"""

from fastapi import APIRouter

from app import enum_map, responses
from app.schemas import ChatRequest
from app.services import chat_service

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
def chat(body: ChatRequest):
    """工作台自由提问：评判输入意义 → 透传 directive 到对应生成链路。

    - mode=domestic → 国内表达（5.1 shape）
    - mode=overseas → 跨文化表达（5.2 shape）
    - mode=material → 营销物料（6.1 shape，前端拿 image_prompt 再调 6.2 出图）

    评判 LLM 判无意义 → fallback（empty_or_meaningless_query）；LLM 未启用 →
    feature_not_available fallback（意义评判无 seed 兜底）。
    """
    text = (body.text or "").strip()
    if not text:
        # Pydantic min_length=1 已挡空串，这里再挡 strip 后空（纯空白）
        return responses.fallback_response(
            title="茶语没看懂您的问题",
            message="请输入想了解的茶品风味、成分，或想要的物料内容，再发送哦。",
            suggested_action="例如：这款铁观音的兰花香是怎么来的？",
            fallback_reason="empty_or_meaningless_query",
        )

    data, status, meta = chat_service.judge_and_route(
        tea_id=body.tea_id,
        mode=body.mode,
        text=text,
        audience=body.audience.model_dump(exclude_none=True) if body.audience else None,
        tone=enum_map.resolve_expression_tone(body.tone),
        length=enum_map.resolve_expression_length(body.length),
        time_node=body.time_node,
        task_type=enum_map.resolve_task_type(body.task_type),
        flavor_reference=enum_map.resolve_flavor_reference(body.flavor_reference),
        recipient=enum_map.resolve_recipient(body.recipient),
        language=body.language,
        asset_type=body.asset_type,
        platform=enum_map.resolve_platform(body.platform),
        route_id=body.route_id,
        style=enum_map.resolve_marketing_style(body.style),
        content_theme=enum_map.resolve_content_theme(body.content_theme),
    )

    chat_meta = {
        "chat": {
            "judge_llm_generated": meta.get("judge_llm_generated", False),
            "judge_fallback": meta.get("judge_fallback"),
            "mode": body.mode,
        }
    }

    if status == "disabled":
        # LLM 未启用：意义评判无 seed 兜底
        return responses.fallback_response(
            message="自由提问需要 LLM 支持，当前未配置 LLM。",
            fallback_reason="feature_not_available",
        )
    if status == "empty_or_meaningless":
        # 评判判无意义 → 友好提示，不生成内容
        return responses.fallback_response(
            title="茶语没看懂您的问题",
            message="这个问题茶语没太看懂，可以试试描述想了解的风味、成分，或想要的物料哦。",
            suggested_action="例如：这款茶的回甘是怎么来的？/ 帮我做一张突出兰花香的国风海报。",
            fallback_reason="empty_or_meaningless_query",
        )
    if status == "tea_not_found":
        return responses.error("TEA_NOT_FOUND", "未找到对应茶品")
    if status in ("language_not_supported", "market_not_supported", "audience_not_supported"):
        return responses.fallback_response(
            message="当前目标语言 / 市场 / 受众参照系 Demo 阶段暂未开放。",
            suggested_action="Demo 主路径：铁观音 × 英语 × 欧美市场 × 精品咖啡爱好者。",
        )
    if status == "expression_not_found":
        return responses.fallback_response(message="该茶品表达 Demo 阶段尚未预置。")
    if status == "asset_not_found":
        return responses.fallback_response(message="该茶品对应语言物料 Demo 阶段尚未预置。")
    if status != "ok":
        return responses.fallback_response(message="生成暂不可用，请稍后重试。")

    # 成功：把下游生成 meta + chat meta 合并进响应
    extra = {
        "llm_generated": meta.get("llm_generated", False),
        "used_rule_ids": meta.get("used_rule_ids", []),
    }
    if meta.get("llm_fallback_reason") is not None:
        extra["llm_fallback_reason"] = meta["llm_fallback_reason"]
    # chat 子对象（评判 meta）单独放，不与生成 meta 平级
    return responses.success(data, **extra, chat=chat_meta["chat"])
