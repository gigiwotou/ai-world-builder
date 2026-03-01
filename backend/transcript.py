import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


class Transcript:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.transcript_dir = self.data_dir / "transcripts"
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: List[Dict] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def add_user_message(self, content: str):
        self.current_session.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_ai_message(self, content: str):
        self.current_session.append({
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_tool_call(self, tool_name: str, args: Dict, result: Any):
        self.current_session.append({
            "role": "tool",
            "tool": tool_name,
            "args": args,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_world_state(self, state: Dict):
        self.current_session.append({
            "role": "world_state",
            "tick": state.get("tick", 0),
            "entity_count": len(state.get("entities", [])),
            "timestamp": datetime.now().isoformat()
        })
    
    def add_error(self, error: str):
        self.current_session.append({
            "role": "error",
            "content": error,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_session(self) -> List[Dict]:
        return self.current_session
    
    def save(self):
        if not self.current_session:
            return
        
        transcript_file = self.transcript_dir / f"session_{self.session_id}.jsonl"
        with open(transcript_file, "w", encoding="utf-8") as f:
            for entry in self.current_session:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def load_latest(self) -> List[Dict]:
        transcript_files = sorted(self.transcript_dir.glob("session_*.jsonl"))
        if not transcript_files:
            return []
        
        latest_file = transcript_files[-1]
        sessions = []
        with open(latest_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    sessions.append(json.loads(line.strip()))
                except:
                    pass
        return sessions
    
    def get_summary(self) -> str:
        user_count = sum(1 for e in self.current_session if e.get("role") == "user")
        tool_count = sum(1 for e in self.current_session if e.get("role") == "tool")
        error_count = sum(1 for e in self.current_session if e.get("role") == "error")
        
        return f"Session {self.session_id}: {user_count} user messages, {tool_count} tool calls, {error_count} errors"
    
    def clear(self):
        self.current_session = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
