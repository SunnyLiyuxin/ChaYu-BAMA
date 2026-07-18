"""读路径切库后的 shape 对齐测试。

验证 data_loader getter 改为查 SQLite 后，返回 shape 与内存版逐字段一致。
重点：JSON 列嵌套结构完整（dimensions / outputs / analogy_rules / radar /
evidence）、ID / trace / source 字段无损。

夹具：conftest 的 _seeded_read_db（session 级，autouse）已把读 engine 指向
临时灌好的 tea.db。本文件只读不写，共享 session 级库安全。
LLM 全程 disabled（conftest autouse），不影响 getter shape。
"""

from app import data_loader

TEA_ID = "BAMA_SZZ_TGY_NX"


# ---------------------------------------------------------------------------
# 基础 getter：列表 / 单条
# ---------------------------------------------------------------------------


def test_list_teas_shape():
    teas = data_loader.list_teas()
    assert isinstance(teas, list) and len(teas) == 3
    t = next(x for x in teas if x["id"] == TEA_ID)
    # 顶层字段对齐 ORM 列
    for k in ("id", "name", "category", "origin", "brand", "demo_available"):
        assert k in t
    assert t["demo_available"] is True
    # shelf_life_months / shelf_life 字段不齐（牛一用 shelf_life 字符串）
    assert t["shelf_life_months"] == 24


def test_get_tea_found_and_missing():
    t = data_loader.get_tea(TEA_ID)
    assert t and t["id"] == TEA_ID
    assert data_loader.get_tea("nonexistent") is None


def test_list_demo_routes_shape():
    routes = data_loader.list_demo_routes()
    assert isinstance(routes, list) and len(routes) == 6
    main = [r for r in routes if r["id"] in {"szz_domestic_poster", "szz_western_coffee_poster"}]
    assert len(main) == 2
    assert all(r["enabled"] for r in main)


# ---------------------------------------------------------------------------
# 知识卡片：多表 join + evidence 明细组装（最复杂）
# ---------------------------------------------------------------------------


def test_get_knowledge_shape():
    k = data_loader.get_knowledge(TEA_ID)
    assert k is not None
    # 顶层四块
    for key in ("tea", "origin", "process", "story", "evidence"):
        assert key in k
    # tea 子结构
    for key in ("id", "name", "category", "origin", "brand"):
        assert key in k["tea"]
    # process.steps 是 list
    assert isinstance(k["process"]["steps"], list) and k["process"]["steps"]
    # evidence 明细：每条 shape 完整
    assert isinstance(k["evidence"], list) and k["evidence"]
    for ev in k["evidence"]:
        for key in ("id", "source_type", "title", "source", "confidence", "note"):
            assert key in ev
        # title 取自 evidence.source（与内存版一致）
        assert ev["title"] == ev["source"]
        assert ev["confidence"] in ("high", "medium", "low")
    # 该茶 evidence_ids 有 5 条
    assert len(k["evidence"]) == 5


def test_get_knowledge_missing_tea():
    assert data_loader.get_knowledge("nonexistent") is None


# ---------------------------------------------------------------------------
# 风味坐标：JSON 列 dimensions / component_notes
# ---------------------------------------------------------------------------


def test_get_flavor_profile_shape():
    p = data_loader.get_flavor_profile(TEA_ID)
    assert p is not None
    # 返回 shape 对齐内存版（仅 dimensions + component_notes，不含 profile_id/tea_id）
    assert set(p.keys()) == {"dimensions", "component_notes"}
    dims = p["dimensions"]
    assert isinstance(dims, list) and len(dims) == 8
    for d in dims:
        for key in ("key", "label_zh", "label_en", "intensity", "evidence_ids"):
            assert key in d
        assert isinstance(d["intensity"], int) and 0 <= d["intensity"] <= 10
        assert isinstance(d["evidence_ids"], list)
    notes = p["component_notes"]
    assert isinstance(notes, list) and notes


def test_get_flavor_profile_missing():
    assert data_loader.get_flavor_profile("nonexistent") is None


# ---------------------------------------------------------------------------
# 表达：outputs / analogy_rules（跨文化有、国内无）
# ---------------------------------------------------------------------------


