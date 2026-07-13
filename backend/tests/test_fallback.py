"""Fallback 接口与规则：显式 fallback / P2 占位 / catch-all / health-llm。"""

from tests.conftest import TEA_ID


def test_get_fallback(client):
    resp = client.get("/api/fallback")
    body = resp.json()
    assert body["success"] is True
    assert body["meta"]["fallback"] is True
    assert body["meta"]["fallback_reason"] == "feature_not_available"
    assert "title" in body["data"]


def test_post_fallback(client):
    resp = client.post("/api/fallback", json={"feature": "video_generation"})
    body = resp.json()
    assert body["meta"]["fallback"] is True
    assert "video_generation" in body["data"]["message"]


def test_catch_all_unknown_api(client):
    """未知 /api/* 路由 → catch-all 返回 api_not_implemented fallback。"""
    resp = client.get("/api/totally-made-up-endpoint")
    body = resp.json()
    assert body["success"] is True
    assert body["meta"]["fallback"] is True
    assert body["meta"]["fallback_reason"] == "api_not_implemented"


def test_p2_placeholders_return_fallback(client):
    """P2 占位接口仍返回 fallback（video/translate/audio；image/generate 已升级真实生图）。"""
    r = client.post(f"/api/teas/{TEA_ID}/video-asset")
    assert r.json()["meta"]["fallback"] is True
    r = client.post("/api/translate", json={})
    assert r.json()["meta"]["fallback"] is True
    r = client.post("/api/audio/generate", json={})
    assert r.json()["meta"]["fallback"] is True


def test_health_llm_no_plaintext_key(client):
    """health-llm 不输出明文 key，字段集符合契约。"""
    resp = client.get("/api/health-llm")
    body = resp.json()
    assert body["success"] is True
    d = body["data"]
    for k in ("llm_enabled", "llm_model", "llm_base_url_masked", "llm_supports_json_mode"):
        assert k in d
    # disabled（conftest autouse）→ llm_enabled=False
    assert d["llm_enabled"] is False
    # 不存在任何明文 key 字段（只允许 *masked 的字段）
    for k in d:
        assert "key" not in k.lower(), f"发现疑似明文 key 字段：{k}"
