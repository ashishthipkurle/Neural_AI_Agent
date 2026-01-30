# My AI Agent

A modular, extensible, local-first autonomous AI agent designed for safety and determinism.

## Architecture

The agent follows a layered architecture:
- **Core**: Handles intent parsing, tool routing, and the main execution loop.
- **Tools**: Independent modules for specific capabilities (OS, Math, Vision, etc.).
- **Memory**: Dual-memory system (Vector Store + SQL).
- **Security**: Permission management and audit logging.

## Directory Structure

```
/agent
 ├── core/       # Orchestration logic
 ├── tools/      # Functional modules
 ├── memory/     # Data persistence
 ├── config/     # Configuration files
 ├── main.py     # Entry point
```

## Setup

1. Install dependencies:
   ```bash
   pip install pyyaml
   ```
2. Run the agent:
   ```bash
   python agent/main.py
   ```

## Usage

Currently, the agent supports basic "Hello" and "Time" commands via a mock intent parser.

- "Hello" -> Triggers Chat Tool
- "Time" -> Triggers OS Tool (Mock)
