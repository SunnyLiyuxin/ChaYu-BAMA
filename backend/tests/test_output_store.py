"""output_store 缓存契约测试（写路径接库）。

验证 generated_outputs 表作为 LLM 输出缓存的行为：
- 同输入第二次命中缓存、跳过 LLM 调用、内容一致
- 不同输入不命中、会再次调 LLM
- LLM 失败 / 源文缺失不写缓存
- LLM 未启用时不碰库（DB 行数恒 0）

用 fake LLM（计数调用次数）替代真 LLM；用 conftest 的 _isolated_output_db
autouse fixture 隔离到临时库，不污染真实 tea.db。
"""

from fastapi.testclient import TestClient

from app.config import Settings
from app.services import llm_service, output_store
from app.llm_schemas import (
    AssetCopy,
    CrossCulturalExpressionOutputs,
    DomesticExpressionOutputs,
)
from tests.conftest import _patch_get_settings, TEA_ID

ENABLED_SETTINGS = Settings(
    llm_api_key="fake-key-for-testing",
    llm_base_url="https://fake.example.com",
    llm_model="fake-model",
    llm_supports_json_mode=True,
)


def _fake_llm_factory():
    """构造一个可计数的 fake generate。每次返回固定的合法 LLM 输出。

    返回 (fake_fn, calls list) —— calls 是 list 以便测试读取调用次数。
    """
    calls = []
    _domestic_out = {
        "story_style": "FAKE-story",
        "scientific_style": "FAKE-sci",
        "emotional_style": "FAKE-emo",
    }

    def fake_generate(*, output_model, **kw):
        calls.append(output_model.__name__)
        if output_model is DomesticExpressionOutputs:
            return dict(_domestic_out), "ok"
        # 其他模型本测试不触发
        return None, "parse_error"

    return fake_generate, calls


def test_domestic_cache_hit_skips_llm(client: TestClient, monkeypatch):
    """同输入第二次命中缓存、不再调 LLM、内容一致。"""
    monkeypatch.setattr(llm_service, "generate", _fake_llm_factory()[0])
    _patch_get_settings(monkeypatch, ENABLED_SETTINGS)
    # autouse fixture 已把 output_store 重定向到临时库

    url = f"/api/teas/{TEA_ID}/domestic-expression"
    first = client.post(url, json={}).json()
    assert first["meta"]["llm_generated"] is True
    assert first["data"]["outputs"]["story_style"] == "FAKE-story"
    assert output_store.count_rows() == 1, "首次应写一条缓存"

    # 替换 LLM：若被调用就抛错（证明第二次不该调）
    def explode(**kw):
        raise AssertionError("第二次同输入应命中缓存，不应调 LLM")

    monkeypatch.setattr(llm_service, "generate", explode)

    second = client.post(url, json={}).json()
    assert second["meta"]["llm_generated"] is True
    assert second["data"]["outputs"] == first["data"]["outputs"], "命中缓存内容一致"
    assert output_store.count_rows() == 1, "命中缓存不应新增行"


def test_different_input_misses_cache(client: TestClient, monkeypatch):
    """不同 style → 不同 prompt → 哈希变 → 不命中、再调一次 LLM。"""
    fake, calls = _fake_llm_factory()
    monkeypatch.setattr(llm_service, "generate", fake)
    _patch_get_settings(monkeypatch, ENABLED_SETTINGS)

    client.post(f"/api/teas/{TEA_ID}/domestic-expression",
                json={"style": "store_sales"}).json()
    client.post(f"/api/teas/{TEA_ID}/domestic-expression",
                json={"style": "emotional"}).json()
    # 两次不同 style，两次 miss，两次 LLM 调用
    assert len(calls) == 2, f"不同输入应各调一次 LLM，实际 {len(calls)}"
    assert output_store.count_rows() == 2


def test_llm_failure_not_persisted(client: TestClient, monkeypatch):
    """LLM 失败 → 退 seed、不写缓存（DB 行数仍 0）。"""
    monkeypatch.setattr(llm_service, "generate", lambda **kw: (None, "parse_error"))
    _patch_get_settings(monkeypatch, ENABLED_SETTINGS)

    body = client.post(f"/api/teas/{TEA_ID}/domestic-expression", json={}).json()
    assert body["meta"]["llm_generated"] is False
    assert body["meta"]["llm_fallback_reason"] == "parse_error"
    assert output_store.count_rows() == 0, "LLM 失败不应写缓存"


