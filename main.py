from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import client
from routers import userRoutes, productRoutes, orderRoutes, contactRoutes, uploadRoutes
from routers import collectionRoutes
from routers import aiRoutes
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


app.include_router(userRoutes.router)
app.include_router(productRoutes.router)
app.include_router(orderRoutes.router)
app.include_router(contactRoutes.router)
app.include_router(uploadRoutes.router)
app.include_router(collectionRoutes.router)
app.include_router(aiRoutes.router)
@app.on_event("startup")
async def startup_db_client():
    try:
        await client.admin.command('ping')
        print("MongoDB Connected Successfully!")
    except Exception as e:
        print("MongoDB Connection Error:", e)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

@app.get("/")
async def root():
    return {"message": "AI E-commerce Backend is working perfectly!"}