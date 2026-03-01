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
    }
]


class ToolExecutor:
    def __init__(self, world_manager):
        self.world = world_manager
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
            "find_entity_by_name": self._find_entity_by_name
        }
    
    def execute(self, tool_name: str, arguments: Dict) -> Dict:
        if tool_name not in self.tools:
            return {"success": False, "error": f"未知工具: {tool_name}"}
        
        try:
            result = self.tools[tool_name](arguments)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _create_entity(self, args: Dict) -> Dict:
        entity = self.world.create_entity(
            entity_type=args["entity_type"],
            x=args["x"],
            y=args["y"],
            name=args.get("name", ""),
            description=args.get("description", ""),
            **(args.get("properties", {}))
        )
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
