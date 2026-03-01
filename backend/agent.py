from typing import Dict, List, Any, Optional
from .llm_adapter import LLMAdapter
from .world_manager import WorldManager
from .tools import TOOLS, ToolExecutor
from .memory import Memory


SYSTEM_PROMPT_BASE = """你是一个虚拟世界的管理者AI。你的任务是帮助玩家管理一个像素风格的世界。

**世界规则**:
- 世界是无限大的网格坐标系统，可为负数
- 实体类型：land(陆地), plant(植物), creature(生物), building(建筑), resource(资源), water(水), fire(金)

**行为系统**:
1. 设置个体行为：使用 set_entity_behavior 工具
   - 例如："小明向四周探索" → 设置 entity_name="小明", behavior="向四周探索"
   - 例如："小明休息" → 设置 entity_name="小明", behavior="休息"
   
2. 设置临时行为：使用 set_entity_temp_behavior 工具
   - 例如："小明受伤了，需要休息2天" → 设置 entity_name="小明", behavior="休息", duration=2(按tick计算)
   - 临时行为结束后，实体恢复长期行为
   
3. 设置类型技能：使用 add_type_skill 工具
   - 例如："人类都可以行走" → 设置 entity_type="creature"(人类), skill="移动"
   - 例如："火可以蔓延" → 设置 entity_type="fire", skill="蔓延"

**常用行为**:
- creature: "向四周探索", "随机移动", "休息", "觅食", "饮水"
- plant: "生长"
- fire: "蔓延", "燃烧"

**重要**:
- 只使用提供的工具，不要自己编造
- 保持简短但有描述性的反馈"""


class Agent:
    def __init__(self, llm: LLMAdapter, world: WorldManager, memory: Memory = None):
        self.llm = llm
        self.world = world
        self.executor = ToolExecutor(world)
        self.memory = memory
        self.conversation_history: List[Dict[str, str]] = []
        
    def _build_system_prompt(self) -> str:
        if self.memory:
            context = self.memory.get_context_prompt()
            return f"{SYSTEM_PROMPT_BASE}\n\n---\n\n{context}"
        return SYSTEM_PROMPT_BASE
        
    def execute_command(self, command: str) -> Dict[str, Any]:
        self.conversation_history.append({
            "role": "user",
            "content": command
        })
        
        world_state = self.world.get_state()
        world_summary = self._build_world_summary(world_state)
        
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "system", "content": f"当前世界状态:\n{world_summary}"},
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
        if not world_state["entities"]:
            return {"success": True, "message": "世界为空，无需推进"}
        
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
