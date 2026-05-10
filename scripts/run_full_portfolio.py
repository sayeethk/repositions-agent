import os
import sys
import glob

# Add the parent directory to sys.path so we can import from core, data, etc.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.excel_loader import ExcelLoader
from core.agent import RepositionsAgent
from services.copilot_session import CopilotSession
import config.settings

def main():
    # Target directory is the outer input directory
    input_dir = r"c:\Users\H525267\Repositions Project\repositions-agent\input"
    pattern = os.path.join(input_dir, "Simplified*.xlsm")
    files = glob.glob(pattern)

    all_projects = {}

    print(f"Found {len(files)} Simplified Excel files.")

    for file_path in files:
        # Temporarily patch EXCEL_PATH inside excel_loader since it was imported directly
        import data.excel_loader
        data.excel_loader.EXCEL_PATH = file_path
        
        loader = ExcelLoader()
        
        try:
            projects_dict = loader.load_projects()
            all_projects.update(projects_dict)
            print(f"Loaded {len(projects_dict)} projects from {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Failed to load {file_path}: {e}")

    print(f"\nTotal unique projects across all files: {len(all_projects)}")

    # Save to Markdown artifact
    artifact_path = r"c:\Users\H525267\.gemini\antigravity\brain\77608c41-fd3c-4e1c-bf7e-40003fad0f6d\Sayees_Portfolio.md"
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write("# Sayee's Portfolio\n\n")
        f.write("| Part Number | Project Name | Status | Priority Score |\n")
        f.write("|---|---|---|---|\n")
        for part, proj in sorted(all_projects.items()):
            score = getattr(proj, 'priority_score', 0)
            f.write(f"| {part} | {proj.name} | {proj.status.value} | {score} |\n")
    print(f"Saved portfolio list to {artifact_path}")

    # Initialize Agent
    agent = RepositionsAgent()
    agent.load_projects(all_projects)
    
    # Recalculate to set active milestones and priorities properly
    agent.recalculate_all()

    # Run Copilot Session
    session = CopilotSession(agent)
    session.run()

if __name__ == "__main__":
    main()
