# GreenRoom1

GreenRoom1 is a LangChain-powered escape room built on LangGraph. You wake on a cold floor, boxed in by green walls. Freedom demands coaxing a stubborn drawer and finding the lone key that will free the door.

## Quick Start

1. Install dependencies:
   ```bash
   pip install langchain langgraph langchain-openai
   ```

2. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY=your-key-here
   # Or add to .env file
   ```

3. Run the game:
   ```bash
   python play1.py
   ```

## Architecture

### Core Principle

**Objects only exist in the player's reality when `discovered=true`.**

This single rule drives the entire discovery system. The dungeon master:
- Only narrates discovered objects
- Sets `discovered=true` when players observe or find things
- Acts confused if players mention undiscovered objects

### State Structure

```python
ObjectState:
  name: str              # Object identifier
  description: str       # Full description
  position: str          # Location in room
  interactions: dict     # Action → outcome mappings
  mutable: bool          # Can state change?
  discovered: bool       # Does player know it exists?
  properties: dict       # Dynamic attributes

RoomState:
  ambient_conditions: str
  exit_locked: bool
  exit_open: bool

GameState:
  action_history: list
  puzzle_progress: dict
  flags: dict           # Including inventory
```

### Discovery Flow

1. **Initial State**: All objects have `discovered=false`
2. **Look Around**: DM sets `discovered=true` for visible objects (door, table)
3. **Examine Table**: DM reveals drawer by setting its `discovered=true`
4. **Open Drawer**: DM reveals key inside
5. **Take Key**: Added to inventory, can unlock door

### How It Works

The `GreenRoomGraph` orchestrates each turn:

1. **Player acts** → Action sent to graph
2. **Prompt built** → Only discovered objects included in context
3. **LLM responds** → Returns narration + state updates
4. **State merged** → Updates applied, maintaining consistency
5. **Response shown** → Player sees result

The key insight: by only telling the LLM about discovered objects in the main context, we naturally prevent premature mentions without complex validation rules.

### Discovery Enforcement

- `_visible_state` redacts any `discovered=false` entries before the LLM sees the state snapshot, so it never reads about hidden props.
- `_promote_discovered_objects` keeps previously revealed items marked as discovered and scans the dungeon master's narration for new mentions.
- `_object_aliases` builds friendly surface forms (underscore-to-space variants plus any `properties["aliases"]` or `properties["display_name"]`) so prose references still register.
- When the narration names a hidden object, it is automatically flipped to `discovered=true` before the next turn, keeping the prompt and state in sync.

This narration-driven guard rail frees the DM to tell the story while the state machine enforces the discovery contract.

## Game Walkthrough

```
>> look around
[Discovers door and table]

>> examine the table  
[Discovers drawer]

>> pull drawer diagonally
[Opens drawer, discovers key]

>> take the key
[Adds to inventory]

>> unlock door with key
[Door unlocks]

>> open door
[Freedom!]
```

## Design Philosophy

This implementation prioritizes:

- **Simplicity**: One core rule, no special cases
- **Scalability**: Easy to add more rooms and objects
- **Trust**: Let the LLM handle discovery naturally
- **Clarity**: State structure is straightforward

Perfect foundation for a series of increasingly complex escape rooms.

## Files

- `greenroom1/states.py` - Simple state definitions
- `greenroom1/graph.py` - LangGraph orchestration
- `play1.py` - CLI game loop
- `__init__.py` - Package exports

## Extending

To create new rooms:

1. Define new objects in `initial_state()`
2. Set `discovered=false` for hidden items
3. Let the DM handle discovery based on player actions

No special rules needed - the discovery principle handles everything.




## Updated Architecture (DM_Interior/DM_Exterior)

To prevent dungeon master knowledge from leaking undiscovered items, the engine now uses a two-node DM split with validation and redaction.

- DM_Interior: Omniscient input. Decides feasibility and proposes room/object/game updates, plus a list `to_be_revealed` of object ids. Also returns a short `player_side_outcome` and a private `dm_thinks` chain-of-thought.
- Validator: Programmatically merges safe updates and gates reveals based on object locations and container state. It rejects illegal reveals or creations and retries DM_Interior once with a corrective hint.
- DM_Exterior: Receives only player-visible state (discovered ∪ to_be_revealed) with redacted names for unrevealed items (e.g., `hidden item 1`). Writes 2–3 sentence narration. After narration, `to_be_revealed` flips to `discovered=true`.

Key schema notes:
- ObjectState adds: `hidden_name`, `contains_objects`, `open`, `visible_in_room`.
- Container membership is one-way: if A contains B, only B has `position = "A"`. Containers set `contains_objects=True`; no `contains` array is stored on the parent.
- New objects are allowed with metadata (`created`, `origin`, `creation_reason`), and are validated before merging.

These changes replace the old narration-based discovery promotion and alias scanning. The player never sees undiscovered objects, even indirectly through properties.
