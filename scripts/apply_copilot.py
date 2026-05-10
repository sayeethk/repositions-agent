import os
import sys
import glob

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import data.excel_loader
from data.excel_loader import ExcelLoader
from core.agent import RepositionsAgent
from services.copilot_parser import CopilotParser
import config.settings
from data.excel_writer import ExcelWriter
import data.excel_writer

def main():
    user_input = "3060735-3- this part completed FAIR on 04/02/2026"
    
    input_dir = r"c:\Users\H525267\Repositions Project\repositions-agent\input"
    files = glob.glob(os.path.join(input_dir, "Simplified*.xlsm"))

    all_projects = {}
    
    print("Loading projects...")
    for file_path in files:
        data.excel_loader.EXCEL_PATH = file_path
        loader = ExcelLoader()
        try:
            projects_dict = loader.load_projects()
            all_projects.update(projects_dict)
        except Exception as e:
            pass

    agent = RepositionsAgent()
    agent.load_projects(all_projects)
    agent.recalculate_all()
    
    # Extract milestones
    all_milestones = set()
    for proj in agent.projects.values():
        for m in proj.milestones.keys():
            all_milestones.add(m)
            
    parser = CopilotParser(known_part_numbers=list(agent.projects.keys()), known_milestones=list(all_milestones))
    intents = parser.parse(user_input)
    
    print("\nCopilot detected the following actions:")
    for i, intent in enumerate(intents, 1):
        action = intent["action"]
        parts_str = ", ".join(intent["part_numbers"])
        ms = intent["milestone"] or "current milestone"
        date = intent["date"] or "today"
        reason = intent["reason"]
        
        if action == "COMPLETE_MILESTONE":
            print(f"  {i}. Complete '{ms}' on {date} for: {parts_str}")
        elif action == "DELAY_MILESTONE":
            print(f"  {i}. Delay '{ms}' for: {parts_str} (Reason: {reason})")
        elif action == "REVERT_MILESTONE":
            print(f"  {i}. Revert '{ms}' for: {parts_str} (Reason: {reason})")
        else:
            print(f"  {i}. Unknown action for: {parts_str}")
            
    # Apply to memory
    agent.apply_copilot_updates(intents)
    
    print("\nSaving updates to Excel files...")
    writer = ExcelWriter()
    
    saved_count = 0
    for file_path in files:
        config.settings.EXCEL_PATH = file_path
        data.excel_writer.EXCEL_PATH = file_path
        try:
            writer.write_projects(agent.projects)
            saved_count += 1
        except Exception as e:
            print(f"Error saving {file_path}: {e}")
            
    print(f"Saved to {saved_count} files successfully!")

if __name__ == "__main__":
    main()
