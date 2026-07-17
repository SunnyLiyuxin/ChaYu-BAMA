"""前端中文枚举 → 后端内部英文值的映射表。

前端 UI 用中文枚举（"小红书""国风"等），后端日志 / 响应回显 / 缓存键
统一用英文内部值。映射集中在本文件一处，前端加枚举时后端改一处即可，
规则不进超长 prompt（CLAUDE.md 协作约束）。

设计：
- 已知枚举值查表翻成内部值；表内同时收英文内部值自身（自映射），
  让"前端已传英文内部值"也能原样通过，不误判为未知值。
- 未知值（不在表内）不 422、不静默丢弃——Demo 友好，记一条 warning
  后原样透传，由 LLM / 下游自行消化。这避免前端临时新增枚举时后端阻断。

仅 marketing-asset 的 platform / style / content_theme 用到，domestic-expression /
cross-cultural-expression 的 tone / length / task_type / flavor_reference 用到。
表达接口的 style 是后端自有枚举（store_sales 等），不走本表。time_node 不映射
（自由文本，原样透传进 prompt）。
"""

import logging

logger = logging.getLogger("app.enum_map")

# 投放平台：前端中文枚举 → 内部英文值。
# 国内三平台 + 海外三平台各一组。
# 抖音 ≠ TikTok：同一 app，但国内投放偏下沉、海外偏年轻，让 LLM 区别对待，不合并。
PLATFORM_ALIASES: dict[str, str] = {
    # 国内
    "小红书": "xiaohongshu",
    "抖音": "douyin",
    "微信视频号": "wechat_channels",
    # 海外
    "Instagram": "instagram",
    "TikTok": "tiktok",
    "YouTube": "youtube",
}

# 物料风格：前端中文枚举 → 内部英文值。
# 注意：marketing-asset.style 与生图接口的 style（fresh / business）是两套维度——
# 物料风格管文案调性（年轻 / 商务 / 国风），生图风格管画面光照色调。
MARKETING_STYLE_ALIASES: dict[str, str] = {
    "年轻": "youthful",
    "商务": "business",
    "国风": "guofeng",
    # 英文内部值自映射，便于前端已传英文时原样通过
    "youthful": "youthful",
    "business": "business",
    "guofeng": "guofeng",
}

# 表达语气（tone）：前端中文枚举 → 内部英文值。
# 国内链 + 跨文化链共用同一套语气维度。
EXPRESSION_TONE_ALIASES: dict[str, str] = {
    "温润亲切": "warm",
    "专业严谨": "professional",
    "诗意古风": "poetic",
    "活泼年轻": "lively",
    "商务克制": "restrained_business",
    "warm": "warm",
    "professional": "professional",
    "poetic": "poetic",
    "lively": "lively",
    "restrained_business": "restrained_business",
}

# 表达篇幅（length）：前端"短（80字内）/中（80-200字）/长（200字以上）"
# → 内部值 short / medium / long。
EXPRESSION_LENGTH_ALIASES: dict[str, str] = {
    "短（80字内）": "short",
    "中（80-200字）": "medium",
    "长（200字以上）": "long",
    "short": "short",
    "medium": "medium",
    "long": "long",
}

# 物料内容主题：前端 value 已是英文短横线（tea-marketing / tea-culture），
# 后端统一成下划线（tea_marketing / tea_culture）作内部值，避免连字符在
# 标识符 / 缓存键里尴尬。映射收两套形式 + 下划线自映射。
CONTENT_THEME_ALIASES: dict[str, str] = {
    "tea-marketing": "tea_marketing",
    "tea-culture": "tea_culture",
    "tea_marketing": "tea_marketing",
    "tea_culture": "tea_culture",
}

# 表达任务类型（task_type）：前端 value 是英文短横线枚举。
# 后端统一成下划线内部值，并收两套形式自映射。
# component-to-flavor = 成分→风味（把成分翻译成消费者听得懂的风味）
# vague-to-vivid = 模糊→形象描述（抽象表述转具象画面）
TASK_TYPE_ALIASES: dict[str, str] = {
    "component-to-flavor": "component_to_flavor",
    "vague-to-vivid": "vague_to_vivid",
    "component_to_flavor": "component_to_flavor",
    "vague_to_vivid": "vague_to_vivid",
}

# 风味参照体系（flavor_reference）：前端 value 已是英文（coffee / wine / none），
# 无需翻译，但走同一套"未知值透传 + 自映射"通路，保证口径统一。
# coffee = 参考咖啡风味体系；wine = 参考红酒风味体系；none = 纯中式茶文化语境。
FLAVOR_REFERENCE_ALIASES: dict[str, str] = {
    "coffee": "coffee",
    "wine": "wine",
    "none": "none",
}


def _resolve(value: str | None, aliases: dict[str, str], field_name: str) -> str | None:
    """通用映射：查表命中返内部值，未命中 warn 后原样透传。

    None 透传 None（未选）。空串视为未选，透传 None，避免空串进 prompt。
    """
    if value is None or value == "":
        return None
    mapped = aliases.get(value)
    if mapped is not None:
        return mapped
    # 未知值：不阻断，记 warning 后原样透传（让下游 LLM / 响应回显自行处理）
    logger.warning("未知 %s 枚举值原样透传：%r", field_name, value)
    return value


def resolve_platform(platform: str | None) -> str | None:
    """前端平台枚举 → 内部英文值（小红书 → xiaohongshu 等）。未知值透传。"""
    return _resolve(platform, PLATFORM_ALIASES, "platform")


def resolve_marketing_style(style: str | None) -> str | None:
    """前端物料风格枚举 → 内部英文值（国风 → guofeng 等）。未知值透传。"""
    return _resolve(style, MARKETING_STYLE_ALIASES, "marketing-asset style")


def resolve_expression_tone(tone: str | None) -> str | None:
    """前端语气枚举 → 内部英文值（温润亲切 → warm 等）。未知值透传。"""
    return _resolve(tone, EXPRESSION_TONE_ALIASES, "expression tone")


def resolve_expression_length(length: str | None) -> str | None:
    """前端篇幅枚举 → 内部英文值（短（80字内）→ short 等）。未知值透传。"""
    return _resolve(length, EXPRESSION_LENGTH_ALIASES, "expression length")


def resolve_content_theme(content_theme: str | None) -> str | None:
    """前端内容主题 → 内部值（tea-marketing → tea_marketing，连字符转下划线）。未知值透传。"""
    return _resolve(content_theme, CONTENT_THEME_ALIASES, "content_theme")


def resolve_task_type(task_type: str | None) -> str | None:
    """前端任务类型 → 内部值（component-to-flavor → component_to_flavor，连字符转下划线）。未知值透传。"""
    return _resolve(task_type, TASK_TYPE_ALIASES, "task_type")


def resolve_flavor_reference(flavor_reference: str | None) -> str | None:
    """风味参照体系 → 内部值（coffee/wine/none 自映射）。未知值透传。"""
    return _resolve(flavor_reference, FLAVOR_REFERENCE_ALIASES, "flavor_reference")
