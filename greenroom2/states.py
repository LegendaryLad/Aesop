"""Minimal state models and helpers for GreenRoom2.

Design goals:
- Keep data structures tiny and readable.
- Provide helpers for object creation and discovery.
- Make it easy to serialize to JSON for prompting.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List


@dataclass
class Obj:
    id: str
    name: str
    desc: str
    pos: str  # parent location id or "room"
    discovered: bool = False
    open: bool = False
    contains: bool = False
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_public(self) -> Dict[str, Any]:
        # Public snapshot for player-side context (hide internals if needed)
        data = {
            "id": self.id,
            "name": self.name,
            "desc": self.desc,
            "pos": self.pos,
            "discovered": self.discovered,
            "open": self.open,
            "contains": self.contains,
        }
        # Only share non-spoilery props in public view; keep full in omniscient
        safe_props = {
            k: v
            for k, v in (self.properties or {}).items()
            if k in {"held", "locked", "portable"}
        }
        if safe_props:
            data["properties"] = safe_props
        return data


@dataclass
class Room:
    size: str = "20x20 ft"
    exit_locked: bool = True
    exit_open: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class World:
    room: Room
    objects: Dict[str, Obj]
    last_response: str = ""

    def to_omniscient(self) -> Dict[str, Any]:
        return {
            "room": self.room.to_dict(),
            "objects": {k: asdict(v) for k, v in self.objects.items()},
        }

    def to_player(self) -> Dict[str, Any]:
        return {
            "room": {
                "size": self.room.size,
                "door": "open" if self.room.exit_open else ("locked" if self.room.exit_locked else "closed"),
            },
            "objects": {k: v.to_public() for k, v in self.objects.items() if v.discovered},
        }


def create_object(data: Dict[str, Any]) -> Obj:
    """Create an Obj from a loose dict. Missing fields use sensible defaults."""
    return Obj(
        id=data.get("id") or data.get("name") or "object",
        name=data.get("name") or data.get("id") or "object",
        desc=data.get("desc", ""),
        pos=data.get("pos", "room"),
        discovered=bool(data.get("discovered", False)),
        open=bool(data.get("open", False)),
        contains=bool(data.get("contains", False)),
        properties=dict(data.get("properties", {})),
    )


def discover_objects(world: World, object_ids: List[str]) -> None:
    for oid in object_ids or []:
        obj = world.objects.get(oid)
        if obj:
            obj.discovered = True


def initial_state() -> World:
    """Define the GreenRoom2 canonical starting world.

    Room: 20x20, green walls, one green locked door, green desk, green lamp.
    Desk contains a note ("So it begins...") and a screwdriver.
    Lamp's bulb can be unscrewed with the screwdriver to reveal a key hidden in the base.
    The bulb also contains a second message that can be hinted by shaking and found by breaking ("Eureka!").
    """

    objs: Dict[str, Obj] = {
        # Visible on look around
        "door": Obj(
            id="door",
            name="green door",
            desc="A green-painted door with a keyhole.",
            pos="room",
            discovered=True,
            properties={"locked": True, "open": False},
        ),
        "desk": Obj(
            id="desk",
            name="green desk",
            desc="A small green desk with a single drawer, which is discoverable. The origin of the green wood is of concern.",
            pos="room",
            discovered=True,
            contains=True,
        ),
        "lamp": Obj(
            id="lamp",
            name="green lamp",
            desc="A squat green lamp with a screw-in bulb. For some reason it seems to be flirting you when inspected.",
            pos="room",
            discovered=True,
            contains=True,
        ),
        # Hidden until examined/opened
        "note": Obj(
            id="note",
            name="note",
            desc='A small card that reads: "So it begins...", smells slightly of a memory of a lover.',
            pos="desk",
            discovered=False,
            properties={"portable": True},
        ),
        "screwdriver": Obj(
            id="screwdriver",
            name="screwdriver",
            desc="A small flathead screwdriver. Possibly named Tim.",
            pos="desk",
            discovered=False,
            properties={"portable": True, "held": False, "tool": "screwdriver"},
        ),
        "bulb": Obj(
            id="bulb",
            name="bulb",
            desc="A glass bulb screwed into the lamp. Might cry when broken.",
            pos="lamp",
            discovered=False,
            properties={
                "unscrewed": False,
                "broken": False,
                "screwdriver_required": True,
            },
        ),
        "key": Obj(
            id="key",
            name="small key",
            desc="A small key hidden in the bulb base.",
            pos="lamp",
            discovered=False,
            properties={"portable": True, "held": False, "hidden_in_base": True},
        ),
        "eureka": Obj(
            id="eureka",
            name="hidden message",
            desc='A small black card that reads: "Eureka!" Holding it gives the player a memory of being in a red room.',
            pos="bulb",
            discovered=False,
            properties={"hidden_in_glass": True},
        ),
    }

    world = World(room=Room(), objects=objs)
    return world

