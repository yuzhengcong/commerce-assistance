from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    price = Column(Float)
    category = Column(String, index=True)
    brand = Column(String)
    image_url = Column(String)
    tags = Column(String)  # JSON string of tags
    stock = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

# Pydantic models for API
class ProductBase(BaseModel):
    name: str
    description: str
    price: float
    category: str
    brand: Optional[str] = None
    image_url: Optional[str] = None
    tags: Optional[List[str]] = []
    stock: int = 0
    rating: float = 0.0

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProductSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None

class ImageSearchRequest(BaseModel):
    image_data: str  # base64 encoded image
    max_results: int = 10