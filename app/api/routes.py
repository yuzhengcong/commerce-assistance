from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import List, Dict
from sqlalchemy.orm import Session
from app.database.database import get_db, reseed_products
from app.models.chat import ChatMessage, ChatRequest, ChatResponse
from app.models.product import Product, ProductResponse
from app.services.agent import AgentService
import uuid
from datetime import datetime
import json
import logging
import base64

router = APIRouter()
agent_service = AgentService()
logger = logging.getLogger("api")

# ===== Chat endpoints =====
conversation_memory: Dict[str, List[ChatMessage]] = {}

@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest):
    """
    Handle user chat requests; supports AI tool calls.
    """
    try:
        conversation_id = request.conversation_id or str(uuid.uuid4())
        if conversation_id not in conversation_memory:
            conversation_memory[conversation_id] = []

        user_message = ChatMessage(
            role="user",
            content=request.message,
            timestamp=datetime.now()
        )
        conversation_memory[conversation_id].append(user_message)

        agent_result = await agent_service.generate_response(
            user_message=request.message,
            conversation_history=conversation_memory[conversation_id],
            context=request.context
        )

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


@router.post("/products/image-search", tags=["products"])
async def image_search(file: UploadFile = File(...)):
    """
    Image-based product search: accept image upload, use a vision model to generate a query and retrieve in the product index.
    Returns: matching product list (with similarity scores).
    """
    try:
        content = await file.read()
        content_type = file.content_type or "image/jpeg"
        data_url = f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"
        try:
            logger.info("/products/image-search upload: filename=%s, type=%s, size=%d", file.filename, content_type, len(content))
        except Exception:
            logger.warning("/products/image-search: failed to log upload metadata")

        results = await agent_service.tools_executor.search_by_image(data_url)
        if not results:
            message = "No matching products found. Try a clearer image or different angle."
        else:
            top = results[:3]
            def fmt(r: dict) -> str:
                name = r.get("name") or "Unknown"
                brand = r.get("brand")
                price = r.get("price")
                parts = [name]
                if brand:
                    parts.append(f"by {brand}")
                if isinstance(price, (int, float)):
                    parts.append(f"¥{price}")
                return " ".join(parts)
            message = "Found matching products: " + "; ".join(fmt(r) for r in top) + "."
        try:
            logger.info("/products/image-search returned %d results: %s", len(results), json.dumps(results, ensure_ascii=False))
            logger.info("/products/image-search message: %s", message)
        except Exception:
            logger.warning("/products/image-search: failed to log results JSON dump")
        return {"message": message, "results": results}
    except Exception as e:
        print(f"Image Search Error: {e}")
        raise HTTPException(status_code=500, detail="Error occurred during image-based product search")


# ===== Admin endpoints =====
@router.post("/admin/reseed-and-reindex", tags=["admin"])
async def reseed_and_reindex(db: Session = Depends(get_db)):
    """
    Admin endpoint: re-import products from seed file and rebuild the Faiss vector index.
    Returns: number of products re-imported and index entry count.
    """
    try:
        inserted = reseed_products()
        # rebuild_index is implemented in services/vector.py
        from app.services.vector import rebuild_index
        indexed = rebuild_index(db)
        return {"reseeded": inserted, "indexed": indexed}
    except Exception as e:
        print(f"Reseed & Reindex Error: {e}")
        raise HTTPException(status_code=500, detail="Error occurred during reseed and reindexing")