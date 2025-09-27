# AI-Generated Escape Room Engine

## Overview
An AI-powered escape room game where an LLM acts as a sardonic Dungeon Master, managing a physics-based (but magic-permeable) world with radical player freedom. The system tracks complex state, allows creative solutions, and responds to any player action with witty narrative.

## Core Design Philosophy
- **Player Freedom**: Accept any action, validate feasibility, narrate accordingly
- **Coherent World**: Physics rules apply unless magic overrides
- **Sardonic Tone**: Failures are comedic, death is rare but funny
- **Creative Solutions**: Puzzles have intended solutions but accept feasible alternatives
- **Modular Architecture**: Easy to swap rooms, settings, and puzzle configurations
- **Knowledge Isolation**: Prevent LLM from knowing about undiscovered objects (critical lesson from prototypes)
  - DiscoveryState tracking ensures LLM only sees what player has discovered
  - Variable names must not leak information about hidden objects
  - First encounters must not assume prior knowledge

## System Architecture

### 1. State Management
- **Hybrid Mutable State**: Fast working operations with transaction commits
- **Graph-Based World**: Rooms as nodes, transitions as edges
- **Mobile Objects**: Items can move between rooms and inventory
- **Event Sourcing**: Complete action history for replay/debugging

### 2. Property System
- **Base Properties**: Predefined object attributes (weight, material, size)
- **Dynamic Properties**: LLM can declare new properties on-the-fly
- **Nested Dict Structure**: With convenience methods for path-based access
- **Two-Tier Validation**:
  - Hard errors: Structural violations (deleting current room)
  - Soft warnings: Physics violations (frozen fire) → narrative opportunities

### 3. LLM Integration
- **Model**: GPT-5 (when available, GPT-4 fallback)
- **Structured Output**: JSON with narrative + explicit state changes
- **Hidden Changes**: State updates not mentioned in narrative
- **Context Management**:
  - Single room: Full world state each turn
  - Multi-room (future): Hybrid with permanent facts + RAG

### 4. Action Processing Pipeline
```
Raw Text → Embedding Classification → Complexity Assessment → 
→ LLM Interpretation → State Change Generation → Validation → 
→ Application → Narrative Generation
```

- **Embedding-Based Classification**: Vector similarity for action types
- **Adaptive Decomposition**: Complex actions broken into steps
- **Player-Controlled Granularity**: "quickly" vs "carefully" affects outcomes

### 5. Puzzle System
- **Complex Validation Logic**: Functions allowing creative solutions
- **Magic Thresholds**: Hard requirements for magical actions
- **Hint Triggers**: State-based progressive hint system
- **Alternative Approaches**: Multiple solution paths

## Technology Stack

### Core Libraries
- **LangGraph**: Action processing pipeline state machine
- **Pydantic/SQLModel**: Type-safe state management
- **SQLite**: Event history persistence
- **ChromaDB/LanceDB**: Vector storage for action embeddings
- **sentence-transformers**: Local embedding generation
- **jsonpatch**: Efficient state change application
- **OpenAI API**: GPT-5 (primary) / GPT-4 (fallback) integration

### GPT-5 Specific Features
- **Responses API**: For chain-of-thought persistence
- **Reasoning Effort Control**: minimal/low/medium/high
- **Verbosity Control**: low/medium/high  
- **Custom Tools**: For game actions
- **Preambles**: Explaining tool use intentions

### Development Tools
- **Streamlit/Gradio**: Testing UI
- **pytest-bdd**: Gherkin-syntax puzzle testing
- **loguru**: Event chain debugging

## Component Status & Implementation Plan

### Phase 1: Core Engine (Current Focus)
- [x] **GameState Class**
  - [ ] Hybrid mutable state with transactions
  - [ ] Nested dict with convenience accessors
  - [ ] Two-tier validation system
  - [ ] Property path resolution (`door.properties.blessed`)

- [x] **GameObject System**
  - [x] Base class with predefined properties
  - [x] Dynamic property management
  - [x] Location tracking (room/inventory)
  - [x] State serialization
  - [x] 3D positioning system
  - [x] Visibility calculations
  - [x] Discovery state tracking
  - [x] Quantum state collapse for undiscovered objects

- [x] **Player Management**
  - [x] 3D position and facing direction
  - [x] Inventory with weight/size limits
  - [x] Different inventory types (hands, pockets, backpack, sack)
  - [x] Strength-based carrying capacity

- [x] **Room Management**
  - [x] Room class with objects, exits, properties
  - [ ] YAML-based room configuration
  - [ ] Object movement between rooms

- [ ] **Event History**
  - [ ] SQLite event store
  - [ ] Action replay system
  - [ ] State reconstruction from events
  - [ ] Session-based save system

### Phase 2: LLM Integration
- [ ] **Prompt Builder**
  - [ ] World state serialization
  - [ ] Action history context
  - [ ] Personality directives

- [ ] **Response Parser**
  - [ ] JSON extraction from LLM output
  - [ ] State change validation
  - [ ] Hidden change detection

- [ ] **LangGraph Workflow**
  - [ ] Action classification node
  - [ ] Complexity evaluation node
  - [ ] Decomposition node
  - [ ] Execution node with LLM
  - [ ] Validation and application nodes

