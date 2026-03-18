"""
内置实体操作Skill
"""
from . import Skill, create_skill, register_skill


def execute_create(world, params):
    entity = world.create_entity(
        entity_type=params.get("entity_type", "creature"),
        x=params.get("x", 0),
        y=params.get("y", 0),
        name=params.get("name", ""),
        description=params.get("description", "")
    )
    if entity:
        return {"success": True, "entity": entity.to_dict()}
    return {"success": False, "error": "创建失败"}


def execute_move(world, params):
    entity_id = params.get("entity_id")
    entity = world.get_entity(entity_id)
    if not entity:
        entity = world.find_entity_by_name(params.get("entity_name", ""))
    
    if not entity:
        return {"success": False, "error": "找不到实体"}
    
    entity.x = params.get("x", 0)
    entity.y = params.get("y", 0)
    return {"success": True, "entity": entity.to_dict()}


def execute_delete(world, params):
    entity_id = params.get("entity_id")
    if world.delete_entity(entity_id):
        return {"success": True}
    return {"success": False, "error": "删除失败"}


def execute_set_behavior(world, params):
    entity = world.find_entity_by_name(params.get("entity_name", ""))
    if not entity:
        return {"success": False, "error": "找不到实体"}
    
    world.set_entity_behavior(entity.id, params.get("behavior", ""))
    return {"success": True, "behavior": params.get("behavior")}


def execute_add_rule(world, params):
    world.add_rule(params.get("rule", ""))
    return {"success": True}


# 创建内置 Skills
skills = [
    create_skill(
        name="create_entity",
        description="创建新实体（生物、人物、动物、植物、建筑等）",
        aliases=["出现", "来到", "创建", "诞生", "有了", "添加", "生成"],
        parameters={
            "entity_type": "creature",
            "entity_name": "",
            "x": 0,
            "y": 0,
            "description": ""
        }
    ),
    create_skill(
        name="move_entity",
        description="移动实体到指定位置",
        aliases=["移动", "走去", "跑到", "飞向", "游到", "转向"],
        parameters={
            "entity_id": "",
            "entity_name": "",
            "x": 0,
            "y": 0
        }
    ),
    create_skill(
        name="set_behavior",
        description="设置实体的行为（探索、休息、觅食等）",
        aliases=["行为", "向四周探索", "休息", "觅食", "攻击", "逃跑"],
        parameters={
            "entity_name": "",
            "behavior": ""
        }
    ),
    create_skill(
        name="delete_entity",
        description="删除/消灭实体",
        aliases=["删除", "消灭", "移除", "消失", "死亡"],
        parameters={
            "entity_id": "",
            "entity_name": ""
        }
    ),
    create_skill(
        name="add_rule",
        description="添加世界规则",
        aliases=["规则", "规定", "设定"],
        parameters={
            "rule": ""
        }
    )
]

# 为每个Skill绑定执行函数
skills[0].execute = execute_create
skills[1].execute = execute_move
skills[2].execute = execute_set_behavior
skills[3].execute = execute_delete
skills[4].execute = execute_add_rule


def register():
    for skill in skills:
        register_skill(skill)
