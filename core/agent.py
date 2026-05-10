"""
RepositionsAgent — Central orchestration class for the Portfolio Management Agent.

Responsibilities:
- Maintain the project registry (dict keyed by part_number)
- Calculate priority scores for all projects
- Surface top-risk projects and milestones
- Coordinate conversation sessions with PMs
- Track action items by person across all projects
- Maintain audit trail of all interactions
- Write updates back to Excel tracker
"""

import json
import datetime
from typing import Dict, List, Optional
from data.models import Project, Milestone, ActionItem, Status, Function, parse_date
from core.prioritizer import Prioritizer
from core.dependency_engine import DependencyEngine
from core.playbook import Playbook
from services.conversation import ConversationManager
from data.excel_writer import ExcelWriter
from services.isc_chat_client import ISCChatClient


class RepositionsAgent:
    """
    Cross-functional chief of staff for aerospace supplier transition projects.
    """

    def __init__(self):
        self.projects: Dict[str, Project] = {}
        self.audit_log: List[dict] = []
        self._load_dependencies()
        self.prioritizer = Prioritizer(self.dependency_engine)
        self.playbook = Playbook()
        self.conversation = ConversationManager(self.dependency_engine, self.playbook, self)
        self.excel_writer = ExcelWriter()
        self.isc_chat = ISCChatClient()

    def _load_dependencies(self):
        """Load milestone dependency map from config."""
        try:
            with open("./config/milestone_dependencies.json", "r") as f:
                dep_map = json.load(f)
            self.dependency_engine = DependencyEngine(dep_map)
        except FileNotFoundError:
            # Fallback: empty dependency map
            self.dependency_engine = DependencyEngine({})

    def load_projects(self, projects_dict: Dict[str, Project]):
        """Load projects from Excel loader into the agent registry."""
        self.projects = projects_dict
        self._log_event("SYSTEM", f"Loaded {len(projects_dict)} projects into registry")

    # ------------------------------------------------------------------ #
    #  ISC Enrichment
    # ------------------------------------------------------------------ #

    def enrich_with_isc(self) -> int:
        """
        Query ISC Agent for line-down dates and revenue impact via Selenium browser automation.
        Updates projects in registry with the returned data.

        Returns:
            Number of projects successfully enriched.
        """
        if not self.projects:
            print("  [WARN] No projects to enrich.")
            return 0

        part_numbers = list(self.projects.keys())
        print(f"  [ISC] Launching Chrome for ISC Agent...")

        # Launch browser
        if not self.isc_chat.launch():
            print("  [ERROR] Failed to launch ISC Agent. Skipping enrichment.")
            return 0

        print("  [ISC] Browser ready. Sending query...")

        # Query all parts
        results = self.isc_chat.query_parts(part_numbers)

        # Close browser
        self.isc_chat.close()

        # Update projects with results
        enriched = 0
        failed = []

        for part_num, data in results.items():
            if part_num in self.projects:
                proj = self.projects[part_num]
                if data.get("line_down_date"):
                    # Parse FY2026 Week 40 format or DD/MM/YYYY format
                    ld_str = data["line_down_date"]
                    proj.line_down_date = parse_date(ld_str)
                if data.get("revenue_impact"):
                    proj.revenue_impact_daily = float(data["revenue_impact"])
                enriched += 1

        # Track parts that weren't in the response
        responded_parts = set(results.keys())
        for part_num in part_numbers:
            if part_num not in responded_parts:
                failed.append(part_num)

        print(f"  [OK] ISC Enrichment: {enriched}/{len(part_numbers)} parts enriched")
        if failed:
            print(f"  [WARN] {len(failed)} parts not returned by ISC Agent:")
            for p in failed[:10]:
                print(f"    - {p}")
            if len(failed) > 10:
                print(f"    ... and {len(failed) - 10} more")

        self._log_event("ISC_ENRICHMENT", {
            "total": len(part_numbers),
            "enriched": enriched,
            "failed": len(failed),
            "failed_parts": failed,
        })

        return enriched

    # ------------------------------------------------------------------ #
    #  Priority & Ranking
    # ------------------------------------------------------------------ #

    def recalculate_all(self, current_date: Optional[datetime.datetime] = None):
        """Recalculate priority scores and milestone status for every project."""
        for proj in self.projects.values():
            proj.calculate_priority(current_date)

    def get_top_risks(self, limit: int = 5) -> List[Project]:
        """Return the top-N projects sorted by priority score (descending)."""
        ranked = self.prioritizer.rank(self.projects)
        # ranked is list of (part_number, score)
        result = []
        for part_num, _score in ranked[:limit]:
            if part_num in self.projects:
                result.append(self.projects[part_num])
        return result

    # ------------------------------------------------------------------ #
    #  Action Items
    # ------------------------------------------------------------------ #

    def get_open_action_items(self, project: Project) -> List[ActionItem]:
        """Return all non-completed action items for a project."""
        return [ai for ai in project.action_items if ai.status != "Completed"]

    def get_action_items_by_person(self, project: Project) -> Dict[str, List[ActionItem]]:
        """Group open action items by team member name."""
        by_person: Dict[str, List[ActionItem]] = {}
        for ai in self.get_open_action_items(project):
            by_person.setdefault(ai.owner_name, []).append(ai)
        return by_person

    def get_action_items_by_function(self, project: Project) -> Dict[str, List[ActionItem]]:
        """Group open action items by function."""
        by_func: Dict[str, List[ActionItem]] = {}
        for ai in self.get_open_action_items(project):
            by_func.setdefault(ai.owner_function, []).append(ai)
        return by_func

    def add_action_item(self, project: Project, owner_name: str, owner_function: str,
                        description: str, due_date: str, linked_milestone: Optional[str] = None):
        """Create a new action item and attach it to the project and person."""
        ai = ActionItem(
            owner_name=owner_name,
            owner_function=owner_function,
            description=description,
            due_date=due_date,
            linked_milestone=linked_milestone,
        )
        project.action_items.append(ai)
        # Also attach to the Person object if they exist on the team
        for person in project.team:
            if person.name == owner_name:
                person.action_items.append(ai)
                break
        self._log_event("ACTION_ITEM", {
            "project": project.part_number,
            "owner": owner_name,
            "function": owner_function,
            "description": description,
            "due_date": due_date,
        })

    # ------------------------------------------------------------------ #
    #  Audit Trail
    # ------------------------------------------------------------------ #

    def _log_event(self, event_type: str, details):
        """Append an entry to the audit log."""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": event_type,
            "details": details,
        }
        self.audit_log.append(entry)

    def get_audit_trail(self, project_part_number: Optional[str] = None,
                        limit: int = 50) -> List[dict]:
        """Return recent audit entries, optionally filtered by project."""
        trail = self.audit_log
        if project_part_number:
            trail = [e for e in trail if e.get("details", {}).get("project") == project_part_number]
        return trail[-limit:]

    # ------------------------------------------------------------------ #
    #  Excel Write-Back
    # ------------------------------------------------------------------ #

    def save_to_excel(self):
        """Write all project updates back to the Excel tracker."""
        try:
            self.excel_writer.write_projects(self.projects)
            self._log_event("SYSTEM", "Successfully saved updates to Excel tracker")
            return True
        except Exception as e:
            self._log_event("ERROR", f"Failed to save to Excel: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Conversation Session
    # ------------------------------------------------------------------ #

    def run_conversation(self, project: Project):
        """Drive the PM conversation loop for a single project."""
        self._log_event("SESSION_START", {"project": project.part_number, "name": project.name})
        self.conversation.run(project)
        self._log_event("SESSION_END", {"project": project.part_number})
        # Recalculate after conversation
        project.calculate_priority()

    # ------------------------------------------------------------------ #
    #  Copilot Actions
    # ------------------------------------------------------------------ #

    def get_portfolio_summary(self) -> Dict[str, int]:
        """
        Calculates a summary of the portfolio by grouping projects by their
        current active milestone (the first incomplete milestone).
        """
        summary = {}
        for proj in self.projects.values():
            sorted_milestones = sorted(
                proj.milestones.values(),
                key=lambda m: m.baseline or datetime.datetime.max
            )
            
            current_milestone = "Not Started"
            for m in sorted_milestones:
                if m.status != Status.COMPLETE:
                    current_milestone = m.name
                    break
            else:
                if sorted_milestones:
                    current_milestone = "All Complete"
                else:
                    current_milestone = "No Milestones"
                    
            summary[current_milestone] = summary.get(current_milestone, 0) + 1
            
        return summary

    def apply_copilot_updates(self, updates: List[Dict]):
        """
        Applies a list of parsed copilot intents to the portfolio.
        """
        from data.models import parse_date, Status
        
        for update in updates:
            action = update["action"]
            parts = update["part_numbers"]
            ms_name = update["milestone"]
            date_str = update["date"]
            reason = update["reason"]
            
            for part in parts:
                proj = self.projects.get(part)
                if not proj:
                    continue
                    
                if action == "COMPLETE_MILESTONE" and ms_name:
                    if ms_name in proj.milestones:
                        ms = proj.milestones[ms_name]
                        ms.status = Status.COMPLETE
                        ms.is_overdue = False
                        if date_str:
                            parsed = parse_date(date_str)
                            # If date parses, use it. Else use today.
                            ms.actual = parsed if parsed else datetime.datetime.now()
                        else:
                            ms.actual = datetime.datetime.now()
                        self._log_event("COPILOT_COMPLETE", {"part": part, "milestone": ms_name})
                        
                elif action == "DELAY_MILESTONE":
                    # If milestone is provided, delay that specific one. Otherwise delay the project active milestone.
                    if ms_name and ms_name in proj.milestones:
                        ms = proj.milestones[ms_name]
                        ms.status = Status.DELAYED
                        ms.blocker_reason = reason
                        self._log_event("COPILOT_DELAY", {"part": part, "milestone": ms_name, "reason": reason})
                    else:
                        sorted_milestones = sorted(
                            proj.milestones.values(),
                            key=lambda m: m.baseline or datetime.datetime.max
                        )
                        for m in sorted_milestones:
                            if m.status != Status.COMPLETE:
                                m.status = Status.DELAYED
                                m.blocker_reason = reason
                                self._log_event("COPILOT_DELAY", {"part": part, "milestone": m.name, "reason": reason})
                                break
                                
                elif action == "REVERT_MILESTONE" and ms_name:
                    if ms_name in proj.milestones:
                        ms = proj.milestones[ms_name]
                        ms.status = Status.AT_RISK
                        ms.actual = None
                        ms.is_overdue = False
                        if reason:
                            ms.blocker_reason = reason
                        self._log_event("COPILOT_REVERT", {"part": part, "milestone": ms_name})
                        
                # Recalculate project priority after updates
                proj.calculate_priority()
