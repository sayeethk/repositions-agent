"""
Repositions Agent — Portfolio Management for Aerospace Supplier Transitions

Entry point: Loads projects from Excel, calculates priority scores,
displays the risk dashboard, and drives PM conversation sessions.
"""

import sys
import os
import datetime

from data.excel_loader import ExcelLoader
from data.models import Project, Status
from core.agent import RepositionsAgent
from services.copilot_session import CopilotSession
from utils.helpers import (
    format_date,
    format_currency,
    days_remaining,
    status_icon,
    priority_label,
    print_separator,
    print_boxed_header,
)


def main():
    print_boxed_header("REPOSITIONS AGENT v1.0")
    print("  Portfolio Management System for Supplier Transitions")
    print("  Cross-functional Chief of Staff")
    print()

    # ------------------------------------------------------------------ #
    #  1. Load Projects
    # ------------------------------------------------------------------ #
    try:
        loader = ExcelLoader()
        projects_dict = loader.load_projects()
    except FileNotFoundError as e:
        print(f"[ERROR] Critical Error: {e}")
        print("   Check path in config/settings.py (EXCEL_PATH)")
        print()
        print("   To get started, place your tracker file at:")
        print("   ./input/Simplified IMS Template.xlsm")
        return
    except Exception as e:
        print(f"[ERROR] Critical Error: Could not load Excel file.")
        print(f"   Error: {e}")
        return

    # ------------------------------------------------------------------ #
    #  2. Initialize Agent
    # ------------------------------------------------------------------ #
    agent = RepositionsAgent()
    agent.load_projects(projects_dict)

    # Enrich with ISC Agent data (line-down dates + revenue impact)
    skip_isc = "--skip-isc" in sys.argv
    enriched_count = 0
    if not skip_isc:
        print("\n[ISC] Enriching projects with ISC Agent data...")
        print("  This will launch Chrome to query the ISC Agent.")
        print("  Please ensure you are logged into Chrome first.\n")
        input("  Press Enter to launch Chrome...")
        enriched_count = agent.enrich_with_isc()
    else:
        print("\n[ISC] Skipping ISC enrichment as requested.")
    print()

    # Pre-calculate all priorities (now with real ISC data)
    agent.recalculate_all()

    print(f"[OK] Loaded {len(projects_dict)} active project(s).")
    print(f"[OK] Enriched {enriched_count} project(s) with ISC data.")
    print("[OK] Repositions Online.\n")

    # ------------------------------------------------------------------ #
    #  3. Main Loop
    # ------------------------------------------------------------------ #
    while True:
        # Refresh state each cycle
        agent.recalculate_all()

        # Display Dashboard
        display_dashboard(agent)

        # Get PM Command
        print_separator("-")
        user_input = input("> PM Command (e.g., 'select 1', 'update PART-123', 'help'): ").strip().lower()

        if user_input in ('exit', 'quit', 'q'):
            _handle_exit(agent)
            break

        if user_input == 'help':
            _show_help()
            continue

        if user_input == 'status':
            _show_full_registry(agent)
            continue

        if user_input == 'save':
            _handle_save(agent)
            continue

        if user_input == 'copilot':
            _handle_copilot(agent)
            continue

        if user_input.startswith('select '):
            _handle_select(agent, user_input)
            continue

        if user_input.startswith('update '):
            _handle_update(agent, user_input)
            continue

        print("[?] Unrecognized command. Type 'help' for options.\n")


# ------------------------------------------------------------------ #
#  Dashboard Display
# ------------------------------------------------------------------ #

def display_dashboard(agent: RepositionsAgent):
    """Display the top-risk projects dashboard."""
    print()
    print_boxed_header("DASHBOARD: TOP RISK PROJECTS")

    top_risks = agent.get_top_risks(limit=5)

    if not top_risks:
        print("  [OK] All projects appear to be On Track or Complete.")
        print("  Type 'status' for full view, or 'exit' to close.\n")
        return

    for i, proj in enumerate(top_risks, 1):
        days_left = days_remaining(proj.line_down_date)
        icon = status_icon(proj.status)
        label = priority_label(proj.priority_score)

        print(f"  {i}. {icon} {proj.name} (Part: {proj.part_number})")
        print(f"     Status: {proj.status.value} | Priority: {label} ({proj.priority_score:.1f})")
        print(f"     Line-Down: {format_date(proj.line_down_date)} ({days_left} days left)")
        print(f"     Revenue: {format_currency(proj.revenue_impact_daily)}/day")

        # Show overdue milestones
        overdue_ms = [m.name for m in proj.milestones.values() if m.is_overdue]
        if overdue_ms:
            print(f"     [!] Overdue: {', '.join(overdue_ms)}")
        else:
            print(f"     [OK] No overdue milestones")
        print()


