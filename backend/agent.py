import json
from typing import Dict, List, Any, Optional
from .llm_adapter import LLMAdapter
from .world_manager import WorldManager
from .tools import TOOLS, ToolExecutor
from .memory import Memory
from .transcript import Transcript
from .skills import SkillRegistry, Skill


class Agent:
    def __init__(self, llm: LLMAdapter, world: WorldManager, memory: Memory = None, transcript: Transcript = None):
        self.llm = llm
        self.world = world
        self.world.agent_instance = self
        self.executor = ToolExecutor(world, llm)
        self.memory = memory
        self.transcript = transcript
        self.conversation_history: List[Dict[str, str]] = []
        
        # 加载所有Skills
        self.skill_registry = SkillRegistry()
        self._load_skills()
    
    def _load_skills(self):
        """加载Skills"""
        from .skills import entity_skills, terrain_skills
        entity_skills.register()
        terrain_skills.register()
        
        # 从skills目录动态加载
        import os
        skills_dir = os.path.join(os.path.dirname(__file__), "skills")
        self.skill_registry.load_from_directory(skills_dir)
        
        print(f"[Agent] 已加载 {len(self.skill_registry.get_all())} 个Skills", flush=True)
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词，包含当前可用的Skills"""
        skills_list = self.skill_registry.list_skills()
        
        skills_text = "\n".join([
            f'- {s["name"]}: {s["description"]}'
            for s in skills_list
        ])
        
        return f"""你是一个虚拟世界的管理者AI。你的任务是根据用户指令操作世界。

## 可用Skills（操作类型）
{skills_text}

## 实体类型
- creature: 生物/人物/动物（人、小明、孙悟空、狼、狗等）
- plant: 植物（树、花、草等）
- building: 建筑（房屋、城堡等）
- water: 水体（河、湖、海等）
- fire: 火

## 地形类型
- 陆地、山川、河流、海洋

## 重要规则
1. 仔细分析用户输入，找出主要意图
2. "X的死敌Y出现了" → 意图是创建Y，不是X
3. 只返回JSON格式的Skill调用！
4. 坐标默认(0,0)，世界会找到空位"""
    
    def _build_system_prompt(self) -> str:
        if self.memory:
            context = self.memory.get_context_prompt()
            return f"{self._get_system_prompt()}\n\n---\n\n{context}"
        return self._get_system_prompt()
    
    def _analyze_skills(self, entity_type: str, entity_name: str) -> List[str]:
        prompt = f"""分析这个实体应该拥有什么技能和性格。
实体类型: {entity_type}
实体名称: {entity_name}

根据实体名称自主分析它应该有什么技能和性格，用逗号分隔。"""

        response = self.llm.chat([{"role": "user", "content": prompt}])
        if "error" in response:
            return []
        
        content = response.get("message", {}).get("content", "")
        if content:
            skills = [s.strip() for s in content.split(",")]
            return [s for s in skills if s]
        return []
    
    def _explore_surrounding_terrain(self, entity_id: str):
        entity = self.world.get_entity(entity_id)
        if not entity or entity.x is None or entity.y is None:
            return
        
        surrounding_unexplored = self.world.get_nearby_unexplored(entity.x, entity.y)
        if not surrounding_unexplored:
            return
        
        prompt = f"实体 {entity.name} 位于 ({entity.x}, {entity.y})，周围未探索区域: {surrounding_unexplored}\n请决定这些区域的地形类型（陆地/山川/河流/海洋）。"
        self.llm.chat([{"role": "user", "content": prompt}], TOOLS)
    
    def execute_command(self, command: str) -> Dict[str, Any]:
        world_state = self.world.get_state()
        
        if self.transcript:
            self.transcript.add_user_message(command)
            self.transcript.add_world_state(world_state)
        
        print(f"[AI] 收到指令: {command[:50]}...", flush=True)
        
        # 让LLM分析用户意图
        intent = self._parse_command_with_llm(command)
        
        if intent:
            result = self._execute_skill(intent)
            if self.transcript:
                self.transcript.save()
            return result
        
        return {
            "success": False,
            "response": "无法理解指令",
            "world_state": world_state
        }
    
    def _parse_command_with_llm(self, command: str) -> Optional[Dict]:
        """让LLM分析用户指令，返回Skill调用"""
        
        skills_list = self.skill_registry.list_skills()
        skills_names = [s["name"] for s in skills_list]
        
        prompt = f"""分析用户指令，返回JSON格式的Skill调用。

