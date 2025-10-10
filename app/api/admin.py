from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database.database import get_db, reseed_products
from app.services.recommendation_service import rebuild_index

router = APIRouter()

@router.post("/admin/reseed-and-reindex")
async def reseed_and_reindex(db: Session = Depends(get_db)):
    """
    管理接口：从种子文件重导商品并重建 Faiss 向量索引。
    返回：重导的商品数和索引条目数。
    """
    try:
        inserted = reseed_products()
        indexed = rebuild_index(db)
        return {"reseeded": inserted, "indexed": indexed}
    except Exception as e:
        print(f"Reseed & Reindex Error: {e}")
        raise HTTPException(status_code=500, detail="重导并重建索引时发生错误")