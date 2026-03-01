import json
import uuid
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class Entity:
    def __init__(self, entity_type: str, x: int, y: int, name: str = "", description: str = "", **properties):
        self.id = str(uuid.uuid4())[:8]
        self.type = entity_type
        self.x = x
        self.y = y
        self.name = name or entity_type
        self.description = description
        self.properties = properties
        self.behavior = properties.get("behavior", "")
        self.skills = properties.get("skills", [])
        self.temp_behavior = properties.get("temp_behavior", {})
        self.created_at = datetime.now().isoformat()
        
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "name": self.name,
            "description": self.description,
            "properties": self.properties,
            "behavior": self.behavior,
            "skills": self.skills,
            "temp_behavior": self.temp_behavior,
            "created_at": self.created_at
        }
    
    def set_behavior(self, behavior: str):
        self.behavior = behavior
        self.properties["behavior"] = behavior
        
    def set_temp_behavior(self, behavior: str, duration: int, start_tick: int = 0):
        self.temp_behavior = {
            "behavior": behavior,
            "duration": duration,
            "start_tick": start_tick
        }
        self.properties["temp_behavior"] = self.temp_behavior
        
    def add_skill(self, skill: str):
        if skill not in self.skills:
            self.skills.append(skill)
            self.properties["skills"] = self.skills
            
    def get_active_behavior(self, current_tick: int = 0) -> str:
        if self.temp_behavior and self.temp_behavior.get("duration", 0) > 0:
            start = self.temp_behavior.get("start_tick", 0)
            duration = self.temp_behavior.get("duration", 0)
            if current_tick < start + duration:
                return self.temp_behavior["behavior"]
            else:
                self.temp_behavior = {}
                self.properties["temp_behavior"] = {}
        return self.behavior
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Entity":
        e = cls(data["type"], data["x"], data["y"], data.get("name", ""), data.get("description", ""), **data.get("properties", {}))
        e.id = data.get("id", e.id)
        e.created_at = data.get("created_at", e.created_at)
        e.behavior = data.get("behavior", "")
        e.skills = data.get("skills", [])
        e.temp_behavior = data.get("temp_behavior", {})
        return e


class EntityManager:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.entities_dir = self.data_dir / "entities"
        self.entities_dir.mkdir(parents=True, exist_ok=True)
        
    def save_entity(self, entity: Entity):
        entity_file = self.entities_dir / f"{entity.id}.json"
        with open(entity_file, "w", encoding="utf-8") as f:
            json.dump(entity.to_dict(), f, ensure_ascii=False, indent=2)
            
    def load_entity(self, entity_id: str) -> Optional[Entity]:
        entity_file = self.entities_dir / f"{entity_id}.json"
        if entity_file.exists():
            try:
                with open(entity_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return Entity.from_dict(data)
            except:
                pass
        return None
    
    def delete_entity(self, entity_id: str):
        entity_file = self.entities_dir / f"{entity_id}.json"
        if entity_file.exists():
            entity_file.unlink()
        
        memory_file = self.entities_dir / f"{entity_id}_memory.md"
        if memory_file.exists():
            memory_file.unlink()
    
    def load_all_entities(self) -> Dict[str, Entity]:
        entities = {}
        for f in self.entities_dir.glob("*.json"):
            if f.stem.endswith("_memory"):
                continue
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    entity = Entity.from_dict(data)
                    entities[entity.id] = entity
            except:
                pass
        return entities
    
    def get_entity_memory_path(self, entity_id: str) -> Path:
        return self.entities_dir / f"{entity_id}_memory.md"
    
    def read_entity_memory(self, entity_id: str) -> str:
        memory_file = self.get_entity_memory_path(entity_id)
        if memory_file.exists():
            with open(memory_file, "r", encoding="utf-8") as f:
                return f.read()
        return ""
    
    def write_entity_memory(self, entity_id: str, content: str):
        memory_file = self.get_entity_memory_path(entity_id)
        with open(memory_file, "w", encoding="utf-8") as f:
            f.write(content)
    
    def append_entity_memory(self, entity_id: str, content: str):
        memory_file = self.get_entity_memory_path(entity_id)
        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(f"\n{content}")
