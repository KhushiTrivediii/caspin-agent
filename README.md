# 🚀 BLACKBOX AI — The Autonomous Terminal Agent
### *Built for Caspian Hackathon 2026*

**BLACKBOX AI** is an autonomous AI operations employee designed to run startup workflows across multiple communication channels without human intervention. 

Instead of sitting in a web chat window or static dashboard, BLACKBOX AI is built as a **true autonomous CLI agent** (`agent.py`). It exposes its cognitive reasoning, memory graph lookups, tool calls, and Caspian SDK multi-channel actions directly in your terminal.

---

## 🌟 Execution Modes

BLACKBOX AI can be launched in 4 terminal execution modes:

### 1. Sequential Judge Demo Suite (`python agent.py --demo`)
Runs all hackathon operational scenarios in sequence directly in the terminal, showcasing agent thinking, tool executions (`query_memory_graph`, `send_message`), and multi-channel dispatches.

### 2. Interactive Agent Console (`python agent.py --interactive`)
Launches an interactive terminal shell where you can talk to BLACKBOX AI directly. Type inputs like `"refund complaint"`, `"server down"`, or `"checkout bug"` to watch the agent reason and execute actions in real-time.

### 3. Memory Graph Inspector (`python agent.py --inspect`)
Displays a formatted view of the SQLite Memory Graph database, entity relationships, open incident tickets, and multi-channel log feeds.

### 4. Autonomous Agent Daemon (`python agent.py --daemon`)
Runs a persistent background loop listening for incoming Caspian webhooks and monitoring 15-second SLA timeouts.

---

## 🛠️ Cognitive Agent Tools

- `tool_query_memory_graph(entity_id)`: Searches context nodes and relationship edges.
- `tool_send_caspian_message(channel, recipient, text)`: Dispatches multi-channel messages (Email, Slack, Discord, WhatsApp, Telegram).
- `tool_update_ticket(ticket_id, status)`: Manages incident lifecycle states.
- `tool_escalate_founder(ticket_id, reason)`: Handles founder notifications or resolves autonomously if Founder Disappears mode is active.
- `tool_compile_briefing()`: Aggregates startup statistics into executive Telegram reports.

---

## 🚀 Quick Start

### 1. Run the Terminal Demo Suite
```bash
python agent.py --demo
```

### 2. Launch Interactive Console
```bash
python agent.py --interactive
```

### 3. Inspect Memory Graph
```bash
python agent.py --inspect
```

---

## 🧪 Automated Verification Suite

Run the full integration test suite:

```bash
python test_blackbox.py
```

---

## 📄 License
MIT License
