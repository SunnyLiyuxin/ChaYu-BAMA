"""markets / audience-references 枚举接口（已从 P2 fallback 升级为真实列表）。

从 demo_routes 派生，附双语 label。断言结构与契约（非 fallback）。
"""


def test_markets(client):
    resp = client.get("/api/markets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["meta"]["fallback"] is False  # 已升级，不再是 fallback
    markets = body["data"]
    assert isinstance(markets, list) and markets
    ids = [m["id"] for m in markets]
    assert "domestic" in ids and "western" in ids
    for m in markets:
        for k in ("id", "label_zh", "label_en"):
            assert k in m and m[k]


def test_audience_references(client):
    resp = client.get("/api/audience-references")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["fallback"] is False
    refs = body["data"]
    assert isinstance(refs, list) and refs
    ids = [a["id"] for a in refs]
    assert "domestic_general" in ids
    assert "specialty_coffee_lovers" in ids
    for a in refs:
        for k in ("id", "label_zh", "label_en"):
            assert k in a and a[k]


def test_markets_deduped(client):
    """市场列表应去重（demo_routes 多条同 market 只出现一次）。"""
    markets = client.get("/api/markets").json()["data"]
    ids = [m["id"] for m in markets]
    assert len(ids) == len(set(ids))
