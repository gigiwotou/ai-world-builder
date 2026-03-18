"""
行为执行Skills - OpenClaw风格
"""
from . import Skill, create_skill, param, register_skill, SkillContext, SkillResult


def execute_random_move(ctx: SkillContext) -> SkillResult:
    """随机移动"""
    import random
    
    entity_name = ctx.params.get("entity_name", "")
    entity = ctx.world.find_entity_by_name(entity_name) if entity_name else None
    
    if not entity:
        return SkillResult(success=False, error=f"找不到实体: {entity_name}")
    
    dx = random.choice([-1, 0, 1])
    dy = random.choice([-1, 0, 1])
    
    old_x, old_y = entity.x, entity.y
    entity.x += dx
    entity.y += dy
    
    return SkillResult(
        success=True,
        data={"x": entity.x, "y": entity.y, "dx": dx, "dy": dy},
        message=f"{entity.name} 随机移动到 ({entity.x},{entity.y})"
    )


def execute_explore(ctx: SkillContext) -> SkillResult:
    """向四周探索"""
    entity_name = ctx.params.get("entity_name", "")
    entity = ctx.world.find_entity_by_name(entity_name) if entity_name else None
    
    if not entity:
        return SkillResult(success=False, error=f"找不到实体: {entity_name}")
    
    # 探索周围地形
    if hasattr(ctx.world, 'get_nearby_unexplored'):
        unexplored = ctx.world.get_nearby_unexplored(entity.x, entity.y)
        if unexplored:
            ctx.world.explore_terrain(unexplored[0][0], unexplored[0][1], "陆地")
    
    # 随机移动一步
    import random
    dx = random.choice([-1, 0, 1])
    dy = random.choice([-1, 0, 1])
    entity.x += dx
    entity.y += dy
    
    return SkillResult(
        success=True,
        data={"new_pos": (entity.x, entity.y)},
        message=f"{entity.name} 探索了周围并移动到 ({entity.x},{entity.y})"
    )


def execute_grow(ctx: SkillContext) -> SkillResult:
    """生长"""
    entity_name = ctx.params.get("entity_name", "")
    entity = ctx.world.find_entity_by_name(entity_name) if entity_name else None
    
    if not entity:
        return SkillResult(success=False, error=f"找不到实体: {entity_name}")
    
    if entity.type != "plant":
        return SkillResult(success=False, error="只有植物才能生长")
    
    # 植物生长，随机扩散
    import random
    dx = random.choice([-1, 0, 1])
    dy = random.choice([-1, 0, 1])
    
    new_entity = ctx.world.create_entity(
        entity_type="plant",
        x=entity.x + dx,
        y=entity.y + dy,
        name=f"{entity.name}的幼苗",
        description="自然生长的植物"
    )
    
    return SkillResult(
        success=True,
        data={"parent": entity.to_dict(), "seedling": new_entity.to_dict() if new_entity else None},
        message=f"{entity.name} 生长了"
    )


skills = [
    create_skill(
        name="random_move",
        description="让实体随机移动一步",
        aliases=["随机移动", "漫步", "四处走动"],
        parameters={
            "entity_name": param("entity_name", description="实体名称", required=True)
        },
        examples=["让小明随机移动", "狼四处走动"]
    ),
    
    create_skill(
        name="explore",
        description="让实体向四周探索，同时探索周围地形",
        aliases=["探索", "四处探索", "巡视"],
        parameters={
            "entity_name": param("entity_name", description="实体名称", required=True)
        },
        examples=["让小明向四周探索", "狼四处探索领地"]
    ),
    
    create_skill(
        name="grow",
        description="让植物生长（扩散）",
        aliases=["生长", "繁殖", "扩散"],
        parameters={
            "entity_name": param("entity_name", description="植物名称", required=True)
        },
        examples=["让这棵树生长", "草地繁殖"]
    )
]

skills[0].execute = execute_random_move
skills[1].execute = execute_explore
skills[2].execute = execute_grow


def register():
    for skill in skills:
        register_skill(skill)
