"""
ConversationManager — Drives the PM conversation loop for each project.

For each flagged milestone, the flow is:
1. Ask "Has [milestone] been completed?"
2. If yes → log completion, update tracker, recalculate
3. If no → ask "What is blocking this?" → capture reason → suggest solutions
4. Always confirm with PM before logging a solution as the chosen path
5. Track action items by person
6. Maintain full audit trail
"""

import datetime
from typing import Optional
from data.models import Project, Milestone, Status, ActionItem
from core.dependency_engine import DependencyEngine
from core.playbook import Playbook


class ConversationManager:
    """
    Orchestrates the PM conversation loop for a single project session.
    """

    def __init__(self, dependency_engine: DependencyEngine, playbook: Playbook, agent=None):
        self.dependency_engine = dependency_engine
        self.playbook = playbook
        self.agent = agent  # RepositionsAgent reference for logging/action items

    def run(self, project: Project):
        """Run the full conversation loop for a project."""
        self._print_project_header(project)
        self._print_action_items_summary(project)

        # Sort milestones: overdue first, then by baseline date
        sorted_milestones = sorted(
            project.milestones.values(),
            key=lambda m: (0 if m.is_overdue else 1, m.baseline or datetime.datetime.max),
        )

        for milestone in sorted_milestones:
            # Skip already completed milestones
            if milestone.status == Status.COMPLETE:
                continue

            self._handle_milestone(project, milestone)

        # Post-session summary
        self._print_session_summary(project)

    # ------------------------------------------------------------------ #
    #  Display Helpers
    # ------------------------------------------------------------------ #

    def _print_project_header(self, project: Project):
        """Print project context with urgency anchors."""
        print(f"\n{'='*60}")
        print(f"  PROJECT: {project.name}")
        print(f"  Part: {project.part_number} | Program: {project.program}")
        print(f"  Incoming: {project.incoming_supplier} | Outgoing: {project.outgoing_supplier}")

        if project.line_down_date:
            days_left = (project.line_down_date - datetime.datetime.now()).days
            days_left = max(0, days_left)
            print(f"  ⚠️  Line-Down Date: {project.line_down_date.strftime('%d/%m/%Y')} ({days_left} days)")
        print(f"  💰 Revenue Impact: ${project.revenue_impact_daily:,.2f}/day")
        print(f"  Status: {project.status.value} | Priority: {project.priority_score:.1f}")
        print(f"{'='*60}")

    def _print_action_items_summary(self, project: Project):
        """Surface open action items by function."""
        open_items = [ai for ai in project.action_items if ai.status != "Completed"]
        if not open_items:
            return

        print(f"\n📋 OPEN ACTION ITEMS ({len(open_items)})")
        print("-" * 40)

        # Group by function
        by_function = {}
        for ai in open_items:
            by_function.setdefault(ai.owner_function, []).append(ai)

        for func, items in by_function.items():
            for item in items:
                overdue_flag = ""
                if item.due_date and item.due_date < datetime.datetime.now():
                    overdue_flag = " ⛔ OVERDUE"
                print(f"  [{func}] {item.owner_name}: {item.description} (Due: {self._fmt_date(item.due_date)}){overdue_flag}")

        print()

    def _print_session_summary(self, project: Project):
        """Print end-of-session summary."""
        print(f"\n{'='*60}")
        print(f"  SESSION COMPLETE: {project.name}")
        print(f"  Updated Status: {project.status.value}")
        print(f"  Updated Priority: {project.priority_score:.1f}")

        completed = sum(1 for m in project.milestones.values() if m.status == Status.COMPLETE)
        total = len(project.milestones)
        print(f"  Milestones: {completed}/{total} Complete")

        open_items = [ai for ai in project.action_items if ai.status != "Completed"]
        if open_items:
            print(f"  Open Action Items: {len(open_items)}")

        print(f"{'='*60}")

    # ------------------------------------------------------------------ #
    #  Milestone Conversation
    # ------------------------------------------------------------------ #

    def _handle_milestone(self, project: Project, milestone: Milestone):
        """Drive the conversation for a single milestone."""
        status_icon = "⛔" if milestone.is_overdue else "⏳"
        baseline_str = self._fmt_date(milestone.baseline)

        print(f"\n{status_icon} {milestone.name} (Baseline: {baseline_str})")

        # Show cascade impact if overdue
        if milestone.is_overdue:
            impacted = self.dependency_engine.cascade(milestone.name)
            if impacted:
                print(f"   ⚡ Cascade Risk: This blocks → {', '.join(impacted)}")

        # Show revenue anchor
        if project.revenue_impact_daily:
            print(f"   💰 At ${project.revenue_impact_daily:,.2f}/day exposure")

        # --- Question 1: Completion ---
        answer = self._ask(f"Has '{milestone.name}' been completed? (yes/no): ").strip().lower()

        if answer in ("yes", "y"):
            self._log_completion(project, milestone)
            return

        if answer in ("no", "n"):
            self._handle_incomplete(project, milestone)
            return

        if answer in ("idk", "i don't know", "not sure"):
            self._handle_escalation(project, milestone)
            return

        print("  → Please answer 'yes' or 'no'.")
        self._log_audit(project, "INVALID_RESPONSE", {"milestone": milestone.name, "response": answer})

    # ------------------------------------------------------------------ #
    #  Completion Path
    # ------------------------------------------------------------------ #

    def _log_completion(self, project: Project, milestone: Milestone):
        """Log milestone completion with PM confirmation."""
        # Ask for completion date
        date_answer = self._ask("Enter completion date (DD/MM/YYYY) or press Enter for today: ").strip()

        if date_answer:
            from data.models import parse_date
            comp_date = parse_date(date_answer)
            if comp_date:
                milestone.actual = comp_date
            else:
                print("  → Invalid date format. Using today's date.")
                milestone.actual = datetime.datetime.now()
        else:
            milestone.actual = datetime.datetime.now()

        milestone.status = Status.COMPLETE
        milestone.is_overdue = False

        print(f"  ✅ '{milestone.name}' marked COMPLETE on {self._fmt_date(milestone.actual)}")

        self._log_audit(project, "MILESTONE_COMPLETE", {
            "milestone": milestone.name,
            "actual_date": milestone.actual.strftime("%d/%m/%Y") if milestone.actual else None,
        })

    # ------------------------------------------------------------------ #
    #  Incomplete Path
    # ------------------------------------------------------------------ #

    def _handle_incomplete(self, project: Project, milestone: Milestone):
        """Handle incomplete milestone: capture blocker, suggest solutions."""
        # --- Question 2: Blocker ---
        blocker = self._ask("What is blocking this? (Describe the issue): ").strip()

        if not blocker:
            print("  → No blocker provided. Marking as At Risk.")
            blocker = "No reason provided"
            milestone.status = Status.AT_RISK
        else:
            milestone.blocker_reason = blocker
            milestone.status = Status.DELAYED

        self._log_audit(project, "MILESTONE_BLOCKED", {
            "milestone": milestone.name,
            "blocker": blocker,
        })

        # --- Suggest Solutions ---
        solutions = self.playbook.suggest(milestone.name)

        if solutions:
            print(f"\n  💡 Suggested Resolution Paths:")
            for i, sol in enumerate(solutions, 1):
                print(f"    {i}. {sol}")

            choice = self._ask("Select a solution (number) or describe your plan: ").strip()

            if choice.isdigit() and 1 <= int(choice) <= len(solutions):
                chosen = solutions[int(choice) - 1]
                # Confirm before logging
                confirm = self._ask(f"Confirm '{chosen}' as the chosen path? (yes/no): ").strip().lower()
                if confirm in ("yes", "y"):
                    milestone.suggested_solution = chosen
                    print(f"  → Solution logged: {chosen}")
                    self._create_action_item_from_solution(project, milestone, chosen)
                else:
                    print("  → Solution not confirmed. Awaiting PM plan.")
            else:
                milestone.suggested_solution = choice if choice else "PM to provide plan"
                print(f"  → Custom plan noted: {milestone.suggested_solution}")
        else:
            print("  → No standard playbook entry. PM to provide resolution plan.")
            plan = self._ask("What is your resolution plan?").strip()
            if plan:
                milestone.suggested_solution = plan

        # --- Ask for revised forecast ---
        forecast = self._ask("Enter revised forecast date (DD/MM/YYYY) or press Enter to skip: ").strip()
        if forecast:
            from data.models import parse_date
            rev_date = parse_date(forecast)
            if rev_date:
                milestone.revised_forecast = rev_date
                print(f"  → Revised forecast set to {self._fmt_date(rev_date)}")

        # Calculate delay days
        if milestone.baseline:
            delay = (datetime.datetime.now() - milestone.baseline).days
            milestone.is_overdue = delay > 0
            project.delay_days = max(project.delay_days, delay)

    # ------------------------------------------------------------------ #
    #  Escalation Path (PM says "I don't know")
    # ------------------------------------------------------------------ #

    def _handle_escalation(self, project: Project, milestone: Milestone):
        """When PM says 'I don't know', escalate to the relevant function owner."""
        owner = milestone.owner_name or "Project Manager"
        func = milestone.owner_function or "Program Management"

        print(f"\n  ⚡ ESCALATION: Routing to {owner} ({func}) directly.")

        draft = (
            f"Hi {owner},\n"
            f"Milestone '{milestone.name}' on project {project.name} ({project.part_number}) "
            f"is at risk. Baseline was {self._fmt_date(milestone.baseline)}.\n"
            f"PM needs your update. Line-down date: {self._fmt_date(project.line_down_date)}.\n"
            f"Revenue exposure: ${project.revenue_impact_daily:,.2f}/day.\n"
            f"Please provide status and any blockers by EOD."
        )

        print(f"\n  📧 Pre-drafted escalation:\n  {draft.replace(chr(10), chr(10) + '  ')}")

        send = self._ask("Send this escalation? (yes/no): ").strip().lower()

        if send in ("yes", "y"):
            print(f"  → Escalation sent to {owner}.")
            self._log_audit(project, "ESCALATION_SENT", {
                "milestone": milestone.name,
                "to": owner,
                "function": func,
            })
            # Create action item for the function owner
            if self.agent:
                self.agent.add_action_item(
                    project=project,
                    owner_name=owner,
                    owner_function=func,
                    description=f"Provide status update for '{milestone.name}'",
                    due_date=(datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%d/%m/%Y"),
                    linked_milestone=milestone.name,
                )
        else:
            print("  → Escalation skipped. PM to follow up manually.")

    # ------------------------------------------------------------------ #
    #  Action Item Creation from Solutions
    # ------------------------------------------------------------------ #

    def _create_action_item_from_solution(self, project: Project, milestone: Milestone, solution: str):
        """Create an action item from a chosen playbook solution."""
        if not self.agent:
            return

        owner = milestone.owner_name or "Project Manager"
        func = milestone.owner_function or "Program Management"

        # Set due date: 3 business days from now (simplified)
        due = datetime.datetime.now() + datetime.timedelta(days=3)

        self.agent.add_action_item(
            project=project,
            owner_name=owner,
            owner_function=func,
            description=f"Execute: {solution}",
            due_date=due.strftime("%d/%m/%Y"),
            linked_milestone=milestone.name,
        )
        print(f"  → Action item created for {owner}: '{solution}'")

    # ------------------------------------------------------------------ #
    #  Audit Logging
    # ------------------------------------------------------------------ #

    def _log_audit(self, project: Project, event_type: str, details: dict):
        """Log an event to the agent's audit trail."""
        if self.agent:
            details["project"] = project.part_number
            self.agent._log_event(event_type, details)

    # ------------------------------------------------------------------ #
    #  Input / Formatting Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _ask(prompt: str) -> str:
        """Prompt the user and return their input."""
        return input(f"  {prompt} ")

    @staticmethod
    def _fmt_date(date) -> str:
        """Format a datetime object as DD/MM/YYYY, or return 'N/A'."""
        if isinstance(date, datetime.datetime):
            return date.strftime("%d/%m/%Y")
        if date:
            return str(date)
        return "N/A"