def test_llm_disabled_never_touches_db(client: TestClient, monkeypatch):
    """LLM 未启用 → 不查 / 不写缓存，DB 行数恒 0。"""
    disabled = Settings(llm_api_key="", llm_base_url="")
    _patch_get_settings(monkeypatch, disabled)
    # 若被调 LLM 就抛错
    monkeypatch.setattr(
        llm_service, "generate",
        lambda **kw: (_ for _ in ()).throw(AssertionError("未启用不应调 LLM")),
    )

    body = client.post(f"/api/teas/{TEA_ID}/domestic-expression", json={}).json()
    assert body["meta"]["llm_generated"] is False
    assert output_store.count_rows() == 0


def test_cross_cultural_cache_roundtrip(client: TestClient, monkeypatch):
    """跨文化表达同样走缓存：命中复用、analogy_rules 完整回放。"""
    calls = []
    _cross_out = {
        "literal_explanation": "FAKE-lit",
        "beginner_analogy": "FAKE-ana",
        "cultural_narrative": "FAKE-nar",
        "analogy_rules": [
            {"source_dimension": "x", "target_reference": "y",
             "confidence": "medium", "note": "n"},
        ],
    }

    def fake_generate(*, output_model, **kw):
        calls.append(1)
        if output_model is CrossCulturalExpressionOutputs:
            return dict(_cross_out), "ok"
        return None, "parse_error"

    monkeypatch.setattr(llm_service, "generate", fake_generate)
    _patch_get_settings(monkeypatch, ENABLED_SETTINGS)

    payload = {"target_language": "en", "market": "western",
               "audience_reference": "specialty_coffee_lovers"}
    first = client.post(
        f"/api/teas/{TEA_ID}/cross-cultural-expression", json=payload
    ).json()
    assert first["meta"]["llm_generated"] is True
    assert first["data"]["outputs"]["literal_explanation"] == "FAKE-lit"
    assert len(first["data"]["analogy_rules"]) == 1

    # 第二次：让 LLM 抛错，证明走缓存
    monkeypatch.setattr(
        llm_service, "generate",
        lambda **kw: (_ for _ in ()).throw(AssertionError("应命中缓存")),
    )
    second = client.post(
        f"/api/teas/{TEA_ID}/cross-cultural-expression", json=payload
    ).json()
    assert second["meta"]["llm_generated"] is True
    assert second["data"]["outputs"] == first["data"]["outputs"]
    assert len(calls) == 1, "跨文化只应调一次 LLM"


def test_asset_cache_roundtrip(client: TestClient, monkeypatch):
    """物料文案同样走缓存。雷达数值仍来自 seed（缓存只存 copy + image_prompt）。"""
    calls = []
    _asset_out = {
        "headline": "FAKE-headline",
        "subheadline": "FAKE-sub",
        "body": "FAKE-body",
        "image_prompt": "FAKE-image-prompt",
    }

    def fake_generate(*, output_model, **kw):
        calls.append(1)
        if output_model is AssetCopy:
            return dict(_asset_out), "ok"
        return None, "parse_error"

    monkeypatch.setattr(llm_service, "generate", fake_generate)
    _patch_get_settings(monkeypatch, ENABLED_SETTINGS)

    payload = {"language": "en", "asset_type": "poster"}
    first = client.post(
        f"/api/teas/{TEA_ID}/marketing-asset", json=payload
    ).json()
    assert first["meta"]["llm_generated"] is True
    assert first["data"]["copy"]["headline"] == "FAKE-headline"
    # 雷达数值仍来自 seed（非 FAKE），证明缓存只覆盖文本
    radar = first["data"]["visual_data"]["radar"]
    assert isinstance(radar, list) and radar
    assert all(isinstance(r["value"], int) for r in radar)

    monkeypatch.setattr(
        llm_service, "generate",
        lambda **kw: (_ for _ in ()).throw(AssertionError("应命中缓存")),
    )
    second = client.post(
        f"/api/teas/{TEA_ID}/marketing-asset", json=payload
    ).json()
    assert second["meta"]["llm_generated"] is True
    assert second["data"]["copy"] == first["data"]["copy"]
    assert len(calls) == 1


def test_input_hash_isolates_models():
    """不同 output_model 类名 → 不同哈希（三种生成接口哈希空间互不相交）。"""
    h_dom = output_store.compute_input_hash(
        DomesticExpressionOutputs, "sys", "usr"
    )
    h_cross = output_store.compute_input_hash(
        CrossCulturalExpressionOutputs, "sys", "usr"
    )
    h_asset = output_store.compute_input_hash(AssetCopy, "sys", "usr")
    assert len({h_dom, h_cross, h_asset}) == 3, "三类模型哈希应互不相同"
    # 同模型同输入稳定
    assert h_dom == output_store.compute_input_hash(
        DomesticExpressionOutputs, "sys", "usr"
    )
    # 同模型不同输入 → 不同哈希
    assert h_dom != output_store.compute_input_hash(
        DomesticExpressionOutputs, "sys2", "usr"
    )
