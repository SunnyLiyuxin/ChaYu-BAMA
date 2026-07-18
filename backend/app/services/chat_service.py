"""工作台自由提问入口（POST /api/chat）服务：意义评判 + directive 路由。

工作台的自由输入框此前是装饰性的：前端拿到用户文本后只显示气泡，调用
domestic-expression / cross-cultural-expression / marketing-asset 时不传
directive，导致用户输「？」或输正常提问，后端收到的请求完全一样、都按
预设 copySel / matSel 生成一大段。

本服务修复根因：
1. 前置一次「意义评判」LLM（build_chat_query_prompt），判断输入是否有意义：
   - meaningful=false → 返回 fallback（empty_or_meaningless_query），不调生成 LLM。
   - meaningful=true → 把原文作为 directive 透传给对应生成链路。
   评判 LLM 复用 llm_service.generate（同一 LLM_* 配置），结果按 input_hash
   缓存（output_store，namespace=chat_query_intent），同输入二次不重判。
2. 降级约定（对齐 §1.4 既有模式）：
   - LLM 未启用 → (None, "disabled")：意义评判无 seed 兜底，交路由层走
     feature_not_available fallback（与 NL 入口未启用一致）。
   - 评判 LLM 调用失败（network/timeout/parse/gateway）→ 保守放行 meaningful=true，
     让请求继续走到生成链路（宁可让用户看到一段生成内容，也不要因评判抖动拒掉
     正常提问）。judge_fallback 暴露降级原因。
3. mode 路由（tea_id / 链路 / 模式由工作台前置选定，无需识别茶品）：
   - domestic / overseas → 复用 expression_service（domestic / cross-cultural 链），
     透传 directive。响应 shape 与对应链路完全一致。
   - material → 复用 asset_service.get_marketing_asset，透传 directive；响应 shape
     与 marketing-asset 一致（含 image_prompt + trace_id）。真实出图仍由前端拿
     image_prompt 调 /api/image/generate（不在本服务）。
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.llm_schemas import ChatQueryIntent
from app.services import asset_service, expression_service, llm_service, output_store, prompts

logger = logging.getLogger("app.chat")

# status 取值
_OK = "ok"
_DISABLED = "disabled"
# meaningful=false 时返回的 status（路由层据此走 empty_or_meaningless_query fallback）
_EMPTY = "empty_or_meaningless"

# mode → 链路：文案国内 / 海外 / 物料
_VALID_MODES = {"domestic", "overseas", "material"}


def judge_and_route(
    *,
    tea_id: str,
    mode: str,
    text: str,
    audience: dict | None = None,
    tone: str | None = None,
    length: str | None = None,
    time_node: str | None = None,
    task_type: str | None = None,
    flavor_reference: str | None = None,
    recipient: str | None = None,
    # 物料参数
    language: str | None = None,
    asset_type: str = "poster",
    platform: str | None = None,
    route_id: str | None = None,
    style: str | None = None,
    content_theme: str | None = None,
) -> tuple[dict | None, str, dict]:
    """评判用户自由输入是否有意义，有意义则路由到对应生成链路并透传 directive。

    Args:
        tea_id: 工作台前置选定的茶品（不在此识别茶品）。
        mode: domestic（国内文案）/ overseas（海外跨文化文案）/ material（物料）。
        text: 用户原始自由输入（已 strip 非空）。
        audience/tone/length/time_node/task_type/flavor_reference/recipient: 文案
            hint（经 enum_map 翻译后的内部值），透传给 expression_service。
        language/asset_type/platform/route_id/style/content_theme: 物料参数，透传给
            asset_service。

    Returns:
        (data | None, status, meta)。
        status ∈ "ok" / "disabled" / "empty_or_meaningless" / <下游生成链 status>。
        meta：{"judge_llm_generated": bool, "judge_fallback": str | None,
               "mode": str, "llm_generated": bool, "llm_fallback_reason": str | None,
               "used_rule_ids": list[str]}。
    """
    # 先做意义评判
    meaningful, judge_status, judge_llm_generated, judge_fallback = _judge_meaningful(text, mode)

    if judge_status == _DISABLED:
        # LLM 未启用：意义评判无 seed 兜底，交路由层走 feature_not_available fallback
        return None, _DISABLED, _meta(judge_llm_generated, judge_fallback, mode)

    if not meaningful:
        # 评判判无意义 → 返回 empty_or_meaningless，路由层走友好 fallback 提示
        return None, _EMPTY, _meta(judge_llm_generated, judge_fallback, mode)

    # 有意义：把 text 作为 directive 透传到对应生成链路
    if mode == "material":
        # 物料语言默认对齐 mode（material 由前端按国内/海外决定 language）
        lang = language or "zh"
        data, gen_status, llm_meta = asset_service.get_marketing_asset(
            tea_id=tea_id,
            language=lang,
            asset_type=asset_type,
            platform=platform,
            route_id=route_id,
            style=style,
            content_theme=content_theme,
            directive=text,
        )
    elif mode == "overseas":
        data, gen_status, llm_meta = expression_service.get_cross_cultural_expression(
            tea_id=tea_id,
            target_language="en",
            market="western",
            audience_reference="specialty_coffee_lovers",
            directive=text,
            tone=tone,
            length=length,
            time_node=time_node,
            task_type=task_type,
            flavor_reference=flavor_reference,
            recipient=recipient,
        )
    else:  # domestic
        data, gen_status, llm_meta = expression_service.get_domestic_expression(
            tea_id=tea_id,
            audience=audience or {},
            style=None,
            directive=text,
            tone=tone,
            length=length,
            time_node=time_node,
            task_type=task_type,
            flavor_reference=flavor_reference,
            recipient=recipient,
        )

    meta = _meta(judge_llm_generated, judge_fallback, mode)
    meta["llm_generated"] = llm_meta.get("llm_generated", False)
    meta["llm_fallback_reason"] = llm_meta.get("llm_fallback_reason")
    meta["used_rule_ids"] = llm_meta.get("used_rule_ids", [])
    return data, gen_status, meta


def _judge_meaningful(
    text: str, mode: str
) -> tuple[bool, str, bool, str | None]:
    """调意义评判 LLM。返回 (meaningful, status, judge_llm_generated, judge_fallback)。

    - LLM 未启用 → (False, "disabled", False, None)。
    - 评判成功 → (meaningful, "ok", True, None)。
    - 评判失败（网络/超时/解析/网关）→ 保守放行 (True, "ok", False, <reason>)，
      让请求继续走到生成链路，不因评判抖动误拒正常提问。
    """
    if not get_settings().llm_enabled:
        return False, _DISABLED, False, None

    system_prompt, user_prompt = prompts.build_chat_query_prompt(text, mode)
    input_hash = output_store.compute_input_hash(
        ChatQueryIntent, system_prompt, user_prompt
    )

    cached = output_store.get_cached(input_hash)
    if cached is not None:
        return bool(cached.get("meaningful", True)), _OK, True, None

    llm_out, status = llm_service.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_model=ChatQueryIntent,
    )
    if status == _OK and llm_out:
        output_store.persist(
            output_type="chat_query_intent",
            tea_id=None,
            route_id=None,
            input_hash=input_hash,
            content=llm_out,
        )
        return bool(llm_out.get("meaningful", True)), _OK, True, None

    # 评判失败：保守放行，judge_fallback 标记降级原因
    logger.warning("意义评判 LLM 失败，保守放行 reason=%s", status)
    return True, _OK, False, status


def _meta(
    judge_llm_generated: bool, judge_fallback: str | None, mode: str
) -> dict:
    """构造 meta.chat 子对象 + 下游生成 meta 占位。"""
    return {
        "judge_llm_generated": judge_llm_generated,
        "judge_fallback": judge_fallback,
        "mode": mode,
        # 下游生成链 meta（material 路由在 ok 后填）
        "llm_generated": False,
        "llm_fallback_reason": None,
        "used_rule_ids": [],
    }
