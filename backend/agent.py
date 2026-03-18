import json
from typing import Dict, List, Any, Optional
from .llm_adapter import LLMAdapter
from .world_manager import WorldManager
from .tools import TOOLS, ToolExecutor
from .memory import Memory
from .transcript import Transcript


# Skill定义 - OpenClaw风格
SKILLS = {
    "create_entity": {
        "name": "创建实体",
        "description": "当用户提到出现、来到、创建、诞生新的生物、人物、动物、植物时使用",
        "aliases": ["出现", "来到", "创建", "诞生", "有了", "添加", "生成"],
        "tool": "create_entity"
    },
    "move_entity": {
        "name": "移动实体",
        "description": "当用户要求某个实体移动到某处、去向某地时使用",
        "aliases": ["移动", "走去", "跑到", "飞向", "游到", "转向"],
        "tool": "move_entity"
    },
    "set_behavior": {
        "name": "设置行为",
        "description": "当用户要求某个实体做什么动作或行为时使用",
        "aliases": ["向四周探索", "休息", "觅食", "攻击", "逃跑", "跟随"],
        "tool": "set_entity_behavior"
    },
    "delete_entity": {
        "name": "删除实体",
        "description": "当用户要求删除、消灭、移除某个实体时使用",
        "aliases": ["删除", "消灭", "移除", "消失", "死亡"],
        "tool": "delete_entity"
    },
    "add_rule": {
        "name": "添加规则",
        "description": "当用户添加世界规则或游戏规则时使用",
        "aliases": ["规则", "规定", "设定"],
        "tool": "add_rule"
    }
}

SYSTEM_PROMPT_BASE = """你是一个虚拟世界的管理者AI。你的任务是根据用户指令操作世界。

## 可用Skill（操作类型）
""" + "\n".join([f'- {k}: {v["name"]} - {v["description"]}' for k, v in SKILLS.items()]) + """

## 实体类型
- creature: 生物/人物/动物（人、小明、孙悟空、猪八戒、狼、狗等）
- plant: 植物（树、花、草、森林等）
- building: 建筑（房屋、城堡、村庄等）
- resource: 资源（矿、金、银等）
- water: 水体（河、湖、海等）
- fire: 火

## 重要规则
1. 仔细分析用户输入，找出主要意图
2. "X的死敌Y出现了" → 意图是创建Y，不是X
3. "出现/来到/创建" → create_entity
4. 默认坐标(0,0)，世界会找到空位放置
5. 只返回JSON格式的分析结果！"""


