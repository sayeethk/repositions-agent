from data.models import Project, Milestone, ActionItem, Person, Status, Function
from datetime import datetime

class RepositionsAgent:
    def __init__(self):
        self.projects = {}  # part_number -> Project
        self.audit_log = []

    def load_projects(self, loaded_projects: dict):
        """Load projects from ExcelLoader"""
        self.projects = loaded_projects
        # Calculate initial priorities
        now = datetime.now()
        for p in self.projects.values():
            p.calculate_priority(now)

    def get_top_risks(self, limit: int = 3):
        """Return top N projects by priority score"""
        sorted_projects = sorted(self.projects.values(), key=lambda p: p.priority_score, reverse=True)
        return sorted_projects[:limit]

    def log_event(self, project_name: str, event_type: str, details: str):
        """Maintain audit trail"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "project": project_name,
            "type": event_type,
            "details": details
        }
        self.audit_log.append(entry)

    def get_open_action_items(self, project: Project, function: str = None):
        """Filter action items by project and optionally by function"""
        items = project.action_items
        if function:
            items = [ai for ai in items if ai.owner_function.upper() == function.upper()]
        return [ai for ai in items if ai.status != "Completed"]

    def suggest_solution(self, blocker_reason: str, milestone_name: str):
        """Playbook logic: Match reason to known solutions"""
        reason_lower = blocker_reason.lower()
        
        if "tooling" in reason_lower or "fixture" in reason_lower:
            if "delay" in reason_lower or "late" in reason_lower:
                return "Expedite Tooling: Contact supplier engineering for daily updates. Consider bridge supply if possible."
            if "quality" in reason_lower or "fail" in reason_lower:
                return "Quality Block: Request immediate sample shipment for inspection. Engage Quality Eng for joint root cause analysis."
        
        if "material" in reason_lower or "component" in reason_lower:
            return "Supply Chain: Verify inventory at supplier. Authorize air freight for critical components."
        
        if "approval" in reason_lower or "ppap" in reason_lower or "sig" in reason_lower:
            return "Process Block: Escalate to Supplier Quality Manager. Request digital signature workflow if physical is blocked."
        
        if "logistics" in reason_lower or "shipping" in reason_lower:
            return "Logistics: Book dedicated freight. Check customs clearance status."

        return "General Escalation: Request weekly recovery plan from Supplier Project Manager. Define daily checkpoint."

    def update_milestone_completion(self, project: Project, milestone_name: str, pm_confirmation: bool):
        """Update milestone based on PM input"""
        if milestone_name not in project.milestones:
            return False, "Milestone not found."
        
        milestone = project.milestones[milestone_name]
        
        if pm_confirmation:
            milestone.actual = datetime.now().strftime("%d/%m/%Y")
            milestone.status = Status.COMPLETE
            milestone.is_overdue = False
            self.log_event(project.name, "Milestone Completed", f"{milestone_name} marked complete by PM.")
            return True, f"Milestone '{milestone_name}' marked as Complete."
        else:
            # If not complete, we need a blocker reason (handled in chat loop)
            return False, "Acknowledged. Please provide the reason for delay."

    def add_action_item(self, project: Project, owner: str, func: str, desc: str, due: str, milestone: str = None):
        ai = ActionItem(owner, func, desc, due, milestone)
        project.action_items.append(ai)
        self.log_event(project.name, "Action Item Created", f"{owner} ({func}): {desc}")