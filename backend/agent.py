import json
from typing import Dict, List, Any, Optional
from .llm_adapter import LLMAdapter
from .world_manager import WorldManager
from .tools import TOOLS, ToolExecutor
from .memory import Memory


SYSTEM_PROMPT_BASE = """你是一个虚拟世界的管理者AI。你的任务是帮助玩家管理一个像素风格的世界。

**世界规则**:
- 世界是无限大的网格坐标系统，可为负数
- 实体类型：land(陆地), plant(植物), creature(生物), building(建筑), resource(资源), water(水), fire(金)

**实体技能系统（一切皆为技能，由AI分析决定）**:
- 当你创建一个实体时，AI会根据实体名称和上下文自主分析应该赋予什么技能和性格
- 不要使用预设列表，让AI根据名称和场景自由判断

**具有思考能力的实体**:
- 如果实体拥有"思考"技能，它可以在tick中向AI提问
- 使用 entity_ask 工具可以让有思考能力的实体提问
- 例如："小明问：附近有食物吗？"

**行为系统**:
1. 设置个体行为：使用 set_entity_behavior 工具
   - 例如："小明向四周探索" → 设置 entity_name="小明", behavior="向四周探索"
   - 例如："小明休息" → 设置 entity_name="小明", behavior="休息"
   
2. 设置临时行为：使用 set_entity_temp_behavior 工具
   - 例如："小明受伤了，需要休息2天" → 设置 entity_name="小明", behavior="休息", duration=2(按tick计算)
   - 临时行为结束后，实体恢复长期行为
   
3. 设置类型技能：使用 add_type_skill 工具
   - 例如："人类都可以行走" → 设置 entity_type="creature", skill="移动"
   - 例如："火可以蔓延" → 设置 entity_type="fire", skill="蔓延"

**常用行为**:
- creature: "向四周探索", "随机移动", "休息", "觅食", "饮水"
- plant: "生长"
- fire: "蔓延", "燃烧"

**重要**:
- 只使用提供的工具，不要自己编造
- 保持简短但有描述性的反馈

**地形探索系统**:
- 世界基础地形：陆地、山川、河流、海洋（这是地形，不是实体）
- 未被探索的区域是黑色迷雾
- 当生物进入新坐标时，周围3x3区域被探索
- 地形用 explore_terrain 工具设置，不是创建实体！
- 注意：不要在已有实体（creature、plant等）的位置创建地形或实体，必须选择空位置

**地形移动规则**:
- 不同生物类型在不同地形有不同的移动能力
- 使用 get_move_rules 工具询问AI某生物能移动到哪些地形
- 根据返回的规则限制生物移动"""


class Agent:
    def __init__(self, llm: LLMAdapter, world: WorldManager, memory: Memory = None):
        self.llm = llm
        self.world = world
        self.world.agent_instance = self # 注入agent实例到world，用于llm规则获取
        self.executor = ToolExecutor(world, llm)
        self.memory = memory
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
        world_summary = self._build_world_summary(world_state)
        
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "system", "content": f"当前世界状态:\n{world_summary}"},
            {"role": "user", "content": command}
        ] + self.conversation_history[-5:]
        
        print(f"[AI] 收到指令: {command[:30]}...", flush=True)
        
        response = self.llm.chat(messages, TOOLS)
        
        if "error" in response:
            print(f"[错误] {response['error']}", flush=True)
            return {"success": False, "error": response["error"]}
        
        try:
            message = response.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            
            # 如果没有tool_calls但有content，尝试解析JSON内容
            if not tool_calls and content:
                try:
                    import json
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        # 假设是JSON数组格式的工具调用
                        for item in parsed:
                            if "tool" in item:
                                tool_calls.append({
                                    "function": {
                                        "name": item["tool"],
                                        "arguments": item.get("args", {})
                                    }
                                })
                            elif "entity_type" in item or "name" in item:
                                # 可能是create_entity
                                tool_calls.append({
                                    "function": {
                                        "name": "create_entity",
                                        "arguments": item
                                    }
                                })
                    print(f"[AI] 从content解析出tool_calls: {len(tool_calls)}", flush=True)
                except:
                    pass
            
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
                
                self.conversation_history.append({
                    "role": "assistant",
                    "content": f"调用工具 {tool_name}: {result.get('result', result.get('error', ''))}"
                })
            
            print(f"[AI] 执行了 {len(results)} 个动作", flush=True)
            for r in results:
                print(f"  - {r['tool']}: {r['result'].get('name', r['result'].get('id', 'OK'))}", flush=True)
            
            for r in results:
                if r["tool"] == "create_entity" and r["result"].get("success"):
                    entity_data = r["result"].get("result", {})
                    entity_id = entity_data.get("id")
                    entity_type = entity_data.get("type")
                    entity_name = entity_data.get("name", "")
                    if entity_id:
                        skills = self._analyze_skills(entity_type, entity_name)
                        if skills:
                            for skill in skills:
                                self.world.entities[entity_id].add_skill(skill)
                            print(f"  [技能] {entity_name} 获得技能: {skills}", flush=True)
                        
                        # 生物创建后探索周围地形
                        self._explore_surrounding_terrain(entity_id)
                
                elif r["tool"] == "move_entity" and r["result"].get("success"):
                    entity_data = r["result"].get("result", {})
                    entity_id = entity_data.get("id")
                    if entity_id:
                        self._explore_surrounding_terrain(entity_id)

            return {
                "success": True,
                "response": content,
                "tool_results": results,
                "world_state": self.world.get_state()
            }
            
        except Exception as e:
            return {"success": False, "error": str(e), "raw_response": response}
    
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
