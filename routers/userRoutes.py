import os
import random
import requests
from fastapi import APIRouter, Depends, HTTPException
from database import get_db
from utils.auth import get_password_hash, verify_password, create_access_token, get_current_user, get_admin_user
from utils.email_sender import send_otp_email
from bson import ObjectId
from models.userModel import UserCreate, UserLogin, UserUpdate, VerifyEmail, GoogleLogin, ForgotPassword, ResetPassword
from pydantic import BaseModel

router = APIRouter(prefix="/api/users", tags=["Users"])

# --- Pydantic Models for Admin Actions ---
class AdminUserCreate(BaseModel):
    name: str
    email: str
    password: str
    isAdmin: bool = False

class AdminUserUpdate(BaseModel):
    name: str
    email: str
    isAdmin: bool

# --- Helper Function ---
def fix_user_id(user_dict):
    if "_id" in user_dict:
        user_dict["_id"] = str(user_dict["_id"])
    return user_dict


# ==========================================
# AUTHENTICATION & REGISTRATION ROUTES
# ==========================================

@router.post("/register")
async def register_user(user: UserCreate):
    db = get_db()
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists!")
    
    hashed_password = get_password_hash(user.password)
    otp = str(random.randint(100000, 999999))
    
    new_user = {
        "name": user.name,
        "email": user.email,
        "password": hashed_password,
        "role": user.role or "customer",
        "isAdmin": True if user.role == "admin" else False,
        "is_verified": False,
        "auth_provider": "local",
        "verification_code": otp
    }
    
    result = await db.users.insert_one(new_user)
    send_otp_email(user.email, otp)
    
    return {
        "email": new_user["email"],
        "message": "User account created! Please check your email for the verification code."
    }

@router.post("/verify-email")
async def verify_email(data: VerifyEmail):
    db = get_db()
    user = await db.users.find_one({"email": data.email})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")
    
    if user.get("is_verified"):
        raise HTTPException(status_code=400, detail="Email is already verified!")
        
    if user.get("verification_code") != data.otp:
        raise HTTPException(status_code=400, detail="Invalid verification code!")
        
    await db.users.update_one(
        {"email": data.email}, 
        {"$set": {"is_verified": True}, "$unset": {"verification_code": ""}}
    )
    
    return {
        "_id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "role": user.get("role", "customer"),
        "isAdmin": user.get("isAdmin", False),
        "token": create_access_token({"id": str(user["_id"])}),
        "message": "Email verified and login successful!"
    }

@router.post("/login")
async def login_user(user: UserLogin):
    db = get_db()
    db_user = await db.users.find_one({"email": user.email})
    
    if db_user and verify_password(user.password, db_user["password"]):
        if not db_user.get("is_verified") and db_user.get("auth_provider") == "local":
            raise HTTPException(status_code=403, detail="Please verify your email first!")
            
        return {
            "_id": str(db_user["_id"]),
            "name": db_user["name"],
            "email": db_user["email"],
            "role": db_user.get("role", "customer"),
            "isAdmin": db_user.get("isAdmin", False),
            "token": create_access_token({"id": str(db_user["_id"])}),
            "message": "Login successful!"
        }
    raise HTTPException(status_code=401, detail="Invalid email or password!")

@router.post("/google-login")
async def google_login(data: GoogleLogin):
    try:
        google_response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {data.token}"}
        )
        
        if google_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Invalid Google Token!")
            
        user_info = google_response.json()
        email = user_info.get("email")
        name = user_info.get("name")
        
        db = get_db()
        user = await db.users.find_one({"email": email})
        
        if not user:
            new_user = {
                "name": name,
                "email": email,
                "password": "", 
                "isAdmin": False,
                "role": "customer",
                "is_verified": True
            }
            result = await db.users.insert_one(new_user)
            user = await db.users.find_one({"_id": result.inserted_id})
            
        access_token = create_access_token({"id": str(user["_id"])})
        
        return {
            "_id": str(user["_id"]),
            "name": user.get("name"),
            "email": user.get("email"),
            "isAdmin": user.get("isAdmin", False),
            "role": user.get("role", "customer"),
            "token": access_token
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid Google Token!")

@router.post("/forgot-password")
async def forgot_password(data: ForgotPassword):
    db = get_db()
    user = await db.users.find_one({"email": data.email})
    
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email!")
    
    otp = str(random.randint(100000, 999999))
    await db.users.update_one({"email": data.email}, {"$set": {"reset_otp": otp}})
    send_otp_email(data.email, otp) 
    
    return {"message": "Password reset OTP has been sent to your email."}

@router.post("/reset-password")
async def reset_password(data: ResetPassword):
    db = get_db()
    user = await db.users.find_one({"email": data.email})
    
    if not user or user.get("reset_otp") != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP or Email!")
        
    hashed_password = get_password_hash(data.new_password)
    await db.users.update_one(
        {"email": data.email}, 
        {"$set": {"password": hashed_password}, "$unset": {"reset_otp": ""}}
    )
    
    return {"message": "Password changed successfully! You can now log in."}


# ==========================================
# ADMIN PANEL ROUTES (CRUD for Customers)
# ==========================================

# 1. Get all users
@router.get("")
async def get_users(admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    users_cursor = db.users.find({}, {"password": 0})
    users = await users_cursor.to_list(length=1000)
    return [fix_user_id(u) for u in users]

# 2. Create a new user from Admin Panel (CSV Import / Manual Add)
@router.post("")
async def create_user_admin(user: AdminUserCreate, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail=f"Email {user.email} already exists!")
    
    hashed_password = get_password_hash(user.password)
    
    new_user = {
        "name": user.name,
        "email": user.email,
        "password": hashed_password,
        "role": "admin" if user.isAdmin else "customer",
        "isAdmin": user.isAdmin,
        "is_verified": True, 
        "auth_provider": "local"
    }
    
    result = await db.users.insert_one(new_user)
    new_user["_id"] = str(result.inserted_id)
    del new_user["password"]
    
    return new_user

# 3. Get single user by ID for Editing
@router.get("/{id}")
async def get_user_by_id(id: str, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(id)}, {"password": 0})
    if user:
        return fix_user_id(user)
    raise HTTPException(status_code=404, detail="User not found!")

# 4. Update user details
@router.put("/{id}")
async def update_user(id: str, user_update: AdminUserUpdate, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(id)})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")
        
    update_data = {
        "name": user_update.name,
        "email": user_update.email,
        "isAdmin": user_update.isAdmin,
        "role": "admin" if user_update.isAdmin else "customer"
    }
    
    await db.users.update_one({"_id": ObjectId(id)}, {"$set": update_data})
    updated_user = await db.users.find_one({"_id": ObjectId(id)}, {"password": 0})
    
    return fix_user_id(updated_user)

# 5. Delete a user
@router.delete("/{id}")
async def delete_user(id: str, admin_user: dict = Depends(get_admin_user)):
    db = get_db()
    
    # Prevent admin from deleting themselves
    if str(admin_user["_id"]) == id:
        raise HTTPException(status_code=400, detail="You cannot delete your own admin account!")
        
    result = await db.users.delete_one({"_id": ObjectId(id)})
    
    if result.deleted_count == 1:
        return {"message": "User deleted successfully"}
    raise HTTPException(status_code=404, detail="User not found!")