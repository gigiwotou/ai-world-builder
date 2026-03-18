"""
分析Skills - OpenClaw风格
"""
from . import Skill, create_skill, param, register_skill, SkillContext, SkillResult


def execute_analyze_entity(ctx: SkillContext) -> SkillResult:
    """分析实体"""
    entity_name = ctx.params.get("entity_name", "")
    entity = ctx.world.find_entity_by_name(entity_name) if entity_name else None
    
    if not entity:
        return SkillResult(success=False, error=f"找不到实体: {entity_name}")
    
    return SkillResult(
        success=True,
        data=entity.to_dict(),
        message=f"分析了 {entity.name}: 类型={entity.type}, 位置=({entity.x},{entity.y}), 行为={entity.behavior}"
    )


def execute_get_entities(ctx: SkillContext) -> SkillResult:
    """获取实体列表"""
    filter_type = ctx.params.get("type", "")
    
    entities = ctx.world.entities.values()
    
    if filter_type:
        entities = [e for e in entities if e.type == filter_type]
    
    entity_list = [e.to_dict() for e in entities]
    
    return SkillResult(
        success=True,
        data={"entities": entity_list, "count": len(entity_list)},
        message=f"世界中有 {len(entity_list)} 个实体"
    )


def execute_find_entity(ctx: SkillContext) -> SkillResult:
    """查找实体"""
    entity_name = ctx.params.get("entity_name", "")
    
    entity = ctx.world.find_entity_by_name(entity_name) if entity_name else None
    
    if not entity:
        return SkillResult(
            success=False,
            error=f"找不到实体: {entity_name}"
        )
    
    return SkillResult(
        success=True,
        data=entity.to_dict(),
        message=f"找到 {entity.name} 于 ({entity.x},{entity.y})"
    )


def execute_world_status(ctx: SkillContext) -> SkillResult:
    """获取世界状态"""
    state = ctx.world.get_state()
    
    return SkillResult(
        success=True,
        data=state,
        message=f"世界状态: T={state['tick']}, 实体数={len(state['entities'])}"
    )


skills = [
    create_skill(
        name="analyze_entity",
        description="分析指定实体的详细信息",
        aliases=["分析", "查看实体", "实体信息"],
        parameters={
            "entity_name": param("entity_name", description="实体名称", required=True)
        },
        examples=["分析小明", "查看狼的信息"]
    ),
    
    create_skill(
        name="get_entities",
        description="获取世界上所有实体或特定类型的实体",
        aliases=["实体列表", "查看实体", "有哪些实体"],
        parameters={
            "type": param("type", description="实体类型过滤", default="", enum=["", "creature", "plant", "building", "water", "fire"])
        },
        examples=["查看所有生物", "获取植物列表"]
    ),
    
    create_skill(
        name="find_entity",
        description="查找某个实体",
        aliases=["查找实体", "找找看"],
        parameters={
            "entity_name": param("entity_name", description="实体名称", required=True)
        },
        examples=["找找小明在哪", "查找狼"]
    ),
    
    create_skill(
        name="world_status",
        description="获取当前世界的状态",
        aliases=["世界状态", "状态", "当前情况"],
        parameters={},
        examples=["世界现在什么情况", "状态如何"]
    )
]

skills[0].execute = execute_analyze_entity
skills[1].execute = execute_get_entities
skills[2].execute = execute_find_entity
skills[3].execute = execute_world_status


def register():
    for skill in skills:
        register_skill(skill)
