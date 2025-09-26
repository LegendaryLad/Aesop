# GreenRoom2

GreenRoom2 is a lean, prompt-first escape room. It keeps the code simple and lets the model (gpt-5-mini) handle most of the narrative and state transitions within tight, well-scoped instructions.

## Quick Start

1. Install dependencies:
   ```bash
   pip install langchain-openai
   ```

2. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY=your-key-here
   # Or put it in a local .env next to play2.py
   ```

3. Run the game:
   ```bash
   python play2.py
   ```

Environment overrides:
- `GREENROOM2_MODEL` (default: `gpt-5-mini`)
- `GREENROOM2_TEMPERATURE` (default: `0.2`)

## Room Canon

- A small 20x20 ft room with green walls.
- Objects: a green desk, a green locked door, and a green lamp.
- The desk contains a note ("So it begins...") and a screwdriver.
- The lamp’s bulb can be unscrewed with the screwdriver, revealing a key hidden in the lamp’s base.
- The bulb holds a second message that can be hinted at by shaking and found by breaking. The message says "Eureka!".
- The key unlocks the door. Open it to escape.

## Design

- Minimal data model (dataclasses) with discovery built-in.
- One LLM call per turn with a clear, strict JSON contract.
- Helpers for:
  - object state (see `greenroom2/states.py`)
  - object creation (`create_object`)
  - object discovery (`discover_objects`)

## Files

- `greenroom2/states.py` – tiny dataclasses and helpers; `initial_state()` seeds the room.
- `greenroom2/engine.py` – single-call engine that prompts and merges results.
- `play2.py` – simple CLI loop using `gpt-5-mini` by default.

## Notes

- This version intentionally avoids LangGraph for brevity. If you want a more structured pipeline later, you can plug one in without changing the room’s state model.

