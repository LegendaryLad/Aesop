"""
Core game object classes for greenroom3 escape room engine.
Handles 3D positioning, visibility, discovery states, and inventory.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
import json
from copy import deepcopy

class DiscoveryState(Enum):
    """Object discovery states for preventing knowledge leaking."""
    UNKNOWN = "unknown"        # Player hasn't encountered it
    DISCOVERED = "discovered"  # Player aware of existence  
    EXAMINED = "examined"      # Player has inspected closely

class InventoryType(Enum):
    """Types of inventory with different capacities."""
    HANDS = "hands"           # 2 items, 10kg total
    POCKETS = "pockets"       # 5 small items, 5kg total  
    BACKPACK = "backpack"     # 20 items, 30kg total
    SACK = "sack"            # 15 items, 40kg total (slows movement)

@dataclass
class Position3D:
    """3D position in room space."""
    x: float
    y: float  
    z: float
    
    def distance_to(self, other: 'Position3D') -> float:
        """Calculate Euclidean distance to another position."""
        return np.sqrt((self.x - other.x)**2 + 
                      (self.y - other.y)**2 + 
                      (self.z - other.z)**2)
    
    def direction_to(self, other: 'Position3D') -> np.ndarray:
        """Returns unit vector pointing from self to other."""
        vec = np.array([other.x - self.x, 
                       other.y - self.y, 
                       other.z - self.z])
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec
    
    def to_dict(self) -> Dict[str, float]:
        """Serialize to dictionary."""
        return {"x": self.x, "y": self.y, "z": self.z}
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'Position3D':
        """Deserialize from dictionary."""
        return cls(data["x"], data["y"], data["z"])

@dataclass
class InventoryCapacity:
    """Defines carrying capacity limits."""
    max_weight: float      # kg
    max_items: int        
    max_item_size: str    # "small", "medium", "large"

# Default inventory capacities
INVENTORY_LIMITS = {
    InventoryType.HANDS: InventoryCapacity(10, 2, "medium"),
    InventoryType.POCKETS: InventoryCapacity(5, 5, "small"),
    InventoryType.BACKPACK: InventoryCapacity(30, 20, "large"),
    InventoryType.SACK: InventoryCapacity(40, 15, "large"),
}

class GameObject:
    """Base class for all objects in the game world."""
    
    def __init__(self, id: str, **kwargs):
        # Identity
        self.id = id
        self.aliases = kwargs.get('aliases', [])
        
        # Spatial (None if in inventory or quantum)
        self.position: Optional[Position3D] = kwargs.get('position')
        self.container: Optional[str] = kwargs.get('container')  # "player_inventory" or another object id
        
        # Discovery - critical for preventing knowledge leaking
        self.discovery_state = DiscoveryState.UNKNOWN
        self.quantum_properties = kwargs.get('quantum', {})  # Properties not yet determined
        self.collapsed = False  # Has the quantum state collapsed?
        
        # Core properties (physical)
        self.properties = {
            'weight': kwargs.get('weight', 0.1),
            'size': kwargs.get('size', 'small'),  # small/medium/large/huge
            'material': kwargs.get('material', 'unknown'),
            'moveable': kwargs.get('moveable', True),
            'locked': kwargs.get('locked', False),
            'open': kwargs.get('open', True),
            'hidden': kwargs.get('hidden', False),
            'fixed': kwargs.get('fixed', False),  # Permanently attached
        }
        
        # Update properties with any additional kwargs
        for key, value in kwargs.items():
            if key not in ['aliases', 'position', 'container', 'quantum']:
                self.properties[key] = value
        
        # Container functionality
        self.contents: List[str] = []  # IDs of contained objects
        
        # Dynamic properties (LLM-added during gameplay)
        self.dynamic_properties = {}
        
    def visibility_probability(self, player_pos: Position3D, 
                              player_facing: np.ndarray) -> float:
        """Calculate probability player can see this object."""
        if self.container == "player_inventory":
            return 1.0  # Always aware of inventory
        
        if not self.position:
            return 0.0  # Quantum/undefined position
            
        if self.properties.get('hidden'):
            return 0.0  # Explicitly hidden
            
        if self.container:  # Inside something else
            return 0.1  # Might see it sticking out?
        
        # Calculate based on facing angle
        to_object = player_pos.direction_to(self.position)
        angle = np.arccos(np.clip(np.dot(player_facing, to_object), -1, 1))
        
        # Visibility cone (radians)
        if angle < np.pi/4:  # 45° cone in front
            base_prob = 0.9
        elif angle < np.pi/2:  # 90° peripheral
            base_prob = 0.4
        elif angle < 3*np.pi/4:  # 135° barely visible
            base_prob = 0.1
        else:  # Behind
            base_prob = 0.0
            
        # Adjust for distance
        distance = player_pos.distance_to(self.position)
        if distance > 10:
            base_prob *= 0.5
        if distance > 20:
            base_prob *= 0.5
            
        return min(1.0, base_prob)
    
    def is_accessible(self, player_pos: Position3D) -> Tuple[bool, str]:
        """Check if object can be picked up."""
        # Fixed objects cannot be moved
        if self.properties.get('fixed', False):
            return False, "fixed in place"
        
        # Check moveability
        if not self.properties.get('moveable', True):
            return False, "cannot be moved"
        
        # Size check  
        if self.properties.get('size') == 'huge':
            return False, "too large to carry"
            
        # Distance check (must be within reach ~2 meters)
        if self.position and player_pos.distance_to(self.position) > 2.0:
            return False, "too far away"
                
        return True, "accessible"
    
    def collapse_quantum_state(self, chosen_properties: Dict):
        """LLM decides what this object actually is."""
        for key, value in chosen_properties.items():
            if key in self.quantum_properties:
                self.properties[key] = value
        self.quantum_properties = {}
        self.collapsed = True
    
    def to_dict(self, include_hidden: bool = False) -> Dict:
        """Serialize to dictionary for LLM or storage."""
        data = {
            "id": self.id,
            "aliases": self.aliases,
            "discovery_state": self.discovery_state.value,
            "properties": self.properties.copy(),
            "dynamic_properties": self.dynamic_properties.copy(),
            "container": self.container,
            "contents": self.contents.copy(),
            "collapsed": self.collapsed
        }
        
        if self.position:
            data["position"] = self.position.to_dict()
        else:
            data["position"] = None
            
        if include_hidden or self.discovery_state != DiscoveryState.UNKNOWN:
            data["quantum_properties"] = self.quantum_properties
        
        return data

class Player:
    """Represents the player character."""
    
    def __init__(self):
        # Position and orientation
        self.position = Position3D(0, 0, 0)
        self.facing = np.array([0, 1, 0])  # Unit vector (facing +y initially)
        
        # Inventory management
        self.inventory_type = InventoryType.POCKETS  # Default
        self.inventory: List[str] = []  # Object IDs
        
        # Player attributes
        self.strength = 10  # Base strength affects carry capacity
        
        # Knowledge tracking (what player knows exists)
        self.knowledge: Dict[str, bool] = {}
        
    def get_carry_capacity(self) -> InventoryCapacity:
        """Get current carrying capacity based on inventory type and strength."""
        base = INVENTORY_LIMITS[self.inventory_type]
        # Strength modifier: +1kg per strength point above 10
        weight_bonus = max(0, self.strength - 10)
        return InventoryCapacity(
            max_weight=base.max_weight + weight_bonus,
            max_items=base.max_items,
            max_item_size=base.max_item_size
        )
    
    def current_weight(self, objects: Dict[str, GameObject]) -> float:
        """Calculate current inventory weight."""
        return sum(objects[obj_id].properties.get('weight', 0) 
                  for obj_id in self.inventory if obj_id in objects)
    
    def turn_to_face(self, target_pos: Position3D):
        """Update facing direction toward target."""
        self.facing = self.position.direction_to(target_pos)
        
    def look_direction(self, direction: str):
        """Turn to cardinal direction or relative."""
        directions = {
            'north': np.array([0, 1, 0]),
            'south': np.array([0, -1, 0]),
            'east': np.array([1, 0, 0]),
            'west': np.array([-1, 0, 0]),
            'up': np.array([0, 0, 1]),
            'down': np.array([0, 0, -1])
        }
        
        if direction in directions:
            self.facing = directions[direction]
        elif direction == 'around' or direction == 'behind':
            # Flip 180 degrees
            self.facing = -self.facing
    
    def to_dict(self) -> Dict:
        """Serialize player state."""
        return {
            "position": self.position.to_dict(),
            "facing": self.facing.tolist(),
            "inventory": self.inventory.copy(),
            "inventory_type": self.inventory_type.value,
            "strength": self.strength,
            "carry_capacity": {
                "max_weight": self.get_carry_capacity().max_weight,
                "max_items": self.get_carry_capacity().max_items,
                "max_item_size": self.get_carry_capacity().max_item_size
            }
        }


class Room:
    """Represents a room/location in the game."""
    
    def __init__(self, id: str, name: str, description: str = ""):
        self.id = id
        self.name = name
        self.description = description
        self.objects: List[str] = []  # Object IDs in this room
        self.exits: Dict[str, str] = {}  # direction -> room_id
        self.properties = {
            "lighting": "normal",
            "temperature": "comfortable"
        }
        
    def to_dict(self) -> Dict:
        """Serialize room state."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "objects": self.objects.copy(),
            "exits": self.exits.copy(),
            "properties": self.properties.copy()
        }