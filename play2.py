"""Command-line loop for the GreenRoom2 escape room (prompt-first)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from greenroom2 import create_game, default_state, clear_cache
import atexit

try:
    from langchain_openai import ChatOpenAI
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "langchain_openai is required. Install with `pip install langchain-openai` and set OPENAI_API_KEY."
    ) from exc


def load_local_env(env_filename: str = ".env") -> None:
    env_path = Path(__file__).resolve().parent / env_filename
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            s = raw_line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k, v = k.strip(), v.strip()
            if v and len(v) >= 2 and v[0] == v[-1] and v[0] in {'"', "'"}:
                v = v[1:-1]
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


load_local_env()


def load_llm() -> ChatOpenAI:
    model = os.environ.get("GREENROOM2_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-5-mini"
    temperature = float(os.environ.get("GREENROOM2_TEMPERATURE", "0.2"))
    return ChatOpenAI(model=model, temperature=temperature)

# Ensure bytecode caches are cleared on exit
atexit.register(lambda: (clear_cache()))


def main() -> int:
    llm = load_llm()
    game = create_game(llm)
    state = default_state()

    print("You wake on a cold floor inside a small green room.")
    print("A green door, a green desk, and a green lamp stand before you, waiting.")
    print("What do you do?")
    print("Type 'quit' to give up.")

    while True:
        try:
            action = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nThe room remains—silent and green.")
            return 1

        if not action:
            continue
        if action.lower() in {"quit", "exit"}:
            print("You rest against the green wall and let the moment pass.")
            return 0

        try:
            state = game.run_turn(state, action)
        except Exception as error:  # pragma: no cover
            print(f"System falters: {error}")
            continue

        print(state.last_response or "...")

        if state.room.exit_open and not state.room.exit_locked:
            print("\nThe door swings wide. Cool air meets you. You escape.")
            return 0


def entrypoint() -> None:
    sys.exit(main())


if __name__ == "__main__":
    entrypoint()
