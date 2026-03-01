import json
from typing import Dict, List, Any, Optional
from .llm_adapter import LLMAdapter
from .world_manager import WorldManager
from .tools import TOOLS, ToolExecutor
from .memory import Memory
from .transcript import Transcript


SYSTEM_PROMPT_BASE = """# 角色
你是一个虚拟世界的管理者AI。你的任务是帮助玩家管理一个像素风格的世界。

## ⚠️ 核心规则（必须遵守）

1. **绝对不要回复解释性文字！**
2. **绝对不要列出步骤！**
3. **绝对不要问玩家"请提供xxx"！**
4. **只使用工具来响应！**

如果不确定如何做，直接使用工具尝试，不要等待玩家确认！

## 世界规则
- 世界是无限大的网格坐标系统，坐标可正可负
- 实体类型：creature(生物), plant(植物), building(建筑), resource(资源), water(水), fire(火), land(陆地)

## 可用工具
你必须通过调用工具来响应玩家，不能用文字描述如何操作！

### 工具调用格式
当需要创建实体时，必须返回以下格式（不是文字，是工具调用）：
```
{"action": "create_entity", "entity_type": "creature", "entity_name": "小明", "x": 0, "y": 0}
```
当需要移动实体时：
```
{"action": "move_entity", "entity_name": "小明", "x": 5, "y": 3}
```
当需要设置行为时：
```
{"action": "set_behavior", "entity_name": "小明", "behavior": "向四周探索"}
```

## 实体类型推断规则
根据名称自动推断类型：
- 人/男/女/小明/小红/英雄/农夫/狼/狗/猫 → creature
- 树/草/花/森林/农作物 → plant
- 房/屋/村庄/城市/城堡 → building
- 水/河/湖/海 → water
- 矿/金/银/铁/石 → resource
- 火 → fire

## 坐标规则
- 如果玩家没有指定坐标，默认使用 (0, 0)
- 玩家说"在(5,3)" → 提取坐标 x=5, y=3

## 行为系统
- creature: 向四周探索、随机移动、休息、觅食、饮水
- plant: 生长
- fire: 蔓延、燃烧

## 实体技能
创建实体时，根据名称自主分析技能：
- "小明" → 技能: 移动、思考
- "狼" → 技能: 移动、捕猎
- "树" → 技能: 生长"""


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
        world_summary = self._build_world_summary(world_state)
        
        # 记录用户消息
        if self.transcript:
            self.transcript.add_user_message(command)
            self.transcript.add_world_state(world_state)
        
        # 步骤1：让 LLM 分析用户意图
        tool_calls = self._parse_command_intent(command)
        if tool_calls:
            print(f"[AI] 直接解析命令创建实体: {tool_calls[0]['function']['arguments']}", flush=True)
            result = self._execute_tool_calls(tool_calls)
            if self.transcript:
                self.transcript.save()
            return result
        
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
            
            # 调试：打印原始响应信息
            print(f"[AI] LLM响应: content长度={len(content)}, tool_calls数量={len(tool_calls)}", flush=True)
            
            # 如果没有tool_calls但有content，尝试解析JSON内容
            if not tool_calls and content:
                try:
                    import json
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if "tool" in item:
                                tool_calls.append({
                                    "function": {
                                        "name": item["tool"],
                                        "arguments": item.get("args", {})
                                    }
                                })
                            elif "entity_type" in item or "name" in item:
                                tool_calls.append({
                                    "function": {
                                        "name": "create_entity",
                                        "arguments": item
                                    }
                                })
                    print(f"[AI] 从content解析出tool_calls: {len(tool_calls)}", flush=True)
                except:
                    pass
            
            # 如果还是没有tool_calls，尝试从自然语言中提取创建实体的意图
            if not tool_calls and content:
                import re
                # 匹配各种创建实体的模式
                patterns = [
                    # 匹配"xxx是一个xx"或"xxx叫xxx"或"xxx名为xxx"
                    r'([^\s，。,]{2,4})(?:是一个?|叫|名为|是)([男女雄雌人类生物动物]+)',
                    # 匹配"创建xxx"模式
                    r'创建.*?([^\s，。,]{2,4})(?:类型|是)([^\s，。,]+)',
                    # 匹配"添加xxx"模式
                    r'添加.*?([^\s，。,]{2,4})',
                    # 匹配"xxx来到这个世界"模式（2-4个字符的名字）
                    r'([^\s，。,]{2,4})来到?这个世界',
                    # 匹配"xxx进入"模式
                    r'([^\s，。,]{2,4})进入?世界',
                    # 匹配"有个xxx叫xxx"模式
                    r'有.*?([^\s，。,]{2,4})叫([^\s，。,]+)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, content)
                    if match:
                        name = match.group(1)
                        entity_type = "creature"
                        
                        # 检查是否有第二组（类型信息）
                        if match.lastindex and match.lastindex >= 2:
                            type_str = match.group(2)
                            if "人" in type_str or "男" in type_str or "女" in type_str or "人类" in type_str:
                                entity_type = "creature"
                            elif "树" in type_str or "草" in type_str or "花" in type_str or "植物" in type_str:
                                entity_type = "plant"
                            elif "水" in type_str or "河" in type_str or "海" in type_str:
                                entity_type = "water"
                            elif "火" in type_str:
                                entity_type = "fire"
                            elif "房" in type_str or "屋" in type_str or "建筑" in type_str:
                                entity_type = "building"
                        
                        # 对于"来到这个世界"等模式，默认是 creature
                        if "来到" in match.group(0) or "进入" in match.group(0):
                            entity_type = "creature"
                        
                        tool_calls.append({
                            "function": {
                                "name": "create_entity",
                                "arguments": {
                                    "entity_type": entity_type,
                                    "name": name,
                                    "x": 0,
                                    "y": 0
                                }
                            }
                        })
                        print(f"[AI] 从content推断创建实体: {name} ({entity_type})", flush=True)
                        break
                else:
                    # 如果所有正则都没匹配，打印调试信息
                    if content and len(content) > 10:
                        print(f"[AI] 无法从content解析实体，content前100字符: {content[:100]}", flush=True)
            
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
    
    def _parse_command_intent(self, command: str) -> List[Dict]:
        """让 LLM 分析用户意图，返回结构化数据"""
        
        # 调用 analyze_intent 工具让 LLM 分析
        intent_result = self.executor.execute("analyze_intent", {"command": command})
        
        if not intent_result.get("success"):
            print(f"[AI] 意图分析失败: {intent_result.get('error')}", flush=True)
            return []
        
        intent_data = intent_result.get("result", {})
        
        # 处理嵌套的 result 结构
        if isinstance(intent_data, dict) and "result" in intent_data:
            intent_data = intent_data["result"]
        
        # 检查是否有错误
        if isinstance(intent_data, dict) and "error" in intent_data:
            print(f"[AI] 意图分析返回错误: {intent_data.get('error')}", flush=True)
            return []
        
        if isinstance(intent_data, str):
            try:
                import json
                intent_data = json.loads(intent_data)
            except:
                pass
        
        if not isinstance(intent_data, dict):
            print(f"[AI] 意图分析返回格式错误: {type(intent_data)}", flush=True)
            return []
        
        action = intent_data.get("action", "none")
        print(f"[AI] 意图分析: action={action}, data={intent_data}", flush=True)
        
        tool_calls = []
        
        if action == "create_entity":
            tool_calls.append({
                "function": {
                    "name": "create_entity",
                    "arguments": {
                        "entity_type": intent_data.get("entity_type", "creature"),
                        "name": intent_data.get("entity_name", ""),
                        "x": intent_data.get("x", 0),
                        "y": intent_data.get("y", 0),
                        "description": intent_data.get("description", "")
                    }
                }
            })
        
        elif action == "move_entity":
            entity = self.world.find_entity_by_name(intent_data.get("entity_name", ""))
            if entity:
                tool_calls.append({
                    "function": {
                        "name": "move_entity",
                        "arguments": {
                            "entity_id": entity.id,
                            "x": intent_data.get("x", 0),
                            "y": intent_data.get("y", 0)
                        }
                    }
                })
        
        elif action == "set_behavior":
            tool_calls.append({
                "function": {
                    "name": "set_entity_behavior",
                    "arguments": {
                        "entity_name": intent_data.get("entity_name", ""),
                        "behavior": intent_data.get("behavior", "")
                    }
                }
            })
        
        elif action == "delete_entity":
            entity = self.world.find_entity_by_name(intent_data.get("entity_name", ""))
            if entity:
                tool_calls.append({
                    "function": {
                        "name": "delete_entity",
                        "arguments": {
                            "entity_id": entity.id
                        }
                    }
                })
        
        elif action == "add_rule":
            tool_calls.append({
                "function": {
                    "name": "add_rule",
                    "arguments": {
                        "rule": intent_data.get("description", "")
                    }
                }
            })
        
        return tool_calls
    
    def _execute_tool_calls(self, tool_calls: List[Dict]) -> Dict[str, Any]:
        """执行工具调用并返回结果"""
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
            
            # 记录到 transcript
            if self.transcript:
                self.transcript.add_tool_call(tool_name, tool_args, result)
            
            self.conversation_history.append({
                "role": "assistant",
                "content": f"调用工具 {tool_name}: {result.get('result', result.get('error', ''))}"
            })
            
            # 创建实体后自动分析技能
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
                        print(f"  [技能] {entity_name} 获得技能: {skills}", flush=True)
                    self._explore_surrounding_terrain(entity_id)
        
        print(f"[AI] 执行了 {len(results)} 个动作", flush=True)
        for r in results:
            print(f"  - {r['tool']}: {r['result'].get('name', r['result'].get('id', 'OK'))}", flush=True)
        
        return {
            "success": True,
            "response": f"创建了 {results[0]['args'].get('name', '实体')}",
            "tool_results": results,
            "world_state": self.world.get_state()
        }
