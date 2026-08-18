from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from database import get_db
from utils.auth import get_admin_user
from bson import ObjectId

router = APIRouter(prefix="/api/collections", tags=["Collections"])

class CollectionBase(BaseModel):
    name: str

class CollectionProductsUpdate(BaseModel):
    productIds: List[str]

@router.post("")
async def create_collection(collection: CollectionBase, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    existing = await db.collections.find_one({"name": collection.name})
    if existing:
        raise HTTPException(status_code=400, detail="Collection already exists")
    
    new_col = collection.dict()
    res = await db.collections.insert_one(new_col)
    new_col["_id"] = str(res.inserted_id)
    return new_col

@router.get("")
async def get_collections():
    db = get_db()
    cursor = db.collections.find({})
    cols = await cursor.to_list(length=100)
    for c in cols:
        c["_id"] = str(c["_id"])
    return cols

@router.get("/{id}")
async def get_collection(id: str):
    db = get_db()
    col = await db.collections.find_one({"_id": ObjectId(id)})
    if col:
        col["_id"] = str(col["_id"])
        return col
    raise HTTPException(status_code=404, detail="Collection not found")

@router.put("/{id}/products")
async def update_collection_products(id: str, update_data: CollectionProductsUpdate, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    col = await db.collections.find_one({"_id": ObjectId(id)})
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    col_name = col["name"]
    
    await db.products.update_many(
        {"collections": col_name},
        {"$pull": {"collections": col_name}}
    )
    
    if update_data.productIds:
        object_ids = [ObjectId(pid) for pid in update_data.productIds]
        await db.products.update_many(
            {"_id": {"$in": object_ids}},
            {"$addToSet": {"collections": col_name}}
        )
    
    return {"message": "Collection products updated successfully"}

@router.delete("/{id}")
async def delete_collection(id: str, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    res = await db.collections.delete_one({"_id": ObjectId(id)})
    if res.deleted_count == 1:
        return {"message": "Deleted"}
    raise HTTPException(status_code=404, detail="Not found")