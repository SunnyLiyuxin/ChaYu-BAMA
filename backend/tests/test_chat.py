"""工作台自由提问入口（POST /api/chat）测试。

此前的输入框是装饰性的：用户敲的文本不进后端，生成按预设 copySel/matSel。
本入口前置一次意义评判 LLM，拒绝无意义输入（如「？」），有意义输入把
text 作为 directive 透传到 mode 对应生成链路。

策略：conftest 默认 LLM disabled，本文件用 autouse fixture 覆盖为 enabled，
但用 monkeypatch 替换 llm_service.generate 为可控桩（按 output_model 类型
路由返回评判 / 话术 / 物料 / 跨文化结果），不真调 LLM。
"""

import pytest
from fastapi.testclient import TestClient

from app.llm_schemas import (
    AssetCopy,
    ChatQueryIntent,
    CrossCulturalExpressionOutputs,
    DomesticExpressionOutputs,
)
from app.services import chat_service, llm_service, output_store, prompts
from tests.conftest import _patch_get_settings

TEA_TGY = "BAMA_SZZ_TGY_NX"

ENABLED_SETTINGS = __import__("app.config", fromlist=["Settings"]).Settings(
    llm_api_key="fake-key-for-testing",
    llm_base_url="https://fake.example.com",
    llm_model="fake-model",
    llm_supports_json_mode=True,
)


@pytest.fixture(autouse=True)
def _enable_llm(monkeypatch, client: TestClient):
    """覆盖 conftest 的 disabled 默认：本文件让 llm_enabled=True。"""
    _patch_get_settings(monkeypatch, ENABLED_SETTINGS)
    yield


# ---------------------------------------------------------------------------
# 桩：按 output_model 类型分发（评判 / 话术 / 物料 / 跨文化）
# ---------------------------------------------------------------------------


def _make_generate(monkeypatch, *, judge_out, domestic_out=None, cross_out=None, asset_out=None, calls=None):
    """构造按 output_model 类型分发的 generate 桩。

    judge_out：意义评判应返回的 (dict, status)。
    domestic_out / cross_out / asset_out：对应生成链返回值。
    calls：可选，记录每次调用的 output_model 以便断言调用次数 / 顺序。
    """

    def fake_generate(*, system_prompt, user_prompt, output_model):
        if calls is not None:
            calls.append(output_model)
        if output_model is ChatQueryIntent:
            return judge_out
        if output_model is DomesticExpressionOutputs:
            return domestic_out if domestic_out is not None else (None, "parse_error")
        if output_model is CrossCulturalExpressionOutputs:
            return cross_out if cross_out is not None else (None, "parse_error")
        if output_model is AssetCopy:
            return asset_out if asset_out is not None else (None, "parse_error")
        return (None, "parse_error")

    monkeypatch.setattr(llm_service, "generate", fake_generate)
    return fake_generate


# ---------------------------------------------------------------------------
# (1) meaningful=true + domestic → 端到端 domestic shape，directive 进 prompt
# ---------------------------------------------------------------------------


