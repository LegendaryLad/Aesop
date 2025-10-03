"""
Event history and persistence system for greenroom3.
Provides save/load, replay functionality, and debugging tools.
"""

import json
import sqlite3
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import pickle
import hashlib
from dataclasses import dataclass, asdict

from greenroom3.utils import logger
from greenroom3.core.game_state import GameState, StateChange, ChangeType
from greenroom3.core.game_objects import GameObject, Player, Room, Position3D, DiscoveryState


@dataclass
class GameEvent:
    """Represents a single game event."""
    event_id: str
    session_id: str
    turn_number: int
    timestamp: datetime
    event_type: str  # 'player_action', 'state_change', 'llm_response', etc.
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "turn_number": self.turn_number,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "data": self.data
        }


class EventHistory:
    """
    Manages event storage, replay, and session persistence.
    Uses SQLite for event sourcing and debugging.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize the event history system."""
        if db_path is None:
            db_path = os.getenv("EVENT_LOG_PATH", "./greenroom3_events.db")
            
        self.db_path = db_path
        self.connection = None
        self.current_session_id = None
        
        # Create database and tables
        self._init_database()
        
        logger.info(f"EventHistory initialized with database: {db_path}")
    
    def _init_database(self):
        """Initialize the SQLite database schema."""
        self.connection = sqlite3.connect(self.db_path)
        cursor = self.connection.cursor()
        
        # Create events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                turn_number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL DEFAULT (datetime('now'))
            )
        """)
        
        # Create sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        # Create game_states table for checkpoints
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_states (
                state_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                turn_number INTEGER NOT NULL,
                state_data BLOB NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        # Create indices for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_session 
            ON events(session_id, turn_number)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type 
            ON events(event_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_states_session 
            ON game_states(session_id, turn_number)
        """)
        
        self.connection.commit()
        
    # ========== Session Management ==========
    
    def start_session(self, name: str = None) -> str:
        """Start a new game session."""
        session_id = self._generate_session_id()
        timestamp = datetime.now().isoformat()
        
        if name is None:
            name = f"Session_{timestamp[:10]}_{session_id[:8]}"
        
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO sessions (session_id, name, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, name, timestamp, timestamp, json.dumps({})))
        
        self.connection.commit()
        self.current_session_id = session_id
        
        logger.info(f"Started new session: {session_id} ({name})")
        return session_id
    
    def end_session(self):
        """End the current session."""
        if self.current_session_id:
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE sessions 
                SET is_active = 0, updated_at = ?
                WHERE session_id = ?
            """, (datetime.now().isoformat(), self.current_session_id))
            
            self.connection.commit()
            logger.info(f"Ended session: {self.current_session_id}")
            self.current_session_id = None
    
    def resume_session(self, session_id: str) -> bool:
        """Resume an existing session."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT session_id, is_active 
            FROM sessions 
            WHERE session_id = ?
        """, (session_id,))
        
        result = cursor.fetchone()
        if result:
            self.current_session_id = session_id
            
            # Update session as active
            cursor.execute("""
                UPDATE sessions 
                SET is_active = 1, updated_at = ?
                WHERE session_id = ?
            """, (datetime.now().isoformat(), session_id))
            
            self.connection.commit()
            logger.info(f"Resumed session: {session_id}")
            return True
            
        logger.warning(f"Session not found: {session_id}")
        return False
    
    def list_sessions(self, active_only: bool = False) -> List[Dict]:
        """List all available sessions."""
        cursor = self.connection.cursor()
        
        query = "SELECT * FROM sessions"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY updated_at DESC"
        
        cursor.execute(query)
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "session_id": row[0],
                "name": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
                "is_active": bool(row[5])
            })
            
        return sessions
    
    # ========== Event Logging ==========
    
    def log_event(self, event_type: str, data: Dict[str, Any], 
                  turn_number: int = 0) -> str:
        """Log a game event."""
        if not self.current_session_id:
            self.start_session()
        
        event = GameEvent(
            event_id=self._generate_event_id(),
            session_id=self.current_session_id,
            turn_number=turn_number,
            timestamp=datetime.now(),
            event_type=event_type,
            data=data
        )
        
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO events 
            (event_id, session_id, turn_number, timestamp, event_type, data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event.event_id,
            event.session_id,
            event.turn_number,
            event.timestamp.isoformat(),
            event.event_type,
            json.dumps(event.data)
        ))
        
        self.connection.commit()
        
        logger.debug(f"Logged event: {event_type} (turn {turn_number})")
        return event.event_id
    
    def log_player_action(self, action: str, turn_number: int) -> str:
        """Log a player action."""
        return self.log_event("player_action", {"action": action}, turn_number)
    
    def log_llm_response(self, response: Dict, turn_number: int) -> str:
        """Log an LLM response."""
        return self.log_event("llm_response", response, turn_number)
    
    def log_state_changes(self, changes: List[StateChange], turn_number: int) -> str:
        """Log state changes."""
        changes_data = [
            {
                "type": change.type.value,
                "path": change.path,
                "value": change.value,
                "action": change.action,
                "args": change.args
            }
            for change in changes
        ]
        return self.log_event("state_changes", {"changes": changes_data}, turn_number)
    
    def log_error(self, error: str, context: Dict, turn_number: int) -> str:
        """Log an error event."""
        return self.log_event("error", {"error": error, "context": context}, turn_number)
    
    # ========== State Checkpointing ==========
    
    def save_checkpoint(self, game_state: GameState, turn_number: int) -> str:
        """Save a game state checkpoint."""
        if not self.current_session_id:
            raise RuntimeError("No active session")
        
        state_id = self._generate_state_id()
        
        # Serialize the entire game state
        state_data = self._serialize_game_state(game_state)
        
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO game_states 
            (state_id, session_id, turn_number, state_data, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            state_id,
            self.current_session_id,
            turn_number,
            state_data,
            datetime.now().isoformat()
        ))
        
        self.connection.commit()
        
        logger.info(f"Saved checkpoint at turn {turn_number}")
        return state_id
    
    def load_checkpoint(self, session_id: str = None, 
                       turn_number: int = None) -> Optional[GameState]:
        """Load a game state checkpoint."""
        session_id = session_id or self.current_session_id
        if not session_id:
            logger.error("No session specified")
            return None
        
        cursor = self.connection.cursor()
        
        if turn_number is not None:
            # Load specific turn
            cursor.execute("""
                SELECT state_data 
                FROM game_states 
                WHERE session_id = ? AND turn_number = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (session_id, turn_number))
        else:
            # Load latest checkpoint
            cursor.execute("""
                SELECT state_data 
                FROM game_states 
                WHERE session_id = ?
                ORDER BY turn_number DESC, created_at DESC
                LIMIT 1
            """, (session_id,))
        
        result = cursor.fetchone()
        if result:
            game_state = self._deserialize_game_state(result[0])
            logger.info(f"Loaded checkpoint from session {session_id}")
            return game_state
            
        logger.warning(f"No checkpoint found for session {session_id}")
        return None
    
    # ========== Replay System ==========
    
    def get_session_events(self, session_id: str = None, 
                          start_turn: int = 0, 
                          end_turn: int = None) -> List[GameEvent]:
        """Get all events for a session."""
        session_id = session_id or self.current_session_id
        if not session_id:
            return []
        
        cursor = self.connection.cursor()
        
        query = """
            SELECT * FROM events 
            WHERE session_id = ? AND turn_number >= ?
        """
        params = [session_id, start_turn]
        
        if end_turn is not None:
            query += " AND turn_number <= ?"
            params.append(end_turn)
            
        query += " ORDER BY turn_number, created_at"
        
        cursor.execute(query, params)
        
        events = []
        for row in cursor.fetchall():
            events.append(GameEvent(
                event_id=row[0],
                session_id=row[1],
                turn_number=row[2],
                timestamp=datetime.fromisoformat(row[3]),
                event_type=row[4],
                data=json.loads(row[5])
            ))
            
        return events
    
    def replay_session(self, session_id: str = None, 
                      start_turn: int = 0,
                      end_turn: int = None,
                      speed: float = 1.0) -> List[Dict]:
        """
        Replay a session's events.
        Returns the sequence of events for analysis.
        """
        events = self.get_session_events(session_id, start_turn, end_turn)
        
        replay_data = []
        for event in events:
            replay_data.append({
                "turn": event.turn_number,
                "type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data
            })
            
        logger.info(f"Replaying {len(events)} events from session {session_id}")
        return replay_data
    
    def analyze_session(self, session_id: str = None) -> Dict:
        """Analyze a session for patterns and statistics."""
        events = self.get_session_events(session_id)
        
        if not events:
            return {}
        
        analysis = {
            "total_turns": max(e.turn_number for e in events),
            "total_events": len(events),
            "event_types": {},
            "player_actions": [],
            "errors": [],
            "state_changes": 0,
            "session_duration": None
        }
        
        for event in events:
            # Count event types
            event_type = event.event_type
            analysis["event_types"][event_type] = \
                analysis["event_types"].get(event_type, 0) + 1
            
            # Collect specific event data
            if event_type == "player_action":
                analysis["player_actions"].append(event.data.get("action"))
            elif event_type == "error":
                analysis["errors"].append({
                    "turn": event.turn_number,
                    "error": event.data.get("error")
                })
            elif event_type == "state_changes":
                changes = event.data.get("changes", [])
                analysis["state_changes"] += len(changes)
        
        # Calculate session duration
        if len(events) > 1:
            duration = events[-1].timestamp - events[0].timestamp
            analysis["session_duration"] = str(duration)
        
        return analysis
    
    # ========== Debugging Tools ==========
    
    def get_turn_summary(self, turn_number: int, 
                         session_id: str = None) -> Dict:
        """Get a summary of all events in a specific turn."""
        events = self.get_session_events(session_id, turn_number, turn_number)
        
        summary = {
            "turn": turn_number,
            "events": [],
            "player_action": None,
            "llm_response": None,
            "state_changes": [],
            "errors": []
        }
        
        for event in events:
            summary["events"].append(event.event_type)
            
            if event.event_type == "player_action":
                summary["player_action"] = event.data.get("action")
            elif event.event_type == "llm_response":
                summary["llm_response"] = event.data
            elif event.event_type == "state_changes":
                summary["state_changes"] = event.data.get("changes", [])
            elif event.event_type == "error":
                summary["errors"].append(event.data)
        
        return summary
    
    def export_session(self, session_id: str = None, 
                      output_path: str = None) -> str:
        """Export a session to JSON file for analysis."""
        session_id = session_id or self.current_session_id
        if not session_id:
            raise ValueError("No session to export")
        
        # Get session info
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM sessions WHERE session_id = ?
        """, (session_id,))
        
        session_info = cursor.fetchone()
        if not session_info:
            raise ValueError(f"Session not found: {session_id}")
        
        # Get all events
        events = self.get_session_events(session_id)
        
        # Get latest checkpoint
        checkpoint_data = None
        cursor.execute("""
            SELECT turn_number, created_at 
            FROM game_states 
            WHERE session_id = ?
            ORDER BY turn_number DESC
            LIMIT 1
        """, (session_id,))
        
        checkpoint_info = cursor.fetchone()
        
        # Prepare export data
        export_data = {
            "session": {
                "id": session_info[0],
                "name": session_info[1],
                "created_at": session_info[2],
                "updated_at": session_info[3],
                "metadata": json.loads(session_info[4]) if session_info[4] else {}
            },
            "events": [e.to_dict() for e in events],
            "latest_checkpoint": {
                "turn": checkpoint_info[0],
                "created_at": checkpoint_info[1]
            } if checkpoint_info else None,
            "analysis": self.analyze_session(session_id)
        }
        
        # Write to file
        if output_path is None:
            output_path = f"session_{session_id[:8]}_{datetime.now():%Y%m%d_%H%M%S}.json"
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Exported session to {output_path}")
        return output_path
    
    # ========== Private Methods ==========
    
    def _serialize_game_state(self, game_state: GameState) -> bytes:
        """Serialize a GameState object to bytes."""
        # Convert to a serializable format
        state_dict = {
            "player": game_state.player.__dict__,
            "current_room_id": game_state.current_room_id,
            "rooms": {id: room.__dict__ for id, room in game_state.rooms.items()},
            "objects": {id: obj.__dict__ for id, obj in game_state.objects.items()},
            "hidden_mechanics": game_state.hidden_mechanics,
            "narrative_hints": game_state.narrative_hints,
            "recent_references": game_state.recent_references
        }
        
        # Use pickle for complex objects (numpy arrays, etc.)
        return pickle.dumps(state_dict)
    
    def _deserialize_game_state(self, state_data: bytes) -> GameState:
        """Deserialize bytes to a GameState object."""
        state_dict = pickle.loads(state_data)
        
        # Reconstruct GameState
        game_state = GameState()
        
        # Restore player
        game_state.player.__dict__.update(state_dict["player"])
        
        # Restore rooms
        for room_id, room_data in state_dict["rooms"].items():
            room = Room(room_id, "")
            room.__dict__.update(room_data)
            game_state.rooms[room_id] = room
        
        # Restore objects
        for obj_id, obj_data in state_dict["objects"].items():
            obj = GameObject(obj_id)
            obj.__dict__.update(obj_data)
            game_state.objects[obj_id] = obj
        
        # Restore other state
        game_state.current_room_id = state_dict["current_room_id"]
        game_state.hidden_mechanics = state_dict["hidden_mechanics"]
        game_state.narrative_hints = state_dict["narrative_hints"]
        game_state.recent_references = state_dict["recent_references"]
        
        return game_state
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now().isoformat()
        random_str = os.urandom(16).hex()
        return hashlib.sha256(f"{timestamp}{random_str}".encode()).hexdigest()[:16]
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        timestamp = datetime.now().isoformat()
        random_str = os.urandom(8).hex()
        return hashlib.sha256(f"{timestamp}{random_str}".encode()).hexdigest()[:12]
    
    def _generate_state_id(self) -> str:
        """Generate a unique state ID."""
        timestamp = datetime.now().isoformat()
        random_str = os.urandom(8).hex()
        return hashlib.sha256(f"{timestamp}{random_str}".encode()).hexdigest()[:12]
    
    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            logger.info("EventHistory database connection closed")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()