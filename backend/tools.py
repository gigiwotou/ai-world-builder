from typing import Dict, List, Any, Callable
import json


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_entity",
            "description": "在世界中创建新实体（植物、动物、建筑、资源等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "enum": ["land", "plant", "creature", "building", "resource", "water", "fire"],
                        "description": "实体类型"
                    },
                    "x": {"type": "integer", "description": "X坐标（任意整数，可为负）"},
                    "y": {"type": "integer", "description": "Y坐标（任意整数，可为负）"},
                    "name": {"type": "string", "description": "名称（可选）"},
                    "description": {"type": "string", "description": "描述（可选）"},
                    "properties": {"type": "object", "description": "额外属性（可选）"}
                },
                "required": ["entity_type", "x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_entity",
            "description": "更新现有实体的属性",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体ID"},
                    "name": {"type": "string", "description": "新名称（可选）"},
                    "description": {"type": "string", "description": "新描述（可选）"},
                    "x": {"type": "integer", "description": "新X坐标（可选）"},
                    "y": {"type": "integer", "description": "新Y坐标（可选）"},
                    "properties": {"type": "object", "description": "额外属性（可选）"}
                },
                "required": ["entity_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_entity",
            "description": "删除世界中的实体",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体ID"}
                },
                "required": ["entity_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_world_state",
            "description": "获取当前世界的完整状态，包括所有实体和规则",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_rule",
            "description": "添加世界运行规则（如生物会移动、植物会生长等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule": {"type": "string", "description": "规则描述"}
                },
                "required": ["rule"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_entities_by_type",
            "description": "按类型获取实体列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string", "description": "实体类型"}
                },
                "required": ["entity_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_event",
            "description": "记录一个事件到世界历史",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "事件消息"}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_entity",
            "description": "移动实体到新位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体ID"},
                    "x": {"type": "integer", "description": "目标X坐标"},
                    "y": {"type": "integer", "description": "目标Y坐标"}
                },
                "required": ["entity_id", "x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_entity_behavior",
            "description": "设置实体的长期行为（如向四周探索、休息、觅食等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "实体名称"},
                    "behavior": {"type": "string", "description": "行为描述"}
                },
                "required": ["entity_name", "behavior"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_entity_temp_behavior",
            "description": "设置实体的临时行为，持续指定tick数",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "实体名称"},
                    "behavior": {"type": "string", "description": "临时行为描述"},
                    "duration": {"type": "integer", "description": "持续tick数"}
                },
                "required": ["entity_name", "behavior", "duration"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_type_skill",
            "description": "给某类型的所有实体添加技能",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string", "description": "实体类型"},
                    "skill": {"type": "string", "description": "技能名称"}
                },
                "required": ["entity_type", "skill"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_entity_by_name",
            "description": "根据名称查找实体ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "实体名称"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "entity_ask",
            "description": "具有思考能力的实体可以向AI提问一个问题",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "提问的实体名称"},
                    "question": {"type": "string", "description": "实体想要问的问题"}
                },
                "required": ["entity_name", "question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_intent",
            "description": "分析用户指令的意图，返回结构化数据供后续执行",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "用户的原始指令"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explore_terrain",
            "description": "探索指定坐标周围3x3区域的地形，由AI决定每个坐标的地形类型",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "中心X坐标"},
                    "y": {"type": "integer", "description": "中心Y坐标"}
                },
                "required": ["x", "y"]
            }
        }
    }
]


