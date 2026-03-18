"""
Skill基类 - OpenClaw风格
"""
import json
import os
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field


@dataclass
class Parameter:
    name: str
    type: str = "string"
    description: str = ""
    default: Any = None
    required: bool = False
    enum: List[Any] = field(default_factory=list)
    
    def to_schema(self) -> Dict:
        schema = {
            "type": self.type,
            "description": self.description
        }
        if self.default is not None:
            schema["default"] = self.default
        if self.enum:
            schema["enum"] = self.enum
        return schema


@dataclass
class Skill:
    """Skill定义 - OpenClaw风格"""
    name: str
    description: str
    
    parameters: Dict[str, Parameter] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    
    execute: Optional[Callable] = None
    
    def match(self, text: str) -> bool:
        text_lower = text.lower()
        if self.name.lower() in text_lower:
            return True
        for alias in self.aliases:
            if alias.lower() in text_lower:
                return True
        return False
    
    def to_schema(self) -> Dict:
        """转换为Tool Schema"""
        properties = {}
        required = []
        
        for name, param in self.parameters.items():
            properties[name] = param.to_schema()
            if param.required:
                required.append(name)
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    
    def get_example_prompt(self) -> str:
        """生成示例提示"""
        if not self.examples:
            return ""
        return "\n".join([f"示例: {ex}" for ex in self.examples])


class SkillContext:
    """Skill执行上下文"""
    def __init__(self, world, params: Dict, history: List[Dict] = None):
        self.world = world
        self.params = params
        self.history = history or []
        self.result: Any = None
        self.error: Optional[str] = None
    
    def add_history(self, skill_name: str, params: Dict, result: Any):
        self.history.append({
            "skill": skill_name,
            "params": params,
            "result": result
        })


class SkillResult:
    """Skill执行结果"""
    def __init__(self, success: bool = True, data: Any = None, error: str = None, message: str = ""):
        self.success = success
        self.data = data
        self.error = error
        self.message = message
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "message": self.message
        }


class SkillRegistry:
    """Skill注册表 - 单例"""
    _instance = None
    _skills: Dict[str, Skill] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._skills = {}
        return cls._instance
    
    def register(self, skill: Skill):
        self._skills[skill.name] = skill
    
    def unregister(self, name: str):
        if name in self._skills:
            del self._skills[name]
    
    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)
    
    def get_all(self) -> Dict[str, Skill]:
        return self._skills.copy()
    
    def list_skills(self) -> List[Dict]:
        return [s.to_schema() for s in self._skills.values()]
    
    def list_skill_names(self) -> List[str]:
        return list(self._skills.keys())
    
    def find_by_text(self, text: str) -> Optional[Skill]:
        text_lower = text.lower()
        for skill in self._skills.values():
            if skill.match(text_lower):
                return skill
        return None
    
    def generate_prompt_context(self) -> str:
        """生成LLM可理解的提示上下文"""
        lines = ["\n## 可用Skills:"]
        for skill in self._skills.values():
            lines.append(f"\n### {skill.name}")
            lines.append(f"描述: {skill.description}")
            
            if skill.parameters:
                lines.append("参数:")
                for pname, param in skill.parameters.items():
                    req = "必需" if param.required else "可选"
                    default = f"(默认: {param.default})" if param.default is not None else ""
                    lines.append(f"  - {pname} ({param.type}) [{req}] {default}: {param.description}")
            
            if skill.examples:
                lines.append("示例:")
                for ex in skill.examples[:2]:
                    lines.append(f"  「{ex}」")
        
        return "\n".join(lines)
    
    def load_from_directory(self, directory: str):
        """从目录动态加载Skill模块"""
        skills_dir = Path(directory)
        if not skills_dir.exists():
            return
        
        for file in skills_dir.glob("*.py"):
            if file.stem.startswith("_"):
                continue
            try:
                module_name = f"backend.skills.{file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "register"):
                        module.register()
                        print(f"[Skill] 加载: {file.stem}", flush=True)
            except Exception as e:
                print(f"[Skill] 加载失败 {file.name}: {e}", flush=True)
    
    def clear(self):
        """清空所有Skills"""
        self._skills.clear()


# 全局函数
def create_skill(
    name: str,
    description: str,
    parameters: Optional[Dict[str, Parameter]] = None,
    aliases: Optional[List[str]] = None,
    examples: Optional[List[str]] = None
) -> Skill:
    return Skill(
        name=name,
        description=description,
        parameters=parameters or {},
        aliases=aliases or [],
        examples=examples or []
    )


def register_skill(skill: Skill):
    SkillRegistry().register(skill)


def param(
    name: str,
    param_type: str = "string",
    description: str = "",
    default: Any = None,
    required: bool = False,
    enum: Optional[List[Any]] = None
) -> Parameter:
    return Parameter(
        name=name,
        type=param_type,
        description=description,
        default=default,
        required=required,
        enum=enum or []
    )
