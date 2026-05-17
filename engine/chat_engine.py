"""
AI Chat assistant — rule-based NLP for spatial planning requirements.
"""

import re
import json


class ChatEngine:
    """Processes natural language requirements and converts to room/furniture config."""

    def __init__(self, furniture_catalog=None):
        self.catalog = furniture_catalog
        self.context = {
            "room_configured": False,
            "furniture_added": [],
            "preferences": {},
        }

    # Pattern matchers
    PATTERNS = {
        "seating_request": [
            r"(?:i\s+)?(?:need|want)\s+(?:seating|seats?)\s+for\s+(\d+)\s+(?:people|persons?|users?)",
            r"(\d+)\s+(?:people|persons?|users?)\s+(?:need|should|will)\s+(?:sit|work|be\s+seated)",
            r"accommodate\s+(\d+)\s+(?:people|persons?)",
            r"capacity\s+(?:of|for)?\s*(\d+)",
        ],
        "add_furniture": [
            r"(?:add|place|put|include)\s+(\d+)\s+(standing\s+desk|work\s+desk|desk|shared\s+table|meeting\s+table|chair|storage|cabinet|lounge\s+chair|sofa|bench|collaborative\s+seat)s?",
            r"(\d+)\s+(standing\s+desk|work\s+desk|desk|shared\s+table|meeting\s+table|chair|storage|cabinet|lounge\s+chair|sofa|bench)s?",
        ],
        "meeting_request": [
            r"(\d+)\s+meeting\s+(?:area|room|space|table)s?",
            r"meeting\s+(?:area|room|space|table)s?\s+(?:for\s+)?(\d+)",
        ],
        "daylight_preference": [
            r"(?:more|maximum|max)\s+(?:daylight|sunlight|natural\s+light|light)\s+(?:for|on|at)\s+(?:the\s+)?(\w+)",
            r"(\w+)\s+(?:near|by|next\s+to|close\s+to)\s+(?:the\s+)?window",
            r"(?:prefer|want)\s+(?:daylight|light|bright)",
        ],
        "layout_style": [
            r"(?:make|keep)\s+(?:it|the\s+layout|things)\s+(?:more\s+)?(collaborative|open|private|flexible|dense|spacious)",
            r"(?:more|very)\s+(collaborative|open|private|flexible|dense|spacious)\s+(?:layout|design|space)",
            r"(collaborative|open|private|flexible)\s+(?:workspace|layout|design|style)",
        ],
        "room_size": [
            r"room\s+(?:is|of)\s+(\d+\.?\d*)\s*(?:m|meters?)?\s*(?:x|by|×)\s*(\d+\.?\d*)\s*(?:m|meters?)?",
            r"(\d+\.?\d*)\s*(?:m|meters?)?\s*(?:x|by|×)\s*(\d+\.?\d*)\s*(?:m|meters?)?\s*room",
        ],
        "remove_furniture": [
            r"(?:remove|delete|take\s+out|no)\s+(?:the\s+)?(\d+)?\s*(desk|table|chair|storage|lounge|sofa|bench)s?",
        ],
        "help": [
            r"(?:help|what\s+can\s+you\s+do|how\s+does\s+this\s+work|commands|options)",
        ],
        "greeting": [
            r"(?:hi|hello|hey|good\s+(?:morning|afternoon|evening))",
        ],
    }

    # Map user terms to furniture categories
    TERM_TO_CATEGORY = {
        "desk": "work_desk",
        "work desk": "work_desk",
        "standing desk": "work_desk",
        "shared table": "shared_table",
        "meeting table": "meeting_table",
        "conference table": "meeting_table",
        "chair": "chair",
        "office chair": "chair",
        "storage": "storage",
        "cabinet": "storage",
        "lounge chair": "lounge",
        "sofa": "lounge",
        "couch": "lounge",
        "bench": "collaborative_seating",
        "collaborative seat": "collaborative_seating",
    }

    TERM_TO_STYLE = {
        "collaborative": "collaborative_hub",
        "open": "collaborative_hub",
        "private": "hot_desking",
        "flexible": "hybrid_flex",
        "dense": "hot_desking",
        "spacious": "collaborative_hub",
    }

    def process_message(self, message):
        """Process a user message and return a response with actions.

        Returns:
            dict with 'response' text, 'actions' list, and 'suggestions'
        """
        message_lower = message.strip().lower()
        actions = []
        suggestions = []

        # Check greeting
        if self._matches(message_lower, "greeting"):
            return {
                "response": "Hello! 👋 I'm your AI spatial planning assistant. I can help you configure your coworking space layout. Try telling me:\n\n"
                           "• **\"I need seating for 20 people\"** — I'll suggest furniture\n"
                           "• **\"Add 4 desks near the windows\"** — I'll place furniture\n"
                           "• **\"Make it more collaborative\"** — I'll adjust the style\n"
                           "• **\"2 meeting areas\"** — I'll add meeting tables\n\n"
                           "What would you like to do?",
                "actions": [],
                "suggestions": ["I need seating for 12 people", "Make it collaborative", "Add 2 meeting tables"],
            }

        # Check help
        if self._matches(message_lower, "help"):
            return {
                "response": "🛠️ **Here's what I can help with:**\n\n"
                           "**Capacity Planning:**\n"
                           "• \"I need seating for 20 people\"\n"
                           "• \"Accommodate 15 users\"\n\n"
                           "**Furniture Management:**\n"
                           "• \"Add 6 work desks\"\n"
                           "• \"Place 2 meeting tables\"\n"
                           "• \"Remove chairs\"\n\n"
                           "**Layout Style:**\n"
                           "• \"Make it more collaborative\"\n"
                           "• \"I want a flexible workspace\"\n"
                           "• \"Keep it dense\"\n\n"
                           "**Daylight Preferences:**\n"
                           "• \"Desks near the windows\"\n"
                           "• \"More daylight for work areas\"\n\n"
                           "**Room Setup:**\n"
                           "• \"Room is 8m x 6m\"\n\n"
                           "Just type naturally — I'll understand! 🚀",
                "actions": [],
                "suggestions": ["I need seating for 15 people", "Add 4 desks and 2 meeting tables", "Make it collaborative"],
            }

        # Check seating request
        match = self._find_match(message_lower, "seating_request")
        if match:
            num_people = int(match.group(1))
            actions.append({
                "type": "suggest_capacity",
                "capacity": num_people,
            })
            # Estimate furniture
            desks = max(1, int(num_people * 0.6))
            chairs = num_people
            shared = max(1, num_people // 6)
            meeting = max(1, num_people // 8)

            return {
                "response": f"📊 For **{num_people} people**, I recommend:\n\n"
                           f"• **{desks}** work desks\n"
                           f"• **{chairs}** chairs\n"
                           f"• **{shared}** shared table(s)\n"
                           f"• **{meeting}** meeting table(s)\n"
                           f"• **{max(1, num_people // 5)}** storage unit(s)\n"
                           f"• **{max(1, num_people // 8)}** lounge piece(s)\n\n"
                           f"Shall I apply this configuration? Or would you prefer a specific coworking style?",
                "actions": actions,
                "suggestions": [
                    "Apply this configuration",
                    "Use Hot Desking style",
                    "Use Team Pods style",
                    "Use Collaborative Hub style",
                ],
                "furniture_suggestion": {
                    "work_desk": desks,
                    "chair": chairs,
                    "shared_table": shared,
                    "meeting_table": meeting,
                    "storage": max(1, num_people // 5),
                    "lounge": max(1, num_people // 8),
                },
            }

        # Check add furniture
        match = self._find_match(message_lower, "add_furniture")
        if match:
            count = int(match.group(1))
            term = match.group(2).strip()
            category = self.TERM_TO_CATEGORY.get(term, "work_desk")

            actions.append({
                "type": "add_furniture",
                "category": category,
                "count": count,
            })

            return {
                "response": f"✅ Adding **{count} {term}(s)** to the layout. "
                           f"Click **Generate Layouts** to see the updated plan!",
                "actions": actions,
                "suggestions": ["Generate layouts", f"Add {count} more chairs", "Add meeting table"],
            }

        # Check meeting request
        match = self._find_match(message_lower, "meeting_request")
        if match:
            count = int(match.group(1))
            chairs_per = 6
            actions.append({
                "type": "add_furniture",
                "category": "meeting_table",
                "count": count,
            })
            actions.append({
                "type": "add_furniture",
                "category": "chair",
                "count": count * chairs_per,
            })

            return {
                "response": f"🤝 Adding **{count} meeting area(s)** with **{count * chairs_per} chairs**. "
                           f"Each meeting table seats {chairs_per} people.",
                "actions": actions,
                "suggestions": ["Generate layouts", "Add more seating", "Less chairs per table"],
            }

        # Check layout style
        match = self._find_match(message_lower, "layout_style")
        if match:
            style = match.group(1).strip()
            use_case = self.TERM_TO_STYLE.get(style, "hybrid_flex")
            actions.append({
                "type": "apply_use_case",
                "use_case": use_case,
            })

            style_desc = {
                "collaborative_hub": "open collaborative workspace with shared tables and lounge areas",
                "hot_desking": "efficient individual workstations with maximized desk space",
                "hybrid_flex": "balanced mix of work, meeting, and collaboration zones",
                "team_pods": "team-oriented clusters with shared workspaces",
            }

            return {
                "response": f"🎨 Switching to **{style}** layout style — {style_desc.get(use_case, '')}. "
                           f"Use **Smart Suggest** to regenerate furniture quantities, then **Generate Layouts**!",
                "actions": actions,
                "suggestions": ["Apply Smart Suggest", "Generate layouts"],
            }

        # Check daylight preference
        match = self._find_match(message_lower, "daylight_preference")
        if match:
            actions.append({
                "type": "set_preference",
                "key": "daylight_priority",
                "value": "high",
            })

            return {
                "response": "☀️ Setting **high daylight priority** — work desks and collaborative areas "
                           "will be placed near windows for maximum natural light.",
                "actions": actions,
                "suggestions": ["Generate layouts", "Set sun orientation"],
            }

        # Check room size
        match = self._find_match(message_lower, "room_size")
        if match:
            width = float(match.group(1))
            height = float(match.group(2))
            actions.append({
                "type": "set_room_size",
                "width_m": width,
                "height_m": height,
            })

            area = width * height
            capacity = int(area / 5.5)

            return {
                "response": f"📐 Room set to **{width}m × {height}m** ({area:.0f} sqm). "
                           f"Estimated capacity: **{capacity} people**.\n\n"
                           f"Draw the room on the canvas or use a preset template!",
                "actions": actions,
                "suggestions": [f"I need seating for {capacity} people", "Use preset template", "Add windows"],
            }

        # Check remove furniture
        match = self._find_match(message_lower, "remove_furniture")
        if match:
            term = match.group(2).strip() if match.group(2) else "all"
            category = self.TERM_TO_CATEGORY.get(term, term)
            actions.append({
                "type": "remove_furniture",
                "category": category,
            })

            return {
                "response": f"🗑️ Removing **{term}(s)** from the layout.",
                "actions": actions,
                "suggestions": ["Generate layouts", "Add furniture"],
            }

        # Apply configuration request
        if any(kw in message_lower for kw in ["apply", "confirm", "yes", "go ahead", "do it"]):
            actions.append({"type": "confirm_last_action"})
            return {
                "response": "✅ Configuration applied! Click **Generate Layouts** to create optimized plans.",
                "actions": actions,
                "suggestions": ["Generate layouts"],
            }

        # Fallback
        return {
            "response": "🤔 I'm not sure what you mean. Try something like:\n\n"
                       "• \"I need seating for 15 people\"\n"
                       "• \"Add 4 work desks\"\n"
                       "• \"Make it more collaborative\"\n"
                       "• \"2 meeting areas\"\n\n"
                       "Type **help** for all available commands.",
            "actions": [],
            "suggestions": ["Help", "I need seating for 12 people", "Add 6 desks"],
        }

    def _matches(self, text, pattern_key):
        """Check if text matches any pattern in pattern_key."""
        for pattern in self.PATTERNS.get(pattern_key, []):
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _find_match(self, text, pattern_key):
        """Find first match from patterns."""
        for pattern in self.PATTERNS.get(pattern_key, []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match
        return None