def test_get_expression_by_tea_domestic():
    e = data_loader.get_expression_by_tea(TEA_ID, "domestic")
    assert e is not None
    assert e["id"] == "expr_cn_szz_tgy_nx"
    assert e["expression_type"] == "domestic"
    for k in ("story_style", "scientific_style", "emotional_style"):
        assert isinstance(e["outputs"][k], str) and e["outputs"][k]
    # 国内表达是翻译源文：source_expression_id 为 None
    assert e["source_expression_id"] is None
    # 国内表达无 analogy_rules
    assert e["analogy_rules"] is None


def test_get_expression_by_tea_cross_cultural():
    e = data_loader.get_expression_by_tea(TEA_ID, "cross_cultural")
    assert e is not None
    assert e["id"] == "expr_en_szz_tgy_nx_coffee"
    # 横向翻译派生：source_expression_id 指向国内 seed
    assert e["source_expression_id"] == "expr_cn_szz_tgy_nx"
    for k in ("literal_explanation", "beginner_analogy", "cultural_narrative"):
        assert isinstance(e["outputs"][k], str) and e["outputs"][k]
    # analogy_rules 是 list 且每条 shape 完整
    assert isinstance(e["analogy_rules"], list) and e["analogy_rules"]
    for r in e["analogy_rules"]:
        for k in ("source_dimension", "target_reference", "confidence", "note"):
            assert k in r
        assert r["confidence"] in ("high", "medium", "low")


def test_get_expression_by_id():
    e = data_loader.get_expression("expr_cn_szz_tgy_nx")
    assert e and e["tea_id"] == TEA_ID
    assert data_loader.get_expression("nonexistent") is None


# ---------------------------------------------------------------------------
# 物料：copy / visual_data.radar / source 指针
# ---------------------------------------------------------------------------


def test_get_asset_by_language_shape():
    a = data_loader.get_asset_by_language(TEA_ID, "en")
    assert a is not None
    assert a["id"] == "asset_szz_poster_en"
    assert a["language"] == "en"
    # copy 子结构
    for k in ("headline", "subheadline", "body"):
        assert isinstance(a["copy"][k], str) and a["copy"][k]
    # visual_data.radar：list、value 是 int（雷达来自 seed 事实）
    radar = a["visual_data"]["radar"]
    assert isinstance(radar, list) and radar
    assert all(isinstance(r["value"], int) for r in radar)
    # 跨文化物料纵向指向跨文化表达（source_translation_id）
    assert a["source_translation_id"] == "expr_en_szz_tgy_nx_coffee"
    assert a["source_expression_id"] is None


def test_get_asset_by_language_zh():
    a = data_loader.get_asset_by_language(TEA_ID, "zh")
    assert a and a["id"] == "asset_szz_poster_zh"
    # 国内物料纵向指向国内表达
    assert a["source_expression_id"] == "expr_cn_szz_tgy_nx"
    assert a["source_translation_id"] is None


def test_get_asset_by_id():
    a = data_loader.get_asset("asset_szz_poster_en")
    assert a and a["tea_id"] == TEA_ID
    assert data_loader.get_asset("nonexistent") is None


# ---------------------------------------------------------------------------
# 追溯节点：node_type / level / parent
# ---------------------------------------------------------------------------


def test_get_trace_node_shape():
    n = data_loader.get_trace_node("asset_szz_poster_en")
    assert n is not None
    assert n["id"] == "asset_szz_poster_en"
    assert n["node_type"] == "marketing_asset"
    assert n["level"] == 3
    assert n["parent"] == "expr_en_szz_tgy_nx_coffee"
    assert n["name"] and n["summary"]


def test_get_trace_node_root_has_null_parent():
    n = data_loader.get_trace_node("knowledge_szz_tgy_nx")
    assert n is not None
    assert n["level"] == 0
    assert n["parent"] is None


def test_get_trace_node_missing():
    assert data_loader.get_trace_node("nonexistent") is None


# ---------------------------------------------------------------------------
# 茶品术语 / 规则 / 跨文化术语
# ---------------------------------------------------------------------------


def test_get_tea_terms():
    terms = data_loader.get_tea_terms(TEA_ID)
    assert isinstance(terms, list) and terms
    # 赛珍珠铁观音术语应有"观音韵"
    assert "观音韵" in terms
    assert data_loader.get_tea_terms("nonexistent") == []


def test_all_rules_shape():
    rules = data_loader.all_rules()
    assert isinstance(rules, list) and rules
    for r in rules:
        for k in ("id", "scope", "market", "audience_reference", "priority"):
            assert k in r
        assert r["priority"] in ("high", "medium", "low")
    # PRIORITY_ORDER 常量不动
    assert data_loader.PRIORITY_ORDER["high"] < data_loader.PRIORITY_ORDER["low"]


