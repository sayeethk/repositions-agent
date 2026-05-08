"""
Prioritizer — Computes priority scores and ranks projects.

Score formula:
  urgency = 1000 / days_to_line_down  (higher = more urgent)
  financial = revenue_impact_daily * 0.1
  overdue = count(overdue_milestones) * 50
  cascade = cascade_risk_bonus

Total = urgency + financial + overdue + cascade
"""

from datetime import datetime
from typing import Dict, List, Tuple

from data.models import Project


class Prioritizer:
    """Ranks projects by computed priority score."""

    def __init__(self, dependency_engine=None):
        self.dependency_engine = dependency_engine

    def score(self, project: Project) -> float:
        """Calculate the priority score for a single project."""
        today = datetime.now()

        ldd = project.line_down_date
        revenue = project.revenue_impact_daily

        # Count overdue milestones
        overdue_count = sum(1 for m in project.milestones.values() if m.is_overdue)

        if not ldd:
            # No line-down date: score on overdue + revenue only
            return (revenue * 0.1) + (overdue_count * 50)

        days = max((ldd - today).days, 1)

        urgency = 1000.0 / days
        financial = revenue * 0.1
        overdue = overdue_count * 50.0

        # Cascade risk: check if overdue milestones block downstream gates
        cascade = 0.0
        if self.dependency_engine:
            for m in project.milestones.values():
                if m.is_overdue:
                    impacted = self.dependency_engine.cascade(m.name)
                    cascade += len(impacted) * 10.0

        return urgency + financial + overdue + cascade

    def rank(self, projects: Dict[str, Project]) -> List[Tuple[str, float]]:
        """
        Return a list of (part_number, score) tuples sorted by score descending.
        """
        scored = [(part_num, self.score(proj)) for part_num, proj in projects.items()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
