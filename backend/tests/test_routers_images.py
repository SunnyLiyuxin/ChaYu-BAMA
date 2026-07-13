"""生图接口（POST /api/image/generate）契约测试。

覆盖：
- 未启用 → fallback（fallback_reason="image_not_enabled"）
- 成功 → 200 / success / image_url 非空 / meta.image_generated=true
- 调用失败 → fallback（fallback_reason=具体原因）
- 缺 prompt → 422 VALIDATION_ERROR（走 main.py 统一 handler）

LLM 默认 disabled（conftest autouse）；本文件用局部 fixture 覆盖启用 image。
不真调智谱——monkeypatch image_service.generate_image 返固定结果。
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.services import image_service
from tests.conftest import _patch_get_settings, TEA_ID

ENABLED_SETTINGS = Settings(
    image_api_key="fake-image-key",
    image_base_url="https://open.bigmodel.cn/api/paas/v4",
    image_model="cogview-4",
)
DISABLED_SETTINGS = Settings(image_api_key="", image_base_url="")


@pytest.fixture(autouse=True)
def _image_disabled(monkeypatch, client: TestClient):
    """默认 disabled（覆盖 conftest 默认也行，显式更稳）。

    每个测试再按需 patch 成 ENABLED 或 monkeypatch generate_image。
    conftest 的 llm_disabled（autouse）已把 image_service.get_settings 设成
    _DISABLED_SETTINGS（llm 与 image 都空）；本 fixture 显式再设一次 image 部分，
    避免真 .env 的 IMAGE_* 让 image_enabled=True 真调智谱。
    """
    _patch_get_settings(monkeypatch, DISABLED_SETTINGS)
    yield


def test_image_generate_disabled_fallback(client: TestClient, monkeypatch):
    """未配置 IMAGE_* → fallback，reason=image_not_enabled。

    真实 generate_image 在 image_enabled=False 时直接返 (None,"disabled")、
    不触网（router 总会调 generate_image，但它在 _client() 前就返回）。
    故这里不 monkeypatch generate_image——用真函数 + disabled settings 验证。
    """
    # _image_disabled autouse 已把 image 设成 disabled（image_api_key/base_url 均空）
    # 加防触网兜底：若误进 _client() 就抛
    monkeypatch.setattr(
        image_service, "_client",
        lambda: (_ for _ in ()).throw(AssertionError("disabled 不应触网")),
    )
    resp = client.post("/api/image/generate", json={"prompt": "海报"})
    body = resp.json()
    assert body["success"] is True  # fallback 仍是 success=true
    assert body["meta"]["fallback"] is True
    assert body["meta"]["fallback_reason"] == "image_not_enabled"
    assert "image_url" not in body["data"]


def test_image_generate_success(client: TestClient, monkeypatch):
    """启用 image + monkeypatch 返成功 → 返回 image_url。"""
    _patch_get_settings(monkeypatch, ENABLED_SETTINGS)
    monkeypatch.setattr(
        image_service, "generate_image",
        lambda **kw: (
            {"url": "https://example.com/img.png",
             "model": "cogview-4", "size": kw.get("size") or "1024x1024"},
            "ok",
        ),
    )
    resp = client.post(
        "/api/image/generate",
        json={"prompt": "赛珍珠铁观音海报", "tea_id": TEA_ID, "route_id": "szz_domestic_poster"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["meta"]["fallback"] is False
    assert body["meta"]["image_generated"] is True
    d = body["data"]
    assert d["image_url"] == "https://example.com/img.png"
    assert d["prompt"] == "赛珍珠铁观音海报"
    assert d["model"] == "cogview-4"
    assert d["tea_id"] == TEA_ID
    assert d["route_id"] == "szz_domestic_poster"


def test_image_generate_failure_fallback(client: TestClient, monkeypatch):
    """生图调用失败 → fallback，fallback_reason=具体原因。"""
    _patch_get_settings(monkeypatch, ENABLED_SETTINGS)
    monkeypatch.setattr(
        image_service, "generate_image",
        lambda **kw: (None, "gateway_error"),
    )
    resp = client.post("/api/image/generate", json={"prompt": "海报"})
    body = resp.json()
    assert body["meta"]["fallback"] is True
    assert body["meta"]["fallback_reason"] == "gateway_error"
    assert "image_url" not in body["data"]


def test_image_generate_missing_prompt(client: TestClient, monkeypatch):
    """不传 prompt → 422 VALIDATION_ERROR（走 main.py 统一 handler）。"""
    _patch_get_settings(monkeypatch, ENABLED_SETTINGS)
    # 防触网：即便误进也抛
    monkeypatch.setattr(
        image_service, "_client",
        lambda: (_ for _ in ()).throw(AssertionError("缺 prompt 不应触网")),
    )
    resp = client.post("/api/image/generate", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_image_generate_minimal_prompt(client: TestClient, monkeypatch):
    """只传 prompt（不传 size/tea_id/route_id）也能成功。"""
    _patch_get_settings(monkeypatch, ENABLED_SETTINGS)
    monkeypatch.setattr(
        image_service, "generate_image",
        lambda **kw: (
            {"url": "https://example.com/x.png", "model": "cogview-4", "size": "1024x1024"},
            "ok",
        ),
    )
    resp = client.post("/api/image/generate", json={"prompt": "p"})
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["image_url"] == "https://example.com/x.png"
    # 不传 tea_id / route_id → data 不含这俩键
    assert "tea_id" not in body["data"]
    assert "route_id" not in body["data"]