def test_chat_domestic_meaningful(client, monkeypatch):
    judge = {"meaningful": True, "reason": "询问兰花香"}
    domestic = {
        "story_style": "亲切简短三香话术。",
        "scientific_style": "成分说明：公开文献代理数据。",
        "emotional_style": "场景化饮用体验。",
    }
    calls = []
    _make_generate(
        monkeypatch,
        judge_out=(judge, "ok"),
        domestic_out=(domestic, "ok"),
        calls=calls,
    )

    resp = client.post(
        "/api/chat",
        json={
            "tea_id": TEA_TGY,
            "mode": "domestic",
            "text": "这款铁观音的兰花香是怎么来的",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["meta"]["fallback"] is False

    # shape 同 domestic-expression
    d = body["data"]
    assert d["tea_id"] == TEA_TGY
    for k in ("story_style", "scientific_style", "emotional_style"):
        assert d["outputs"][k] == domestic[k]

    # meta.chat
    chat = body["meta"]["chat"]
    assert chat["mode"] == "domestic"
    assert chat["judge_llm_generated"] is True
    assert chat["judge_fallback"] is None

    # 两次 LLM 调用：先评判，后话术
    assert calls == [ChatQueryIntent, DomesticExpressionOutputs]
    # 话术走了 LLM
    assert body["meta"]["llm_generated"] is True


def test_chat_directive_enters_domestic_prompt(client, monkeypatch):
    """directive 文本应出现在 build_domestic_prompt 输出的 user_prompt 里。"""
    captured = {}

    def fake_generate(*, system_prompt, user_prompt, output_model):
        if output_model is DomesticExpressionOutputs:
            captured["user_prompt"] = user_prompt
        return ({"meaningful": True, "reason": "x"}, "ok") if output_model is ChatQueryIntent else (
            ({"story_style": "s", "scientific_style": "s", "emotional_style": "s"}, "ok")
            if output_model is DomesticExpressionOutputs
            else (None, "parse_error")
        )

    monkeypatch.setattr(llm_service, "generate", fake_generate)

    directive = "我想了解这款铁观音的兰花香是怎么来的"
    client.post(
        "/api/chat",
        json={"tea_id": TEA_TGY, "mode": "domestic", "text": directive},
    )

    assert "用户指令" in captured["user_prompt"]
    assert directive in captured["user_prompt"]


# ---------------------------------------------------------------------------
# (2) meaningful=true + overseas → 跨文化 shape
# ---------------------------------------------------------------------------


def test_chat_overseas_meaningful(client, monkeypatch):
    judge = {"meaningful": True, "reason": "介绍铁观音给老外"}
    cross = {
        "literal_explanation": "en literal",
        "beginner_analogy": "en analogy",
        "cultural_narrative": "en narrative",
        "analogy_rules": [],
    }
    calls = []
    _make_generate(
        monkeypatch,
        judge_out=(judge, "ok"),
        cross_out=(cross, "ok"),
        calls=calls,
    )

    resp = client.post(
        "/api/chat",
        json={"tea_id": TEA_TGY, "mode": "overseas", "text": "introduce this tea to westerners"},
    )
    body = resp.json()
    assert body["success"] is True
    assert body["meta"]["fallback"] is False
    assert body["meta"]["chat"]["mode"] == "overseas"
    d = body["data"]
    for k in ("literal_explanation", "beginner_analogy", "cultural_narrative"):
        assert d["outputs"][k] == cross[k]
    assert calls == [ChatQueryIntent, CrossCulturalExpressionOutputs]


# ---------------------------------------------------------------------------
# (3) meaningful=true + material → marketing-asset shape，directive 进 prompt
# ---------------------------------------------------------------------------


def test_chat_material_meaningful(client, monkeypatch):
    judge = {"meaningful": True, "reason": "要做国风海报"}
    asset = {
        "headline": "兰香海报",
        "subheadline": "三香层层递进",
        "body": "正文文案。",
        "image_prompt": "Tieguanyin oolong tea, orchid flowers, white gaiwan, golden liquor.",
    }
    calls = []
    _make_generate(
        monkeypatch,
        judge_out=(judge, "ok"),
        asset_out=(asset, "ok"),
        calls=calls,
    )

    resp = client.post(
        "/api/chat",
        json={
            "tea_id": TEA_TGY,
            "mode": "material",
            "text": "帮我做一张突出兰花香的国风海报",
            "language": "zh",
            "style": "国风",
            "platform": "小红书",
        },
    )
    body = resp.json()
    assert body["success"] is True
    assert body["meta"]["fallback"] is False
    assert body["meta"]["chat"]["mode"] == "material"
    d = body["data"]
    assert d["copy"]["headline"] == "兰香海报"
    assert d["image_prompt"]
    assert calls == [ChatQueryIntent, AssetCopy]


def test_chat_directive_enters_asset_prompt(client, monkeypatch):
    """material 模式：directive 应出现在 build_asset_copy_prompt 的 user_prompt 里。"""
    captured = {}

    def fake_generate(*, system_prompt, user_prompt, output_model):
        if output_model is AssetCopy:
            captured["user_prompt"] = user_prompt
        return ({"meaningful": True, "reason": "x"}, "ok") if output_model is ChatQueryIntent else (
            ({
                "headline": "h", "subheadline": "s", "body": "b",
                "image_prompt": "Tieguanyin tea, orchid, gaiwan.",
            }, "ok")
            if output_model is AssetCopy
            else (None, "parse_error")
        )

    monkeypatch.setattr(llm_service, "generate", fake_generate)

    directive = "帮我做一张突出兰花香的国风海报"
    client.post(
        "/api/chat",
        json={"tea_id": TEA_TGY, "mode": "material", "text": directive, "language": "zh"},
    )

    assert "用户指令" in captured["user_prompt"]
    assert directive in captured["user_prompt"]


# ---------------------------------------------------------------------------
# (4) meaningful=false → fallback，不调生成 LLM
# ---------------------------------------------------------------------------


def test_chat_meaningless_returns_fallback(client, monkeypatch):
    """评判判无意义 → fallback（empty_or_meaningless_query），不调生成 LLM。"""
    calls = []
    _make_generate(
        monkeypatch,
        judge_out=({"meaningful": False, "reason": "纯标点无意义"}, "ok"),
        domestic_out=(None, "parse_error"),  # 不应被调用
        calls=calls,
    )

    resp = client.post(
        "/api/chat",
        json={"tea_id": TEA_TGY, "mode": "domestic", "text": "？"},
    )
    body = resp.json()
    assert body["meta"]["fallback"] is True
    assert body["meta"]["fallback_reason"] == "empty_or_meaningless_query"
    # 只调了一次评判，没调生成 LLM
    assert calls == [ChatQueryIntent]


def test_chat_pure_whitespace_returns_fallback_without_llm(client, monkeypatch):
    """纯空白文本（strip 后空）→ 直接 fallback，连评判 LLM 都不调。"""
    called = []

    def boom(**kw):
        called.append(1)
        return (None, "parse_error")

    monkeypatch.setattr(llm_service, "generate", boom)

    resp = client.post(
        "/api/chat",
        json={"tea_id": TEA_TGY, "mode": "domestic", "text": "   "},
    )
    body = resp.json()
    assert body["meta"]["fallback"] is True
    assert body["meta"]["fallback_reason"] == "empty_or_meaningless_query"
    assert called == []  # 没调 LLM


# ---------------------------------------------------------------------------
# (5) 评判 LLM 失败 → 保守放行（仍走生成链，judge_fallback 标记）
# ---------------------------------------------------------------------------


def test_chat_judge_failure_passes_through(client, monkeypatch):
    """评判 LLM 失败（network_error）→ 保守放行 meaningful=true，仍走生成链。"""
    judge_out = (None, "network_error")
    domestic = {
        "story_style": "s", "scientific_style": "s", "emotional_style": "s",
    }
    _make_generate(
        monkeypatch,
        judge_out=judge_out,
        domestic_out=(domestic, "ok"),
    )

    resp = client.post(
        "/api/chat",
        json={"tea_id": TEA_TGY, "mode": "domestic", "text": "随便问点啥"},
    )
    body = resp.json()
    assert body["success"] is True
    assert body["meta"]["fallback"] is False
    # 放行了 → 走到了生成
    assert body["data"]["outputs"]["story_style"] == "s"
    # judge_fallback 标记降级原因
    assert body["meta"]["chat"]["judge_fallback"] == "network_error"
    assert body["meta"]["chat"]["judge_llm_generated"] is False


# ---------------------------------------------------------------------------
# (6) LLM 未启用 → feature_not_available fallback
# ---------------------------------------------------------------------------


def test_chat_llm_disabled_returns_fallback(client, monkeypatch):
    """LLM 未启用 → 意义评判无 seed 兜底，整个接口走 feature_not_available fallback。"""
    from app.config import Settings

    _patch_get_settings(monkeypatch, Settings(llm_api_key="", llm_base_url=""))
    monkeypatch.setattr(
        llm_service, "generate",
        lambda **kw: (_ for _ in ()).throw(AssertionError("未启用不应调 LLM")),
    )
    resp = client.post(
        "/api/chat",
        json={"tea_id": TEA_TGY, "mode": "domestic", "text": "问个问题"},
    )
    body = resp.json()
    assert body["meta"]["fallback"] is True
    assert body["meta"]["fallback_reason"] == "feature_not_available"


# ---------------------------------------------------------------------------
# (7) 评判缓存命中：同 text 二次调用 → 评判跳过 LLM
# ---------------------------------------------------------------------------


def test_chat_judge_cache_hit(client, monkeypatch):
    """同一 text+mode 二次调用 → 评判结果命中缓存，不再调评判 LLM。"""
    judge = {"meaningful": True, "reason": "正常提问"}
    domestic = {"story_style": "s", "scientific_style": "s", "emotional_style": "s"}
    judge_calls = []

    def fake_generate(*, system_prompt, user_prompt, output_model):
        if output_model is ChatQueryIntent:
            judge_calls.append(1)
            return (judge, "ok")
        if output_model is DomesticExpressionOutputs:
            return (domestic, "ok")
        return (None, "parse_error")

    monkeypatch.setattr(llm_service, "generate", fake_generate)

    payload = {"tea_id": TEA_TGY, "mode": "domestic", "text": "这款茶的回甘是怎么来的"}
    client.post("/api/chat", json=payload)
    first = len(judge_calls)
    client.post("/api/chat", json=payload)
    # 评判第二次应命中缓存 → 评判调用次数不增
    assert len(judge_calls) == first


def test_chat_judge_cached_after_first_call(client, monkeypatch):
    """评判结果写入了 generated_outputs（output_type=chat_query_intent）。"""
    judge = {"meaningful": True, "reason": "x"}
    domestic = {"story_style": "s", "scientific_style": "s", "emotional_style": "s"}
    _make_generate(monkeypatch, judge_out=(judge, "ok"), domestic_out=(domestic, "ok"))

    before = output_store.count_rows()
    client.post(
        "/api/chat",
        json={"tea_id": TEA_TGY, "mode": "domestic", "text": "介绍下这款铁观音"},
    )
    after = output_store.count_rows()
    assert after > before


# ---------------------------------------------------------------------------
# (8) 回归：现有 marketing-asset 调用点 directive=None 时 prompt 不含用户指令段
# ---------------------------------------------------------------------------


def test_existing_marketing_asset_directive_none_unchanged(client, monkeypatch):
    """现有 marketing-asset 路由调用点不传 directive → prompt 不应出现【用户指令】段。"""
    captured = {}

    def fake_generate(*, system_prompt, user_prompt, output_model):
        if output_model is AssetCopy:
            captured["user_prompt"] = user_prompt
            return ({
                "headline": "h", "subheadline": "s", "body": "b",
                "image_prompt": "Tieguanyin tea.",
            }, "ok")
        return (None, "parse_error")

    monkeypatch.setattr(llm_service, "generate", fake_generate)

    client.post(
        f"/api/teas/{TEA_TGY}/marketing-asset",
        json={"language": "zh", "asset_type": "poster"},
    )
    assert "用户指令" not in captured["user_prompt"]


def test_existing_domestic_endpoint_directive_none_unchanged(client, monkeypatch):
    """回归：现有 domestic-expression 路由 prompt 不含【用户指令】段。"""
    captured = {}

    def fake_generate(*, system_prompt, user_prompt, output_model):
        if output_model is DomesticExpressionOutputs:
            captured["user_prompt"] = user_prompt
            return ({"story_style": "s", "scientific_style": "s", "emotional_style": "s"}, "ok")
        return (None, "parse_error")

    monkeypatch.setattr(llm_service, "generate", fake_generate)

    client.post(
        f"/api/teas/{TEA_TGY}/domestic-expression",
        json={"audience": {"age_group": "gen_z"}, "style": "store_sales"},
    )
    assert "用户指令" not in captured["user_prompt"]


# ---------------------------------------------------------------------------
# (9) 单元级：build_chat_query_prompt 注入用户输入 + mode 上下文
# ---------------------------------------------------------------------------


def test_build_chat_query_prompt_injects_text():
    system, user = prompts.build_chat_query_prompt("这款茶怎么样？", "material")
    assert "意义评判" in system
    assert "meaningful" in system
    assert "这款茶怎么样？" in user
    assert "物料" in user  # mode 上下文描述


def test_judge_meaningful_disabled():
    """LLM 未启用 → (False, 'disabled', False, None)。"""
    from app.config import Settings

    import app.services.chat_service as cs
    original = cs.get_settings
    cs.get_settings = lambda: Settings(llm_api_key="", llm_base_url="")
    try:
        meaningful, status, gen, fb = cs._judge_meaningful("问个问题", "domestic")
        assert meaningful is False
        assert status == "disabled"
        assert gen is False
        assert fb is None
    finally:
        cs.get_settings = original