# ------------------------------------------------------------------ #
#  Command Handlers
# ------------------------------------------------------------------ #

def _handle_exit(agent: RepositionsAgent):
    """Save state and exit."""
    print("\nShutting down Repositions. Saving updates...")
    agent.save_to_excel()
    print("[OK] State saved. Goodbye.\n")
    sys.exit(0)


def _show_help():
    """Display available commands."""
    print()
    print_boxed_header("AVAILABLE COMMANDS")
    print("  select [number]  - Drill into a project from the dashboard")
    print("  update [part]    - Report status on a specific part number")
    print("  copilot          - Open the Weekly IMS Auto-Update Copilot")
    print("  status           - Show full project registry")
    print("  save             - Save updates to Excel tracker")
    print("  help             - Show this help menu")
    print("  exit / quit      - Save and close\n")


def _show_full_registry(agent: RepositionsAgent):
    """Display all projects in the registry."""
    print()
    print_boxed_header("FULL PROJECT REGISTRY")
    print()

    for part_num, proj in agent.projects.items():
        icon = status_icon(proj.status)
        label = priority_label(proj.priority_score)
        print(f"  {icon} {part_num} | {proj.name} | {proj.status.value} | Score: {proj.priority_score:.1f} [{label}]")

    print()


def _handle_save(agent: RepositionsAgent):
    """Save current state to Excel."""
    success = agent.save_to_excel()
    if success:
        print("[OK] Updates saved to Excel tracker.")
    else:
        print("[ERROR] Failed to save. Check file permissions and path.")


def _handle_copilot(agent: RepositionsAgent):
    """Run the Weekly IMS Auto-Update Copilot session."""
    session = CopilotSession(agent)
    session.run()


def _handle_select(agent: RepositionsAgent, user_input: str):
    """Drill into a project by dashboard index."""
    try:
        idx = int(user_input.split(' ')[1]) - 1
        top_risks = agent.get_top_risks(limit=5)
        if 0 <= idx < len(top_risks):
            project = top_risks[idx]
            _run_project_session(agent, project)
        else:
            print("[ERROR] Invalid selection index.")
    except (IndexError, ValueError):
        print("[ERROR] Invalid format. Use 'select 1' (number from dashboard).")


def _handle_update(agent: RepositionsAgent, user_input: str):
    """Drill into a project by part number."""
    part_num = user_input.split(' ', 1)[1].strip()
    proj = agent.projects.get(part_num)
    if proj:
        _run_project_session(agent, proj)
    else:
        print(f"[ERROR] Project with Part Number '{part_num}' not found.")
        print("   Type 'status' to see all registered projects.")


# ------------------------------------------------------------------ #
#  Project Session
# ------------------------------------------------------------------ #

def _run_project_session(agent: RepositionsAgent, project: Project):
    """Run the full conversation session for a single project."""
    print()
    print_boxed_header(f"PROJECT SESSION: {project.name}")
    print(f"  Part: {project.part_number}")
    print(f"  Incoming: {project.incoming_supplier}")
    print(f"  Outgoing: {project.outgoing_supplier}")
    print()

    # Show team roster
    if project.team:
        print("  [TEAM] Team Roster:")
        for person in project.team:
            open_count = len([ai for ai in person.action_items if ai.status != "Completed"])
            print(f"    - {person.name} ({person.function.value}) -- {open_count} open item(s)")
        print()

    # Run conversation
    agent.run_conversation(project)

    # Post-session: ask to save
    print()
    save = input("  Save updates to Excel? (yes/no): ").strip().lower()
    if save in ('yes', 'y'):
        agent.save_to_excel()
        print("  [OK] Saved.\n")


if __name__ == "__main__":
    main()
