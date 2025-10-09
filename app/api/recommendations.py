from fastapi import APIRouter, HTTPException, Depends
from app.models.product import ProductSearchRequest, ImageSearchRequest, ProductResponse
from typing import List
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.services.recommendation_service import recommend_by_text, rebuild_index

router = APIRouter()

@router.post("/recommend", response_model=List[ProductResponse])
async def recommend_products(request: ProductSearchRequest, db: Session = Depends(get_db)):
    """
    基于文本相似度的商品推荐
    """
    try:
        results = recommend_by_text(db, request.query, top_k=5)
        return results
    except Exception as e:
        print(f"Recommend Products Error: {e}")
        raise HTTPException(status_code=500, detail="商品推荐时发生错误")

@router.post("/search-image", response_model=List[ProductResponse])
async def search_by_image(request: ImageSearchRequest):
    """
    基于图像的商品搜索（暂时简单实现）
    """
    try:
        # 这里后续会实现图像搜索逻辑
        return []
    except Exception as e:
        print(f"Image Search Error: {e}")
        raise HTTPException(status_code=500, detail="图像搜索时发生错误")


@router.post("/rebuild-index")
async def rebuild_vector_index(db: Session = Depends(get_db)):
    """
    重建 Faiss 索引（从数据库商品描述重新生成向量并写入索引文件）
    """
    try:
        count = rebuild_index(db)
        return {"indexed": count}
    except Exception as e:
        print(f"Rebuild Index Error: {e}")
        raise HTTPException(status_code=500, detail="重建索引时发生错误")