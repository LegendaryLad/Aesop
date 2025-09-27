"""
Core game engine components for greenroom3.

This module contains the fundamental game mechanics:
- Game objects and spatial relationships
- Player state and inventory management  
- Room management
- State tracking and transactions
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

# Will add as we build
# from .game_state import GameState
# from .history import EventHistory
# from .validation import StateValidator

__all__ = [
    "GameObject",
    "Player",
    "Room", 
    "Position3D",
    "DiscoveryState",
    "InventoryType",
    "InventoryCapacity",
    "INVENTORY_LIMITS",
]