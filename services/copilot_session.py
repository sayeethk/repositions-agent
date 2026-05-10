"""
CopilotSession — Interactive weekly update layer for the PM.
"""

from services.copilot_parser import CopilotParser
from utils.helpers import print_boxed_header

class CopilotSession:
    def __init__(self, agent):
        self.agent = agent

    def run(self):
        print("\n")
        print_boxed_header("WEEKLY IMS AUTO-UPDATE COPILOT")
        print("  Analyzing portfolio status...\n")
        
        # 1. Print Portfolio Summary
        summary = self.agent.get_portfolio_summary()
        # Sort summary by count descending
        sorted_summary = sorted(summary.items(), key=lambda x: x[1], reverse=True)
        
        for milestone, count in sorted_summary:
            print(f"  • {count} parts at {milestone}")
            
        print("\n" + "-"*60)
        
        # 2. Ask natural language question
        response = input("  > What changed since last week?\n  > ").strip()
        
        if not response:
            print("  [Copilot] No changes provided. Exiting copilot.")
            return

        # 3. Parse Response
        all_parts = list(self.agent.projects.keys())
        
        # Gather all known milestones across all projects
        all_milestones = set()
        for proj in self.agent.projects.values():
            for m in proj.milestones.keys():
                all_milestones.add(m)
                
        parser = CopilotParser(known_part_numbers=all_parts, known_milestones=list(all_milestones))
        
        print("\n  [Copilot] Interpreting response...")
        intents = parser.parse(response)
        
        if not intents:
            print("  [Copilot] Could not detect any actionable updates from the response.")
            return
            
        # 4. Preview Changes
        print("\n  [Copilot] I detected the following actions:\n")
        for i, intent in enumerate(intents, 1):
            action = intent["action"]
            parts_str = ", ".join(intent["part_numbers"])
            ms = intent["milestone"] or "current milestone"
            date = intent["date"] or "today"
            reason = intent["reason"]
            
            if action == "COMPLETE_MILESTONE":
                print(f"    {i}. Complete '{ms}' on {date} for: {parts_str}")
            elif action == "DELAY_MILESTONE":
                print(f"    {i}. Delay '{ms}' for: {parts_str} (Reason: {reason})")
            elif action == "REVERT_MILESTONE":
                print(f"    {i}. Revert '{ms}' for: {parts_str} (Reason: {reason})")
            else:
                print(f"    {i}. Unknown action for: {parts_str}")
                
        print()
        confirm = input("  > Apply these updates? (yes/no): ").strip().lower()
        
        # 5. Apply Changes
        if confirm in ("yes", "y"):
            self.agent.apply_copilot_updates(intents)
            print("\n  [Copilot] ✅ Updates applied to projects.")
            save = input("  > Save updates to Excel? (yes/no): ").strip().lower()
            if save in ("yes", "y"):
                self.agent.save_to_excel()
                print("  [Copilot] 💾 Saved.")
        else:
            print("\n  [Copilot] Updates discarded.")
