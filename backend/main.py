import json
import asyncio
import os
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import Dict, Set

from .llm_adapter import LLMAdapter
from .world_manager import WorldManager
from .agent import Agent
from .memory import Memory
from .transcript import Transcript

BASE_DIR = Path(__file__).parent.parent

config = {
    "provider": "ollama",
    "model": "qwen2.5:7b",
    "base_url": "http://localhost:11434",
    "api_key": "",
    "tick_interval": 5,
    "world_width": 800,
    "world_height": 600,
    "cell_size": 20,
    "host": "0.0.0.0",
    "port": 8000,
    "data_dir": str(BASE_DIR / "data")
}

config_file = BASE_DIR / "config" / "settings.json"
if config_file.exists():
    with open(config_file, "r", encoding="utf-8") as f:
        config.update(json.load(f))

llm = LLMAdapter(config)
world = WorldManager(config)
memory = Memory(config["data_dir"])
transcript = Transcript(config["data_dir"])
agent = Agent(llm, world, memory, transcript)

app = FastAPI(title="AI World Builder")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message: Dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except:
                self.active_connections.discard(connection)

manager = ConnectionManager()

running = True

def tick_loop():
    while running:
        try:
            result = agent.auto_tick()
            if result.get("success") and result.get("world_state"):
                asyncio.run(manager.broadcast({
                    "type": "tick",
                    "data": result.get("world_state"),
                    "message": f"T={result['world_state']['tick']} 自动推进完成"
                }))
        except Exception as e:
            print(f"Tick error: {e}")
        import time
        time.sleep(config.get("tick_interval", 5))

import threading
tick_thread = threading.Thread(target=tick_loop, daemon=True)
tick_thread.start()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "welcome",
            "message": "连接到AI世界管理器",
            "world_state": world.get_state()
        })
        
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "command":
                command = data.get("content", "")
                result = agent.execute_command(command)
                await websocket.send_json({
                    "type": "command_result",
                    "result": result,
                    "message": result.get("response", "执行完成")
                })
                await manager.broadcast({
                    "type": "state_update",
                    "world_state": result.get("world_state", world.get_state())
                })
                
            elif msg_type == "get_state":
                await websocket.send_json({
                    "type": "state",
                    "world_state": world.get_state()
                })
                
            elif msg_type == "start_tick":
                await websocket.send_json({
                    "type": "info",
                    "message": "世界自动推进运行中"
                })
                    
            elif msg_type == "stop_tick":
                pass
                
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
        manager.disconnect(websocket)

@app.get("/")
async def get_index():
    html_file = BASE_DIR / "frontend" / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text(encoding="utf-8"))
    return {"message": "前端文件不存在"}

@app.get("/api/status")
async def get_status():
    return {
        "llm_available": llm.is_available(),
        "world": world.get_state(),
        "config": {
            "provider": config.get("provider"),
            "model": config.get("model"),
            "tick_interval": config.get("tick_interval")
        },
        "tokens": llm.get_token_stats()
    }

if __name__ == "__main__":
    import uvicorn
    import sys
    
    print("=" * 50, flush=True)
    print("AI World Builder 启动中...", flush=True)
    print(f"模型: {config.get('model')}", flush=True)
    print(f"服务地址: http://localhost:{config.get('port', 8000)}", flush=True)
    print("请在浏览器打开上述地址", flush=True)
    print("=" * 50, flush=True)
    
    uvicorn.run(app, host=config.get("host", "0.0.0.0"), port=config.get("port", 8000), log_level="info")
