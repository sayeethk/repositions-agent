"""
Playbook — Known resolution paths for common milestone blockers.

Each milestone maps to a list of actionable resolution strategies that have
worked in past supplier transition projects. The PM selects one, and we log
it as the chosen path with an action item.
"""

from typing import Dict, List


# Playbook: milestone -> list of resolution strategies
PLAYBOOK: Dict[str, List[str]] = {
    # Tooling Release blockers
    "Tooling Release": [
        "Expedite tooling via air freight from OEM",
        "Engage backup tooling vendor for parallel build",
        "Escalate to supplier executive for priority scheduling",
        "Pre-release partial tooling to start early operations",
    ],
    # First Off Tool Samples blockers
    "First Off Tool Samples": [
        "Arrange expedited courier for sample shipment",
        "Request digital first-off data (CMM reports) before physical parts",
        "Engage Engineering for remote dimensional review",
        "Authorize air freight for critical samples",
    ],
    # FAIR Complete blockers
    "FAIR Complete": [
        "Pre-submit FAIR draft for early Engineering review",
        "Arrange joint FAIR review call with supplier Engineering",
        "Parallel-process FAIR sections (split between teams)",
        "Escalate FAIR review SLA to Quality leadership",
    ],
    # PPAP Submission blockers
    "PPAP Submission": [
        "Submit partial PPAP package (flag missing sections)",
        "Arrange virtual PPAP submission review",
        "Engage supplier Quality for gap closure support",
        "Expedite missing documentation via dedicated liaison",
    ],
    # PPAP Approval blockers
    "PPAP Approval": [
        "Escalate to internal Quality leadership for fast-track approval",
        "Arrange on-site PPAP review at supplier facility",
        "Submit conditional approval with close-out action items",
        "Engage customer for early PPAP acceptance (if allowed)",
    ],
    # Logistics Setup blockers
    "Logistics Setup": [
        "Arrange bridge supply from existing inventory",
        "Engage 3PL for expedited logistics setup",
        "Pre-position buffer stock at receiving site",
        "Activate backup logistics route",
    ],
    # Line Trial blockers
    "Line Trial": [
        "Schedule line trial during non-production hours",
        "Arrange supplier technician on-site support",
        "Pre-stage trial materials 48hrs in advance",
        "Coordinate cross-functional standby team for rapid issue resolution",
    ],
    # SOP Readiness blockers
    "SOP Readiness": [
        "Implement interim work instructions (temporary SOP)",
        "Run parallel production line for validation",
        "Escalate SOP approval through fast-track process",
        "Engage Production Management for resource reallocation",
    ],
    # Generic fallback for unmapped milestones
    "_default": [
        "Escalate to supplier executive for resolution",
        "Arrange bridge supply to buy time",
        "Engage cross-functional task force",
        "Expedite via air freight / priority shipping",
        "Request daily status calls until resolved",
    ],
}


class Playbook:
    """Provides resolution suggestions for milestone blockers."""

    def __init__(self):
        self.data = PLAYBOOK

    def suggest(self, milestone_name: str) -> List[str]:
        """
        Return a list of suggested resolution paths for the given milestone.
        Falls back to the default playbook entry if the milestone is unmapped.
        """
        return self.data.get(milestone_name, self.data.get("_default", []))

    def add_entry(self, milestone_name: str, solutions: List[str]):
        """Add a new playbook entry (for learning from past resolutions)."""
        self.data[milestone_name] = solutions
