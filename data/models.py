from datetime import datetime

def parse_date(value):
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except:
                continue
    return None


class Milestone:
    def __init__(self, name):
        self.name = name
        self.baseline = None
        self.actual = None

    def is_overdue(self):
        baseline = parse_date(self.baseline)

        if not baseline or self.actual:
            return False

        return baseline < datetime.today()


class Project:
    def __init__(self, name, metadata, milestones):
        self.name = name
        self.metadata = metadata
        self.milestones = milestones

    def overdue_milestones(self):
        return [m for m in self.milestones.values() if m.is_overdue()]