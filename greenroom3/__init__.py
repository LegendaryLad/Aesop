"""
Greenroom3: AI-Powered Escape Room Engine

An escape room game where an LLM acts as a sardonic Dungeon Master,
managing a physics-based world with radical player freedom.
"""

__version__ = "0.1.0"
__author__ = "Greenroom3 Team"

# Core exports
from greenroom3.core.game_objects import (
    GameObject,
    Player,
    Room,
    Position3D,
    DiscoveryState,
    InventoryType
)

# Will be added as we build them
# from greenroom3.core.game_state import GameState
# from greenroom3.llm.client import LLMClient
# from greenroom3.game import Game

__all__ = [
    "GameObject",
    "Player", 
    "Room",
    "Position3D",
    "DiscoveryState",
    "InventoryType",
]