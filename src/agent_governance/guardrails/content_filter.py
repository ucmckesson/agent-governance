from __future__ import annotations

from typing import Dict, Iterable

from ..models import GuardrailAction, GuardrailResult


CATEGORY_KEYWORDS = {
    "harassment": ["idiot", "stupid", "moron"],
    "hate_speech": ["racial slur"],
    "violence": ["kill", "shoot", "bomb"],
    "self_harm": ["suicide", "self harm"],
    "sexual_content": ["explicit sex"],
}


class ContentFilter:
    def __init__(self, config: Dict[str, object]) -> None:
        cfg = config.get("content_safety", {})
        self.enabled = bool(cfg.get("enabled", True))
        self.block_categories = [c.lower() for c in (cfg.get("block_categories") or [])]
        self.topic_blocklist = [t.lower() for t in (cfg.get("topic_blocklist") or [])]
        self.blocklist_keywords = [k.lower() for k in (cfg.get("blocklist_keywords") or [])]

    def check(self, text: str) -> GuardrailResult:
        if not self.enabled or not self.block_categories:
            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="content_safety_disabled", reason="OK")
        lower = text.lower()
        for category in self.block_categories:
            for keyword in CATEGORY_KEYWORDS.get(category, []):
                if keyword in lower:
                    return GuardrailResult(
                        action=GuardrailAction.BLOCK,
                        rule_name=f"content_{category}",
                        reason=f"Content blocked for category: {category}",
                    )
        for topic in self.topic_blocklist:
            if topic in lower:
                return GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    rule_name="content_topic",
                    reason=f"Content blocked for topic: {topic}",
                )
        for keyword in self.blocklist_keywords:
            if keyword in lower:
                return GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    rule_name="content_keyword",
                    reason="Content blocked by keyword",
                )
        return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="content_safe", reason="OK")