class ToolExecutor:
    def __init__(self, world_manager, llm_adapter=None):
        self.world = world_manager
        self.llm = llm_adapter
        self.tools: Dict[str, Callable] = {
            "create_entity": self._create_entity,
            "update_entity": self._update_entity,
            "delete_entity": self._delete_entity,
            "get_world_state": self._get_world_state,
            "add_rule": self._add_rule,
            "get_entities_by_type": self._get_entities_by_type,
            "log_event": self._log_event,
            "move_entity": self._move_entity,
            "set_entity_behavior": self._set_entity_behavior,
            "set_entity_temp_behavior": self._set_entity_temp_behavior,
            "add_type_skill": self._add_type_skill,
            "find_entity_by_name": self._find_entity_by_name,
            "entity_ask": self._entity_ask,
            "explore_terrain": self._explore_terrain,
            "analyze_intent": self._analyze_intent
        }
    
    def execute(self, tool_name: str, arguments: Dict, max_retries: int = 2) -> Dict:
        if tool_name not in self.tools:
            return {"success": False, "error": f"未知工具: {tool_name}"}
        
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = self.tools[tool_name](arguments)
                if isinstance(result, dict) and "error" in result:
                    if attempt < max_retries:
                        last_error = result.get("error")
                        continue
                    return {"success": False, "error": result.get("error")}
                return {"success": True, "result": result}
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    continue
        
        return {"success": False, "error": f"重试{max_retries}次后仍失败: {last_error}"}
    
    def _create_entity(self, args: Dict) -> Dict:
        entity = self.world.create_entity(
            entity_type=args["entity_type"],
            x=args["x"],
            y=args["y"],
            name=args.get("name", ""),
            description=args.get("description", ""),
            **(args.get("properties", {}))
        )
        if entity is None:
            return {"success": False, "error": "创建失败：位置被占用或坐标无效"}
        return entity.to_dict()
    
    def _update_entity(self, args: Dict) -> Dict:
        entity = self.world.update_entity(
            entity_id=args["entity_id"],
            name=args.get("name"),
            description=args.get("description"),
            x=args.get("x"),
            y=args.get("y"),
            properties=args.get("properties")
        )
        if entity:
            return entity.to_dict()
        return {"error": "实体不存在"}
    
    def _delete_entity(self, args: Dict) -> Dict:
        success = self.world.delete_entity(args["entity_id"])
        return {"deleted": success}
    
    def _get_world_state(self, args: Dict) -> Dict:
        return self.world.get_state()
    
    def _add_rule(self, args: Dict) -> Dict:
        self.world.add_rule(args["rule"])
        return {"rule": args["rule"], "total_rules": len(self.world.rules)}
    
    def _get_entities_by_type(self, args: Dict) -> Dict:
        entities = self.world.get_entities_by_type(args["entity_type"])
        return {"entities": [e.to_dict() for e in entities], "count": len(entities)}
    
    def _log_event(self, args: Dict) -> Dict:
        self.world.add_event(args["message"])
        return {"logged": True}
    
    def _move_entity(self, args: Dict) -> Dict:
        entity = self.world.update_entity(
            entity_id=args["entity_id"],
            x=args["x"],
            y=args["y"]
        )
        if entity:
            return entity.to_dict()
        return {"error": "实体不存在"}
    
    def _set_entity_behavior(self, args: Dict) -> Dict:
        entity = self.world.find_entity_by_name(args["entity_name"])
        if entity:
            self.world.set_entity_behavior(entity.id, args["behavior"])
            return {"success": True, "entity": entity.to_dict(), "behavior": args["behavior"]}
        return {"error": f"找不到实体: {args['entity_name']}"}
    
    def _set_entity_temp_behavior(self, args: Dict) -> Dict:
        entity = self.world.find_entity_by_name(args["entity_name"])
        if entity:
            self.world.set_entity_temp_behavior(entity.id, args["behavior"], args["duration"])
            return {"success": True, "entity": entity.to_dict(), "temp_behavior": args["behavior"], "duration": args["duration"]}
        return {"error": f"找不到实体: {args['entity_name']}"}
    
    def _add_type_skill(self, args: Dict) -> Dict:
        success = self.world.add_type_skill(args["entity_type"], args["skill"])
        if success:
            return {"success": True, "entity_type": args["entity_type"], "skill": args["skill"]}
        return {"error": f"技能已存在或类型无效"}
    
    def _find_entity_by_name(self, args: Dict) -> Dict:
        entity = self.world.find_entity_by_name(args["name"])
        if entity:
            return {"entity_id": entity.id, "name": entity.name, "type": entity.type, "x": entity.x, "y": entity.y}
        return {"error": f"找不到实体: {args['name']}"}
    
    def _entity_ask(self, args: Dict) -> Dict:
        entity = self.world.find_entity_by_name(args["entity_name"])
        if not entity:
            return {"error": f"找不到实体: {args['entity_name']}"}
        
        if "思考" not in entity.skills and "思考能力" not in entity.skills:
            return {"error": f"{entity.name}没有思考能力，无法提问"}
        
        if not self.llm:
            return {"error": "AI未连接，无法回答问题"}
        
        question = args["question"]
        
        messages = [
            {"role": "system", "content": f"你是{entity.name}，一个虚拟世界中的生物。你正在向世界管理者提问。\n\n你的问题：{question}\n\n请用简短的一句话回答这个问题。"},
        ]
        
        response = self.llm.chat(messages)
        
        if "error" in response:
            return {"error": response["error"]}
        
        answer = response.get("message", {}).get("content", "...")
        
        self.world.add_event(f"{entity.name}思考: {question} → {answer}")
        
        return {
            "success": True,
            "entity": entity.name,
            "question": question,
            "answer": answer
        }
    
    def _explore_terrain(self, args: Dict) -> Dict:
        x, y = args["x"], args["y"]
        surrounding = self.world.get_surrounding_9(x, y)
        
        prompt = f"""你是一个世界地形规划者AI。你的任务是根据给定的中心坐标和周围地形，判断其中未探索的区域应该是什么地形。

**当前已探索区域**:
{json.dumps(surrounding, ensure_ascii=False, indent=2)}

**世界已知规则**:
- 陆地很大，海洋更大，河流很长，山比生物大几倍
- 地形类型：陆地、山川、河流、海洋、未探索

请为每个"未探索"的坐标，决定其地形类型。返回一个JSON列表，每个元素包含x, y和terrain_type。

示例格式:
[
  {{"x": 1, "y": 1, "terrain_type": "陆地"}},
  {{"x": 1, "y": 2, "terrain_type": "河流"}}
]

只需返回JSON列表，不要任何其他文字。"""
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.llm.chat(messages)
            if "error" in response:
                return {"error": response["error"]}
            
            content = response.get("message", {}).get("content", "")
            if not content:
                return {"success": False, "message": "LLM未返回地形信息"}
            
            terrain_decisions = json.loads(content)
            
            explored_count = 0
            for td in terrain_decisions:
                nx, ny, terrain_type = td["x"], td["y"], td["terrain_type"]
                if self.world.get_terrain_at(nx, ny) == "未探索":
                    self.world.explore_terrain(nx, ny, terrain_type)
                    explored_count += 1
            
            return {"success": True, "explored_count": explored_count, "new_terrain": terrain_decisions}
            
        except Exception as e:
            return {"success": False, "error": str(e), "raw_response": response}
    
    def _analyze_intent(self, args: Dict) -> Dict:
        """
        分析用户指令意图，返回结构化数据
        返回格式：
        {
            "action": "create_entity" | "move_entity" | "set_behavior" | "delete_entity" | "add_rule" | "none",
            "entity_type": "creature" | "plant" | ...,
            "entity_name": "xxx",
            "x": 0, "y": 0,
            "behavior": "向四周探索",
            "description": "xxx",
            "reason": "为什么做这个决定"
        }
        """
        command = args.get("command", "")
        
        prompt = f"""你是一个指令分析器。请分析以下用户指令，返回结构化数据。

用户指令：{command}

请返回JSON格式的分析结果：
{{
    "action": "操作类型(create_entity/move_entity/set_behavior/delete_entity/add_rule/none)",
    "entity_type": "实体类型(creature/plant/building/resource/water/fire/land)",
    "entity_name": "实体名称(如果适用)",
    "x": 数字坐标X(如果适用),
    "y": 数字坐标Y(如果适用),
    "behavior": "行为描述(如果适用)",
    "description": "描述(如果适用)",
    "reason": "你为什么做这个分析"
}}

规则：
- 只返回JSON，不要其他文字
- 如果指令不明确需要创建实体，action设为"create_entity"
- 坐标默认为0,0
- entity_type根据名称推断：
  - 人/男/女/小明/小红/动物 → creature
  - 树/草/花/森林 → plant
  - 房/屋/村庄/城市 → building
  - 水/河/湖/海 → water
  - 矿/金/银/铁/石 → resource
  - 火 → fire
  - 地/陆地 → land

只返回JSON！"""

        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = self.llm.chat(messages)
            if "error" in response:
                return {"error": response["error"]}
            
            content = response.get("message", {}).get("content", "")
            
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                return {"result": result}
            else:
                return {"result": {"error": "无法解析JSON", "raw": content}}
                
        except Exception as e:
            return {"result": {"error": str(e)}}
