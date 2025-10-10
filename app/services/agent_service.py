import openai
import os
import json
from typing import List, Dict, Optional, Any
from app.models.chat import ChatMessage, ConversationContext
from app.models.product import ProductResponse
import logging; 
log = logging.getLogger("agent_service")
from app.database.database import SessionLocal
from app.services.recommendation_service import recommend_by_text
from app.services.vector_store import query_with_scores as vs_query_with_scores

class AgentService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = openai.OpenAI(api_key=api_key)
        self.mock_mode = False
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

        # Define available tools (English, limited to catalog)
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
            
            # 构建消息历史
            messages = [{"role": "system", "content": self.system_prompt}]
            log.debug("System prompt prepared for chat completion")
            
            
            # 添加对话历史
            if conversation_history:
                for msg in conversation_history[-10:]:
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # 添加当前用户消息
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # 第一次调用：让AI决定是否需要使用工具
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=self.tools,
                tool_choice="auto",  # 让AI自动决定是否使用工具
                max_tokens=500,
                temperature=0.7
            )
            
            response_message = response.choices[0].message
            
            # 检查AI是否想要调用工具
            if response_message.tool_calls:
                # AI决定使用工具
                messages.append(response_message)
                log.info(f"AI decided to use tools: {response_message.tool_calls}")
                
                # 执行工具调用
                tool_results = []
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # 调用相应的工具函数
                    tool_result = await self._execute_tool(function_name, function_args)
                    
                    # 将工具结果添加到消息历史
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
                    tool_results.append({
                        "function": function_name,
                        "arguments": function_args,
                        "result": tool_result
                    })
                
                # 在第二次调用前追加简短指令：使用工具结果生成自然语言推荐
                messages.append({
                    "role": "system",
                    "content": (
                        "Use the tool results above to craft a concise, natural recommendation. "
                        "Do not mention tools or internal IDs. Refer to product names (and price if helpful). "
                        "Reply in English and keep it to 1–2 sentences."
                    )
                })

                # 第二次调用：基于工具结果生成最终回复
                final_response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=500,
                    temperature=0.7
                )
                
                return {
                    "response": final_response.choices[0].message.content,
                    "tool_calls": tool_results
                }
            else:
                # AI决定不使用工具，直接回复
                log.info(f"AI decided not to use tools: {response_message.content}")
                return {
                    "response": response_message.content,
                    "tool_calls": []
                }
                
        except Exception as e:
            log.exception("Agent Service encountered an error")
            return {
                "response": "Sorry, I cannot process your request right now. Please try again later.",
                "tool_calls": []
            }

    
    async def _execute_tool(self, function_name: str, arguments: Dict) -> Any:
        """
        Execute specific tool function.
        """
        if function_name == "recommend_products":
            return await self._recommend_products(**arguments)
        elif function_name == "search_by_image":
            return await self._search_by_image(**arguments)
        else:
            return {"error": f"Unknown function: {function_name}"}


    async def _recommend_products(self, user_preferences: str, budget: float = None, min_similarity: float = 0.5) -> List[Dict]:
        """
        Recommend products via text similarity (FAISS) from predefined catalog.
        Unified to use recommendation_service.recommend_by_text for single source of truth.
        """
        db = SessionLocal()
        try:
            # Query with similarity scores, then apply threshold filtering
            hits = vs_query_with_scores(db, query_text=user_preferences, top_k=2)
            recs = []
            for p, score in hits:
                if score < min_similarity:
                    continue
                recs.append({
                    "id": p.id,
                    "name": p.name,
                    "price": p.price,
                    "category": p.category,
                    "brand": p.brand,
                    "similarity": score,
                    "reason": f"Recommended based on your preferences: '{user_preferences}'"
                })
            if budget is not None:
                recs = [r for r in recs if r["price"] is not None and r["price"] <= budget]
            return recs
        finally:
            db.close()

    async def _search_by_image(self, image_url: str) -> List[Dict]:
        """
        Image-based product search within predefined catalog (placeholder).
        """
        # TODO: integrate real image search. For now, return empty list.
        return []