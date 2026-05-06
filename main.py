import json
from data.excel_loader import ExcelLoader
from core.dependency_engine import DependencyEngine
from core.prioritizer import Prioritizer
from config.settings import DEPENDENCIES_PATH
from services.conversation import ConversationManager


def main():
    print("\n=== Repositioning Agent ===")
    project_name = input("Enter Project Name: ").strip()
    part_numbers = input("Enter Part Numbers (comma-separated): ").split(",")
    part_numbers = [p.strip() for p in part_numbers]
    irb_date = input("Enter IRB Approval Date (DD/MM/YYYY): ").strip()

    print("DEBUG: Projects loaded =", len(projects))   # 👈 ADD THIS

    if not projects:
        print("❌ No projects found. Check Excel format.")
        return

    with open(DEPENDENCIES_PATH) as f:
        dep_map = json.load(f)

    dependency_engine = DependencyEngine(dep_map)

    prioritizer = Prioritizer(dependency_engine)
    ranked = prioritizer.rank(projects)

    print("\nTop Projects:")
    for name, score in ranked[:5]:
        print(name, score)

    project = projects[ranked[0][0]]

    convo = ConversationManager(dependency_engine)
    convo.run(project)


if __name__ == "__main__":
    main()