class Agent:
    def __init__(self, llm: LLMAdapter, world: WorldManager, memory: Memory = None, transcript: Transcript = None):
        self.llm = llm
        self.world = world
        self.world.agent_instance = self
        self.executor = ToolExecutor(world, llm)
        self.memory = memory
        self.transcript = transcript
        self.conversation_history: List[Dict[str, str]] = []
        
    def _build_system_prompt(self) -> str:
        if self.memory:
            context = self.memory.get_context_prompt()
            return f"{SYSTEM_PROMPT_BASE}\n\n---\n\n{context}"
        return SYSTEM_PROMPT_BASE
    
    def _analyze_skills(self, entity_type: str, entity_name: str) -> List[str]:
        prompt = f"""分析这个实体应该拥有什么技能和性格。
实体类型: {entity_type}
实体名称: {entity_name}

根据实体名称自主分析它应该有什么技能和性格。
- 技能：行动能力（移动、觅食、攻击、思考等）
- 性格：行为特征（勇敢、胆怯、善良、奸诈、热情、冷漠等）
- 习性：生活方式（群居、独居、领地意识等）

只需要返回你认为最合适的3-8个技能/性格，用逗号分隔。"""

        messages = [
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.llm.chat(messages)
            if "error" in response:
                return []
            
            content = response.get("message", {}).get("content", "")
            if content == "无" or not content:
                return []
            
            skills = [s.strip() for s in content.split(",")]
            return [s for s in skills if s]
        except:
            return []
    
    def _explore_surrounding_terrain(self, entity_id: str):
        entity = self.world.get_entity(entity_id)
        if not entity or entity.x is None or entity.y is None:
            return
        
        surrounding_unexplored = self.world.get_nearby_unexplored(entity.x, entity.y)
        if not surrounding_unexplored:
            return
        
        # 告诉AI需要探索哪些点
        prompt = f"实体 {entity.name} (类型: {entity.type}) 位于 ({entity.x}, {entity.y})。\n请使用 explore_terrain 工具探索其周围3x3未探索的区域，并决定这些区域的地形类型。\n需要探索的坐标有: {surrounding_unexplored}。\n\n请确保返回的地形类型是「陆地」「山川」「河流」或「海洋」，并遵循大片陆地、大片海洋、长河流、大山川的规则。"
        
        self.llm.chat([
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": prompt}
        ], TOOLS)
        
    def execute_command(self, command: str) -> Dict[str, Any]:
        world_state = self.world.get_state()
        
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
    
    def _build_tool_calls_from_intent(self, intent: Dict) -> List[Dict]:
        """根据Intent构建Tool Calls - OpenClaw风格"""
        tool_calls = []
        skill = intent.get("skill", "none")
        
        if skill not in SKILLS:
            print(f"[AI] 未知的skill: {skill}", flush=True)
            return tool_calls
        
        tool_name = SKILLS[skill]["tool"]
        
        if skill == "create_entity":
            entity_name = intent.get("entity_name", "")
            if not entity_name:
                print(f"[AI] create_entity缺少entity_name", flush=True)
                return tool_calls
            
            tool_calls.append({
                "function": {
                    "name": tool_name,
                    "arguments": {
                        "entity_type": intent.get("entity_type", "creature"),
                        "name": entity_name,
                        "x": intent.get("x", 0),
                        "y": intent.get("y", 0),
                        "description": intent.get("description", "")
                    }
                }
            })
            print(f"[AI] 构建ToolCall: create_entity - {entity_name}", flush=True)
        
        elif skill == "move_entity":
            entity = self.world.find_entity_by_name(intent.get("entity_name", ""))
            if not entity:
                print(f"[AI] 找不到实体: {intent.get('entity_name', '')}", flush=True)
                return tool_calls
            
            tool_calls.append({
                "function": {
                    "name": tool_name,
                    "arguments": {
                        "entity_id": entity.id,
                        "x": intent.get("x", 0),
                        "y": intent.get("y", 0)
                    }
                }
            })
            print(f"[AI] 构建ToolCall: move_entity - {entity.name}", flush=True)
        
        elif skill == "set_behavior":
            tool_calls.append({
                "function": {
                    "name": tool_name,
                    "arguments": {
                        "entity_name": intent.get("entity_name", ""),
                        "behavior": intent.get("behavior", "")
                    }
                }
            })
            print(f"[AI] 构建ToolCall: set_behavior", flush=True)
        
        elif skill == "delete_entity":
            entity = self.world.find_entity_by_name(intent.get("entity_name", ""))
            if entity:
                tool_calls.append({
                    "function": {
                        "name": tool_name,
                        "arguments": {"entity_id": entity.id}
                    }
                })
                print(f"[AI] 构建ToolCall: delete_entity - {entity.name}", flush=True)
        
        elif skill == "add_rule":
            tool_calls.append({
                "function": {
                    "name": tool_name,
                    "arguments": {"rule": intent.get("description", "")}
                }
            })
            print(f"[AI] 构建ToolCall: add_rule", flush=True)
        
        return tool_calls
    
    def _execute_tool_calls(self, tool_calls: List[Dict]) -> Dict[str, Any]:
        """执行工具调用"""
        results = []
        
        for tool_call in tool_calls:
            func = tool_call.get("function", {})
            tool_name = func.get("name")
            tool_args = func.get("arguments", {})
            
            if isinstance(tool_args, str):
                tool_args = json.loads(tool_args)
            
            result = self.executor.execute(tool_name, tool_args)
            results.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result
            })
            
            if self.transcript:
                self.transcript.add_tool_call(tool_name, tool_args, result)
            
            self.conversation_history.append({
                "role": "assistant",
                "content": f"调用工具 {tool_name}: {result.get('result', result.get('error', ''))}"
            })
            
            if tool_name == "create_entity" and result.get("success"):
                entity_data = result.get("result", {})
                entity_id = entity_data.get("id")
                entity_type = entity_data.get("type")
                entity_name = entity_data.get("name", "")
                if entity_id:
                    skills = self._analyze_skills(entity_type, entity_name)
                    if skills:
                        for skill in skills:
                            self.world.entities[entity_id].add_skill(skill)
                        print(f"  [技能] {entity_name}: {skills}", flush=True)
                    self._explore_surrounding_terrain(entity_id)
        
        print(f"[AI] 执行了 {len(results)} 个动作", flush=True)
        for r in results:
            rd = r['result']
            if rd.get("success"):
                ed = rd.get("result", {})
                print(f"  - {r['tool']}: {ed.get('name', ed.get('id', 'OK'))}", flush=True)
            else:
                print(f"  - {r['tool']}: 失败 - {rd.get('error', 'unknown')}", flush=True)
        
        return {
            "success": True,
            "response": f"执行了 {len(results)} 个操作",
            "tool_results": results,
            "world_state": self.world.get_state()
        }
    
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
    
