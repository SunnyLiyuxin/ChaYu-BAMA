"""前端中文枚举 → 后端内部英文值映射（app.enum_map）测试。

验证：
- 已知枚举翻成内部值
- None / 空串透传 None（不进 prompt、不进缓存键）
- 未知值不 422、原样透传 + 记 warning
- 抖音 ≠ TikTok（同一 app 但国内/海外两套内部值，不合并）
- 英文内部值自映射（前端已传英文时原样通过，不误判未知）
"""

from app import enum_map


# ---------------------------------------------------------------------------
# platform
# ---------------------------------------------------------------------------


def test_platform_domestic_aliases():
    assert enum_map.resolve_platform("小红书") == "xiaohongshu"
    assert enum_map.resolve_platform("抖音") == "douyin"
    assert enum_map.resolve_platform("微信视频号") == "wechat_channels"


def test_platform_overseas_aliases():
    assert enum_map.resolve_platform("Instagram") == "instagram"
    assert enum_map.resolve_platform("TikTok") == "tiktok"
    assert enum_map.resolve_platform("YouTube") == "youtube"


def test_platform_douyin_neq_tiktok():
    """抖音与 TikTok 映射到不同内部值，不合并。"""
    assert enum_map.resolve_platform("抖音") != enum_map.resolve_platform("TikTok")
    assert enum_map.resolve_platform("抖音") == "douyin"
    assert enum_map.resolve_platform("TikTok") == "tiktok"


def test_platform_none_and_empty():
    assert enum_map.resolve_platform(None) is None
    assert enum_map.resolve_platform("") is None


def test_platform_unknown_value_passthrough(caplog):
    """未知平台值不阻断：原样透传 + 记 warning。"""
    import logging

    with caplog.at_level(logging.WARNING, logger="app.enum_map"):
        result = enum_map.resolve_platform("微博")
    assert result == "微博", "未知值应原样透传，不丢弃"
    assert any("platform" in r.message for r in caplog.records), "应记 warning"


def test_platform_internal_value_self_mapped():
    """前端已传内部英文值时原样通过（自映射），不误判为未知。"""
    assert enum_map.resolve_platform("tiktok") == "tiktok"
    assert enum_map.resolve_platform("xiaohongshu") == "xiaohongshu"


# ---------------------------------------------------------------------------
# marketing-asset style（≠ 生图 style fresh/business）
# ---------------------------------------------------------------------------


def test_marketing_style_aliases():
    assert enum_map.resolve_marketing_style("年轻") == "youthful"
    assert enum_map.resolve_marketing_style("商务") == "business"
    assert enum_map.resolve_marketing_style("国风") == "guofeng"


def test_marketing_style_none_and_empty():
    assert enum_map.resolve_marketing_style(None) is None
    assert enum_map.resolve_marketing_style("") is None


def test_marketing_style_unknown_value_passthrough(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="app.enum_map"):
        result = enum_map.resolve_marketing_style("赛博朋克")
    assert result == "赛博朋克"
    assert any("marketing-asset style" in r.message for r in caplog.records)


def test_marketing_style_internal_value_self_mapped():
    """英文内部值自映射：前端传 youthful 原样通过。"""
    assert enum_map.resolve_marketing_style("youthful") == "youthful"
    assert enum_map.resolve_marketing_style("guofeng") == "guofeng"
