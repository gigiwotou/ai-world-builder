"""
移动规则Skills - OpenClaw风格
"""
from . import Skill, create_skill, param, register_skill, SkillContext, SkillResult


def execute_get_move_rules(ctx: SkillContext) -> SkillResult:
    """获取实体的移动规则"""
    entity_type = ctx.params.get("entity_type", "creature")
    skills_list = ctx.params.get("skills", "")
    
    # 使用默认规则
    default_rules = {
        "creature": ["陆地", "山川", "河流", "海洋"],
        "plant": ["陆地"],
        "water": ["河流", "海洋"],
        "fire": ["陆地", "山川", "河流", "海洋"],
        "building": ["陆地"],
        "resource": ["陆地"]
    }
    
    rules = default_rules.get(entity_type, ["陆地", "山川"])
    
    return SkillResult(
        success=True,
        data={"entity_type": entity_type, "allowed_terrains": rules},
        message=f"{entity_type} 可以移动到: {', '.join(rules)}"
    )


def execute_can_move_to(ctx: SkillContext) -> SkillResult:
    """检查实体是否能移动到某位置"""
    entity_name = ctx.params.get("entity_name", "")
    x = ctx.params.get("x", 0)
    y = ctx.params.get("y", 0)
    
    entity = ctx.world.find_entity_by_name(entity_name) if entity_name else None
    
    if not entity:
        return SkillResult(success=False, error=f"找不到实体: {entity_name}")
    
    # 获取地形
    terrain = ctx.world.get_terrain_at(x, y) if hasattr(ctx.world, 'get_terrain_at') else "陆地"
    
    # 检查规则
    allowed = ctx.world.get_move_rules_for_entity(entity.type, entity.skills) if hasattr(ctx.world, 'get_move_rules_for_entity') else ["陆地", "山川"]
    
    can_move = terrain in allowed or terrain == "未探索"
    
    return SkillResult(
        success=True,
        data={
            "entity": entity.name,
            "target": (x, y),
            "terrain": terrain,
            "can_move": can_move,
            "allowed": allowed
        },
        message=f"{entity.name} {'可以' if can_move else '不能'}移动到 ({x},{y})，地形是{terrain}"
    )


def execute_set_move_rules(ctx: SkillContext) -> SkillResult:
    """设置实体的移动规则"""
    # 这个Skill允许LLM更新默认规则
    entity_type = ctx.params.get("entity_type", "")
    allowed = ctx.params.get("allowed_terrains", [])
    
    if not entity_type or not allowed:
        return SkillResult(
            success=False,
            error="需要 entity_type 和 allowed_terrains"
        )
    
    # 注意：这个只返回提示，实际规则存储需要扩展
    return SkillResult(
        success=True,
        message=f"提示：{entity_type} 的移动规则建议设置为: {', '.join(allowed)}"
    )


skills = [
    create_skill(
        name="get_move_rules",
        description="获取某类型实体的移动规则（可以在哪些地形移动）",
        aliases=["移动规则", "能去哪", "地形限制"],
        parameters={
            "entity_type": param("entity_type", description="实体类型", default="creature", enum=["creature", "plant", "water", "fire", "building", "resource"]),
            "skills": param("skills", description="实体技能列表")
        },
        examples=["获取生物的移动规则", "人类能去哪"]
    ),
    
    create_skill(
        name="can_move_to",
        description="检查实体是否能移动到某位置",
        aliases=["能否移动", "能去吗"],
        parameters={
            "entity_name": param("entity_name", description="实体名称", required=True),
            "x": param("x", "integer", "目标X坐标", required=True),
            "y": param("y", "integer", "目标Y坐标", required=True)
        },
        examples=["小明能去(5,5)吗", "狼可以去海洋吗"]
    ),
    
    create_skill(
        name="set_move_rules",
        description="设置某类型实体的移动规则",
        aliases=["更新规则", "修改移动规则"],
        parameters={
            "entity_type": param("entity_type", description="实体类型", required=True),
            "allowed_terrains": param("allowed_terrains", description="允许的地形列表", required=True)
        },
        examples=["设置鱼类只能在水中", "更新飞行生物规则"]
    )
]

skills[0].execute = execute_get_move_rules
skills[1].execute = execute_can_move_to
skills[2].execute = execute_set_move_rules


def register():
    for skill in skills:
        register_skill(skill)
