from pydantic import BaseModel
from typing import List, Optional

class ReviewCreate(BaseModel):
    rating: float
    comment: str

class ProductCreate(BaseModel):
    name: str
    price: Optional[float] = 0.0
    compareAtPrice: Optional[float] = 0.0
    description: Optional[str] = ""
    image: Optional[str] = "/images/sample.jpg"
    collections: List[str] = []
    images: Optional[List[str]] = []
    brand: Optional[str] = ""
    category: Optional[str] = ""
    countInStock: Optional[int] = 0
    status: Optional[str] = "Active"
    collection_name: str | None = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    compareAtPrice: Optional[float] = None
    description: Optional[str] = None
    image: Optional[str] = None
    images: Optional[List[str]] = None
    collections: Optional[List[str]] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    countInStock: Optional[int] = None
    status: Optional[str] = None
    collection_name: str | None = None