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
        self.current_entity_index: int = 0
        
        # 加载Skills
        self.skill_registry = SkillRegistry()
        self._load_skills()
    
    def _load_skills(self):
        """加载所有Skills"""
        # 先清空注册表
        self.skill_registry.clear()
        
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
        
        skills = self.skill_registry.get_all()
        print(f"[Agent] 已加载 {len(skills)} 个Skills: {list(skills.keys())}", flush=True)
    
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
        
        skills = self.skill_registry.get_all()
        if not skills:
            print(f"[AI] 错误: 没有已注册的Skills!", flush=True)
            return None
        
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

        print(f"[AI] 发送解析请求到LLM...", flush=True)
        response = self.llm.chat([{"role": "user", "content": prompt}])
        
        if "error" in response:
            print(f"[AI] LLM错误: {response['error']}", flush=True)
            return None
        
        content = response.get("message", {}).get("content", "")
        print(f"[AI] LLM原始响应:\n{content[:500]}...", flush=True)
        
        # 尝试提取JSON
        import re
        
        # 提取 {...}
        json_match = re.search(r'\{[\s\S]*\}', content)
        
        if not json_match:
            print(f"[AI] 无法提取JSON", flush=True)
            return None
        
        try:
            json_str = json_match.group()
            intent = json.loads(json_str)
            skill_name = intent.get("skill", "")
            
            if not skill_name:
                print(f"[AI] JSON中没有skill字段: {intent}", flush=True)
                return None
            
            print(f"[AI] 解析成功: skill={skill_name}, params={intent.get('params', {})}", flush=True)
            return intent
        except json.JSONDecodeError as e:
            print(f"[AI] JSON解析失败: {e}", flush=True)
            return None
        
        try:
            json_str = json_match.group()
            intent = json.loads(json_str)
            skill_name = intent.get("skill", "")
            
            if not skill_name:
                print(f"[AI] JSON中没有skill字段: {intent}", flush=True)
                return None
            
            print(f"[AI] 解析成功: skill={skill_name}, params={intent.get('params', {})}", flush=True)
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
        """探索周围地形 - 非阻塞版本"""
        entity = self.world.get_entity(entity_id)
        if not entity or entity.x is None:
            return
        
        unexplored = self.world.get_nearby_unexplored(entity.x, entity.y)
        if not unexplored:
            return
        
        # 直接用随机地形，不阻塞等待LLM
        import random
        terrains = ["陆地", "陆地", "陆地", "山川", "河流", "海洋"]
        count = 0
        for pos in unexplored[:3]:  # 只探索最多3个位置
            x, y = pos
            terrain = random.choice(terrains)
            self.world.explore_terrain(x, y, terrain)
            count += 1
        
        if count > 0:
            print(f"[AI] {entity.name} 周围探索了 {count} 个位置", flush=True)
    
    def auto_tick(self) -> Dict[str, Any]:
        """自动Tick - 每次只tick一个实体，按顺序循环"""
        try:
            # 推进世界时间
            self.world.tick_world()
            
            world_state = self.world.get_state()
            tick = world_state["tick"]
            
            entities = world_state["entities"]
            if not entities:
                return {"success": True, "tick": tick, "world_state": world_state}
            
            # 探索生物周围地形
            for entity in entities:
                if entity["type"] == "creature":
                    self._explore_surrounding_terrain(entity["id"])
            
            # 获取当前要处理的实体
            if self.current_entity_index >= len(entities):
                self.current_entity_index = 0
            
            entity = entities[self.current_entity_index]
            self.current_entity_index += 1
            
            # 为当前实体执行tick
            self.entity_tick(entity, tick)
            
            return {
                "success": True,
                "tick": self.world.tick,
                "world_state": self.world.get_state()
            }
            
        except Exception as e:
            print(f"[AI] auto_tick错误: {e}", flush=True)
            return {"success": False, "error": str(e)}
    
    def entity_tick(self, entity: Dict, tick: int) -> None:
        """为单个实体执行tick决策"""
        try:
            entity_name = entity.get("name", "未知")
            entity_type = entity.get("type", "unknown")
            entity_id = entity.get("id", "")
            entity_x = entity.get("x", 0)
            entity_y = entity.get("y", 0)
            entity_behavior = entity.get("behavior", "")
            
            # 获取该实体周围的地形
            nearby_terrain = []
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    nx, ny = entity_x + dx, entity_y + dy
                    terrain = self.world.get_terrain_at(nx, ny)
                    if terrain and terrain != "未探索":
                        nearby_terrain.append(f"({nx},{ny}):{terrain}")
            
            terrain_info = ", ".join(nearby_terrain) if nearby_terrain else "周围无已探索地形"
            
            # 查找附近的其他实体
            nearby_entities = []
            for e in self.world.entities.values():
                if e.id != entity_id and abs(e.x - entity_x) <= 5 and abs(e.y - entity_y) <= 5:
                    nearby_entities.append(f"{e.name}({e.type}) at ({e.x},{e.y})")
            
            nearby_info = "\n".join(nearby_entities) if nearby_entities else "附近无其他实体"
            
            # 获取实体属性
            entity_props = entity.get("properties", {})
            entity_skills = entity.get("skills", [])
            gender = entity.get("gender", "")
            
            props_str = ""
            if entity_props:
                props_str = f", 属性: {entity_props}"
            skills_str = f", 技能: {', '.join(entity_skills)}" if entity_skills else ""
            gender_str = f", 性别: {gender}" if gender else ""
            
            prompt = f"""你是实体「{entity_name}」的AI控制器。

【实体信息】
- 名称: {entity_name}
- 类型: {entity_type}
- 位置: ({entity_x}, {entity_y})
- 行为: {entity_behavior}{props_str}{skills_str}{gender_str}

【周围地形】
{terrain_info}

【附近实体】
{nearby_info}

【可用技能】
{self._get_skill_prompt()}

请决定「{entity_name}」这个时间单位要做什么。
重要：必须返回纯JSON格式，不要有markdown代码块！
格式示例：
{{"actions": [{{"skill": "move_entity", "params": {{"entity_id": "{entity_id}", "x": 0, "y": 1}}}}]}}
{{"actions": []}}"""

            system_prompt = "你是一个游戏实体的AI控制器，控制实体的行为和决策。"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            print(f"[AI] {entity_name} 发送LLM请求...", flush=True)
            response = self.llm.chat(messages)
            print(f"[AI] {entity_name} 收到LLM响应", flush=True)
            
            if "error" in response:
                return
            
            content = response.get("message", {}).get("content", "")
            
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    actions = data.get("actions", data.get("operations", []))
                    
                    if not isinstance(actions, list):
                        actions = []
                    
                    for action in actions:
                        if not isinstance(action, dict):
                            continue
                        skill_name = action.get("skill", action.get("type", ""))
                        params = action.get("params", action.get("parameter", {}))
                        if isinstance(params, str):
                            params = {}
                        if skill_name:
                            self._execute_skill({"skill": skill_name, "params": params})
                    
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"[AI] {entity_name} 执行动作失败: {e}", flush=True)
                    
        except Exception as e:
            print(f"[AI] {entity.get('name', '未知')} entity_tick错误: {e}", flush=True)
