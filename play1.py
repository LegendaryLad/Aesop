"""Command-line loop for the GreenRoom1 escape room."""

from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path

from greenroom1 import create_game, default_state

try:
    from langchain_openai import ChatOpenAI
except ImportError as exc:  # pragma: no cover - informative CLI failure
    raise SystemExit(
        "langchain_openai is required to run the GreenRoom1 demo CLI. "
        "Install it with `pip install langchain-openai` and set an OPENAI_API_KEY."
    ) from exc


def load_local_env(env_filename: str = ".env") -> None:
    """Populate os.environ from a sibling .env file if available."""

    env_path = Path(__file__).resolve().parent / env_filename
    if not env_path.exists():
        return
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value


load_local_env()


def load_llm() -> ChatOpenAI:
    """Create the language model driver from environment configuration."""

    model = (
        os.environ.get("GREENROOM1_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-4o-mini"
    )
    temperature_raw = os.environ.get("GREENROOM1_TEMPERATURE", "0.3")
    try:
        temperature = float(temperature_raw)
    except ValueError:
        temperature = 0.3
    return ChatOpenAI(model=model, temperature=temperature)



def clear_pycache() -> None:
    """Remove cached bytecode to avoid stale runs."""
    cache_dir = Path(__file__).resolve().parent / "greenroom1" / "__pycache__"
    try:
        shutil.rmtree(cache_dir)
    except (FileNotFoundError, OSError):
        pass

def main() -> int:
    try:
        llm = load_llm()
        game = create_game(llm)
        state = default_state()

        print("You wake on a cold floor. Green walls press in.")
        print("Type actions like 'stand up' or 'inspect room'. Type 'quit' to give up.")

        while True:
            try:
                action = input(">> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nThe room wins today.")
                return 1

            if not action:
                continue
            if action.lower() in {"quit", "exit"}:
                print("You lie back down on the cold floor. The room hums in victory.")
                return 0

            try:
                state = game.run_turn(state, action)
            except Exception as error:  # pragma: no cover - runtime guardrail
                print(f"System stumbles: {error}")
                continue

            print(state.last_response)
            if state.room.exit_open and not state.room.exit_locked:
                print("\nThe door yawns open. Green light spills into freedom. You escape.")
                return 0
    finally:
        clear_pycache()

def entrypoint() -> None:
    sys.exit(main())


if __name__ == "__main__":
    entrypoint()






