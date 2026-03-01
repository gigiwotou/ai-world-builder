import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


MEMORY_DIR = "memory"
CORE_FILES = {
    "soul": "SOUL.md",
    "agents": "AGENTS.md", 
    "memory": "MEMORY.md",
    "user": "USER.md",
    "identity": "IDENTITY.md"
}


class Memory:
    def __init__(self, data_dir: str, config: Dict = None):
        self.data_dir = Path(data_dir)
        self.memory_dir = self.data_dir / MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or {}
        
        self._init_core_files()
    
    def _init_core_files(self):
        defaults = {
            "SOUL.md": """# SOUL.md - AI 核心人格

你是一个仁慈的世界管理者，负责根据玩家的指令创造和发展一个像素风格的虚拟世界。

## 价值观
- 尊重玩家的创造意愿
- 保持世界的逻辑一致性
- 创造有趣且生动的世界

## 行为约束
- 只使用提供的工具操作世界
- 保持简短但有描述性的反馈
- 确保实体位置不重叠
""",
            "AGENTS.md": """# AGENTS.md - 操作规则

## 核心原则
1. 理解玩家意图，用行动实现
2. 创建多个相似实体时，一次性创建
3. 相关实体应该放在一起
4. 保持世界连贯性

## 执行流程
1. 解析玩家指令
2. 确定需要创建/修改的实体
3. 使用工具执行操作
4. 描述执行结果
""",
            "MEMORY.md": self._generate_memory_content(),
            "USER.md": """# USER.md - 用户信息

（由AI自动更新）
""",
            "IDENTITY.md": """# IDENTITY.md - 身份信息

## AI身份
- 名称: 世界管理者
- 角色: 虚拟世界的创造者与守护者

## 能力
- 创建和删除实体
- 移动实体
- 添加世界规则
"""
        }
        
        for filename, content in defaults.items():
            filepath = self.data_dir / filename
            if not filepath.exists():
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
    
    def _generate_memory_content(self) -> str:
        world_width = self.config.get("world_width", 800)
        world_height = self.config.get("world_height", 600)
        cell_size = self.config.get("cell_size", 20)
        
        grid_width = world_width // cell_size
        grid_height = world_height // cell_size
        
        return f"""# MEMORY.md - 长期知识

## 世界规则
- 世界是无限大的网格坐标系统（坐标可正可负）
- 每个格子 {cell_size} 像素
- 实体类型：land(陆地), plant(植物), creature(生物), building(建筑), resource(资源), water(水), fire(火)

## 已知实体
（由AI自动更新）
"""
    
    def get_soul(self) -> str:
        return self._read_file("SOUL.md")
    
    def get_agents(self) -> str:
        return self._read_file("AGENTS.md")
    
    def get_memory(self) -> str:
        return self._read_file("MEMORY.md")
    
    def get_user(self) -> str:
        return self._read_file("USER.md")
    
    def get_identity(self) -> str:
        return self._read_file("IDENTITY.md")
    
    def get_context_prompt(self) -> str:
        parts = [
            self.get_identity(),
            self.get_soul(),
            self.get_agents(),
            self.get_memory(),
            self.get_user()
        ]
        return "\n\n---\n\n".join(parts)
    
    def _read_file(self, filename: str) -> str:
        filepath = self.data_dir / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        return ""
    
    def append_daily_log(self, content: str):
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.memory_dir / f"{today}.md"
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"\n## {timestamp}\n{content}\n"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
    
    def get_today_log(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.memory_dir / f"{today}.md"
        
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                return f.read()
        return ""
    
    def update_memory(self, key: str, value: str):
        memory_file = self.data_dir / "MEMORY.md"
        
        with open(memory_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        if f"## {key}" in content:
            lines = content.split("\n")
            new_lines = []
            in_section = False
            for line in lines:
                if line.strip() == f"## {key}":
                    in_section = True
                    new_lines.append(line)
                elif in_section and line.startswith("## "):
                    in_section = False
                    new_lines.append(line)
                elif in_section and line.strip():
                    continue
                else:
                    new_lines.append(line)
            content = "\n".join(new_lines)
        
        with open(memory_file, "w", encoding="utf-8") as f:
            f.write(content)
            if not f"## {key}" in content:
                f.write(f"\n## {key}\n")
            f.write(f"{value}\n")
    
    def append_memory(self, content: str):
        memory_file = self.data_dir / "MEMORY.md"
        
        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(f"\n- {content}")
    
    def get_all_logs(self) -> List[str]:
        logs = []
        if self.memory_dir.exists():
            for f in sorted(self.memory_dir.glob("*.md")):
                logs.append(f.name)
        return logs
