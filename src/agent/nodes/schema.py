from typing import List, Dict, Optional, Any, Literal

from pydantic import BaseModel, Field, field_validator

class IntentResult(BaseModel):
    """意图识别的强类型约束模型 (全局置信度版)"""

    reasoning: str = Field(
        description="思索过程：必须包含对多个意图之间关联性的分析，以及为什么给出一个统一的置信分数；并在末尾给出简要结论"
    )

    #  List 结构以支持多意图（与 §12.3、router.INTENT_TASK_MAPPING 对齐）
    intents: List[Literal[
        "profile_sync", "recipe_search", "inventory_check",
        "inventory_add",
        "dietary_advice", "shopping_list", "inventory_commit", "general_chat",
        "help", "out_of_scope", "recipe_adopt", "user_clarify",
    ]] = Field(description="识别出的意图列表（§12.3 目录）")

    # 全局置信度分数
    confidence: float = Field(
        ge=0, le=1,
        description="全局置信分数：代表模型对‘整套意图组合’及‘实体提取’准确性的综合评估"
    )

    entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="兼容迁移期的原始实体（路由层归一为 §12.2 slots）",
    )

    slots: Dict[str, Any] = Field(
        default_factory=dict,
        description="§12.2 全局槽位命名空间（可与 entities 并存；路由会与 entities 合并）",
    )

    missing_slots: List[str] = Field(
        default_factory=list,
        description="模型自检的本轮仍缺的槽位名（路由会与规则校验 §12.5 合并去重）",
    )

class Ingredient(BaseModel):
    """单项食材需求量 $R$"""
    name: str = Field(description="食材名称，如：五花肉")
    amount: float = Field(description="数值量，如：500.0。若为'适量'，请根据常识估算数值")
    unit: str = Field(description="标准单位，如：g, ml, 个, 勺")

class StructuredRecipe(BaseModel):
    """菜谱结构化解析结果"""
    title: str = Field(description="菜品名称")
    ingredients: List[Ingredient] = Field(description="结构化食材清单")
    steps: List[str] = Field(description="简化的烹饪步骤")


class TasteTags(BaseModel):
    like: List[str] = Field(default_factory=list, description="偏爱的口味或食材")
    dislike: List[str] = Field(default_factory=list, description="讨厌的口味或食材")

    @field_validator("like", "dislike", mode="before")
    @classmethod
    def _coerce_list_fields(cls, v: Any) -> List[str]:
        """LLM 偶发输出空串或非 list，避免整轮 MemoryKeeper 失败。"""
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            return [] if not s else [s]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []


class LongTermUpdates(BaseModel):
    allergens: List[str] = Field(default_factory=list, description="过敏原")
    medical_restrictions: List[str] = Field(default_factory=list, description="医疗/生理禁忌")
    dietary_target: Optional[str] = Field(default=None, description="长期膳食目标")
    taste_tags: TasteTags = Field(default_factory=TasteTags, description="口味偏好")
    cooking_habits: List[str] = Field(default_factory=list, description="烹饪习惯")


class ShortTermStates(BaseModel):
    conditions: List[str] = Field(default_factory=list, description="短期状态，如感冒需清淡")
    is_temporary: bool = Field(default=True, description="是否为临时状态")


class MemoryKeeperOutput(BaseModel):
    reasoning: str = Field(description="LLM 的推理过程摘要")
    has_update: bool = Field(description="是否提取到新的偏好信息")
    intent_type: str = Field(
        default="passive_extract",
        description="passive_extract 或 explicit_correction"
    )
    long_term_updates: Optional[LongTermUpdates] = Field(
        default=None, description="长期画像更新内容"
    )
    short_term_states: Optional[ShortTermStates] = Field(
        default=None, description="短期状态"
    )
