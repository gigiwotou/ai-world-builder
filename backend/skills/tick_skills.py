"""
世界推进Skills - OpenClaw风格
"""
from . import Skill, create_skill, param, register_skill, SkillContext, SkillResult


def execute_tick(ctx: SkillContext) -> SkillResult:
    """推进世界一个时间单位"""
    ctx.world.tick_world()
    
    state = ctx.world.get_state()
    
    return SkillResult(
        success=True,
        data={"tick": state["tick"], "entity_count": len(state["entities"])},
        message=f"世界推进到 T={state['tick']}"
    )


def execute_auto_play(ctx: SkillContext) -> SkillResult:
    """自动运行多个Tick"""
    ticks = ctx.params.get("ticks", 5)
    
    results = []
    for i in range(min(ticks, 20)):  # 最多20个
        ctx.world.tick_world()
        state = ctx.world.get_state()
        results.append({
            "tick": state["tick"],
            "entities": len(state["entities"])
        })
        
        # 每个creature探索周围
        for entity in state["entities"]:
            if entity["type"] == "creature" and hasattr(ctx.world, 'get_nearby_unexplored'):
                unexplored = ctx.world.get_nearby_unexplored(entity["x"], entity["y"])
                if unexplored:
                    ctx.world.explore_terrain(unexplored[0][0], unexplored[0][1], "陆地")
    
    return SkillResult(
        success=True,
        data={"ticks_executed": len(results), "final_tick": results[-1]["tick"] if results else 0},
        message=f"执行了 {len(results)} 个时间单位，当前 T={results[-1]['tick'] if results else 0}"
    )


def execute_reset_world(ctx: SkillContext) -> SkillResult:
    """重置世界"""
    confirm = ctx.params.get("confirm", False)
    
    if not confirm:
        return SkillResult(
            success=False,
            error="需要 confirm=true 才能重置世界"
        )
    
    # 清空所有实体
    entity_ids = list(ctx.world.entities.keys())
    for eid in entity_ids:
        ctx.world.delete_entity(eid)
    
    ctx.world.tick = 0
    
    return SkillResult(
        success=True,
        message="世界已重置"
    )


skills = [
    create_skill(
        name="tick",
        description="推进世界一个时间单位",
        aliases=["时间推进", "过一秒", "经过"],
        parameters={},
        examples=["时间推进一秒", "过一会儿"]
    ),
    
    create_skill(
        name="auto_play",
        description="自动运行多个时间单位，让世界运转",
        aliases=["自动运行", "快进", "推进"],
        parameters={
            "ticks": param("ticks", "integer", "运行多少个时间单位", default=5)
        },
        examples=["快进10秒", "自动运行20个时间"]
    ),
    
    create_skill(
        name="reset_world",
        description="重置世界（清空所有实体，时间归零）",
        aliases=["重置", "清空世界"],
        parameters={
            "confirm": param("confirm", "boolean", "确认重置", default=False)
        },
        examples=["重置世界"]
    )
]

skills[0].execute = execute_tick
skills[1].execute = execute_auto_play
skills[2].execute = execute_reset_world


def register():
    for skill in skills:
        register_skill(skill)