用户指令：「{command}」

当前世界状态：{self.world.get_summary()}

可用Skills：{', '.join(skills_names)}

返回JSON格式：
{{
    "skill": "使用的skill名称",
    "params": {{
        "entity_type": "creature/plant/building/water/fire",
        "entity_name": "实体名称",
        "name": "实体名称(同entity_name)",
        "x": 数字坐标,
        "y": 数字坐标,
        "behavior": "行为描述",
        "terrain_type": "地形类型"
    }}
}}

注意：
- "X的死敌Y出现了" → skill=create_entity, entity_name=Y
- 只返回JSON！"""

        response = self.llm.chat([{"role": "user", "content": prompt}])
        
        if "error" in response:
            print(f"[AI] LLM解析失败: {response['error']}", flush=True)
            return None
        
        content = response.get("message", {}).get("content", "")
        print(f"[AI] LLM响应: {content[:200]}...", flush=True)
        
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            return None
        
        try:
            intent = json.loads(json_match.group())
            skill_name = intent.get("skill", "")
            print(f"[AI] 解析: skill={skill_name}", flush=True)
            return intent
        except:
            return None
    
    def _execute_skill(self, intent: Dict) -> Dict[str, Any]:
        """执行Skill"""
        skill_name = intent.get("skill", "")
        params = intent.get("params", {})
        
        skill = self.skill_registry.get(skill_name)
        if not skill:
            return {"success": False, "error": f"未知Skill: {skill_name}"}
        
        if skill.execute:
            try:
                result = skill.execute(self.world, params)
                print(f"[AI] Skill执行结果: {result}", flush=True)
                return result
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": f"Skill {skill_name} 没有执行函数"}
        
        if self.transcript:
            self.transcript.add_user_message(command)
            self.transcript.add_world_state(world_state)
        
        print(f"[AI] 收到指令: {command[:50]}...", flush=True)
        
        # 让LLM分析用户意图
        intent = self._parse_command_with_llm(command)
        
        if intent:
            tool_calls = self._build_tool_calls_from_intent(intent)
            if tool_calls:
                result = self._execute_tool_calls(tool_calls)
                if self.transcript:
                    self.transcript.save()
                return result
        
        return {
            "success": False,
            "response": "无法理解指令，请尝试更明确的表达",
            "world_state": world_state
        }
    
    def _parse_command_with_llm(self, command: str) -> Optional[Dict]:
        """OpenClaw风格：让LLM分析用户指令，返回结构化Intent"""
        
        prompt = f"""分析以下用户指令，返回JSON格式的结果：

用户指令：「{command}」

当前世界状态：
{self.world.get_summary()}

请分析用户的真实意图，返回JSON：
{{
    "skill": "使用的技能",
    "entity_name": "涉及的实体名称",
    "entity_type": "实体类型(creature/plant/building/resource/water/fire)",
    "x": 数字坐标(默认0),
    "y": 数字坐标(默认0),
    "behavior": "行为描述(如向四周探索)",
    "description": "额外描述"
}}

