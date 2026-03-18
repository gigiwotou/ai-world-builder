"""
实体操作Skills - OpenClaw风格
"""
from . import Skill, create_skill, param, register_skill, SkillContext, SkillResult


def execute_create(ctx: SkillContext) -> SkillResult:
    """创建实体"""
    p = ctx.params
    
    entity = ctx.world.create_entity(
        entity_type=p.get("entity_type", "creature"),
        x=p.get("x", 0),
        y=p.get("y", 0),
        name=p.get("name", ""),
        description=p.get("description", "")
    )
    
    if entity:
        return SkillResult(
            success=True,
            data=entity.to_dict(),
            message=f"创建了 {entity.name}"
        )
    
    return SkillResult(
        success=False,
        error="创建失败，可能位置被占用"
    )


def execute_move(ctx: SkillContext) -> SkillResult:
    """移动实体"""
    p = ctx.params
    
    entity_id = p.get("entity_id")
    entity_name = p.get("entity_name", "")
    
    entity = ctx.world.get_entity(entity_id) if entity_id else ctx.world.find_entity_by_name(entity_name)
    
    if not entity:
        return SkillResult(
            success=False,
            error=f"找不到实体: {entity_name or entity_id}"
        )
    
    old_x, old_y = entity.x, entity.y
    entity.x = p.get("x", 0)
    entity.y = p.get("y", 0)
    
    return SkillResult(
        success=True,
        data=entity.to_dict(),
        message=f"{entity.name} 从 ({old_x},{old_y}) 移动到 ({entity.x},{entity.y})"
    )


def execute_delete(ctx: SkillContext) -> SkillResult:
    """删除实体"""
    p = ctx.params
    
    entity_id = p.get("entity_id")
    entity_name = p.get("entity_name", "")
    
    entity = ctx.world.get_entity(entity_id) if entity_id else ctx.world.find_entity_by_name(entity_name)
    
    if not entity:
        return SkillResult(
            success=False,
            error=f"找不到实体: {entity_name or entity_id}"
        )
    
    if ctx.world.delete_entity(entity.id):
        return SkillResult(
            success=True,
            message=f"删除了 {entity.name}"
        )
    
    return SkillResult(
        success=False,
        error="删除失败"
    )


def execute_set_behavior(ctx: SkillContext) -> SkillResult:
    """设置行为"""
    p = ctx.params
    
    entity = ctx.world.find_entity_by_name(p.get("entity_name", ""))
    
    if not entity:
        return SkillResult(
            success=False,
            error=f"找不到实体: {p.get('entity_name')}"
        )
    
    behavior = p.get("behavior", "")
    ctx.world.set_entity_behavior(entity.id, behavior)
    
    return SkillResult(
        success=True,
        data={"behavior": behavior},
        message=f"{entity.name} 的行为设为: {behavior}"
    )


def execute_add_rule(ctx: SkillContext) -> SkillResult:
    """添加规则"""
    p = ctx.params
    rule = p.get("rule", "")
    
    if not rule:
        return SkillResult(
            success=False,
            error="规则内容为空"
        )
    
    ctx.world.add_rule(rule)
    
    return SkillResult(
        success=True,
        message=f"添加了规则: {rule}"
    )


# 创建Skills
skills = [
    create_skill(
        name="create_entity",
        description="创建新的实体（生物、人物、动物、植物、建筑等）到世界中",
        aliases=["出现", "来到", "创建", "诞生", "有了", "添加", "生成"],
        parameters={
            "name": param("name", description="实体名称", required=True),
            "entity_type": param(
                "entity_type", 
                description="实体类型",
                default="creature",
                enum=["creature", "plant", "building", "water", "fire", "resource"]
            ),
            "x": param("x", "integer", "世界X坐标", default=0),
            "y": param("y", "integer", "世界Y坐标", default=0),
            "description": param("description", "实体描述", default="")
        },
        examples=[
            "世界上出现了孙悟空",
            "创建一个小明",
            "添加一个狼"
        ]
    ),
    
    create_skill(
        name="move_entity",
        description="移动已存在的实体到指定坐标",
        aliases=["移动", "走去", "跑到", "飞向", "游到", "转向"],
        parameters={
            "entity_name": param("entity_name", description="实体名称", required=True),
            "entity_id": param("entity_id", description="实体ID"),
            "x": param("x", "integer", "目标X坐标", required=True),
            "y": param("y", "integer", "目标Y坐标", required=True)
        },
        examples=[
            "小明走到(5,3)",
            "狼移动到(10,0)"
        ]
    ),
    
    create_skill(
        name="set_behavior",
        description="设置实体的行为模式",
        aliases=["行为", "向四周探索", "休息", "觅食", "攻击", "逃跑"],
        parameters={
            "entity_name": param("entity_name", description="实体名称", required=True),
            "behavior": param(
                "behavior",
                description="行为类型",
                required=True,
                enum=["向四周探索", "随机移动", "休息", "觅食", "饮水", "攻击", "逃跑", "跟随", "静止"]
            )
        },
        examples=[
            "让小明向四周探索",
            "狼开始觅食"
        ]
    ),
    
    create_skill(
        name="delete_entity",
        description="删除或消灭一个实体",
        aliases=["删除", "消灭", "移除", "消失", "死亡"],
        parameters={
            "entity_name": param("entity_name", description="实体名称"),
            "entity_id": param("entity_id", description="实体ID")
        },
        examples=[
            "消灭这只狼",
            "删除小明"
        ]
    ),
    
    create_skill(
        name="add_rule",
        description="添加世界规则",
        aliases=["规则", "规定", "设定"],
        parameters={
            "rule": param("rule", description="规则内容", required=True)
        },
        examples=[
            "添加规则：所有生物不能进入海洋",
            "设定规则：植物不能移动"
        ]
    )
]

# 绑定执行函数
skills[0].execute = execute_create
skills[1].execute = execute_move
skills[2].execute = execute_set_behavior
skills[3].execute = execute_delete
skills[4].execute = execute_add_rule


def register():
    for skill in skills:
        register_skill(skill)