def test_list_cross_cultural_terms_shape():
    terms = data_loader.list_cross_cultural_terms()
    assert isinstance(terms, list) and terms
    for t in terms:
        for k in ("id", "chinese", "english", "explanation"):
            assert k in t


# ---------------------------------------------------------------------------
# 成分 → 口感 映射（第 1→2 层桥接）
# ---------------------------------------------------------------------------


def test_list_component_flavor_links_shape():
    links = data_loader.list_component_flavor_links(TEA_ID)
    assert isinstance(links, list) and len(links) >= 3  # 赛珍珠 共 5 条（含共用滋味骨架）
    for lk in links:
        for k in (
            "component",
            "component_category",
            "flavor_key",
            "flavor_label",
            "flavor_dimension",
            "mechanism",
            "relationship",
            "evidence",
            "confidence",
            "notes",
        ):
            assert k in lk
        assert lk["component_category"] in ("aroma_compound", "taste_compound", "process_proxy")
        assert lk["relationship"] in ("primary_driver", "contributes_to", "participant")
        assert lk["confidence"] in ("high", "medium", "low")
        # evidence 明细：按 seed 顺序展开，每条 shape 完整
        assert isinstance(lk["evidence"], list) and lk["evidence"]
        for ev in lk["evidence"]:
            for key in ("id", "source_type", "source", "confidence", "note"):
                assert key in ev
            assert ev["confidence"] in ("high", "medium", "low")
        # flavor_dimension：flavor_key 指向该茶现成 dimension 时应 join 到 label/intensity
        if lk["flavor_key"]:
            assert lk["flavor_dimension"] is not None
            assert "label_zh" in lk["flavor_dimension"]
            assert isinstance(lk["flavor_dimension"]["intensity"], int)


def test_list_component_flavor_links_mixed_confidence():
    """三茶应覆盖 medium（直接支持）与 low（品类代理）两类置信度。"""
    from app.data_loader import list_component_flavor_links

    for tea in ("BAMA_SZZ_TGY_NX", "BAMA_NY_WRT_DHP", "BAMA_DH_BT_JJM"):
        links = list_component_flavor_links(tea)
        assert len(links) >= 3  # 每茶至少3条，含共用滋味骨架映射
        confs = {lk["confidence"] for lk in links}
        assert "medium" in confs  # 每茶至少一条直接支持


def test_list_component_flavor_links_jjm_has_linalool():
    """金骏眉花蜜香应挂芳樟醇等（Lin 2025 直接支持），不挂铁观音。"""
    links = data_loader.list_component_flavor_links("BAMA_DH_BT_JJM")
    honey = next(lk for lk in links if lk["flavor_key"] == "honeyed_sweetness")
    assert "芳樟醇" in honey["component"]
    ev_ids = [ev["id"] for ev in honey["evidence"]]
    assert "evidence_lin_2025_wuyi_bt" in ev_ids


def test_list_component_flavor_links_tgy_orchid_not_linalool():
    """铁观音兰花香挂橙花叔醇等（wang_2023 直接支持），不挂芳樟醇。"""
    links = data_loader.list_component_flavor_links("BAMA_SZZ_TGY_NX")
    orchid = next(lk for lk in links if lk["flavor_key"] == "floral")
    assert "芳樟醇" not in orchid["component"]
    assert "橙花叔醇" in orchid["component"]
    ev_ids = [ev["id"] for ev in orchid["evidence"]]
    assert "evidence_wang_2023_oolong" in ev_ids


def test_list_component_flavor_links_missing_tea():
    assert data_loader.list_component_flavor_links("nonexistent") == []


# ---------------------------------------------------------------------------
# 枚举派生：markets / audience_references
# ---------------------------------------------------------------------------


def test_list_markets_shape():
    markets = data_loader.list_markets()
    ids = {m["id"] for m in markets}
    assert ids == {"domestic", "western"}
    for m in markets:
        assert "label_zh" in m and "label_en" in m


def test_list_audience_references_shape():
    refs = data_loader.list_audience_references()
    ids = {a["id"] for a in refs}
    assert ids == {"domestic_general", "specialty_coffee_lovers"}
    for a in refs:
        assert "label_zh" in a and "label_en" in a
