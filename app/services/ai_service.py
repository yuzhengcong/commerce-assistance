import openai
import os
from typing import List, Dict, Optional
from app.models.chat import ChatMessage, ConversationContext

class AIService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.system_prompt = """你是一个专业的电商购物助手，类似于Amazon的Rufus。你的主要职责是：

1. 回答用户的一般问题，保持友好和专业的态度
2. 根据用户的需求推荐合适的商品
3. 帮助用户找到他们想要的产品
4. 提供购物建议和产品比较

请用中文回复用户，保持简洁明了的回答风格。如果用户询问你的身份，告诉他们你是AI购物助手。"""

    async def generate_response(
        self, 
        user_message: str, 
        conversation_history: List[ChatMessage] = None,
        context: ConversationContext = None
    ) -> str:
        """
        生成AI回复
        """
        try:
            # 构建消息历史
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # 添加对话历史
            if conversation_history:
                for msg in conversation_history[-10:]:  # 只保留最近10条消息
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # 添加当前用户消息
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # 调用OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"AI Service Error: {e}")
            return "抱歉，我现在无法处理您的请求。请稍后再试。"
    
    def is_product_related_query(self, message: str) -> bool:
        """
        判断用户消息是否与商品相关
        """
        product_keywords = [
            "推荐", "买", "购买", "商品", "产品", "价格", "便宜", "质量",
            "品牌", "评价", "reviews", "recommend", "buy", "product", "price"
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in product_keywords)
    
    def extract_product_preferences(self, message: str) -> Dict:
        """
        从用户消息中提取商品偏好
        """
        preferences = {}
        
        # 这里可以添加更复杂的NLP逻辑来提取用户偏好
        # 目前简单实现
        if "便宜" in message or "cheap" in message.lower():
            preferences["price_preference"] = "low"
        elif "高端" in message or "premium" in message.lower():
            preferences["price_preference"] = "high"
            
        return preferences