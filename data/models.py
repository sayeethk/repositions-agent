import datetime
from enum import Enum
from typing import Optional

class Status(Enum):
    ON_TRACK = "On Track"
    AT_RISK = "At Risk"
    DELAYED = "Delayed"
    COMPLETE = "Complete"

class Function(Enum):
    ENGINEERING = "Engineering"
    QUALITY = "Quality"
    PROGRAM_MGMT = "Program Management"
    BUYER = "Buyer"
    PLANNER = "Production Site Planner"

def parse_date(date_str):
    """Parses DD/MM/YYYY or MM/DD/YYYY, returning a datetime object or None."""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    if not date_str:
        return None
    
    # Try DD/MM/YYYY first (common in UK/Aero)
    try:
        return datetime.datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        pass
    
    # Try MM/DD/YYYY (common in US)
    try:
        return datetime.datetime.strptime(date_str, "%m/%d/%Y")
    except ValueError:
        pass
        
    # Try ISO format YYYY-MM-DD
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass

    return None

class ActionItem:
    def __init__(self, owner_name: str, owner_function: str, description: str, due_date: str, linked_milestone: Optional[str] = None):
        self.owner_name = owner_name
        self.owner_function = owner_function
        self.description = description
        self.due_date = parse_date(due_date)
        self.linked_milestone = linked_milestone
        self.status = "Open"  # Open, In Progress, Completed, Blocked
        self.created_at = datetime.datetime.now()

class Person:
    def __init__(self, name: str, function: str):
        self.name = name
        self.function = Function(function.upper()) if function.upper() in [f.value for f in Function] else Function.PROGRAM_MGMT # Default fallback
        self.action_items = []

class Milestone:
    """A project milestone with baseline/actual tracking and blocker resolution."""
    name: str
    baseline: Optional[datetime.datetime]
    actual: Optional[datetime.datetime]
    owner_name: Optional[str]
    owner_function: Optional[str]
    is_overdue: bool
    status: Status
    blocker_reason: Optional[str]
    suggested_solution: Optional[str]
    revised_forecast: Optional[datetime.datetime]

    def __init__(self, name: str, baseline: Optional[str] = None, actual: Optional[str] = None, owner: Optional[str] = None, function: Optional[str] = None):
        self.name = name
        self.baseline = parse_date(baseline) if baseline else None
        self.actual = parse_date(actual) if actual else None
        self.owner_name = owner
        self.owner_function = function
        self.is_overdue = False
        self.status = Status.ON_TRACK
        self.blocker_reason = None
        self.suggested_solution = None
        self.revised_forecast = None

    def check_status(self, current_date=None):
        check_date = current_date or datetime.datetime.now()
        if self.actual:
            self.status = Status.COMPLETE
            self.is_overdue = False
        elif self.baseline and self.baseline < check_date:
            self.status = Status.DELAYED
            self.is_overdue = True
        elif self.baseline:
            self.status = Status.ON_TRACK
            self.is_overdue = False
        else:
            self.status = Status.AT_RISK
            self.is_overdue = False

class Project:
    def __init__(self, name: str, part_number: str, program: str, 
                 incoming_supplier: str, outgoing_supplier: str,
                 line_down_date: str, revenue_impact_daily: float):
        
        self.name = name
        self.part_number = part_number
        self.program = program
        self.incoming_supplier = incoming_supplier
        self.outgoing_supplier = outgoing_supplier
        self.line_down_date = parse_date(line_down_date)
        self.revenue_impact_daily = float(revenue_impact_daily) if revenue_impact_daily else 0.0
        
        self.milestones = {}  # dict[str, Milestone]
        self.team = []        # list[Person]
        self.action_items = [] # list[ActionItem]
        self.status = Status.AT_RISK
        self.delay_days = 0
        self.priority_score = 0

    def add_milestone(self, name: str, baseline: Optional[str] = None, actual: Optional[str] = None, owner: Optional[str] = None, function: Optional[str] = None):
        m = Milestone(name, baseline, actual, owner, function)
        self.milestones[name] = m

    def calculate_priority(self, current_date=None):
        """
        Score = (Days to Line Down Weight) + (Revenue Impact) + (Overdue Milestones) + (Cascade Risk)
        """
        if not current_date:
            current_date = datetime.datetime.now()
            
        days_to_line_down = 0
        if self.line_down_date:
            delta = self.line_down_date - current_date
            days_to_line_down = max(0, delta.days) # Don't count negative days as high priority (already down)

        # 1. Urgency: Less days = Higher score (Inverse)
        # Cap at 90 days for calculation stability
        urgency_score = max(0, 90 - days_to_line_down) * 1.0 

        # 2. Financial Impact: Higher $ = Higher score
        # Normalize revenue: Every $1000/day adds 1 point
        financial_score = self.revenue_impact_daily / 1000.0

        # 3. Milestone Health: Overdue milestones add huge points
        overdue_count = 0
        for m in self.milestones.values():
            m.check_status(current_date)
            if m.is_overdue:
                overdue_count += 1
        
        milestone_score = overdue_count * 5.0 # Each overdue milestone is critical

        # 4. Cascade Risk: If "PPAP Approval" is overdue, "SOP" is at risk
        # Simplified: If key gate is overdue, add bonus
        cascade_bonus = 0
        critical_gates = ["PPAP Approval", "Line Trial", "SOP Readiness"]
        for gate in critical_gates:
            if gate in self.milestones and self.milestones[gate].is_overdue:
                cascade_bonus += 10.0

        self.priority_score = urgency_score + financial_score + milestone_score + cascade_bonus
        
        # Update overall project status
        if overdue_count > 0:
            self.status = Status.DELAYED
        elif any(m.status == Status.AT_RISK for m in self.milestones.values()):
            self.status = Status.AT_RISK
        else:
            self.status = Status.ON_TRACK

        return self.priority_score