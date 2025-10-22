import json
import logging
from typing import List, Dict, Any

from app.database.database import SessionLocal
from app.services.vector import query_with_scores as vs_query_with_scores

log = logging.getLogger("tool_executor")


class ToolExecutor:
    def __init__(self, client: Any, session_factory=SessionLocal) -> None:
        self.client = client
        self.SessionFactory = session_factory

    async def execute(self, function_name: str, arguments: Dict) -> Any:
        """Dispatch tool execution by name."""
        
        if function_name == "recommend_products":
            return await self.recommend_products(**arguments)
        elif function_name == "search_by_image":
            return await self.search_by_image(**arguments)
        else:
            return {"error": f"Unknown function: {function_name}"}

    async def recommend_products(
        self,
        user_preferences: str,
        budget: float = None,
        min_similarity: float = 0.5,
    ) -> List[Dict]:
        
        """Recommend products via text similarity (FAISS)."""
        db = self.SessionFactory()
        try:
            hits = vs_query_with_scores(db, query_text=user_preferences, top_k=2)
            recs: List[Dict[str, Any]] = []
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
                    "reason": f"Recommended based on your preferences: '{user_preferences}'",
                })
            if budget is not None:
                recs = [r for r in recs if r.get("price") is not None and r["price"] <= budget]
            return recs
        finally:
            db.close()

    async def search_by_image(self, image_url: str) -> List[Dict]:
        """Image-based product search within predefined catalog."""
        db = self.SessionFactory()
        try:
            vision_messages = [
                {
                    "role": "system",
                    "content": (
                        "You analyze a shopping product photo and produce a concise English query "
                        "that captures product type, visible brand if any, and key attributes like color/material. "
                        "Return a short phrase (<=12 words), no full sentences."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe the product for catalog search."},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ]

            vision_resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=vision_messages,
                max_tokens=60,
                temperature=0.2,
            )
            query_text = (vision_resp.choices[0].message.content or "").strip()
            log.info("Image vision query_text: %s", query_text)
            if not query_text:
                return []

            top_k = 5
            min_similarity = 0.4
            hits = vs_query_with_scores(db, query_text=query_text, top_k=top_k)
            log.debug("FAISS hits: %s", [(getattr(p, "name", None), s) for p, s in hits])
            results: List[Dict] = []
            for p, score in hits:
                if score < min_similarity:
                    continue
                results.append({
                    "id": p.id,
                    "name": p.name,
                    "price": p.price,
                    "category": p.category,
                    "brand": p.brand,
                    "similarity": score,
                    "reason": f"Matched image query: '{query_text}'",
                })
            try:
                log.info("Image search results (%d): %s", len(results), json.dumps(results, ensure_ascii=False))
            except Exception:
                log.warning("Failed to dump image search results for logging")
            return results
        except Exception:
            log.exception("Image-based search failed in ToolExecutor")
            return []
        finally:
            db.close()