"""生图服务：调智谱 CogView-4 文生图。

设计要点（镜像 llm_service.generate）：
- 基于 openai SDK（OpenAI 兼容），智谱 CogView 端点 {base_url}/images/generations
  与 GLM 共用智谱 key + base_url。但本服务凭证独立走 IMAGE_*（当前 LLM_* 多半
  指向 DeepSeek，不覆盖智谱生图端点）—— 不回退 LLM_*，必须独立配 IMAGE_*。
- 同步调用，与现有同步 service 风格一致（FastAPI 把同步 handler 丢线程池跑）。
- 失败永不抛：未启用 / 网络 / 超时 / 解析失败统一返回降级状态，由路由层走 fallback。
  生图无 seed 兜底（没有预置图），与文本三接口"退回 seed"不同。

返回 (result | None, status)：
  status ∈ "ok" / "disabled" / "network_error" / "timeout"
         / "parse_error" / "gateway_error"
  result = {"url": str, "model": str, "size": str}

缓存（镜像 intent_service）：按 prompt + size 算 input_hash，命中且 created_at
≤29 天（智谱图片临时链接 30 天有效）即复用、跳过 CogView 调用；否则调 CogView、
成功后写回。缓存命中仍标 success（对前端透明）。
"""

import logging
from datetime import datetime, timedelta, timezone

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
)

from app.config import get_settings
from app.llm_schemas import ImageResult
from app.services import output_store

logger = logging.getLogger("app.image")

# 生图缓存有效期：智谱图片临时链接 30 天，留 1 天裕量提前判 miss 重生。
_CACHE_TTL = timedelta(days=29)

# status 取值（与 llm_service 对齐，便于路由层统一处理）
FALLBACK_DISABLED = "disabled"
FALLBACK_NETWORK = "network_error"
FALLBACK_TIMEOUT = "timeout"
FALLBACK_PARSE = "parse_error"
FALLBACK_GATEWAY = "gateway_error"


def _client() -> OpenAI:
    """构造 OpenAI 兼容 client（指向配置的 IMAGE_BASE_URL）。"""
    s = get_settings()
    api_key, base_url = s.image_credentials()
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=s.image_timeout,
        max_retries=0,  # 不静默延长延迟；失败即降级
    )


def generate_image(*, prompt: str, size: str | None = None) -> tuple[dict | None, str]:
    """调 CogView-4 生图。

    Args:
        prompt: 图片生成 prompt（通常来自 marketing-asset.image_prompt）
        size: 输出尺寸，空则用配置默认 image_size

    Returns:
        (result | None, status)。
        成功 → ({"url","model","size"}, "ok")；否则 → (None, fallback_reason)。
    """
    s = get_settings()
    if not s.image_enabled:
        return None, FALLBACK_DISABLED

    used_size = size or s.image_size

    # 先查缓存：命中且未过期即复用，跳过 CogView 调用。
    input_hash = output_store.compute_input_hash(ImageResult, prompt, used_size)
    cached = output_store.get_cached(input_hash)
    if cached is not None and _cache_fresh(cached):
        return _build_result(cached, s.image_model, used_size), "ok"

    try:
        resp = _client().images.generate(
            model=s.image_model,
            prompt=prompt,
            n=1,
            size=used_size,
        )
    except APITimeoutError:
        logger.warning("生图超时 model=%s timeout=%s", s.image_model, s.image_timeout)
        return None, FALLBACK_TIMEOUT
    except APIConnectionError as e:
        # APITimeoutError 是 APIConnectionError 子类，必须放它之前
        logger.warning("生图连接失败 model=%s err=%s", s.image_model, e)
        return None, FALLBACK_NETWORK
    except APIStatusError as e:
        body = ""
        try:
            body = e.response.text[:500]
        except Exception:
            body = ""
        logger.warning(
            "生图网关错误 model=%s status=%s body=%s err=%s",
            s.image_model, e.status_code, body, e,
        )
        return None, FALLBACK_GATEWAY
    except Exception as e:  # 其他未预期异常，兜底为 network_error
        logger.warning("生图调用失败（未分类）model=%s err=%s", s.image_model, e)
        return None, FALLBACK_NETWORK

    # 取图片 URL；代理可能返回非标准 ImagesResponse 形状，统一兜住。
    try:
        url = resp.data[0].url
    except (AttributeError, IndexError, TypeError) as e:
        logger.warning(
            "生图响应非标准 ImagesResponse 形状，降级 model=%s type=%s err=%s",
            s.image_model, type(resp).__name__, e,
        )
        return None, FALLBACK_PARSE
    if not url:
        logger.warning("生图响应 data[0].url 为空，降级 model=%s", s.image_model)
        return None, FALLBACK_PARSE

    now = datetime.now(timezone.utc).isoformat()
    content = {"url": url, "model": s.image_model, "size": used_size, "created_at": now}
    output_store.persist(
        output_type="image",
        tea_id=None,
        route_id=None,
        input_hash=input_hash,
        content=content,
    )
    logger.info("生图成功 model=%s size=%s prompt_chars=%d", s.image_model, used_size, len(prompt))
    return _build_result(content, s.image_model, used_size), "ok"


def _cache_fresh(cached: dict) -> bool:
    """缓存是否在有效期内（created_at ≤29 天）。

    created_at 缺失或解析失败视为过期（强制重生，避免死链）。
    """
    created = cached.get("created_at")
    if not created:
        return False
    try:
        ts = datetime.fromisoformat(created)
    except (ValueError, TypeError):
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - ts < _CACHE_TTL


def _build_result(content: dict, model: str, size: str) -> dict:
    """从缓存内容组装返回结果（命中缓存时模型/尺寸沿用缓存值）。"""
    return {
        "url": content["url"],
        "model": content.get("model") or model,
        "size": content.get("size") or size,
    }
