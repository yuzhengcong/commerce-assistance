from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from app.models.product import Product, ProductResponse, ProductCreate
from typing import List
from sqlalchemy.orm import Session
from app.database.database import get_db
import json
import logging
import base64
from app.services.agent_service import AgentService

router = APIRouter()
agent_service = AgentService()
logger = logging.getLogger("api.products")

@router.get("/products", response_model=List[ProductResponse])
async def get_products(db: Session = Depends(get_db)):
    """
    获取商品列表
    """
    try:
        products = db.query(Product).all()
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
                created_at=p.created_at
            ) for p in products
        ]
    except Exception as e:
        print(f"Get Products Error: {e}")
        raise HTTPException(status_code=500, detail="获取商品列表时发生错误")

@router.post("/products", response_model=ProductResponse)
async def create_product(request: ProductCreate, db: Session = Depends(get_db)):
    """
    创建单个商品并插入数据库
    """
    try:
        product = Product(
            name=request.name,
            description=request.description,
            price=request.price,
            category=request.category,
            brand=request.brand,
            image_url=request.image_url,
            tags=json.dumps(request.tags or [], ensure_ascii=False),
            stock=request.stock,
            rating=request.rating,
        )
        db.add(product)
        db.commit()
        db.refresh(product)

        return ProductResponse(
            id=product.id,
            name=product.name,
            description=product.description,
            price=product.price,
            category=product.category,
            brand=product.brand,
            image_url=product.image_url,
            tags=json.loads(product.tags) if product.tags else [],
            stock=product.stock,
            rating=product.rating,
            created_at=product.created_at,
        )
    except Exception as e:
        print(f"Create Product Error: {e}")
        raise HTTPException(status_code=500, detail="创建商品时发生错误")

@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """
    获取单个商品详情
    """
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="商品未找到")
        return ProductResponse(
            id=product.id,
            name=product.name,
            description=product.description,
            price=product.price,
            category=product.category,
            brand=product.brand,
            image_url=product.image_url,
            tags=json.loads(product.tags) if product.tags else [],
            stock=product.stock,
            rating=product.rating,
            created_at=product.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get Product Error: {e}")
        raise HTTPException(status_code=500, detail="获取商品详情时发生错误")

@router.post("/products/image-search")
async def image_search(file: UploadFile = File(...)):
    """
    以图搜商品：接收图片上传，使用视觉模型生成查询并在商品索引中检索。
    返回：匹配商品列表（含相似度）。
    """
    try:
        content = await file.read()
        content_type = file.content_type or "image/jpeg"
        data_url = f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"
        try:
            logger.info("/products/image-search upload: filename=%s, type=%s, size=%d", file.filename, content_type, len(content))
        except Exception:
            logger.warning("/products/image-search: failed to log upload metadata")

        results = await agent_service._search_by_image(data_url)
        # Compose a short natural-language message summarizing matches
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
        raise HTTPException(status_code=500, detail="以图搜商品时发生错误")