注意：
- "X的死敌Y出现了" → entity_name应该是Y，不是X
- "出现/来到/创建/诞生" → skill是create_entity
- "移动/走去" → skill是move_entity
- 只返回JSON，不要其他文字！"""

        response = self.llm.chat([{"role": "user", "content": prompt}])
        
        if "error" in response:
            print(f"[AI] LLM解析失败: {response['error']}", flush=True)
            return None
        
        content = response.get("message", {}).get("content", "")
        print(f"[AI] LLM原始响应: {content[:200]}...", flush=True)
        
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            print(f"[AI] 无法提取JSON", flush=True)
            return None
        
        try:
            intent = json.loads(json_match.group())
            skill = intent.get("skill", "none")
            print(f"[AI] 解析结果: skill={skill}, entity_name={intent.get('entity_name', '')}", flush=True)
            return intent
        except json.JSONDecodeError as e:
            print(f"[AI] JSON解析失败: {e}", flush=True)
            return None
    
    def auto_tick(self) -> Dict[str, Any]:
        world_state = self.world.get_state()
        
        self.world.tick_world()
        
        for entity in world_state["entities"]:
            if entity["type"] == "creature":
                self._explore_surrounding_terrain(entity["id"])
                
        if not world_state["entities"]:
            return {"success": True, "message": "世界为空", "world_state": self.world.get_state()}
        
        world_summary = self._build_world_summary(world_state)
        
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "system", "content": f"这是世界的自动推进时间 T={world_state['tick']}。\n当前世界状态:\n{world_summary}\n\n请根据当前规则和世界状态，决定需要执行什么动作来推进世界发展。\n如果有生物，思考它们应该如何移动。\n如果有植物，思考是否应该生长。\n只返回必要的工具调用，不要返回解释。"},
        ]
        
        response = self.llm.chat(messages, TOOLS)
        
        if "error" in response:
            return {"success": False, "error": response["error"]}
        
        try:
            message = response.get("message", {})
            tool_calls = message.get("tool_calls", [])
            
            results = []
            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                tool_name = func.get("name")
                tool_args = func.get("arguments", {})
                
                if isinstance(tool_args, str):
                    import json
                    tool_args = json.loads(tool_args)
                
                result = self.executor.execute(tool_name, tool_args)
                results.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })
            
            self.world.tick_world()
            
            return {
                "success": True,
                "actions": results,
                "world_state": self.world.get_state()
            }
            
        except Exception as e:
            self.world.tick_world()
            return {"success": True, "error": str(e), "world_state": self.world.get_state()}
    
    def _get_move_rules_from_llm(self, entity_type: str, skills: List[str]) -> List[str]:
        prompt = f"""判断类型为 {entity_type}，拥有技能 {skills} 的实体可以在什么地形上移动？
        
可选地形类型：陆地、山川、河流、海洋

规则示例：
- 陆地生物：只能移动到陆地、山川
- 飞行生物：可以移动到任何地形
- 水生生物：只能移动到河流、海洋
- 有游泳技能的生物：可以移动到河流、海洋

请直接返回该实体可以移动到的地形类型列表，用逗号分隔。例如："陆地,山川" """

        messages = [
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.llm.chat(messages)
            if "error" in response:
                return ["陆地", "山川"]  # 默认值
            
            content = response.get("message", {}).get("content", "")
            if not content:
                return ["陆地", "山川"]
            
            terrains = [t.strip() for t in content.split(",")]
            valid_terrains = ["陆地", "山川", "河流", "海洋"]
            return [t for t in terrains if t in valid_terrains]
        except:
            return ["陆地", "山川"]
    
    def _build_world_summary(self, state: Dict) -> str:
        summary = f"世界时间: T={state['tick']}\n"
        summary += f"实体数量: {state['stats']['entity_count']}\n"
        
        by_type = {}
        for e in state["entities"]:
            t = e["type"]
            by_type[t] = by_type.get(t, 0) + 1
        
        if by_type:
            summary += "实体分布: " + ", ".join([f"{k}:{v}" for k, v in by_type.items()]) + "\n"
        
        if state["entities"]:
            summary += "实体列表:\n"
            for e in state["entities"][:10]:
                summary += f"  - {e['name']}({e['type']}) at ({e['x']}, {e['y']})"
                if e.get('description'):
                    summary += f": {e['description']}"
                summary += "\n"
            if len(state["entities"]) > 10:
                summary += f"  ... 还有 {len(state['entities']) - 10} 个实体\n"
        
        if state["rules"]:
            summary += f"\n当前规则:\n"
            for rule in state["rules"]:
                summary += f"  - {rule}\n"
        
        return summary
    
    def reset(self):
        self.conversation_history = []
    
