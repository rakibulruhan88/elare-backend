from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import get_db
from utils.auth import get_admin_user
from bson import ObjectId
from datetime import datetime


router = APIRouter(prefix="/api/contact", tags=["Contact"])


class ContactCreate(BaseModel):
    name: str
    email: str
    subject: str
    message: str


def fix_contact_id(contact_dict):
    if "_id" in contact_dict:
        contact_dict["_id"] = str(contact_dict["_id"])
    return contact_dict


@router.post("")
async def create_message(contact: ContactCreate):
    db = get_db()
    new_message = contact.dict()
    new_message["createdAt"] = datetime.utcnow()
    new_message["isRead"] = False
    
    result = await db.contacts.insert_one(new_message)
    new_message["_id"] = str(result.inserted_id)
    return new_message


@router.get("")
async def get_messages(admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    cursor = db.contacts.find().sort("createdAt", -1) # নতুন মেসেজ আগে দেখাবে
    messages = await cursor.to_list(length=1000)
    return [fix_contact_id(m) for m in messages]


@router.get("/{id}")
async def get_message(id: str, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    message = await db.contacts.find_one({"_id": ObjectId(id)})
    
    if message:

        if not message.get("isRead"):
            await db.contacts.update_one({"_id": ObjectId(id)}, {"$set": {"isRead": True}})
        return fix_contact_id(message)
        
    raise HTTPException(status_code=404, detail="Message not found!")


@router.delete("/{id}")
async def delete_message(id: str, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    result = await db.contacts.delete_one({"_id": ObjectId(id)})
    
    if result.deleted_count == 1:
        return {"message": "Message deleted successfully"}
        
    raise HTTPException(status_code=404, detail="Message not found!")