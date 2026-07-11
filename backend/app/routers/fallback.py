"""Fallback 路由。

P1：GET/POST /api/fallback —— 显式 fallback 入口。
P2：占位接口（video-asset / translate / image/generate / audio/generate
     / markets / audience-references）统一返回 fallback，避免 404。
"""

import functools
import re

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app import responses
from app.schemas import FallbackRequest

router = APIRouter(prefix="/api", tags=["fallback"])


@router.get("/fallback")
def get_fallback():
    """显式 fallback 入口（P1）。"""
    return responses.fallback_response()


@router.post("/fallback")
def post_fallback(body: FallbackRequest):
    """前端访问未开放功能时的统一占位（P1）。"""
    return responses.fallback_response(
        message=f"功能 {body.feature or '未知'} 已在产品规划中，Demo 阶段暂不提供。"
        if body.feature
        else "该能力已在产品规划中，Demo 阶段暂不提供真实生成结果。"
    )


# ---------------------------------------------------------------------------
# P2 占位接口：注册路由 + 返回 fallback，不实现真实逻辑
# ---------------------------------------------------------------------------


@router.post("/teas/{tea_id}/video-asset")
def video_asset(tea_id: str):
    """视频生成（P2 占位）。"""
    return responses.fallback_response(message="视频生成 Demo 阶段暂不开放。")


@router.post("/translate")
def translate(body: dict | None = None):
    """通用翻译（P2 占位）。"""
    return responses.fallback_response(
        message="通用翻译 Demo 阶段暂不开放，跨文化表达请走 cross-cultural-expression。"
    )


@router.post("/image/generate")
def image_generate(body: dict | None = None):
    """真实生图（P2 占位）。"""
    return responses.fallback_response(
        message="真实生图 Demo 阶段暂不开放，marketing-asset 返回 image_prompt 供前端渲染。"
    )


@router.post("/audio/generate")
def audio_generate(body: dict | None = None):
    """音频生成（P2 占位）。"""
    return responses.fallback_response(message="音频生成 Demo 阶段暂不开放。")


@router.get("/markets")
def markets():
    """市场列表（P2 占位）。"""
    return responses.fallback_response(message="市场列表 Demo 阶段暂以 demo-routes 暴露。")


@router.get("/audience-references")
def audience_references():
    """受众参照系列表（P2 占位）。"""
    return responses.fallback_response(message="受众参照系列表 Demo 阶段暂以 demo-routes 暴露。")


# ---------------------------------------------------------------------------
# 全局 /api/* 404 fallback：未知 API 路由不返回默认 404，返回 fallback JSON
# ---------------------------------------------------------------------------


def _registered_paths(app) -> set[str]:
    """收集所有已注册路由的 path（去尾斜杠归一），含嵌套 router 的子路由。

    catch-all 据此判断：带尾斜杠的请求若其实命中某真实路由，则重定向到无尾斜杠的
    规范形式，而非当作未知路由吞掉。include_router 后 app.routes 里是带 /api 前缀
    的完整 path（如 /api/teas/{tea_id}/knowledge），参数占位 {tea_id} 保留。

    排除 path 转换器（{...:path}）路由：它匹配跨多段、正是 catch-all / 挂载点，
    若纳入会让"真未知单段路由"自匹配后重定向到自己（死循环）。
    """
    paths: set[str] = set()

    def collect(routes):
        for route in routes:
            path = getattr(route, "path", None)
            if path and ":path}" not in path:
                paths.add(path.rstrip("/"))
            sub = getattr(route, "routes", None)
            if sub:
                collect(sub)

    collect(app.routes)
    return paths


@functools.lru_cache(maxsize=None)
def _compile_route(pattern: str) -> re.Pattern:
    """把 FastAPI 路径模式编译成锚定正则。

    {param} 段匹配 [^/]+，其余字面量逐段 re.escape 后拼接（避免正则注入）。
    如 /api/teas/{tea_id}/knowledge → ^/api/teas/[^/]+/knowledge$。
    用于把具体 URL 与动态段路由模式比对（catch-all 收到的尾斜杠请求需重定向）。
    """
    parts = re.split(r"(\{[^/]+\})", pattern.rstrip("/"))
    src: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("{") and part.endswith("}"):
            src.append(r"[^/]+")
        else:
            src.append(re.escape(part))
    return re.compile("^" + "".join(src) + "$")


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def catch_all_api(path: str, request: Request):
    """捕获所有未匹配的 /api/* 请求。

    本路由挂在 prefix="/api" 下，path 是去掉 "/api/" 后的部分
    （如 "demo-routes/" 或 "teas/tieguanyin_001/knowledge/"）。

    - 若带尾斜杠的请求其实命中某已注册路由（含动态段路由 /teas/{tea_id}/knowledge/），
      则 302 重定向到无尾斜杠的规范形式，修复"真实路由被 catch-all 误吞成 fallback"。
    - 否则返回 fallback（fallback_reason=api_not_implemented）。
    """
    normalized = path.rstrip("/")
    target = f"/api/{normalized}"
    for registered in _registered_paths(request.app):
        if _compile_route(registered).match(target):
            return RedirectResponse(url=target, status_code=302)

    return responses.fallback_response(
        title="接口暂未开放",
        message="该接口尚未在 Demo 后端中实现。请确认是否属于后续功能。",
        fallback_reason="api_not_implemented",
    )
