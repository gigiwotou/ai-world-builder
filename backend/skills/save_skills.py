"""
存档Skills - OpenClaw风格
"""
from . import Skill, create_skill, param, register_skill, SkillContext, SkillResult


def execute_save(ctx: SkillContext) -> SkillResult:
    """保存世界"""
    try:
        # 触发保存
        if hasattr(ctx.world, '_save'):
            ctx.world._save()
        
        return SkillResult(
            success=True,
            message="世界已保存"
        )
    except Exception as e:
        return SkillResult(
            success=False,
            error=f"保存失败: {str(e)}"
        )


def execute_load(ctx: SkillContext) -> SkillResult:
    """加载世界"""
    try:
        if hasattr(ctx.world, '_load'):
            ctx.world._load()
        
        state = ctx.world.get_state()
        return SkillResult(
            success=True,
            data={"tick": state["tick"], "entities": len(state["entities"])},
            message=f"世界已加载: T={state['tick']}, 实体={len(state['entities'])}"
        )
    except Exception as e:
        return SkillResult(
            success=False,
            error=f"加载失败: {str(e)}"
        )


def execute_export(ctx: SkillContext) -> SkillResult:
    """导出世界数据"""
    filename = ctx.params.get("filename", "world_export.json")
    
    try:
        state = ctx.world.get_state()
        import json
        import os
        
        filepath = os.path.join(ctx.world.data_dir, filename)
        os.makedirs(ctx.world.data_dir, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        return SkillResult(
            success=True,
            data={"filename": filename, "path": filepath},
            message=f"导出成功: {filename}"
        )
    except Exception as e:
        return SkillResult(
            success=False,
            error=f"导出失败: {str(e)}"
        )


skills = [
    create_skill(
        name="save",
        description="保存当前世界状态",
        aliases=["存档", "保存", "保存世界"],
        parameters={},
        examples=["保存世界", "存档"]
    ),
    
    create_skill(
        name="load",
        description="从文件加载世界状态",
        aliases=["读档", "加载", "读取存档"],
        parameters={},
        examples=["加载世界", "读档"]
    ),
    
    create_skill(
        name="export",
        description="导出自定义文件名",
        aliases=["导出", "导出世界"],
        parameters={
            "filename": param("filename", description="文件名", default="world_export.json")
        },
        examples=["导出世界到test.json"]
    )
]

skills[0].execute = execute_save
skills[1].execute = execute_load
skills[2].execute = execute_export


def register():
    for skill in skills:
        register_skill(skill)
