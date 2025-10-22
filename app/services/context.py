import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from app.models.chat import ChatMessage, ConversationContext

log = logging.getLogger("context_manager")


class ContextManager:
    def __init__(
        self,
        client: Any,
        system_prompt: str,
        max_history_turns: int = 4,
        keep_recent_turns: int = 2,
    ) -> None:
        self.client = client
        self.system_prompt = system_prompt
        self.max_history_turns = max_history_turns
        self.keep_recent_turns = keep_recent_turns

    def summarize_history(self, conversation_history: List[ChatMessage]) -> Optional[str]:
        """
            Summarize earlier conversation turns to reduce context length.
        """
       
        try:
            if not conversation_history or len(conversation_history) <= self.keep_recent_turns:
                return None
            older = conversation_history[:-self.keep_recent_turns]
            if not older:
                return None

            messages: List[Dict[str, Any]] = [
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that produces a brief, neutral conversation summary. "
                        "Capture the user's preferences, constraints (e.g., budget), decisions taken, and any pending questions. "
                        "Keep it under 120 words, in English."
                    ),
                }
            ]
            for msg in older[-20:]:
                messages.append({"role": msg.role, "content": msg.content})

            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=200,
                temperature=0.2,
            )
            return resp.choices[0].message.content
        except Exception:
            log.exception("History summarization failed in ContextManager")
            return None

    
    def summarize_for_memory(self, conversation_history: List[ChatMessage]) -> Optional[ChatMessage]:
        """
            Summarize earlier conversation turns to reduce context length.
        """

        summary = self.summarize_history(conversation_history)
        if summary:
            return ChatMessage(role="system", content=f"Conversation summary: {summary}", timestamp=datetime.now())
        return None

    def build_messages(self, conversation_history: List[ChatMessage], user_message: str) -> List[Dict[str, Any]]:
        """
            Build base messages with optional compression and user message.
        """
        
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        # Include any persisted summary message already in the history
        if conversation_history:
            for msg in reversed(conversation_history):
                if msg.role == "system" and isinstance(msg.content, str) and msg.content.startswith("Conversation summary:"):
                    messages.append({"role": "system", "content": msg.content})
                    break

        # Add dynamic summary when history is long
        if conversation_history and len(conversation_history) > self.max_history_turns:
            summary = self.summarize_history(conversation_history)
            if summary:
                messages.append({"role": "system", "content": f"Conversation summary: {summary}"})

        # Add recent turns
        if conversation_history:
            recent = conversation_history[-self.keep_recent_turns:]
            for msg in recent:
                messages.append({"role": msg.role, "content": msg.content})

        # Current user message
        messages.append({"role": "user", "content": user_message})
        return messages

    def add_tool_synthesis_instruction(self, messages: List[Dict[str, Any]]) -> None:
        """
            Append instruction to synthesize tool results into concise natural recommendation.
        """
        
        messages.append(
            {
                "role": "system",
                "content": (
                    "Use the tool results above to craft a concise, natural recommendation. "
                    "Do not mention tools or internal IDs. Refer to product names (and price if helpful). "
                    "Reply in English and keep it to 1–2 sentences."
                ),
            }
        )