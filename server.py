from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import os

# Create FastAPI app
app = FastAPI()

# Allow your frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection (uses Railway environment variable)
MONGO_URL = os.environ.get("MONGO_URL")
client = AsyncIOMotorClient(MONGO_URL)
db = client["portfolio_db"]

# Consultation types
class InquiryType(str, Enum):
    advisory = "advisory"
    interim = "interim"
    transformation = "transformation"
    board = "board"
    consulting = "consulting"

# What the form sends
class ConsultationCreate(BaseModel):
    name: str
    email: EmailStr
    company: str
    title: str
    inquiry_type: InquiryType
    message: str

# What we store
class Consultation(BaseModel):
    name: str
    email: EmailStr
    company: str
    title: str
    inquiry_type: InquiryType
    message: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

# Response back to frontend
class ConsultationResponse(BaseModel):
    success: bool
    message: str
    consultation_id: Optional[str] = None

# Test endpoint
@app.get("/")
async def root():
    return {"message": "API is running!"}

# Test API endpoint
@app.get("/api")
async def api_root():
    return {"message": "API endpoint is working!"}

# Submit consultation (POST)
@app.post("/api/consultation", response_model=ConsultationResponse)
async def submit_consultation(consultation: ConsultationCreate):
    try:
        consultation_data = Consultation(**consultation.dict())
        result = await db.consultations.insert_one(consultation_data.dict())
        return ConsultationResponse(
            success=True,
            message="Your consultation request has been submitted successfully!",
            consultation_id=str(result.inserted_id)
        )
    except Exception as e:
        return ConsultationResponse(
            success=False,
            message=f"Error: {str(e)}"
        )

# Get all consultations (for you to view submissions)
@app.get("/api/consultations")
async def get_consultations():
    consultations = await db.consultations.find().to_list(100)
    for c in consultations:
        c["_id"] = str(c["_id"])
    return consultations
