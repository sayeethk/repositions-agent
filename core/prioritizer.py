from datetime import datetime

class Prioritizer:

    def __init__(self, dependency_engine):
        self.dependency_engine = dependency_engine

    def score(self, project):
        today = datetime.today()

        ldd = project.metadata.get("line_down_date")
        revenue = project.metadata.get("revenue", 0)

        overdue = project.overdue_milestones()

        if not ldd:
            return 0

        days = max((ldd - today).days, 1)

        return (1000 / days) + (revenue * 0.1) + (len(overdue) * 50)

    def rank(self, projects):
        return sorted(
            [(p.name, self.score(p)) for p in projects.values()],
            key=lambda x: x[1],
            reverse=True
        )