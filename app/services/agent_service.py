import openai
import os
import json
from typing import List, Dict, Optional, Any
from app.models.chat import ChatMessage, ConversationContext
from app.models.product import ProductResponse

class AgentService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = openai.OpenAI(api_key=api_key)
        self.mock_mode = False
        self.system_prompt = """你是一个专业的电商购物助手，类似于Amazon的Rufus。你有以下工具可以使用：

1. search_products: 搜索商品
2. get_product_details: 获取商品详情
3. recommend_products: 推荐商品
4. search_by_image: 通过图片搜索商品

当用户询问商品相关问题时，你应该主动使用这些工具来帮助用户。
请用中文回复用户，保持简洁明了的回答风格。"""

        # 定义可用的工具
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_products",
                    "description": "搜索商品",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索关键词"
                            },
                            "category": {
                                "type": "string",
                                "description": "商品分类（可选）"
                            },
                            "max_price": {
                                "type": "number",
                                "description": "最高价格（可选）"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_product_details",
                    "description": "获取商品详细信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "integer",
                                "description": "商品ID"
                            }
                        },
                        "required": ["product_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "recommend_products",
                    "description": "根据用户需求推荐商品",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_preferences": {
                                "type": "string",
                                "description": "用户偏好描述"
                            },
                            "budget": {
                                "type": "number",
                                "description": "预算范围（可选）"
                            }
                        },
                        "required": ["user_preferences"]
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
        生成AI回复，支持工具调用
        """
        try:
            # 如果是模拟模式，返回模拟响应
            if self.mock_mode:
                return await self._generate_mock_response(user_message)
            
            # 构建消息历史
            messages = [{"role": "system", "content": self.system_prompt}]
            
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
                model="gpt-3.5-turbo",
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
                
                # 执行工具调用
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
                
                # 第二次调用：基于工具结果生成最终回复
                final_response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    max_tokens=500,
                    temperature=0.7
                )
                
                return {
                    "response": final_response.choices[0].message.content,
                    "tool_calls": [
                        {
                            "function": tool_call.function.name,
                            "arguments": json.loads(tool_call.function.arguments),
                            "result": await self._execute_tool(
                                tool_call.function.name, 
                                json.loads(tool_call.function.arguments)
                            )
                        }
                        for tool_call in response_message.tool_calls
                    ]
                }
            else:
                # AI决定不使用工具，直接回复
                return {
                    "response": response_message.content,
                    "tool_calls": []
                }
                
        except Exception as e:
            print(f"Agent Service Error: {e}")
            return {
                "response": "抱歉，我现在无法处理您的请求。请稍后再试。",
                "tool_calls": []
            }

    async def _generate_mock_response(self, user_message: str) -> Dict[str, Any]:
        """
        生成模拟响应，用于演示工具调用
        """
        user_message_lower = user_message.lower()
        
        # 根据用户消息内容决定是否模拟工具调用
        if any(keyword in user_message_lower for keyword in ["搜索", "找", "买", "购买", "商品"]):
            # 模拟搜索商品工具调用
            mock_tool_call = {
                "function": "search_products",
                "arguments": {"query": "运动T恤" if "t恤" in user_message_lower else "商品"},
                "result": await self._search_products("运动T恤" if "t恤" in user_message_lower else "商品")
            }
            
            return {
                "response": f"我为您搜索了相关商品，找到了一些不错的选择。根据搜索结果，我推荐您看看这些商品。",
                "tool_calls": [mock_tool_call]
            }
        
        elif any(keyword in user_message_lower for keyword in ["详情", "详细", "信息", "id"]):
            # 模拟获取商品详情工具调用
            mock_tool_call = {
                "function": "get_product_details",
                "arguments": {"product_id": 1},
                "result": await self._get_product_details(1)
            }
            
            return {
                "response": f"我为您查询了商品的详细信息，这是一款很不错的商品。",
                "tool_calls": [mock_tool_call]
            }
        
        elif any(keyword in user_message_lower for keyword in ["推荐", "建议"]):
            # 模拟推荐商品工具调用
            mock_tool_call = {
                "function": "recommend_products",
                "arguments": {"user_preferences": user_message},
                "result": await self._recommend_products(user_message)
            }
            
            return {
                "response": f"根据您的需求，我为您推荐了一些商品，希望您会喜欢。",
                "tool_calls": [mock_tool_call]
            }
        
        else:
            # 普通对话，不使用工具
            return {
                "response": f"您好！我是AI电商助手。您可以问我关于商品搜索、商品详情或商品推荐的问题。比如：'我想买一件运动T恤'、'推荐一些300元以下的耳机'等。",
                "tool_calls": []
            }

    async def _execute_tool(self, function_name: str, arguments: Dict) -> Any:
        """
        执行具体的工具函数
        """
        if function_name == "search_products":
            return await self._search_products(**arguments)
        elif function_name == "get_product_details":
            return await self._get_product_details(**arguments)
        elif function_name == "recommend_products":
            return await self._recommend_products(**arguments)
        else:
            return {"error": f"Unknown function: {function_name}"}

    async def _search_products(self, query: str, category: str = None, max_price: float = None) -> List[Dict]:
        """
        搜索商品的具体实现
        """
        # 这里是示例数据，实际应该查询数据库
        sample_products = [
            {
                "id": 1,
                "name": "运动T恤",
                "description": "透气舒适的运动T恤",
                "price": 89.0,
                "category": "服装",
                "brand": "Nike"
            },
            {
                "id": 2,
                "name": "无线蓝牙耳机",
                "description": "高音质无线蓝牙耳机",
                "price": 299.0,
                "category": "电子产品",
                "brand": "Sony"
            }
        ]
        
        # 简单的搜索逻辑
        results = []
        for product in sample_products:
            if query.lower() in product["name"].lower() or query.lower() in product["description"].lower():
                if category is None or product["category"] == category:
                    if max_price is None or product["price"] <= max_price:
                        results.append(product)
        
        return results

    async def _get_product_details(self, product_id: int) -> Dict:
        """
        获取商品详情的具体实现
        """
        # 示例实现
        sample_products = {
            1: {
                "id": 1,
                "name": "运动T恤",
                "description": "透气舒适的运动T恤，适合健身和日常穿着",
                "price": 89.0,
                "category": "服装",
                "brand": "Nike",
                "stock": 50,
                "rating": 4.5
            },
            2: {
                "id": 2,
                "name": "无线蓝牙耳机",
                "description": "高音质无线蓝牙耳机，降噪功能强大",
                "price": 299.0,
                "category": "电子产品",
                "brand": "Sony",
                "stock": 30,
                "rating": 4.8
            }
        }
        
        return sample_products.get(product_id, {"error": "Product not found"})

    async def _recommend_products(self, user_preferences: str, budget: float = None) -> List[Dict]:
        """
        推荐商品的具体实现
        """
        # 这里应该有更复杂的推荐算法
        # 目前返回示例数据
        recommendations = [
            {
                "id": 1,
                "name": "运动T恤",
                "price": 89.0,
                "reason": "根据您的需求，这款运动T恤透气舒适，适合运动"
            }
        ]
        
        if budget:
            recommendations = [p for p in recommendations if p["price"] <= budget]
            
        return recommendations