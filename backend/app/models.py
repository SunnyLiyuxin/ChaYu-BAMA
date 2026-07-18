"""SQLAlchemy ORM 模型：与 backend/data/seeds/*.yaml 一一对应。

设计约定：
- 嵌套结构（origin/process/story、dimensions 列表、outputs/analogy_rules、
  copy/visual_data）统一用 JSON 列，不为每个嵌套子结构建关系表。
- 主键用 seed 里的可读字符串 id；tea_knowledge / flavor_profiles 没有 id
  字段，按其天然唯一键（tea_id / profile_id）作主键。
- 字段不齐（如 shelf_life_months 仅部分茶有）一律 nullable=True，不在
  schema 层硬约束 —— seed 是事实源，表如实反映。
- expressions / assets 单独建表（非塞进 generated_outputs），字段差异大、
  便于测试断言。generated_outputs 存 LLM 生成结果缓存（output_store 写入）。
- tea_terms 在 seed 里是 dict（tea_id → [term...]），展开成独立表行。
- trace_links 如实反映 seed 的扁平 trace_nodes + parent 结构，不用边表。

灌表逻辑见 scripts/seed.py。
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database import Base


class Tea(Base):
    __tablename__ = "teas"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String)
    origin: Mapped[str | None] = mapped_column(String)
    brand: Mapped[str | None] = mapped_column(String)
    demo_available: Mapped[bool | None] = mapped_column(Boolean)
    series: Mapped[str | None] = mapped_column(String)
    tea_class: Mapped[str | None] = mapped_column(String)
    product_archetype: Mapped[str | None] = mapped_column(String)
    demo_sku: Mapped[str | None] = mapped_column(String)
    grade: Mapped[str | None] = mapped_column(String)
    shelf_life_months: Mapped[int | None] = mapped_column(Integer)  # 牛一无此字段
    shelf_life: Mapped[str | None] = mapped_column(String)  # 仅牛一有
    standard: Mapped[str | None] = mapped_column(String)
    brand_sensory: Mapped[str | None] = mapped_column(String)
    cultural_core: Mapped[str | None] = mapped_column(String)
    core_process: Mapped[str | None] = mapped_column(String)
    brew_method_id: Mapped[str | None] = mapped_column(String)
    region_note: Mapped[str | None] = mapped_column(String)  # 赛珍珠无此字段


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    claim: Mapped[str | None] = mapped_column(String)
    source_type: Mapped[str | None] = mapped_column(String)
    source: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[str | None] = mapped_column(String)
    evidence_level: Mapped[str | None] = mapped_column(String)
    collected_by: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)


class TeaKnowledge(Base):
    """每款茶一条知识卡片，以 tea_id 作主键（天然唯一）。"""

    __tablename__ = "tea_knowledge"

    tea_id: Mapped[str] = mapped_column(
        String, ForeignKey("teas.id"), primary_key=True
    )
    origin: Mapped[dict | None] = mapped_column(JSON)  # region/terroir/source_note
    process: Mapped[dict | None] = mapped_column(JSON)  # name/steps[]/key_technique/brand_claim
    story: Mapped[dict | None] = mapped_column(JSON)  # title/content/cultural_core
    evidence_ids: Mapped[list | None] = mapped_column(JSON)  # list[str]


class FlavorProfile(Base):
    __tablename__ = "flavor_profiles"

    profile_id: Mapped[str] = mapped_column(String, primary_key=True)
    tea_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teas.id"), index=True
    )
    dimensions: Mapped[list | None] = mapped_column(JSON)  # list[dict]
    component_notes: Mapped[list | None] = mapped_column(JSON)  # list[dict]


class DemoRoute(Base):
    __tablename__ = "demo_routes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tea_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teas.id"), index=True
    )
    tea_name: Mapped[str | None] = mapped_column(String)
    market: Mapped[str | None] = mapped_column(String)
    target_language: Mapped[str | None] = mapped_column(String)
    audience_reference: Mapped[str | None] = mapped_column(String)
    asset_type: Mapped[str | None] = mapped_column(String)
    enabled: Mapped[bool | None] = mapped_column(Boolean)
    description: Mapped[str | None] = mapped_column(String)


class ComponentFlavorLink(Base):
    """成分 → 口感 映射：第 1→2 层桥接关系的物化，不进纵向追溯链。

    把散落在 component_notes / dimensions.description / evidence.notes 里的
    "成分→口感"对应结构化成行。flavor_key 指向该茶 flavor_profiles.dimensions[].key
    （茶级归属、因茶而异）；evidence_ids 指向 evidence_sources 已有条目，不新造证据。
    """

    __tablename__ = "component_flavor_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tea_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teas.id"), index=True
    )
    component: Mapped[str | None] = mapped_column(String)
    component_category: Mapped[str | None] = mapped_column(String)
    flavor_key: Mapped[str | None] = mapped_column(String, index=True)
    flavor_label: Mapped[str | None] = mapped_column(String)
    mechanism: Mapped[str | None] = mapped_column(String)
    relationship: Mapped[str | None] = mapped_column(String)
    evidence_ids: Mapped[list | None] = mapped_column(JSON)  # list[str]
    confidence: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)


class GenerationRule(Base):
    __tablename__ = "generation_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str | None] = mapped_column(String)
    market: Mapped[str | None] = mapped_column(String)
    audience_reference: Mapped[str | None] = mapped_column(String)
    priority: Mapped[str | None] = mapped_column(String)
    instruction: Mapped[str | None] = mapped_column(String)
    negative_example: Mapped[str | None] = mapped_column(String)
    positive_example: Mapped[str | None] = mapped_column(String)
    enabled: Mapped[bool | None] = mapped_column(Boolean)
    trigger_terms: Mapped[list | None] = mapped_column(JSON)  # list[str]


class CrossCulturalTerm(Base):
    __tablename__ = "cross_cultural_terms"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    chinese: Mapped[str | None] = mapped_column(String)
    english: Mapped[str | None] = mapped_column(String)
    not_recommended: Mapped[str | None] = mapped_column(String)  # 不推荐的译法
    explanation: Mapped[str | None] = mapped_column(String)
    analogy_strategy: Mapped[str | None] = mapped_column(String)
    preserve_strategy: Mapped[str | None] = mapped_column(String)
    evidence_ids: Mapped[list | None] = mapped_column(JSON)  # list[str]


class ExpressionStrategy(Base):
    __tablename__ = "expression_strategies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str | None] = mapped_column(String)
    market: Mapped[str | None] = mapped_column(String)
    audience_reference: Mapped[str | None] = mapped_column(String)
    instruction: Mapped[str | None] = mapped_column(String)
    output_slots: Mapped[list | None] = mapped_column(JSON)  # list[str]


class Expression(Base):
    """预置表达（seed mock_outputs.expressions）。"""

    __tablename__ = "expressions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tea_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teas.id"), index=True
    )
    expression_type: Mapped[str | None] = mapped_column(String)
    strategy_id: Mapped[str | None] = mapped_column(String)
    target_language: Mapped[str | None] = mapped_column(String)  # 国内表达无
    market: Mapped[str | None] = mapped_column(String)  # 国内表达无
    audience_reference: Mapped[str | None] = mapped_column(String)  # 国内表达无
    source_profile_id: Mapped[str | None] = mapped_column(String)
    source_expression_id: Mapped[str | None] = mapped_column(String)  # 国内表达为 null
    trace_id: Mapped[str | None] = mapped_column(String)
    audience: Mapped[dict | None] = mapped_column(JSON)  # age_group/...
    outputs: Mapped[dict | None] = mapped_column(JSON)  # story_style/... 或 literal_explanation/...
    analogy_rules: Mapped[list | None] = mapped_column(JSON)  # 仅跨文化有


class Asset(Base):
    """预置物料（seed mock_outputs.assets）。"""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tea_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teas.id"), index=True
    )
    asset_type: Mapped[str | None] = mapped_column(String)
    platform: Mapped[str | None] = mapped_column(String)
    language: Mapped[str | None] = mapped_column(String)
    image_prompt: Mapped[str | None] = mapped_column(String)
    source_expression_id: Mapped[str | None] = mapped_column(String)  # 国内链
    source_translation_id: Mapped[str | None] = mapped_column(String)  # 跨文化链
    trace_id: Mapped[str | None] = mapped_column(String)
    copy: Mapped[dict | None] = mapped_column(JSON)  # headline/subheadline/body
    visual_data: Mapped[dict | None] = mapped_column(JSON)  # radar list


class TraceLink(Base):
    """扁平 trace_nodes + parent 结构（非边表）。横向翻译关系不在此表。"""

    __tablename__ = "trace_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    node_type: Mapped[str | None] = mapped_column(String)
    level: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(String)
    parent: Mapped[str | None] = mapped_column(String, index=True)  # 根节点为 null


class TeaTerm(Base):
    """tea_terms 展开：seed 里是 dict(tea_id → [term...])，这里每行一条。"""

    __tablename__ = "tea_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tea_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teas.id"), index=True
    )
    term: Mapped[str | None] = mapped_column(String, index=True)


class QuarantineItem(Base):
    """高风险知识隔离清单（§23）：禁止对外发布的内容，取得可靠证据后可重新启用。"""

    __tablename__ = "quarantine_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    content: Mapped[str | None] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(String)
    re_enable_condition: Mapped[str | None] = mapped_column(String)
    review_status: Mapped[str | None] = mapped_column(String)  # quarantine / verified
    retrievable_for_external_generation: Mapped[bool | None] = mapped_column(Boolean)
    required_evidence: Mapped[list | None] = mapped_column(JSON)  # list[str]
    review_owner: Mapped[str | None] = mapped_column(String)


class CreativeAnalogy(Base):
    """创意类比候选池（§20）：创意可被保存、筛选和测试，验证前禁止自动进入外部物料。"""

    __tablename__ = "creative_analogies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tea_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teas.id"), index=True
    )
    reference_category: Mapped[str | None] = mapped_column(String)  # coffee / wine / spirits / perfume
    reference_object: Mapped[str | None] = mapped_column(String)
    shared_sensory_cues: Mapped[list | None] = mapped_column(JSON)  # list[str]
    mapping_type: Mapped[str | None] = mapped_column(String)  # creative_hypothesis / approved_narrative_bridge
    scientific_equivalence: Mapped[bool | None] = mapped_column(Boolean)
    validation_status: Mapped[str | None] = mapped_column(String)  # untested / blinded / audience_tested / approved
    requires_blind_tasting: Mapped[bool | None] = mapped_column(Boolean)
    requires_audience_test: Mapped[bool | None] = mapped_column(Boolean)
    allowed_use: Mapped[str | None] = mapped_column(String)  # internal_ideation_only / approved_external
    risk_notes: Mapped[str | None] = mapped_column(String)
    approved_sensory_cues: Mapped[list | None] = mapped_column(JSON)  # 可借用的部分
    must_avoid: Mapped[list | None] = mapped_column(JSON)  # 必须避免的表述


class GeneratedOutput(Base):
    """LLM 生成结果缓存表（output_store 写入，按 input_hash 去重复用）。"""

    __tablename__ = "generated_outputs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    output_type: Mapped[str | None] = mapped_column(String)
    tea_id: Mapped[str | None] = mapped_column(String)
    route_id: Mapped[str | None] = mapped_column(String)
    input_hash: Mapped[str | None] = mapped_column(String)
    content_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[str | None] = mapped_column(String)  # ISO 时间戳，seed.py 灌时写入
