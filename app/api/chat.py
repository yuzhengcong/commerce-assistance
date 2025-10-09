from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from app.models.chat import ChatMessage, ChatRequest, ChatResponse, ConversationContext
from app.services.agent_service import AgentService
import uuid
from datetime import datetime

router = APIRouter()
agent_service = AgentService()

# 简单的内存存储对话历史（生产环境应使用数据库）
conversation_memory: Dict[str, List[ChatMessage]] = {}

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    处理用户聊天请求，支持AI工具调用
    """
    try:
        # 获取或创建对话历史
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        if conversation_id not in conversation_memory:
            conversation_memory[conversation_id] = []
        
        # 添加用户消息到历史
        user_message = ChatMessage(
            role="user",
            content=request.message,
            timestamp=datetime.now()
        )
        conversation_memory[conversation_id].append(user_message)
        
        # 使用Agent服务生成回复
        agent_result = await agent_service.generate_response(
            user_message=request.message,
            conversation_history=conversation_memory[conversation_id],
            context=request.context
        )
        
        # 创建AI回复消息
        ai_message = ChatMessage(
            role="assistant",
            content=agent_result["response"],
            timestamp=datetime.now()
        )
        conversation_memory[conversation_id].append(ai_message)
        
        return ChatResponse(
            message=agent_result["response"],
            conversation_id=conversation_id,
            tool_calls=agent_result.get("tool_calls", []),
            timestamp=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """
    获取对话历史
    """
    if conversation_id not in conversation_memory:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        "conversation_id": conversation_id,
        "messages": conversation_memory[conversation_id]
    }

@router.delete("/chat/history/{conversation_id}")
async def clear_conversation_history(conversation_id: str):
    """
    清除对话历史
    """
    try:
        if conversation_id in conversation_storage:
            del conversation_storage[conversation_id]
        return {"message": "对话历史已清除", "conversation_id": conversation_id}
    except Exception as e:
        print(f"Clear History Error: {e}")
        raise HTTPException(status_code=500, detail="清除对话历史时发生错误")