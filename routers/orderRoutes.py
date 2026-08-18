from fastapi import APIRouter, Depends, HTTPException
from database import get_db
from utils.auth import get_current_user, get_admin_user
from models.orderModel import OrderCreate
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/api/orders", tags=["Orders"])

def fix_object_ids(order_dict):
    if "_id" in order_dict:
        order_dict["_id"] = str(order_dict["_id"])
    if "user" in order_dict and isinstance(order_dict["user"], ObjectId):
        order_dict["user"] = str(order_dict["user"])
    
    if "orderItems" in order_dict:
        for item in order_dict["orderItems"]:
            if "product" in item:
                item["product"] = str(item["product"])
            if "_id" in item:
                item["_id"] = str(item["_id"])
    return order_dict

@router.post("")
async def add_order_items(order: OrderCreate, current_user: dict = Depends(get_current_user)):
    if not order.orderItems:
        raise HTTPException(status_code=400, detail="No order items found. Cart is empty.")

    db = get_db()
    new_order = order.dict()
    new_order["user"] = ObjectId(current_user["_id"])
    
    if new_order.get("paymentMethod") == "bKash":
        new_order["isPaid"] = True
        new_order["paidAt"] = datetime.utcnow()
    else:
        new_order["isPaid"] = False
        
    new_order["isDelivered"] = False
    new_order["createdAt"] = datetime.utcnow()
    new_order["updatedAt"] = datetime.utcnow()

    result = await db.orders.insert_one(new_order)
    new_order["_id"] = str(result.inserted_id)
    new_order["user"] = str(new_order["user"])
    
    return fix_object_ids(new_order)

@router.get("/mine")
async def get_my_orders(current_user: dict = Depends(get_current_user)):
    db = get_db()
    orders_cursor = db.orders.find({"user": ObjectId(current_user["_id"])})
    orders = await orders_cursor.to_list(length=100)
    
    for o in orders:
        fix_object_ids(o)
    return orders

@router.get("/summary")
async def get_order_summary(admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    total_orders = await db.orders.count_documents({})
    total_users = await db.users.count_documents({})
    total_products = await db.products.count_documents({})

    orders_cursor = db.orders.find({})
    orders = await orders_cursor.to_list(length=total_orders if total_orders > 0 else 1)
    total_sales = sum(o.get("totalPrice", 0) for o in orders)

    pipeline = [
        {
            "$group": {
                "_id": { "$dateToString": { "format": "%Y-%m-%d", "date": "$createdAt" } },
                "sales": { "$sum": "$totalPrice" }
            }
        },
        { "$sort": { "_id": 1 } }
    ]
    daily_orders_cursor = db.orders.aggregate(pipeline)
    daily_orders = await daily_orders_cursor.to_list(length=100)

    return {
        "totalOrders": total_orders,
        "totalUsers": total_users,
        "totalProducts": total_products,
        "totalSales": total_sales,
        "dailyOrders": daily_orders
    }

@router.get("")
async def get_orders(admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    pipeline = [
        {
            "$lookup": {
                "from": "users",
                "localField": "user",
                "foreignField": "_id",
                "as": "userDetails"
            }
        },
        { "$unwind": { "path": "$userDetails", "preserveNullAndEmptyArrays": True } }
    ]
    orders_cursor = db.orders.aggregate(pipeline)
    orders = await orders_cursor.to_list(length=100)
    
    for o in orders:
        fix_object_ids(o)
        if "userDetails" in o and o["userDetails"]:
            o["user"] = {"id": str(o["userDetails"]["_id"]), "name": o["userDetails"].get("name", "Unknown")}
            del o["userDetails"]
        else:
            o["user"] = {"id": "", "name": "Deleted User"}
            
    return orders

@router.get("/{id}")
async def get_order_by_id(id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    pipeline = [
        { "$match": { "_id": ObjectId(id) } },
        {
            "$lookup": {
                "from": "users",
                "localField": "user",
                "foreignField": "_id",
                "as": "userDetails"
            }
        },
        { "$unwind": { "path": "$userDetails", "preserveNullAndEmptyArrays": True } }
    ]
    order_cursor = db.orders.aggregate(pipeline)
    orders = await order_cursor.to_list(length=1)
    
    if orders:
        order = orders[0]
        fix_object_ids(order)
        if "userDetails" in order and order["userDetails"]:
            order["user"] = {"name": order["userDetails"].get("name", "Unknown"), "email": order["userDetails"].get("email", "Unknown")}
            del order["userDetails"]
        else:
            order["user"] = {"name": "Deleted User", "email": "No email provided"}
        return order
        
    raise HTTPException(status_code=404, detail="Order not found!")

@router.put("/{id}/deliver")
async def update_order_to_delivered(id: str, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    order = await db.orders.find_one({"_id": ObjectId(id)})
    if order:
        await db.orders.update_one(
            {"_id": ObjectId(id)}, 
            {"$set": {"isDelivered": True, "updatedAt": datetime.utcnow()}}
        )
        updated_order = await db.orders.find_one({"_id": ObjectId(id)})
        return fix_object_ids(updated_order)
        
    raise HTTPException(status_code=404, detail="Order not found!")

@router.delete("/{id}")
async def delete_order(id: str, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    result = await db.orders.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 1:
        return {"message": "Order deleted successfully"}
    raise HTTPException(status_code=404, detail="Order not found")