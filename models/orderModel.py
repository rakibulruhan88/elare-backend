from pydantic import BaseModel
from typing import List, Optional

class OrderItem(BaseModel):
    name: str
    qty: int
    image: str
    price: float
    product: str
    size: Optional[str] = None

class ShippingAddress(BaseModel):
    fullName: str
    mobileNumber: str
    email: str
    address: str
    comment: Optional[str] = ""

class OrderCreate(BaseModel):
    orderItems: List[OrderItem]
    shippingAddress: ShippingAddress
    paymentMethod: str
    itemsPrice: float
    shippingPrice: float
    totalPrice: float