import json
from typing import List
import logging
from sqlalchemy.orm import Session
from app.models.product import ProductResponse
from app.services.vector_store import query as vs_query, build_index

log = logging.getLogger("recommendation_service")

def recommend_by_text(db: Session, query: str, top_k: int = 1) -> List[ProductResponse]:
    products = vs_query(db, query_text=query, top_k=top_k)
    return [
        ProductResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            price=p.price,
            category=p.category,
            brand=p.brand,
            image_url=p.image_url,
            tags=json.loads(p.tags) if p.tags else [],
            stock=p.stock,
            rating=p.rating,
            created_at=p.created_at,
        )
        for p in products
    ]

def rebuild_index(db: Session) -> int:
    index, ids = build_index(db)
    return len(ids)