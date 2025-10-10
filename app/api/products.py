from fastapi import APIRouter, HTTPException, Depends
from app.models.product import Product, ProductResponse, ProductCreate
from typing import List
from sqlalchemy.orm import Session
from app.database.database import get_db
import json

router = APIRouter()

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