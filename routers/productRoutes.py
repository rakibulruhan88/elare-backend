from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from database import get_db
from utils.auth import get_current_user, get_admin_user
from models.productModel import ProductCreate, ProductUpdate, ReviewCreate
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/api/products", tags=["Products"])

@router.get("")
async def get_products(collection_name: Optional[str] = None):
    db = get_db()
    query = {}
    
    if collection_name:
        query["collections"] = collection_name 
        
    products_cursor = db.products.find(query)
    products = await products_cursor.to_list(length=100)
    for p in products:
        p["_id"] = str(p["_id"])
        p["user"] = str(p.get("user", ""))
        for r in p.get("reviews", []):
            r["user"] = str(r["user"])
    return products

@router.post("")
async def create_product(product: ProductCreate, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    new_product = product.dict()
    new_product["user"] = ObjectId(admin_user["_id"])
    
    if "collections" not in new_product or not new_product["collections"]:
        new_product["collections"] = []
        
    new_product["reviews"] = []
    new_product["rating"] = 0.0
    new_product["numReviews"] = 0
    new_product["createdAt"] = datetime.utcnow()
    new_product["updatedAt"] = datetime.utcnow()

    result = await db.products.insert_one(new_product)
    new_product["_id"] = str(result.inserted_id)
    new_product["user"] = str(new_product["user"])
    return new_product

@router.get("/{id}")
async def get_product_by_id(id: str):
    db = get_db()
    product = await db.products.find_one({"_id": ObjectId(id)})
    if product:
        product["_id"] = str(product["_id"])
        product["user"] = str(product.get("user", ""))
        for r in product.get("reviews", []):
            r["user"] = str(r["user"])
        return product
    raise HTTPException(status_code=404, detail="Product not found")


@router.get("/{id}/related")
async def get_related_products(id: str):
    db = get_db()
    product = await db.products.find_one({"_id": ObjectId(id)})
    
    if product and "collections" in product and product["collections"]:
        cursor = db.products.find({
            "collections": {"$in": product["collections"]},
            "_id": {"$ne": ObjectId(id)} 
        }).limit(4)
        
        related = await cursor.to_list(length=4)
        for p in related:
            p["_id"] = str(p["_id"])
            p["user"] = str(p.get("user", ""))
            for r in p.get("reviews", []):
                r["user"] = str(r["user"]) 
        return related
    return []

@router.put("/{id}")
async def update_product(id: str, product_update: ProductUpdate, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    product = await db.products.find_one({"_id": ObjectId(id)})
    if product:
        update_data = {k: v for k, v in product_update.dict().items() if v is not None}
        update_data["updatedAt"] = datetime.utcnow()
        await db.products.update_one({"_id": ObjectId(id)}, {"$set": update_data})
        
        updated_product = await db.products.find_one({"_id": ObjectId(id)})
        updated_product["_id"] = str(updated_product["_id"])
        updated_product["user"] = str(updated_product.get("user", ""))
        for r in updated_product.get("reviews", []):
            r["user"] = str(r["user"])
        return updated_product
    raise HTTPException(status_code=404, detail="Product not found")

@router.delete("/{id}")
async def delete_product(id: str, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    result = await db.products.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 1:
        return {"message": "Product deleted successfully"}
    raise HTTPException(status_code=404, detail="Product not found")

@router.post("/{id}/reviews")
async def create_product_review(id: str, review: ReviewCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    order = await db.orders.find_one({
        "user": ObjectId(current_user["_id"]),
        "isDelivered": True,
        "orderItems.product": id
    })
    if not order:
        raise HTTPException(status_code=400, detail="You must purchase and receive this product to write a review.")
    
    product = await db.products.find_one({"_id": ObjectId(id)})
    if product:
        already_reviewed = any(str(r.get("user")) == str(current_user["_id"]) for r in product.get("reviews", []))
        if already_reviewed:
            raise HTTPException(status_code=400, detail="Product already reviewed")
            
        new_review = {
            "name": current_user["name"],
            "rating": review.rating,
            "comment": review.comment,
            "user": ObjectId(current_user["_id"]),
            "createdAt": datetime.utcnow()
        }
        reviews = product.get("reviews", [])
        reviews.append(new_review)
        
        num_reviews = len(reviews)
        rating = sum(r["rating"] for r in reviews) / num_reviews if num_reviews > 0 else 0
        
        await db.products.update_one(
            {"_id": ObjectId(id)},
            {"$set": {
                "reviews": reviews,
                "numReviews": num_reviews,
                "rating": rating,
                "updatedAt": datetime.utcnow()
            }}
        )
        return {"message": "Review added successfully"}
    raise HTTPException(status_code=404, detail="Product not found")