from fastapi import APIRouter, HTTPException
from app.models.product import ProductResponse
from typing import List

router = APIRouter()

# 临时的商品数据（后续会连接数据库）
SAMPLE_PRODUCTS = [
    {
        "id": 1,
        "name": "运动T恤",
        "description": "透气舒适的运动T恤，适合健身和日常穿着",
        "price": 89.0,
        "category": "服装",
        "brand": "Nike",
        "image_url": "https://example.com/tshirt.jpg",
        "tags": ["运动", "T恤", "透气"],
        "stock": 50,
        "rating": 4.5,
        "created_at": "2024-01-01T00:00:00"
    },
    {
        "id": 2,
        "name": "无线蓝牙耳机",
        "description": "高音质无线蓝牙耳机，降噪功能强大",
        "price": 299.0,
        "category": "电子产品",
        "brand": "Sony",
        "image_url": "https://example.com/headphones.jpg",
        "tags": ["耳机", "蓝牙", "降噪"],
        "stock": 30,
        "rating": 4.8,
        "created_at": "2024-01-01T00:00:00"
    }
]

@router.get("/products", response_model=List[ProductResponse])
async def get_products():
    """
    获取商品列表
    """
    try:
        return SAMPLE_PRODUCTS
    except Exception as e:
        print(f"Get Products Error: {e}")
        raise HTTPException(status_code=500, detail="获取商品列表时发生错误")

@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int):
    """
    获取单个商品详情
    """
    try:
        product = next((p for p in SAMPLE_PRODUCTS if p["id"] == product_id), None)
        if not product:
            raise HTTPException(status_code=404, detail="商品未找到")
        return product
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get Product Error: {e}")
        raise HTTPException(status_code=500, detail="获取商品详情时发生错误")