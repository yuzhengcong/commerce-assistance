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
                seed_products = [
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

                for p in seed_products:
                    db.add(
                        Product(
                            id=p["id"],
                            name=p["name"],
                            description=p["description"],
                            price=p["price"],
                            category=p["category"],
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