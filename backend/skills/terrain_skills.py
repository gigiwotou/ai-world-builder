"""
地形操作Skills - OpenClaw风格
"""
from . import Skill, create_skill, param, register_skill, SkillContext, SkillResult


def execute_explore_terrain(ctx: SkillContext) -> SkillResult:
    """探索地形"""
    p = ctx.params
    x = p.get("x", 0)
    y = p.get("y", 0)
    
    surrounding = ctx.world.get_surrounding_9(x, y)
    
    return SkillResult(
        success=True,
        data={"surrounding": surrounding},
        message=f"探索了 ({x},{y}) 周围的地形"
    )


def execute_set_terrain(ctx: SkillContext) -> SkillResult:
    """设置地形"""
    p = ctx.params
    x = p.get("x", 0)
    y = p.get("y", 0)
    terrain_type = p.get("terrain_type", "陆地")
    
    ctx.world.explore_terrain(x, y, terrain_type)
    
    return SkillResult(
        success=True,
        data={"x": x, "y": y, "terrain": terrain_type},
        message=f"设置 ({x},{y}) 为 {terrain_type}"
    )


def execute_get_terrain(ctx: SkillContext) -> SkillResult:
    """获取地形"""
    p = ctx.params
    x = p.get("x", 0)
    y = p.get("y", 0)
    
    terrain = ctx.world.get_terrain_at(x, y)
    
    return SkillResult(
        success=True,
        data={"x": x, "y": y, "terrain": terrain},
        message=f"({x},{y}) 是 {terrain}"
    )


skills = [
    create_skill(
        name="explore_terrain",
        description="探索某位置周围3x3区域的地形",
        aliases=["探索", "查看地形", "周围是什么", "地形探索"],
        parameters={
            "x": param("x", "integer", "中心X坐标", required=True),
            "y": param("y", "integer", "中心Y坐标", required=True)
        },
        examples=[
            "探索(0,0)周围的地形",
            "查看这里周围"
        ]
    ),
    
    create_skill(
        name="set_terrain",
        description="设置某位置的地形类型",
        aliases=["设置地形", "地形是", "改变地形"],
        parameters={
            "x": param("x", "integer", "X坐标", required=True),
            "y": param("y", "integer", "Y坐标", required=True),
            "terrain_type": param(
                "terrain_type",
                description="地形类型",
                required=True,
                enum=["陆地", "山川", "河流", "海洋", "森林", "沙漠", "草原"]
            )
        },
        examples=[
            "设置(5,5)为海洋",
            "让这块地变成山川"
        ]
    ),
    
    create_skill(
        name="get_terrain",
        description="获取某位置的地形类型",
        aliases=["地形", "这里是什么", "查询地形"],
        parameters={
            "x": param("x", "integer", "X坐标", required=True),
            "y": param("y", "integer", "Y坐标", required=True)
        },
        examples=[
            "查看(0,0)是什么地形",
            "这里是什么"
        ]
    )
]

skills[0].execute = execute_explore_terrain
skills[1].execute = execute_set_terrain
skills[2].execute = execute_get_terrain


def register():
    for skill in skills:
        register_skill(skill)
