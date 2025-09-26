"""Core state data structures for the GreenRoom1 escape room game."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ObjectState:
    """Represents a single interactable object in the room."""

    name: str
    description: str
    position: str
    interactions: Dict[str, str]
    mutable: bool
    # Optional name to use before the object is truly identified by the player
    hidden_name: str = ""
    discovered: bool = False  # Simple binary state
    # Whether this object (typically a container) has contents
    contains_objects: bool = False
    # Whether a container-like object is open
    open: bool = False
    # Whether this object can be discovered by a simple room look
    visible_in_room: bool = False
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "hidden_name": self.hidden_name,
            "description": self.description,
            "position": self.position,
            "interactions": self.interactions,
            "mutable": self.mutable,
            "discovered": self.discovered,
            "contains_objects": self.contains_objects,
            "open": self.open,
            "visible_in_room": self.visible_in_room,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObjectState":
        return cls(
            name=data.get("name", ""),
            hidden_name=data.get("hidden_name", ""),
            description=data.get("description", ""),
            position=data.get("position", ""),
            interactions=data.get("interactions", {}),
            mutable=data.get("mutable", False),
            discovered=data.get("discovered", False),
            contains_objects=data.get("contains_objects", False),
            open=data.get("open", False),
            visible_in_room=data.get("visible_in_room", False),
            properties=data.get("properties", {}),
        )


@dataclass
class RoomState:
    """Snapshot of the room."""

    ambient_conditions: str
    exit_locked: bool = True
    exit_open: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ambient_conditions": self.ambient_conditions,
            "exit_locked": self.exit_locked,
            "exit_open": self.exit_open,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoomState":
        return cls(
            ambient_conditions=data.get(
                "ambient_conditions", "Air tastes metallic and still."
            ),
            exit_locked=data.get("exit_locked", True),
            exit_open=data.get("exit_open", False),
        )


@dataclass
class GameState:
    """Tracks player progress and history."""

    action_history: List[str] = field(default_factory=list)
    puzzle_progress: Dict[str, bool] = field(default_factory=dict)
    flags: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_history": self.action_history,
            "puzzle_progress": self.puzzle_progress,
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameState":
        return cls(
            action_history=list(data.get("action_history", [])),
            puzzle_progress=dict(data.get("puzzle_progress", {})),
            flags=dict(data.get("flags", {})),
        )


@dataclass
class GreenRoomState:
    """Wrapper that bundles room, objects, and game metadata."""

    room: RoomState
    objects: Dict[str, ObjectState]
    game: GameState
    last_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "room": self.room.to_dict(),
            "objects": {name: obj.to_dict() for name, obj in self.objects.items()},
            "game": self.game.to_dict(),
            "last_response": self.last_response,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GreenRoomState":
        return cls(
            room=RoomState.from_dict(data.get("room", {})),
            objects={
                name: ObjectState.from_dict(obj)
                for name, obj in data.get("objects", {}).items()
            },
            game=GameState.from_dict(data.get("game", {})),
            last_response=data.get("last_response", ""),
        )


def initial_state() -> GreenRoomState:
    """Return the canonical initial state for GreenRoom1."""
    
    room = RoomState(
        ambient_conditions="Air tastes metallic and still.",
        exit_locked=True,
        exit_open=False,
    )
    
    objects = {
        "door": ObjectState(
            name="door",
            hidden_name="door",
            description="A steel door painted the same oppressive green, locked with a brass keyhole.",
            position="north wall",
            interactions={
                "inspect": "The lock is old; the hinges look solid.",
                "open": "The lock holds. You need a key.",
            },
            mutable=True,
            discovered=False,
            contains_objects=False,
            open=False,
            visible_in_room=True,
            properties={"locked": True},
        ),
        "side_table": ObjectState(
            name="side_table",
            hidden_name="table",
            description="A narrow side table listing slightly, supporting one drawer.",
            position="east wall",
            interactions={
                "inspect": "The drawer is shut tight; the wood is swollen.",
                "open": "It resists every straight pull.",
            },
            mutable=False,
            discovered=False,
            contains_objects=True,
            open=False,
            visible_in_room=True,
            properties={"drawer_stuck": True},
        ),
        "drawer": ObjectState(
            name="drawer",
            hidden_name="shallow drawer",
            description="A shallow drawer with a cheap brass handle.",
            position="side_table",
            interactions={
                "inspect": "You notice faint scratches angling toward the hinge.",
                "pull_diagonal": "The drawer jerks loose with a splintering sigh.",
            },
            mutable=True,
            discovered=False,
            contains_objects=True,
            open=False,
            visible_in_room=False,
            properties={
                "stuck": True,
                "angle_hint": "Pull toward the hinge while lifting."
            },
        ),
        "key": ObjectState(
            name="key",
            hidden_name="hidden item 1",
            description="A tarnished brass key with a jagged bite.",
            position="drawer",
            interactions={
                "inspect": "It could match the door's lock.",
                "take": "It is light but cold in your palm.",
                "use_on_door": "The key might turn if the lock allows.",
            },
            mutable=True,
            discovered=False,
            contains_objects=False,
            open=False,
            visible_in_room=False,
            properties={"portable": True, "held": False},
        ),
    }
    
    game = GameState(
        action_history=[],
        puzzle_progress={"drawer_opened": False, "door_unlocked": False, "door_opened": False},
        flags={"player_inventory": []},
    )
    
    return GreenRoomState(room=room, objects=objects, game=game)
