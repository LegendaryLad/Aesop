"""LangGraph wiring for the GreenRoom1 escape room."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, TypedDict, Optional, Tuple

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from .states import GameState, GreenRoomState, ObjectState, RoomState, initial_state


class GraphState(TypedDict, total=False):
    """State container passed through the LangGraph."""

    # Persisted game state snapshot
    greenroom_state: Dict[str, Any]
    # Player action for this turn
    action: str
    # Ephemeral, DM-internal structured payload from DM_Interior
    interior_payload: Dict[str, Any]
    # Ephemeral: objects to reveal this turn
    to_be_revealed: List[str]
    # Ephemeral: mapping internal object ids -> player-facing labels
    redaction_map: Dict[str, str]
    # Ephemeral: interior guidance message for retry
    interior_hint: str
    # Ephemeral: violations found by validator
    violations: List[str]
    # Ephemeral: retry count for this turn
    retry_count: int
    # Ephemeral: player-side outcome summary from DM_Interior (redacted)
    player_outcome: str
    # Final DM response to present to player
    dm_response: str


class DungeonMasterRoomPayload(TypedDict, total=False):
    """Partial room updates returned by the dungeon master."""

    ambient_conditions: str
    exit_locked: bool
    exit_open: bool


class DungeonMasterObjectPayload(TypedDict, total=False):
    """Partial object updates returned by the dungeon master."""

    name: str
    description: str
    position: str
    interactions: Dict[str, str]
    mutable: bool
    discovered: bool
    properties: Dict[str, Any]
    # Optional creation metadata when introducing new objects
    created: bool
    origin: str  # e.g., "crafted" | "found"
    creation_reason: str


class DungeonMasterGamePayload(TypedDict, total=False):
    """Partial game metadata updates returned by the dungeon master."""

    action_history: List[str]
    puzzle_progress: Dict[str, bool]
    flags: Dict[str, Any]


class DungeonMasterResponse(TypedDict):
    """Structured dungeon master payload enforced via with_structured_output."""

    response: str
    room: DungeonMasterRoomPayload
    objects: Dict[str, DungeonMasterObjectPayload]
    game: DungeonMasterGamePayload


class DMInteriorResponse(TypedDict, total=False):
    """LLM response from the DM_Interior node."""

    dm_thinks: str
    player_side_outcome: str
    room: DungeonMasterRoomPayload
    objects: Dict[str, DungeonMasterObjectPayload]
    game: DungeonMasterGamePayload
    to_be_revealed: List[str]


class DMExteriorResponse(TypedDict):
    """LLM response from the DM_Exterior node."""

    narration: str


class GreenRoomGraph:
    """Builds and runs the LangGraph that powers GreenRoom1."""

    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm
        # Build separate prompts/structured drivers
        self.interior_prompt = self._build_interior_prompt()
        self.exterior_prompt = self._build_exterior_prompt()
        self.structured_interior = self.llm.with_structured_output(
            DMInteriorResponse, method="json_schema"
        )
        self.structured_exterior = self.llm.with_structured_output(
            DMExteriorResponse, method="json_schema"
        )
        self.graph = self._build_graph()

    def _build_interior_prompt(self) -> ChatPromptTemplate:
        system_message = (
            "You are DM_Interior: decide feasibility, outcomes, and propose state updates.\n"
            "You have full omniscient state, but your narration is split.\n"
            "Rules:\n"
            "- Evaluate action with D&D commoner constraints.\n"
            "- Update room/object/game truthfully. Physics matters.\n"
            "- Propose to_be_revealed as object ids that become known this turn,\n"
            "  based on location (visible_in_room, parent visibility/open) and sensible context.\n"
            "- New objects are allowed only if coherent (e.g., crafted or found); include created, origin, creation_reason.\n"
            "- Do NOT mark objects discovered here; discovery will be applied later.\n"
            "- Provide dm_thinks as a compact chain-of-thought (not shown to player).\n"
            "- Provide player_side_outcome: a brief, player-appropriate summary for the next narrator.\n"
        )

        user_template = (
            "Full omniscient state (JSON):\n{full_state}\n\n"
            "Player action: {action}\n\n"
            "Optional corrective hint: {hint}\n\n"
            "Return JSON with dm_thinks, player_side_outcome, room/objects/game updates, and to_be_revealed (ids)."
        )
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_template),
        ])

    def _build_exterior_prompt(self) -> ChatPromptTemplate:
        system_message = (
            "You are DM_Exterior: write a 2-3 sentence narrative for the player.\n"
            "Rules:\n"
            "- Only refer to objects present in player_visible_objects.\n"
            "- For items listed with placeholder names (hidden_name), use those labels.\n"
            "- Do not mention anything else.\n"
        )
        user_template = (
            "Player-visible state (JSON):\n{player_state}\n\n"
            "Outcome to narrate: {player_outcome}\n\n"
            "Return JSON with narration only."
        )
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_template),
        ])

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(GraphState)
        graph.add_node("dm_interior", self._run_dm_interior)
        graph.add_node("validate", self._validate_and_merge)
        graph.add_node("dm_exterior", self._run_dm_exterior)
        graph.set_entry_point("dm_interior")
        graph.add_edge("dm_interior", "validate")
        # Conditional edge out of validator
        graph.add_conditional_edges(
            "validate",
            self._validation_route,
            {"retry": "dm_interior", "ok": "dm_exterior"},
        )
        graph.add_edge("dm_exterior", END)
        return graph.compile()

    def _get_discovered_objects(self, state: GreenRoomState) -> List[Dict[str, Any]]:
        """Return discovered objects as plain dicts (sanitized)."""
        discovered: List[Dict[str, Any]] = []
        for name, obj in sorted(state.objects.items()):
            if not obj.discovered:
                continue
            discovered.append({
                "id": name,
                "name": obj.name,
                "description": obj.description,
                "position": obj.position,
                "interactions": obj.interactions,
                "contains_objects": obj.contains_objects,
                "open": obj.open,
                "visible_in_room": obj.visible_in_room,
                "properties": obj.properties,
            })
        return discovered

    def _visible_state(self, state: GreenRoomState) -> Dict[str, Any]:
        """Return a state snapshot with only discovered objects (sanitized)."""
        snapshot = state.to_dict()
        sanitized_objects: Dict[str, Any] = {}
        for name, raw in snapshot.get("objects", {}).items():
            if not raw.get("discovered"):
                continue
            # Remove any legacy leaking fields if present
            props = dict(raw.get("properties", {}))
            sanitized = dict(raw)
            sanitized["properties"] = props
            sanitized_objects[name] = sanitized
        snapshot["objects"] = sanitized_objects
        return snapshot

    def _build_player_state(
        self,
        state: GreenRoomState,
        to_be_revealed: List[str],
        redaction_map: Dict[str, str],
    ) -> Dict[str, Any]:
        """Build the player-visible state for DM_Exterior, with redactions applied."""
        # Use contextless room variables to avoid revealing lock specifics
        room_public = {
            "ambient": state.room.ambient_conditions,
            "egress_state": "open" if state.room.exit_open else "closed",
        }
        visible: Dict[str, Any] = {"room": room_public, "objects": {}, "game": {}}
        for name, obj in state.objects.items():
            if not (obj.discovered or name in to_be_revealed):
                continue
            label = redaction_map.get(name, obj.name)
            visible["objects"][name] = {
                "name": label,
                "description": obj.description,
                "position": obj.position,
                "interactions": obj.interactions,
                "open": obj.open,
                "contains_objects": obj.contains_objects,
            }
        # Player inventory as list of ids
        inventory = state.game.flags.get("player_inventory", [])
        visible["game"]["player_inventory"] = list(inventory)
        return visible

    # Legacy discovery helpers removed; discovery now governed by validator and to_be_revealed

    def _run_dm_interior(self, state: GraphState) -> GraphState:
        if "greenroom_state" not in state:
            raise ValueError("greenroom_state missing from graph state")
        green_state = GreenRoomState.from_dict(state["greenroom_state"])
        action = state.get("action", "").strip()
        if not action:
            raise ValueError("An action string is required to advance the game.")

        full_state = json.dumps(green_state.to_dict(), indent=2, sort_keys=True)
        hint = state.get("interior_hint", "").strip() or "(none)"
        prompt_messages = self.interior_prompt.format_messages(
            full_state=full_state,
            action=action,
            hint=hint,
        )
        try:
            parsed = self.structured_interior.invoke(prompt_messages)
        except Exception as exc:
            raise ValueError("DM_Interior failed to return structured payload.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("DM_Interior returned malformed structured payload.")

        # Store interior payload for validation/merge
        return GraphState(
            greenroom_state=green_state.to_dict(),
            action=action,
            interior_payload=dict(parsed),
            retry_count=int(state.get("retry_count", 0) or 0),
        )

    def _merge_with_rules(
        self,
        previous_state: GreenRoomState,
        interior_payload: Dict[str, Any],
        action: str,
    ) -> Tuple[GreenRoomState, List[str], List[str]]:
        """Merge interior updates subject to reveal/creation rules.

        Returns: (merged_state, accepted_to_reveal_ids, violations)
        """
        # Parse proposed updates
        llm_room = interior_payload.get("room", {}) or {}
        llm_objects = interior_payload.get("objects", {}) or {}
        llm_game = interior_payload.get("game", {}) or {}
        llm_to_reveal = list(interior_payload.get("to_be_revealed", []) or [])

        # Merge room
        room_payload = previous_state.room.to_dict()
        room_payload.update(llm_room)
        room = RoomState.from_dict(room_payload)

        # Merge objects (updates for existing; track potential creations)
        merged_objects: Dict[str, ObjectState] = {}
        violations: List[str] = []

        for name, existing in previous_state.objects.items():
            merged_dict = existing.to_dict()
            if name in llm_objects:
                merged_dict.update(llm_objects[name])
            merged_objects[name] = ObjectState.from_dict(merged_dict)

        # Handle creations and unknown object updates
        for name, data in llm_objects.items():
            if name in merged_objects:
                continue
            created = bool(data.get("created"))
            origin = data.get("origin")
            reason = data.get("creation_reason")
            if not created or not origin or not reason:
                violations.append(f"Unknown object '{name}' without valid creation metadata.")
                continue
            try:
                merged_objects[name] = ObjectState.from_dict(data)
            except Exception:
                violations.append(f"Failed to construct created object '{name}'.")

        # Compute allowed reveals
        allowed = self._allowed_reveals(previous_state, merged_objects, action)
        accepted_reveals = [oid for oid in llm_to_reveal if oid in merged_objects and oid in allowed]
        rejected = [oid for oid in llm_to_reveal if oid not in accepted_reveals]
        if rejected:
            violations.append("Disallowed reveals: " + ", ".join(rejected))

        # Do NOT flip discovery yet; that happens after exterior narration
        # Preserve prior discoveries
        for name, obj in merged_objects.items():
            prev_obj = previous_state.objects.get(name)
            if prev_obj and prev_obj.discovered:
                obj.discovered = True

        # Merge game
        game_payload = previous_state.game.to_dict()
        for key, value in (llm_game or {}).items():
            if isinstance(game_payload.get(key), dict) and isinstance(value, dict):
                merged_dict = dict(game_payload[key])
                merged_dict.update(value)
                game_payload[key] = merged_dict
            else:
                game_payload[key] = value
        game = GameState.from_dict(game_payload)

        # Sync door state with room
        door = merged_objects.get("door")
        if door:
            if door.properties.get("locked") is False:
                room.exit_locked = False
            elif room.exit_locked is False:
                door.properties["locked"] = False
            # Sync open state
            if door.open is True:
                room.exit_open = True
            elif room.exit_open is True:
                door.open = True

        # Update puzzle progress based on room state
        if not room.exit_locked:
            puzzle_progress = dict(game.puzzle_progress)
            puzzle_progress["door_unlocked"] = True
            game.puzzle_progress = puzzle_progress
        if room.exit_open:
            puzzle_progress = dict(game.puzzle_progress)
            puzzle_progress["door_opened"] = True
            game.puzzle_progress = puzzle_progress

        # Update action history
        if action and (not game.action_history or game.action_history[-1] != action):
            game.action_history.append(action)

        merged_state = GreenRoomState(room=room, objects=merged_objects, game=game, last_response="")
        return merged_state, accepted_reveals, violations

    def _allowed_reveals(
        self,
        previous_state: GreenRoomState,
        objects: Dict[str, ObjectState],
        action: str,
    ) -> List[str]:
        """Derive allowed reveals based on locations and simple action heuristics."""
        action_lower = (action or "").lower()
        allowed: List[str] = []

        # Room look reveals visible_in_room
        if any(tok in action_lower for tok in ["look", "look around", "inspect room", "survey", "scan"]):
            for name, obj in objects.items():
                if not previous_state.objects.get(name):
                    # new objects should not be auto-revealed by look unless visible
                    if obj.visible_in_room:
                        allowed.append(name)
                elif not previous_state.objects[name].discovered and obj.visible_in_room:
                    allowed.append(name)

        # Reveal children of open containers or examined parents
        parent_open: Dict[str, bool] = {}
        for pname, pobj in objects.items():
            parent_open[pname] = pobj.open is True

        for name, obj in objects.items():
            parent = obj.position
            if not parent:
                continue
            # Parent discovered or becomes open
            parent_state_prev = previous_state.objects.get(parent)
            parent_state_now = objects.get(parent)

            parent_discovered = bool(parent_state_prev and parent_state_prev.discovered)
            becomes_open = bool(parent_state_now and parent_state_now.open)

            if parent_discovered and (parent_state_now and (parent_state_now.open or parent_state_now.contains_objects)):
                allowed.append(name)
            elif becomes_open:
                allowed.append(name)

        # De-duplicate
        return list(dict.fromkeys(allowed))

    def _build_redaction_map(
        self, state: GreenRoomState, to_be_revealed: List[str]
    ) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        counter = 1
        for oid in to_be_revealed:
            obj = state.objects.get(oid)
            if not obj:
                continue
            label = obj.hidden_name.strip() or f"hidden item {counter}"
            mapping[oid] = label
            counter += 1
        # Discovered objects keep their name
        for name, obj in state.objects.items():
            if obj.discovered and name not in mapping:
                mapping[name] = obj.name
        return mapping

    def _validate_and_merge(self, state: GraphState) -> GraphState:
        if "greenroom_state" not in state:
            raise ValueError("greenroom_state missing from graph state")
        green_state = GreenRoomState.from_dict(state["greenroom_state"])
        action = state.get("action", "")
        payload = state.get("interior_payload", {}) or {}

        merged_state, accepted_reveals, violations = self._merge_with_rules(
            green_state, payload, action
        )

        # Prepare redaction map and redacted outcome text
        redaction_map = self._build_redaction_map(merged_state, accepted_reveals)
        outcome_raw = (payload.get("player_side_outcome") or "").strip()
        player_outcome = outcome_raw
        if redaction_map and outcome_raw:
            for oid, label in redaction_map.items():
                player_outcome = re.sub(rf"\b{re.escape(oid)}\b", label, player_outcome)

        # Prepare corrective hint if violations and retry allowed
        retry_count = int(state.get("retry_count", 0) or 0)
        interior_hint = ""
        if violations and retry_count < 1:
            interior_hint = (
                "Adjust your proposal: " + "; ".join(violations) + ". "
                "Only reveal objects visible_in_room on a look, or children of a discovered/open parent. "
                "Unknown objects require created=true, origin, creation_reason."
            )

        return GraphState(
            greenroom_state=(green_state.to_dict() if violations and retry_count < 1 else merged_state.to_dict()),
            action=action,
            to_be_revealed=accepted_reveals,
            redaction_map=redaction_map,
            interior_hint=interior_hint,
            violations=violations,
            retry_count=(retry_count + 1 if violations and retry_count < 1 else retry_count),
            player_outcome=player_outcome,
        )

    def _validation_route(self, state: GraphState) -> str:
        violations = state.get("violations", []) or []
        retry_count = int(state.get("retry_count", 0) or 0)
        if violations and retry_count <= 1 and state.get("interior_hint"):
            return "retry"
        return "ok"

    def _run_dm_exterior(self, state: GraphState) -> GraphState:
        if "greenroom_state" not in state:
            raise ValueError("greenroom_state missing from graph state")
        green_state = GreenRoomState.from_dict(state["greenroom_state"])
        to_reveal = list(state.get("to_be_revealed", []) or [])
        redaction_map = dict(state.get("redaction_map", {}) or {})
        player_outcome = state.get("player_outcome", "")

        player_state = self._build_player_state(green_state, to_reveal, redaction_map)
        prompt_messages = self.exterior_prompt.format_messages(
            player_state=json.dumps(player_state, indent=2, sort_keys=True),
            player_outcome=player_outcome or "",
        )
        try:
            parsed = self.structured_exterior.invoke(prompt_messages)
        except Exception as exc:
            raise ValueError("DM_Exterior failed to return structured payload.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("DM_Exterior returned malformed structured payload.")
        narration = (parsed.get("narration") or "").strip()

        # Commit reveals and finalize state
        for oid in to_reveal:
            if oid in green_state.objects:
                green_state.objects[oid].discovered = True

        green_state.last_response = narration
        return GraphState(
            greenroom_state=green_state.to_dict(),
            action="",
            dm_response=narration,
        )

    def run_turn(self, green_state: GreenRoomState, action: str) -> GreenRoomState:
        result = self.graph.invoke(
            GraphState(
                greenroom_state=green_state.to_dict(),
                action=action,
            )
        )
        return GreenRoomState.from_dict(result["greenroom_state"])


def create_game(llm: BaseChatModel) -> GreenRoomGraph:
    """Factory to create a GreenRoomGraph with the supplied language model."""
    return GreenRoomGraph(llm=llm)


def default_state() -> GreenRoomState:
    """Expose the starting state for external callers."""
    return initial_state()

