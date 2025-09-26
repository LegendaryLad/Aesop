"""Prompt-first, minimal engine for GreenRoom2.

This engine relies on a single LLM call per turn with carefully crafted
instructions. Discovery and creation are applied via simple helpers.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from pathlib import Path
import shutil

from langchain_openai import ChatOpenAI

from .states import World, initial_state, discover_objects, create_object


SYSTEM_PROMPT = (
    "You are the Dungeon Master (DM) and prompt-native game engine for GreenRoom2.\n"
    "Write short, cinematic responses that are playful and clever while strictly updating state.\n"
    "\n"
    "Voice & tone:\n"
    "- Sardonic, dryly funny, and witty—sly remarks welcome, never cruel.\n"
    "- Second-person, present tense. Vary rhythm. Keep it tight.\n"
    "- Always react to the player's exact action; acknowledge success or why it fails.\n"
    "\n"
    "Narrative goals each turn:\n"
    "- Reflect cause and effect of the action; describe immediate results and relevant sensory details.\n"
    "- If nothing obvious changes, say so with a wry aside.\n"
    "- After repeated failed attempts (same idea, state unchanged), gently escalate hints (subtle → clearer), never spoilers.\n"
    "- Never mention undiscovered objects unless you include their ids in 'discover'.\n"
    "\n"
    "Canonical room truth:\n"
    "- A 20x20 ft green room with a green desk, a green lamp, and a green locked door.\n"
    "- The desk has a discoverable drawer which contains a note that reads 'So it begins...' and a screwdriver.\n"
    "- The lamp has a screw-in bulb. Using the screwdriver to unscrew the bulb reveals a key hidden in the lamp's base.\n"
    "- The bulb holds a second message hinted by shaking and revealed by breaking: 'Eureka!'.\n"
    "- The door unlocks with the key, then can be opened to escape.\n"
    "\n"
    "Narration rules:\n"
    "- Only mention already discovered objects plus any ids you add to 'discover' this turn.\n"
    "- Keep narration to 1–3 short sentences, sardonic and witty.\n"
    "- Do not spoil or reference undiscovered items.\n"
    "\n"
    "State update rules:\n"
    "- Taking an item → set its pos='inventory' and properties.held=true.\n"
    "- Unscrewing the bulb requires the screwdriver; on success set bulb.properties.unscrewed=true and reveal the key (discover=['key'] if hidden).\n"
    "- Shaking bulb without breaking only hints; breaking reveals the message (discover=['eureka']).\n"
    "- Unlocking door requires the key → set door.properties.locked=false. Opening → room.exit_open=true.\n"
    "- You may include 'room' updates (exit_locked/exit_open). Only create new objects if absolutely necessary for coherent actions.\n"
    "\n"
    "Strict output contract:\n"
    "- Return STRICT JSON only, no prose, no markdown fences.\n"
    "- Keys: narration:str, discover:list[str], updates:{object_id:{pos?, open?, name?, desc?, properties?}},\n"
    "  create:[{id,name,desc,pos,discovered?,open?,contains?,properties?}], room:{exit_locked?,exit_open?}, end?:bool.\n"
    "- Keep 'narration' concise and witty; everything else is structured.\n"
)


def _safe_json_parse(text: str) -> Dict[str, Any]:
    """Parse JSON from model output, stripping code fences if present."""
    s = text.strip()
    if s.startswith("```"):
        # Try to strip ```json fences
        lines = s.splitlines()
        if len(lines) >= 2:
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            s = "\n".join(lines).strip()
    try:
        return json.loads(s or "{}")
    except Exception:
        # Last-resort: find outermost braces
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(s[start : end + 1])
            except Exception:
                pass
    return {}


class GreenRoom2:
    def __init__(self, llm: ChatOpenAI) -> None:
        self.llm = llm

    def run_turn(self, world: World, action: str) -> World:
        # Build user payload with omniscient state and the player-visible snapshot for context
        user_payload = {
            "omniscient_state": world.to_omniscient(),
            "player_state": world.to_player(),
            "action": action.strip(),
        }

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]

        result = self.llm.invoke(messages)
        content = getattr(result, "content", "") or ""
        data = _safe_json_parse(content)

        # Apply updates
        narration = (data.get("narration") or "").strip()
        discover = list(data.get("discover") or [])
        updates: Dict[str, Dict[str, Any]] = dict(data.get("updates") or {})
        creations: List[Dict[str, Any]] = list(data.get("create") or [])
        room_updates: Dict[str, Any] = dict(data.get("room") or {})

        # Discoveries first
        discover_objects(world, discover)

        # New objects
        for obj_data in creations:
            obj = create_object(obj_data or {})
            world.objects[obj.id] = obj

        # Merge object updates
        for oid, patch in updates.items():
            obj = world.objects.get(oid)
            if not obj:
                continue
            if "pos" in patch:
                obj.pos = patch["pos"]
            if "open" in patch:
                obj.open = bool(patch["open"])
            if "name" in patch:
                obj.name = str(patch["name"]) or obj.name
            if "desc" in patch:
                obj.desc = str(patch["desc"]) or obj.desc
            if "properties" in patch and isinstance(patch["properties"], dict):
                obj.properties.update(patch["properties"])  # shallow merge is fine here

        # Room updates and victory detection
        if "exit_locked" in room_updates:
            world.room.exit_locked = bool(room_updates["exit_locked"])
        if "exit_open" in room_updates:
            world.room.exit_open = bool(room_updates["exit_open"])

        # Guard: if door is marked open and unlocked at the object level, reflect in room
        door = world.objects.get("door")
        if door and (door.properties.get("open") is True or door.open):
            world.room.exit_open = True
        if door and door.properties.get("locked") is False:
            world.room.exit_locked = False

        world.last_response = narration or world.last_response
        return world


def create_game(llm: ChatOpenAI) -> GreenRoom2:
    return GreenRoom2(llm=llm)


def default_state() -> World:
    return initial_state()


def clear_cache() -> None:
    """Remove local bytecode caches for greenroom2 to avoid stale runs.

    This is a light utility for CLI usage; it is safe to call even if the
    cache folders do not exist.
    """
    base = Path(__file__).resolve().parent
    try:
        # Remove direct __pycache__ and any nested ones if present
        targets = [p for p in base.rglob("__pycache__")]
        for t in targets:
            try:
                shutil.rmtree(t)
            except Exception:
                pass
    except Exception:
        # Best-effort cleanup; ignore IO issues
        pass
