"""
Agent - OpenClaw风格的AI Agent
"""
import json
import re
from typing import Dict, List, Any, Optional
from .llm_adapter import LLMAdapter
from .world_manager import WorldManager
from .memory import Memory
from .transcript import Transcript
from .skills import SkillRegistry, SkillContext, SkillResult


class Agent:
    def __init__(self, llm: LLMAdapter, world: WorldManager, memory: Memory = None, transcript: Transcript = None):
        self.llm = llm
        self.world = world
        self.world.agent_instance = self
        self.memory = memory
        self.transcript = transcript
        self.conversation_history: List[Dict] = []
        self.skill_history: List[Dict] = []
        
        # 加载Skills
        self.skill_registry = SkillRegistry()
        self._load_skills()
    
    def _load_skills(self):
        """加载所有Skills"""
        # 导入会触发register
        from .skills import (
            entity_skills,
            terrain_skills,
            behavior_skills,
            analyze_skills,
            tick_skills,
            save_skills,
            move_rules_skills
        )
        
        entity_skills.register()
        terrain_skills.register()
        behavior_skills.register()
        analyze_skills.register()
        tick_skills.register()
        save_skills.register()
        move_rules_skills.register()
        
        # 从目录动态加载（加载额外的.py文件）
        import os
        skills_dir = os.path.join(os.path.dirname(__file__), "skills")
        self.skill_registry.load_from_directory(skills_dir)
        
        print(f"[Agent] 已加载 {len(self.skill_registry.get_all())} 个Skills", flush=True)
    
    def _get_skill_prompt(self) -> str:
        """生成Skill提示"""
        return self.skill_registry.generate_prompt_context()
    
    def _get_system_prompt(self) -> str:
        """系统提示"""
        return f"""你是一个虚拟世界的管理者AI。

## 你的职责
根据用户指令，使用Skills操作世界。

{self._get_skill_prompt()}

## 重要规则
1. 仔细分析用户输入，找出真实意图
2. "X的死敌Y出现了" → 意图是创建Y，不是X
3. 只返回JSON格式的Skill调用！
4. 坐标默认(0,0)，世界会自动找空位"""
    
    def _build_system_prompt(self) -> str:
        if self.memory:
            context = self.memory.get_context_prompt()
            return f"{self._get_system_prompt()}\n\n---\n\n{context}"
        return self._get_system_prompt()
    
    def execute_command(self, command: str) -> Dict[str, Any]:
        world_state = self.world.get_state()
        
        if self.transcript:
            self.transcript.add_user_message(command)
            self.transcript.add_world_state(world_state)
        
        print(f"[AI] 收到指令: {command[:50]}...", flush=True)
        
        # 解析Skill调用
        intent = self._parse_skill_call(command)
        
        if not intent:
            return {
                "success": False,
                "response": "无法理解指令",
                "world_state": world_state
            }
        
        # 执行Skill
        result = self._execute_skill(intent)
        
        if self.transcript:
            self.transcript.save()
        
        return result
    
    def _parse_skill_call(self, command: str) -> Optional[Dict]:
        """让LLM解析用户指令，返回Skill调用"""
        
        skills_context = self._get_skill_prompt()
        
        prompt = f"""分析用户指令，返回JSON格式的Skill调用。

用户指令：「{command}」

当前世界：{self.world.get_summary()}

{skills_context}

返回JSON格式：
{{
    "skill": "skill名称",
    "params": {{
        // 根据skill需要的参数填写
    }}
}}

规则：
- "X的死敌Y出现了" → entity_name/name 是 Y
- 只返回JSON，不要其他文字！"""

        response = self.llm.chat([{"role": "user", "content": prompt}])
        
        if "error" in response:
            print(f"[AI] 解析失败: {response['error']}", flush=True)
            return None
        
        content = response.get("message", {}).get("content", "")
        print(f"[AI] LLM响应: {content[:200]}...", flush=True)
        
        # 提取JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            print(f"[AI] 无法提取JSON", flush=True)
            return None
        
        try:
            intent = json.loads(json_match.group())
            skill_name = intent.get("skill", "")
            print(f"[AI] 解析: skill={skill_name}, params={intent.get('params', {})}", flush=True)
            return intent
        except json.JSONDecodeError as e:
            print(f"[AI] JSON解析失败: {e}", flush=True)
            return None
    
    def _execute_skill(self, intent: Dict) -> Dict[str, Any]:
        """执行Skill"""
        skill_name = intent.get("skill", "")
        params = intent.get("params", {})
        
        skill = self.skill_registry.get(skill_name)
        if not skill:
            return {"success": False, "error": f"未知Skill: {skill_name}"}
        
        if not skill.execute:
            return {"success": False, "error": f"Skill {skill_name} 没有执行函数"}
        
        # 创建执行上下文
        ctx = SkillContext(self.world, params, self.skill_history)
        
        try:
            result = skill.execute(ctx)
            
            if isinstance(result, SkillResult):
                # SkillResult
                if result.success:
                    print(f"[AI] Skill成功: {result.message}", flush=True)
                    
                    # 记录历史
                    self.skill_history.append({
                        "skill": skill_name,
                        "params": params,
                        "result": result.to_dict()
                    })
                    
                    # 如果创建了实体，分析技能并探索地形
                    if skill_name == "create_entity" and result.data:
                        entity_id = result.data.get("id")
                        if entity_id:
                            self._on_entity_created(entity_id, result.data)
                    
                    return {
                        "success": True,
                        "response": result.message,
                        "data": result.data,
                        "world_state": self.world.get_state()
                    }
                else:
                    print(f"[AI] Skill失败: {result.error}", flush=True)
                    return {
                        "success": False,
                        "response": result.error,
                        "error": result.error,
                        "world_state": self.world.get_state()
                    }
            else:
                # 兼容旧的dict返回
                return result
                
        except Exception as e:
            print(f"[AI] Skill执行异常: {e}", flush=True)
            return {"success": False, "error": str(e)}
    
    def _on_entity_created(self, entity_id: str, entity_data: Dict):
        """实体创建后的处理"""
        entity_type = entity_data.get("type", "creature")
        entity_name = entity_data.get("name", "")
        
        # 分析实体技能
        skills = self._analyze_entity_skills(entity_type, entity_name)
        if skills:
            for skill in skills:
                self.world.entities[entity_id].add_skill(skill)
            print(f"[AI] {entity_name} 获得技能: {skills}", flush=True)
        
        # 探索周围地形
        self._explore_surrounding_terrain(entity_id)
    
    def _analyze_entity_skills(self, entity_type: str, entity_name: str) -> List[str]:
        """分析实体技能"""
        prompt = f"""分析实体应该拥有什么技能，用逗号分隔。
实体类型: {entity_type}
实体名称: {entity_name}
"""
        response = self.llm.chat([{"role": "user", "content": prompt}])
        
        if "error" in response:
            return []
        
        content = response.get("message", {}).get("content", "")
        if content:
            return [s.strip() for s in content.split(",") if s.strip()]
        return []
    
    def _explore_surrounding_terrain(self, entity_id: str):
        """探索周围地形"""
        entity = self.world.get_entity(entity_id)
        if not entity or entity.x is None:
            return
        
        unexplored = self.world.get_nearby_unexplored(entity.x, entity.y)
        if not unexplored:
            return
        
        prompt = f"""实体 {entity.name} 位于 ({entity.x},{entity.y})，周围未探索: {unexplored}
请决定这些位置的地形类型：陆地、山川、河流、海洋
遵循：大陆相连、海洋大片、河流绵长、山川雄伟

返回JSON:
{{
    "decisions": [
        {{"x": 1, "y": 1, "terrain": "陆地"}}
    ]
}}"""

        response = self.llm.chat([{"role": "user", "content": prompt}])
        
        if "error" in response:
            return
        
        content = response.get("message", {}).get("content", "")
        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                for d in data.get("decisions", []):
                    self.world.explore_terrain(d["x"], d["y"], d["terrain"])
                print(f"[AI] 探索了 {len(data.get('decisions', []))} 个位置", flush=True)
        except:
            pass
    
    def auto_tick(self) -> Dict[str, Any]:
        """自动Tick"""
        world_state = self.world.get_state()
        self.world.tick_world()
        
        # 探索生物周围地形
        for entity in world_state["entities"]:
            if entity["type"] == "creature":
                self._explore_surrounding_terrain(entity["id"])
        
        if not world_state["entities"]:
            return {"success": True, "world_state": self.world.get_state()}
        
        # 让AI决定做什么
        return {
            "success": True,
            "world_state": self.world.get_state()
        }
