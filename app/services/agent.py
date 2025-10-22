import openai
import os
import json
from typing import List, Dict, Optional, Any
from app.models.chat import ChatMessage, ConversationContext
from app.services.context import ContextManager
from app.services.tool import ToolExecutor


import logging; 
log = logging.getLogger("agent_service")

class AgentService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = openai.OpenAI(api_key=api_key)
        self.mock_mode = False
        # Context compression configuration
        self.max_history_turns = 4
        self.keep_recent_turns = 2
        self.system_prompt = """You are a helpful shopping assistant for an e-commerce site.

        Capabilities:
        1) General conversation with the agent (e.g., 'What's your name?', 'What can you do?')
        2) Text-Based Product Recommendation (e.g., 'Recommend me a t-shirt for sports.')
        3) Image-Based Product Search.

        Important constraints:
        - Product recommendation and search are limited to items in a predefined catalog.
        - Keep responses concise and clear.
        - Reply in English.
        - When tool results are present, synthesize them into a natural sentence recommendation.
          For example: "I recommend the blue t-shirt for you." Do not mention tools or IDs.
          Prefer top relevant items; reference product names (and price if helpful)."""

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "recommend_products",
                    "description": "Recommend products from the predefined catalog based on user needs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_preferences": {
                                "type": "string",
                                "description": "User preference or query (e.g., 'sports t-shirt')."
                            },
                            "budget": {
                                "type": "number",
                                "description": "Optional budget limit."
                            }
                        },
                        "required": ["user_preferences"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_by_image",
                    "description": "Image-based product search within the predefined catalog.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_url": {
                                "type": "string",
                                "description": "URL of the image to search by."
                            }
                        },
                        "required": ["image_url"]
                    }
                }
            }
        ]

        # Initialize managers
        self.context_manager = ContextManager(
            self.client,
            system_prompt=self.system_prompt,
            max_history_turns=self.max_history_turns,
            keep_recent_turns=self.keep_recent_turns,
        )
        self.tools_executor = ToolExecutor(self.client)


    def summarize_for_memory(self, conversation_history: List[ChatMessage]) -> Optional[ChatMessage]:
        """Summarize earlier history (delegated) and return a system ChatMessage."""
        return self.context_manager.summarize_for_memory(conversation_history)
    
    async def _route_intent(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 500,
        tool_choice: str = "auto",
    ):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=self.tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message
    
    async def _finalize_with_tools(
        self,
        messages: List[Dict[str, Any]],
        response_message: Any,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> Dict[str, Any]:
        if not getattr(response_message, "tool_calls", None):
            log.info(f"AI decided not to use tools: {response_message.content}")
            return {"response": response_message.content, "tool_calls": []}

        messages.append(response_message)
        log.info(f"AI decided to use tools: {response_message.tool_calls}")

        tool_results: List[Dict[str, Any]] = []
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            tool_result = await self.tools_executor.execute(function_name, function_args)
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": json.dumps(tool_result, ensure_ascii=False),
            })
            tool_results.append({
                "function": function_name,
                "arguments": function_args,
                "result": tool_result,
            })

        self.context_manager.add_tool_synthesis_instruction(messages)

        final_response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return {"response": final_response.choices[0].message.content, "tool_calls": tool_results}
    
    async def generate_response(
        self, 
        user_message: str, 
        conversation_history: List[ChatMessage] = None,
        context: ConversationContext = None
    ) -> Dict[str, Any]:
        """
        Generate AI response with optional tool usage (English-only outputs).
        """
        try:
            log.info("conversation_history: %s", conversation_history)
            messages = self.context_manager.build_messages(conversation_history or [], user_message)
            response_message = await self._route_intent(messages)
            result = await self._finalize_with_tools(messages, response_message)
            return result
        except Exception as e:
            log.exception("Agent Service encountered an error")
            return {
                "response": "Sorry, I cannot process your request right now. Please try again later.",
                "tool_calls": []
            }

    


    