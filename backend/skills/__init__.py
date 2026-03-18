import json
import os
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class Skill:
    name: str
    description: str
    aliases: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    execute: Optional[Callable] = None
    
    def match(self, text: str) -> bool:
        text_lower = text.lower()
        if self.name in text_lower:
            return True
        for alias in self.aliases:
            if alias in text_lower:
                return True
        return False


class SkillRegistry:
    _instance = None
    _skills: Dict[str, Skill] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, skill: Skill):
        self._skills[skill.name] = skill
        print(f"[Skill] 注册: {skill.name}", flush=True)
    
    def unregister(self, name: str):
        if name in self._skills:
            del self._skills[name]
            print(f"[Skill] 注销: {name}", flush=True)
    
    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)
    
    def get_all(self) -> Dict[str, Skill]:
        return self._skills.copy()
    
    def find_by_text(self, text: str) -> Optional[Skill]:
        text_lower = text.lower()
        for skill in self._skills.values():
            if skill.match(text_lower):
                return skill
        return None
    
    def list_skills(self) -> List[Dict]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "aliases": s.aliases
            }
            for s in self._skills.values()
        ]
    
    def load_from_directory(self, directory: str):
        skills_dir = Path(directory)
        if not skills_dir.exists():
            skills_dir.mkdir(parents=True, exist_ok=True)
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
            except Exception as e:
                print(f"[Skill] 加载失败 {file.name}: {e}", flush=True)


def register_skill(skill: Skill):
    SkillRegistry().register(skill)


def create_skill(
    name: str,
    description: str,
    aliases: Optional[List[str]] = None,
    parameters: Optional[Dict[str, Any]] = None
):
    return Skill(
        name=name,
        description=description,
        aliases=aliases if aliases else [],
        parameters=parameters if parameters else {}
    )
