#!/usr/bin/env python3
"""
BLACKBOX AI — The Autonomous Terminal Agent
Built for Caspian Hackathon 2026

Usage:
    python agent.py --demo         Run the sequential 6-demo hackathon judge suite in terminal
    python agent.py --interactive  Launch interactive terminal shell to talk directly to BLACKBOX AI
    python agent.py --daemon       Run persistent background agent daemon
"""

import sys
import os
import argparse
import asyncio
import logging

# Ensure Windows UTF-8 stdout encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend modules import cleanly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.models import ChannelType, IncidentCategory, TicketStatus
from backend.database import init_db, list_tickets, get_channel_messages, get_settings, update_setting
from backend.agent_engine import agent_engine, COLOR_BOLD, COLOR_CYAN, COLOR_GREEN, COLOR_YELLOW, COLOR_MAGENTA, COLOR_RED, COLOR_RESET
from backend.scheduler import scheduler_service

logging.basicConfig(level=logging.WARNING)


def print_banner():
    banner = f"""
{COLOR_BOLD}{COLOR_CYAN}
  [#] [#] [#]  [#]      [A]    [#] [#]  [#]   [#]  [#] [#] [#]  [#] [#]  [#]   [#]
  [#]      [#] [#]     [A A]   [#]      [#]  [#]   [#]      [#] [#]   [#] [#] [#]
  [#] [#] [#]  [#]    [A   A]  [#]      [#] [#]    [#] [#] [#]  [#]   [#] [#] [#]
  [#]      [#] [#]   [A A A A] [#]      [#]  [#]   [#]      [#] [#]   [#] 
  [#] [#] [#]  [#] [#][A     A][#] [#]  [#]   [#]  [#] [#] [#]  [#] [#]  [#]   [#]
{COLOR_RESET}
  {COLOR_BOLD}BLACKBOX AI — Autonomous Startup Operator{COLOR_RESET} | Powered by Caspian SDK 2026
  -------------------------------------------------------------------------
"""
    print(banner)


async def run_demo_suite():
    """Execute the 6 hackathon judge demonstration scenarios in sequence."""
    print_banner()
    print(f"{COLOR_BOLD}{COLOR_GREEN}▶ STARTING BLACKBOX AI JUDGE DEMO SUITE{COLOR_RESET}\n")

    await init_db()

    demos = [
        ("1. Customer Support Rescue", ChannelType.EMAIL, "client_alex", "Alex Mercer", "Hi support, I still haven't received my refund for order #9928. Can you check this?"),
        ("2. Team Operations Blocker", ChannelType.SLACK, "dev_bob", "Bob (Backend)", "🚨 BLOCKER: Payments System Gateway is down! Out of memory error."),
        ("3. Community Bug Report", ChannelType.DISCORD, "sarah_discord", "Sarah Chen", "Hey team, found a bug on checkout page. Throws 404 on domestic cards."),
        ("4. Vendor Intelligence Delay", ChannelType.WHATSAPP, "vendor_dhl", "DHL Express Logistics", "Shipment VND-9988 for Payments System Gateway hardware is delayed outside Bangalore."),
        ("5. Lead Engagement Follow-up", ChannelType.EMAIL, "lead_tesla", "Tesla Procurement Desk", "Interested in your enterprise task automation solution. Let's schedule a time."),
    ]

    for title, channel, sender_id, sender_name, text in demos:
        print(f"\n{COLOR_BOLD}{COLOR_MAGENTA}==================================================================={COLOR_RESET}")
        print(f"{COLOR_BOLD}{COLOR_MAGENTA}   DEMO SCENARIO: {title}{COLOR_RESET}")
        print(f"{COLOR_BOLD}{COLOR_MAGENTA}==================================================================={COLOR_RESET}")
        
        await agent_engine.process_reasoning_cycle(channel, sender_id, sender_name, text)
        await asyncio.sleep(1.5)

    # Demo 6: Daily Briefing
    print(f"\n{COLOR_BOLD}{COLOR_MAGENTA}==================================================================={COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_MAGENTA}   DEMO SCENARIO: 6. Founder Daily Briefing{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_MAGENTA}==================================================================={COLOR_RESET}")
    await agent_engine.tool_compile_briefing()

    # Demo 7: Founder Disappears Mode
    print(f"\n{COLOR_BOLD}{COLOR_MAGENTA}==================================================================={COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_MAGENTA}   DEMO SCENARIO: 7. WOW Feature: Founder Disappears Mode{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_MAGENTA}==================================================================={COLOR_RESET}")
    print(f"{COLOR_YELLOW}Toggling Founder Disappears Mode -> ACTIVE (True)...{COLOR_RESET}")
    await update_setting("founder_disappears_mode", "1")
    
    await agent_engine.process_reasoning_cycle(
        ChannelType.EMAIL, 
        "client_alex", 
        "Alex Mercer", 
        "Where is my refund for cancellation?"
    )

    print(f"\n{COLOR_BOLD}{COLOR_GREEN}==================================================================={COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_GREEN}   [SUCCESS] ALL DEMO SCENARIOS EXECUTED SUCCESSFULLY! (7/7){COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_GREEN}==================================================================={COLOR_RESET}\n")


