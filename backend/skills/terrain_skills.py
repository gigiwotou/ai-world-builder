"""
地形探索Skill
"""
from . import Skill, create_skill, register_skill


def execute_explore_terrain(world, params):
    x = params.get("x", 0)
    y = params.get("y", 0)
    
    surrounding = world.get_surrounding_9(x, y)
    return {"success": True, "surrounding": surrounding}


def execute_set_terrain(world, params):
    x = params.get("x", 0)
    y = params.get("y", 0)
    terrain_type = params.get("terrain_type", "陆地")
    
    world.explore_terrain(x, y, terrain_type)
    return {"success": True, "x": x, "y": y, "terrain": terrain_type}


def execute_get_terrain(world, params):
    x = params.get("x", 0)
    y = params.get("y", 0)
    terrain = world.get_terrain_at(x, y)
    return {"success": True, "x": x, "y": y, "terrain": terrain}


skills = [
    create_skill(
        name="explore_terrain",
        description="探索地形，决定某区域的地形类型",
        aliases=["探索", "查看地形", "周围是什么"],
        parameters={
            "x": 0,
            "y": 0
        }
    ),
    create_skill(
        name="set_terrain",
        description="设置某位置的地形类型",
        aliases=["设置地形", "地形是"],
        parameters={
            "x": 0,
            "y": 0,
            "terrain_type": "陆地"
        }
    ),
    create_skill(
        name="get_terrain",
        description="获取某位置的地形",
        aliases=["地形", "这里是什么"],
        parameters={
            "x": 0,
            "y": 0
        }
    )
]

skills[0].execute = execute_explore_terrain
skills[1].execute = execute_set_terrain
skills[2].execute = execute_get_terrain


def register():
    for skill in skills:
        register_skill(skill)
