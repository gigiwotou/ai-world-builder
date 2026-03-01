import json
import uuid
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from .entity_manager import EntityManager, Entity, TerrainManager


class WorldManager:
    ENTITY_COLORS = {
        "land": "#8B4513",
        "plant": "#228B22", 
        "creature": "#FF6347",
        "building": "#4682B4",
        "resource": "#FFD700",
        "water": "#1E90FF",
        "fire": "#FF4500",
        "default": "#808080"
    }
    
    ENTITY_LABELS = {
        "land": "地",
        "plant": "植",
        "creature": "生",
        "building": "建",
        "resource": "矿",
        "water": "水",
        "fire": "火",
        "default": "？"
    }
    
    TYPE_SKILLS = {
        "creature": ["移动", "觅食", "饮水"],
        "plant": ["生长"],
        "fire": ["燃烧", "蔓延"]
    }
    
    def __init__(self, config: Dict):
        self.config = config
        self.width = config.get("world_width", 800)
        self.height = config.get("world_height", 600)
        self.cell_size = config.get("cell_size", 20)
        self.entities: Dict[str, Entity] = {}
        self.rules: List[str] = []
        self.tick = 0
        self.data_dir = config.get("data_dir", "data")
        self.world_file = os.path.join(self.data_dir, "world.json")
        self.entity_manager = EntityManager(self.data_dir)
        self.terrain_manager = TerrainManager(self.data_dir)
        self.agent_instance = None # 会在Agent初始化时传入
        self._load()
        
    def _load(self):
        if os.path.exists(self.world_file):
            try:
                with open(self.world_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.tick = data.get("tick", 0)
                    self.rules = data.get("rules", [])
            except:
                pass
        self.entities = self.entity_manager.load_all_entities()
    
    def _save(self):
        os.makedirs(self.data_dir, exist_ok=True)
        data = {
            "tick": self.tick,
            "rules": self.rules
        }
        with open(self.world_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        for entity in self.entities.values():
            self.entity_manager.save_entity(entity)
    
    def create_entity(self, entity_type: str, x, y, name: str = "", description: str = "", **properties) -> Optional[Entity]:
        try:
            x = int(x)
            y = int(y)
        except:
            return None
        
        if x is None or y is None:
            return None
        
        for e in self.entities.values():
            if e.x == x and e.y == y:
                return None
        
        entity = Entity(entity_type, x, y, name, description, **properties)
        self.entities[entity.id] = entity
        self.add_event(f"创建了{name or entity_type}")
        self._save()
        return entity
    
    def update_entity(self, entity_id: str, **updates) -> Optional[Entity]:
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            for key, value in updates.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self._save()
            return entity
        return None
    
    def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            del self.entities[entity_id]
            self.entity_manager.delete_entity(entity_id)
            self.add_event(f"删除了{entity.name}")
            self._save()
            return True
        return False
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self.entities.get(entity_id)
    
    def get_entities_at(self, x: int, y: int) -> List[Entity]:
        return [e for e in self.entities.values() if e.x == x and e.y == y]
    
    def add_rule(self, rule: str):
        if rule not in self.rules:
            self.rules.append(rule)
            self.add_event(f"添加了规则: {rule}")
            self._save()
    
    def remove_rule(self, rule: str):
        if rule in self.rules:
            self.rules.remove(rule)
            self._save()
    
    def add_event(self, message: str):
        pass
    
    def tick_world(self):
        self._cleanup_invalid_entities()
        self.tick += 1
        self.execute_behaviors()
        self._save()
    
    def _cleanup_invalid_entities(self):
        invalid_ids = []
        for entity in self.entities.values():
            if entity.x is None or entity.y is None or entity.x == "null" or entity.y == "null":
                invalid_ids.append(entity.id)
        
        for entity_id in invalid_ids:
            if entity_id in self.entities:
                name = self.entities[entity_id].name
                del self.entities[entity_id]
                self.entity_manager.delete_entity(entity_id)
                print(f"[清理] 删除无效实体: {name}")
    
    def execute_behaviors(self):
        import random
        
        creatures = [e for e in self.entities.values() if e.type == "creature"]
        
        for i, entity in enumerate(creatures):
            try:
                entity.x = int(entity.x)
                entity.y = int(entity.y)
            except:
                continue
            
            behavior = entity.get_active_behavior(self.tick)
            
            if not behavior:
                continue
            
            if entity.type == "creature":
                # 获取移动规则
                can_move_terrains = self.get_move_rules_for_entity(entity.type, entity.skills)
                
                if behavior == "向四周探索" or behavior == "随机移动":
                    dx = random.choice([-1, 0, 1])
                    dy = random.choice([-1, 0, 1])
                    if dx != 0 or dy != 0:
                        new_x = max(-1000, min(1000, entity.x + dx))
                        new_y = max(-1000, min(1000, entity.y + dy))
                        
                        target_terrain = self.get_terrain_at(new_x, new_y)
                        if target_terrain == "未探索":
                            # 如果是未探索区域，先不移动，由agent去探索
                            continue
                        
                        if target_terrain in can_move_terrains and \
                           not any(e.x == new_x and e.y == new_y for e in self.entities.values()):
                            entity.x = new_x
                            entity.y = new_y
                            print(f"[移动] {entity.name} 移动到 ({entity.x}, {entity.y}) (地形: {target_terrain})")
                            
                elif behavior == "休息" or behavior == "静止":
                    pass
        
        self._separate_overlapping_creatures()
                    
        for entity in self.entities.values():
            behavior = entity.get_active_behavior(self.tick)
            
            if entity.type == "plant":
                if behavior == "生长":
                    pass
                    
            elif entity.type == "fire":
                if behavior == "蔓延":
                    if random.random() < 0.3:
                        dx = random.choice([-1, 0, 1])
                        dy = random.choice([-1, 0, 1])
                        new_x = entity.x + dx
                        new_y = entity.y + dy
                        
                        target_terrain = self.get_terrain_at(new_x, new_y)
                        if target_terrain == "未探索":
                            continue
                        
                        if not any(e.x == new_x and e.y == new_y for e in self.entities.values()):
                            self.create_entity("fire", new_x, new_y, "火")
    
    def _separate_overlapping_creatures(self):
        import random
        
        creatures = [e for e in self.entities.values() if e.type == "creature"]
        
        for i, entity in enumerate(creatures):
            for j, other in enumerate(creatures[i+1:], i+1):
                if entity.x == other.x and entity.y == other.y:
                    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), 
                                  (-1, -1), (-1, 1), (1, -1), (1, 1)]
                    random.shuffle(directions)
                    
                    for dx, dy in directions:
                        new_x1 = max(-1000, min(1000, entity.x + dx))
                        new_y1 = max(-1000, min(1000, entity.y + dy))
                        
                        occupied = False
                        for e in self.entities.values():
                            if e.id != entity.id and e.id != other.id:
                                if e.x == new_x1 and e.y == new_y1:
                                    occupied = True
                                    break
                        
                        if not occupied:
                            entity.x = new_x1
                            entity.y = new_y1
                            break
    
    def set_entity_behavior(self, entity_id: str, behavior: str) -> bool:
        if entity_id in self.entities:
            self.entities[entity_id].set_behavior(behavior)
            self.add_event(f"设置{self.entities[entity_id].name}的行为: {behavior}")
            self._save()
            return True
        return False
    
    def set_entity_temp_behavior(self, entity_id: str, behavior: str, duration: int) -> bool:
        if entity_id in self.entities:
            self.entities[entity_id].set_temp_behavior(behavior, duration, self.tick)
            self.add_event(f"设置{self.entities[entity_id].name}临时行为: {behavior}({duration}tick)")
            self._save()
            return True
        return False
    
    def add_type_skill(self, entity_type: str, skill: str) -> bool:
        if entity_type not in self.TYPE_SKILLS:
            self.TYPE_SKILLS[entity_type] = []
        if skill not in self.TYPE_SKILLS[entity_type]:
            self.TYPE_SKILLS[entity_type].append(skill)
            self.add_event(f"{entity_type}类型获得技能: {skill}")
            for entity in self.entities.values():
                if entity.type == entity_type:
                    entity.add_skill(skill)
            self._save()
            return True
        return False
    
    def find_entity_by_name(self, name: str) -> Optional[Entity]:
        name_lower = name.lower()
        for entity in self.entities.values():
            if entity.name.lower() == name_lower:
                return entity
            if name_lower in entity.name.lower():
                return entity
        return None
    
    def get_entity_memory(self, entity_id: str) -> str:
        return self.entity_manager.read_entity_memory(entity_id)
    
    def write_entity_memory(self, entity_id: str, content: str):
        self.entity_manager.write_entity_memory(entity_id, content)
    
    def append_entity_memory(self, entity_id: str, content: str):
        self.entity_manager.append_entity_memory(entity_id, content)
    
    def get_terrain_at(self, x: int, y: int) -> str:
        return self.terrain_manager.get_terrain(x, y)
    
    def get_visible_terrain(self, entities: List[Entity], view_range: int = 5) -> Dict:
        visible = {}
        for entity in entities:
            for dx in range(-view_range, view_range + 1):
                for dy in range(-view_range, view_range + 1):
                    x, y = entity.x + dx, entity.y + dy
                    key = f"{x},{y}"
                    if key not in visible:
                        visible[key] = {
                            "x": x,
                            "y": y,
                            "terrain": self.terrain_manager.get_terrain(x, y)
                        }
        return visible
    
    def explore_terrain(self, x: int, y: int, terrain_type: str):
        self.terrain_manager.set_terrain(x, y, terrain_type)
    
    def get_nearby_unexplored(self, x: int, y: int) -> List[tuple]:
        return self.terrain_manager.get_nearby_unexplored(x, y)
    
    def get_surrounding_9(self, x: int, y: int) -> List[Dict]:
        return self.terrain_manager.get_surrounding_9(x, y)
    
    def get_move_rules_for_entity(self, entity_type: str, skills: List[str]) -> List[str]:
        # 这是一个占位符，实际规则从LLM获取
        return self.agent_instance._get_move_rules_from_llm(entity_type, skills)

    def get_state(self) -> Dict:
        terrain_data = {}
        for entity in self.entities.values():
            for dx in range(-15, 16):
                for dy in range(-15, 16):
                    x, y = entity.x + dx, entity.y + dy
                    key = f"{x},{y}"
                    if key not in terrain_data:
                        terrain = self.terrain_manager.get_terrain(x, y)
                        terrain_data[key] = terrain
        
        return {
            "tick": self.tick,
            "entities": [e.to_dict() for e in self.entities.values()],
            "rules": self.rules,
            "stats": {
                "entity_count": len(self.entities),
                "rule_count": len(self.rules)
            },
            "terrain": terrain_data
        }
    
    def get_summary(self) -> str:
        summary = f"世界时间: T={self.tick}\n"
        summary += f"实体数量: {len(self.entities)}\n"
        
        by_type = {}
        for e in self.entities.values():
            by_type[e.type] = by_type.get(e.type, 0) + 1
        
        if by_type:
            summary += "实体类型分布: " + ", ".join([f"{k}:{v}" for k, v in by_type.items()])
        
        if self.rules:
            summary += f"\n当前规则数: {len(self.rules)}"
        
        return summary
    
    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        return [e for e in self.entities.values() if e.type == entity_type]