async def run_interactive_shell():
    """Launch interactive CLI console to talk to BLACKBOX AI directly."""
    print_banner()
    print(f"{COLOR_BOLD}{COLOR_GREEN}▶ INTERACTIVE AGENT SHELL ACTIVE{COLOR_RESET}")
    print("Type your message below. You can simulate channel inputs (e.g. 'refund complaint', 'server down', 'bug 404') or type 'exit' to quit.\n")

    await init_db()

    while True:
        try:
            user_input = input(f"{COLOR_BOLD}{COLOR_CYAN}User Input > {COLOR_RESET}").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting BLACKBOX Agent Console. Goodbye!")
                break

            # Process input through Agent Reasoning Cycle
            await agent_engine.process_reasoning_cycle(
                ChannelType.WEB,
                "terminal_user",
                "Console User",
                user_input,
            )
        except (KeyboardInterrupt, EOFError):
            print("\nExiting agent shell.")
            break


async def run_daemon_mode():
    """Run persistent background agent daemon."""
    print_banner()
    print(f"{COLOR_BOLD}{COLOR_GREEN}▶ RUNNING BLACKBOX AUTONOMOUS AGENT DAEMON{COLOR_RESET}")
    print("Listening for multi-channel Caspian webhooks and monitoring operations SLA...\n")

    await init_db()
    scheduler_service.start()

    try:
        while True:
            await asyncio.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping daemon process...")
    finally:
        scheduler_service.shutdown()


async def run_memory_inspector():
    """Display startup Memory Graph database, active tickets, and channel logs in terminal."""
    print_banner()
    print(f"{COLOR_BOLD}{COLOR_GREEN}▶ COGNITIVE MEMORY GRAPH & OPERATIONS INSPECTOR{COLOR_RESET}\n")

    await init_db()

    from backend.database import get_graph_data, list_tickets, get_channel_messages, get_settings

    # 1. System Settings
    settings = await get_settings()
    is_away = settings.get("founder_disappears_mode") == "1"
    print(f"{COLOR_BOLD}{COLOR_YELLOW}[SYSTEM SETTINGS]{COLOR_RESET}")
    print(f" • Founder Disappears Mode: {COLOR_BOLD}{'ACTIVE (Enabled)' if is_away else 'INACTIVE (Disabled)'}{COLOR_RESET}\n")

    # 2. Memory Graph Nodes & Edges
    graph = await get_graph_data()
    print(f"{COLOR_BOLD}{COLOR_CYAN}[COGNITIVE MEMORY GRAPH]{COLOR_RESET}")
    print(f" • Total Context Nodes: {len(graph['nodes'])}")
    print(f" • Total Entity Links: {len(graph['edges'])}\n")
    
    print(f"{COLOR_BOLD}   Nodes:{COLOR_RESET}")
    for node in graph["nodes"]:
        print(f"    └─ [{node['label']}] {node['id']} ({node['properties'].get('name', 'N/A')})")

    print(f"\n{COLOR_BOLD}   Relationships (Edges):{COLOR_RESET}")
    for edge in graph["edges"]:
        print(f"    └─ {edge['source']} --({edge['type']})--> {edge['target']}")

    # 3. Active Incident Tickets
    tickets = await list_tickets()
    print(f"\n{COLOR_BOLD}{COLOR_MAGENTA}[INCIDENT TICKETS QUEUE] ({len(tickets)} total){COLOR_RESET}")
    for t in tickets:
        print(f"  [{t.id}] Status: {t.status.value} | Category: {t.category.value} | Assignee: {t.assigned_to or 'Unassigned'}")
        print(f"   └─ Title: {t.title}")

    # 4. Recent Multi-Channel Logs
    logs = await get_channel_messages()
    print(f"\n{COLOR_BOLD}{COLOR_GREEN}[RECENT CASPIAN CHANNEL LOGS] ({len(logs)} messages){COLOR_RESET}")
    for msg in logs:
        print(f"  [{msg.channel.upper()}] {msg.sender} -> {msg.recipient} ({msg.timestamp.strftime('%H:%M:%S')})")
        print(f"   └─ Text: {msg.text[:80]}...")
    print("\n")


def main():
    parser = argparse.ArgumentParser(description="BLACKBOX AI — Autonomous Terminal Agent")
    parser.add_argument("--demo", action="store_true", help="Run the hackathon judge demonstration suite in terminal")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive CLI agent shell")
    parser.add_argument("--daemon", action="store_true", help="Run persistent background agent daemon")
    parser.add_argument("--inspect", action="store_true", help="Inspect Memory Graph nodes, edges, tickets, and logs")

    args = parser.parse_args()

    if args.interactive:
        asyncio.run(run_interactive_shell())
    elif args.daemon:
        asyncio.run(run_daemon_mode())
    elif args.inspect:
        asyncio.run(run_memory_inspector())
    else:
        # Default to running the demo suite if no flags provided
        asyncio.run(run_demo_suite())


if __name__ == "__main__":
    main()
