from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import json
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./commerce.db")

# 为不同数据库类型配置引擎（SQLite 与 MySQL）
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # MySQL 等非 SQLite 数据库不需要 check_same_thread
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

async def init_db():
    """
    初始化数据库
    """
    try:
        # 延迟导入模型以避免循环依赖
        from app.models.product import Product

        # 创建所有表（确保模型已导入以注册到元数据）
        Base.metadata.create_all(bind=engine)

        # 迁移：若缺少 embedding 列则添加（兼容 SQLite/MySQL）
        insp = inspect(engine)
        if 'products' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('products')]
            if 'embedding' not in cols:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE products ADD COLUMN embedding TEXT"))

        # 连接并进行数据种入（仅当表为空时）
        db = SessionLocal()
        try:
            count = db.query(Product).count()
            if count == 0:
                # 优先从外部 JSON 文件加载种子数据
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
                seed_path = os.path.join(base_dir, "data", "products_seed.json")

                seed_products = []
                if os.path.exists(seed_path):
                    try:
                        with open(seed_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        # 支持两种格式：数组或 {"products": [...]} 包装
                        seed_products = data.get("products", data) if isinstance(data, dict) else data
                    except Exception:
                        seed_products = []

                # 如果外部文件不可用，回退到内置最小数据集，确保可启动
                if not isinstance(seed_products, list) or not seed_products:
                    seed_products = [
                        {
                            "id": 1,
                            "name": "Sports T-Shirt",
                            "description": "Breathable, lightweight sports t-shirt for workouts and daily wear.",
                            "price": 29.99,
                            "category": "Clothing",
                            "brand": "Nike",
                            "image_url": "https://example.com/sports-tshirt.jpg",
                            "tags": ["sports", "tshirt", "breathable"],
                            "stock": 50,
                            "rating": 4.5,
                            "created_at": "2024-01-01T00:00:00"
                        },
                        {
                            "id": 2,
                            "name": "Wireless Bluetooth Headphones",
                            "description": "High-quality wireless headphones with powerful noise cancellation.",
                            "price": 129.0,
                            "category": "Electronics",
                            "brand": "Sony",
                            "image_url": "https://example.com/headphones.jpg",
                            "tags": ["headphones", "bluetooth", "noise-cancelling"],
                            "stock": 30,
                            "rating": 4.8,
                            "created_at": "2024-01-01T00:00:00"
                        }
                    ]

                for p in seed_products:
                    db.add(
                        Product(
                            id=p.get("id"),
                            name=p.get("name"),
                            description=p.get("description"),
                            price=p.get("price", 0.0),
                            category=p.get("category"),
                            brand=p.get("brand"),
                            image_url=p.get("image_url"),
                            tags=json.dumps(p.get("tags", []), ensure_ascii=False),
                            stock=p.get("stock", 0),
                            rating=p.get("rating", 0.0),
                            created_at=datetime.fromisoformat(p["created_at"]) if p.get("created_at") else datetime.utcnow()
                        )
                    )
                db.commit()

        finally:
            db.close()

        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

def get_db():
    """
    获取数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def reseed_products():
    """
    从外部种子文件重新导入商品数据：
    - 清空现有 products 表
    - 从 backend/data/products_seed.json 加载并插入
    """
    from app.models.product import Product
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    seed_path = os.path.join(base_dir, "data", "products_seed.json")

    db = SessionLocal()
    try:
        # 清空表
        db.query(Product).delete()
        db.commit()

        # 加载种子
        seed_products = []
        if os.path.exists(seed_path):
            try:
                with open(seed_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                seed_products = data.get("products", data) if isinstance(data, dict) else data
            except Exception:
                seed_products = []

        if not isinstance(seed_products, list) or not seed_products:
            # 无数据则直接返回
            return 0

        from datetime import datetime
        for p in seed_products:
            db.add(
                Product(
                    id=p.get("id"),
                    name=p.get("name"),
                    description=p.get("description"),
                    price=p.get("price", 0.0),
                    category=p.get("category"),
                    brand=p.get("brand"),
                    image_url=p.get("image_url"),
                    tags=json.dumps(p.get("tags", []), ensure_ascii=False),
                    stock=p.get("stock", 0),
                    rating=p.get("rating", 0.0),
                    created_at=datetime.fromisoformat(p["created_at"]) if p.get("created_at") else datetime.utcnow()
                )
            )
        db.commit()
        return len(seed_products)
    finally:
        db.close()