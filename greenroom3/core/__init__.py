"""
Core game engine components for greenroom3.

This module contains the fundamental game mechanics:
- Game objects and spatial relationships
- Player state and inventory management  
- Room management
- State tracking and transactions
- Event history and persistence
"""

from .game_objects import (
    GameObject,
    Player,
    Room,
    Position3D,
    DiscoveryState,
    InventoryType,
    InventoryCapacity,
    INVENTORY_LIMITS
)

from .game_state import (
    GameState,
    StateChange,
    ChangeType,
    ValidationLevel,
    ValidationResult
)

from .history import (
    EventHistory,
    GameEvent
)

__all__ = [
    # Game Objects
    "GameObject",
    "Player",
    "Room", 
    "Position3D",
    "DiscoveryState",
    "InventoryType",
    "InventoryCapacity",
    "INVENTORY_LIMITS",
    
    # Game State
    "GameState",
    "StateChange",
    "ChangeType",
    "ValidationLevel",
    "ValidationResult",
    
    # History
    "EventHistory",
    "GameEvent"
]