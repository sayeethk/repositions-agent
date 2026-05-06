class ConversationManager:

    def __init__(self, dependency_engine):
        self.dependency_engine = dependency_engine

    def run(self, project):
        print(f"\nPROJECT: {project.name}")

        for m in project.milestones.values():

            if m.actual:
                continue

            if m.is_overdue():
                print(f"\n⚠️ {m.name} is OVERDUE")

                impacted = self.dependency_engine.cascade(m.name)
                for i in impacted:
                    print(f"→ impacts {i}")

            print(f"\nHas '{m.name}' been completed? (yes/no)")
            res = input().lower()

            if res == "yes":
                m.actual = input("Enter completion date: ")
            else:
                print("Blocker noted.")