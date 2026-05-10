"""
CopilotParser — A lightweight, regex-based NLP engine to interpret PM commands.
"""

import re
from typing import List, Dict, Optional, Tuple

class CopilotParser:
    def __init__(self, known_part_numbers: List[str], known_milestones: List[str]):
        self.known_part_numbers = known_part_numbers
        # Sort milestones by length descending to match longest first
        self.known_milestones = sorted(known_milestones, key=len, reverse=True)

    def parse(self, text: str) -> List[Dict]:
        """
        Parses PM natural language input and returns a list of intended actions.
        """
        intents = []
        
        # Split text into sentences if multiple actions are provided separated by newlines or periods
        sentences = re.split(r'\n|\. ', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            parts = self._extract_parts(sentence)
            if not parts:
                # If no specific parts found, we can't act on this sentence safely
                continue
                
            milestone = self._extract_milestone(sentence)
            date_str = self._extract_date(sentence)
            
            action, reason = self._detect_intent(sentence)
            
            if action == "REVERT_MILESTONE":
                reason = "reverted: " + sentence
                
            intents.append({
                "action": action,
                "part_numbers": parts,
                "milestone": milestone,
                "date": date_str,
                "reason": reason
            })
            
        return intents

    def _extract_parts(self, text: str) -> List[str]:
        found_exact = []
        for part in self.known_part_numbers:
            # Escape regex characters in part
            escaped = re.escape(part)
            # Use regex boundaries to avoid partial matches
            if re.search(rf'\b{escaped}\b', text, re.IGNORECASE):
                found_exact.append(part)
        return found_exact

    def _extract_milestone(self, text: str) -> Optional[str]:
        for ms in self.known_milestones:
            if ms.lower() in text.lower():
                return ms
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        # Match dates like 8-May, May 8, 8/5, 8/5/2026, 8th May
        date_pattern = r'\b(\d{1,2}-[a-zA-Z]{3,4}|\d{1,2}/\d{1,2}(?:/\d{2,4})?|[a-zA-Z]{3,9}\s\d{1,2}(?:st|nd|rd|th)?)\b'
        match = re.search(date_pattern, text)
        if match:
            return match.group(1)
        return None

    def _detect_intent(self, text: str) -> Tuple[str, Optional[str]]:
        text_lower = text.lower()
        
        # Check for revert first
        if "back to" in text_lower or "revert" in text_lower:
            return "REVERT_MILESTONE", None
            
        # Check for delay/hold
        if "delay" in text_lower or "hold" in text_lower or "block" in text_lower:
            # Try to extract the reason
            reason_match = re.search(r'(due to|because of|waiting on)\s+(.*)', text_lower)
            if reason_match:
                reason = reason_match.group(2).strip()
            else:
                reason = "Issue reported via Copilot"
            return "DELAY_MILESTONE", reason
            
        # Default to complete/move
        if "move" in text_lower or "to" in text_lower or "complete" in text_lower or "submit" in text_lower or "approve" in text_lower:
            return "COMPLETE_MILESTONE", None
            
        return "UNKNOWN", None