### Phase 3: Intelligence Layer
- [ ] **Action Embeddings**
  - [ ] Common action database
  - [ ] Similarity search for classification
  - [ ] LLM fallback for complex actions

- [ ] **Narrative Generator**
  - [ ] Sarcastic commentary system
  - [ ] Physics violation acknowledgment
  - [ ] Adaptive failure messages

### Phase 4: Puzzle Framework
- [ ] **Puzzle Base Class**
  - [ ] Validation logic interface
  - [ ] Hint system integration
  - [ ] Alternative solution support

- [ ] **First Test Puzzle**
  - [ ] Simple locked door scenario
  - [ ] Multiple solution paths
  - [ ] Progressive hints

### Phase 5: Polish & Testing
- [ ] **UI Development**
  - [ ] Basic Streamlit interface
  - [ ] State visualization
  - [ ] Debug console

- [ ] **Test Suite**
  - [ ] Unit tests for state management
  - [ ] Integration tests for LLM pipeline
  - [ ] Puzzle solution path testing

## Future Enhancements (Post-MVP)

### Multi-Room System
- Semantic memory with RAG
- Room transition animations
- Persistent world changes

### Advanced Features
- **Skill Checks**: D&D-style ability scores and dice rolls
- **Magic System**: Spell slots, magical abilities, artifact powers
- **NPC System**: Characters with behavior trees (py_trees)
- **Time Mechanics**: Timed puzzles, day/night cycles

### Scaling Considerations
- Redis for working memory cache
- Advanced context management for long sessions
- Multi-model support (Claude, Llama, etc.)

## File Structure
```
greenroom3/
├── __init__.py            # ✅ Created
├── requirements.txt       # ✅ Created  
├── .env.example          # ✅ Created
├── core/
│   ├── __init__.py       # ✅ Created
│   ├── game_objects.py   # ✅ Created (GameObject, Player, Room)
│   ├── game_state.py     # 🔨 Next to build
│   ├── properties.py     # ⏳ Pending
│   └── history.py        # ⏳ Pending
├── llm/
│   ├── __init__.py       # ✅ Created (skeleton)
│   ├── prompt_builder.py # ⏳ Pending
│   ├── response_parser.py# ⏳ Pending
│   └── workflow.py       # ⏳ Pending (LangGraph)
├── utils/
│   ├── __init__.py       # ✅ Created (logger setup)
│   ├── embeddings.py     # ⏳ Pending
│   ├── narrator.py       # ⏳ Pending
│   └── validator.py      # ⏳ Pending
├── puzzles/
│   ├── base.py          # ⏳ Pending
│   └── library/         # ⏳ Pending
├── rooms/
│   └── test_room/
│       ├── config.yaml  # ⏳ Pending
│       └── puzzles.py   # ⏳ Pending
├── ui/
│   └── streamlit_app.py # ⏳ Pending
└── game.py              # ⏳ Pending (main loop)
```

## Design Decisions Summary

1. **State Mutation**: Hybrid (mutable + commits)
2. **Property Access**: Nested dict with convenience methods  
3. **Validation**: Two-tier (structural/physics)
4. **LLM Model**: GPT-5 (GPT-4 fallback)
5. **Classification**: Embedding similarity with LLM fallback
6. **State Syntax**: Dot notation (`door.locked`)
7. **Failure Style**: Adaptive based on absurdity
8. **Save System**: Session-based
9. **Knowledge Leaking Prevention**: DiscoveryState tracking with UNKNOWN/DISCOVERED/EXAMINED states
10. **Physics**: Realistic constraints (no quantum tunneling, weight/size limits respected)

## Next Steps

1. **Implement GameState class** with transaction system
2. **Create GameObject base classes** with property management
3. **Build LangGraph workflow** for action processing
4. **Develop first test room** with simple puzzle
5. **Integrate LLM** with prompt engineering
6. **Add narrative layer** with sardonic personality

## Success Metrics

- Player can attempt any reasonable (or unreasonable) action
- System maintains coherent state through creative solutions
- Failures are entertaining rather than frustrating
- State can be replayed for debugging
- New rooms can be added with just YAML + validation logic

## Notes

The engine prioritizes player agency and narrative flexibility while maintaining enough structure for coherent gameplay. Physics is law until magic says otherwise, and failure is just another punchline in the cosmic joke of escape.

---

## Hand-Off Message

**Currently Working On**: Building core greenroom3 implementation based on architectural decisions.

**Just Completed**:
- ✅ Created project structure and initialization files
- ✅ Built `game_objects.py` with full 3D spatial model, visibility system, discovery states
- ✅ Implemented Player class with realistic inventory management  
- ✅ Set up requirements.txt with GPT-5 support
- ✅ Created .env.example with configuration options
- ✅ Set up logging and utilities

**Current Task**: Building `game_state.py` with transaction management, state validation, and pickup mechanics.

**Key Implementation Notes**:
- Using GPT-5's Responses API for better reasoning control
- Knowledge leaking prevention through DiscoveryState enum
- Realistic physics with weight/size limits (no quantum tunneling)
- Two-tier validation (structural violations vs physics warnings)

**Next Steps**:
1. Complete GameState class with transaction system
2. Build LLM integration layer (prompt builder, response parser)
3. Create LangGraph workflow for action processing
4. Design test room with simple puzzle
5. Implement main game loop