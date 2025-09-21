from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime
from enum import Enum


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Enums
class InquiryType(str, Enum):
    advisory = "advisory"
    interim = "interim"
    transformation = "transformation"
    board = "board"
    consulting = "consulting"
    other = "other"

class ConsultationStatus(str, Enum):
    new = "new"
    contacted = "contacted"
    in_progress = "in_progress"
    closed = "closed"

# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

class ExecutiveConsultation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    company: str = Field(..., min_length=2, max_length=100)
    title: str = Field(..., min_length=2, max_length=100)
    inquiry_type: InquiryType
    message: str = Field(..., min_length=10, max_length=2000)
    status: ConsultationStatus = Field(default=ConsultationStatus.new)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    contacted_at: Optional[datetime] = None
    notes: Optional[str] = None
    priority: str = Field(default="medium")

class ExecutiveConsultationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    company: str = Field(..., min_length=2, max_length=100)
    title: str = Field(..., min_length=2, max_length=100)
    inquiry_type: InquiryType
    message: str = Field(..., min_length=10, max_length=2000)

class ConsultationResponse(BaseModel):
    success: bool
    message: str
    consultation_id: Optional[str] = None
    estimated_response_time: str = "24 hours"

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Executive Portfolio API - Strategic Leadership Services"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

@api_router.post("/consultation", response_model=ConsultationResponse)
async def submit_executive_consultation(consultation: ExecutiveConsultationCreate):
    """
    Submit an executive consultation request
    """
    try:
        # Create consultation object with generated ID and timestamp
        consultation_obj = ExecutiveConsultation(**consultation.dict())
        
        # Store in database
        result = await db.executive_consultations.insert_one(consultation_obj.dict())
        
        if result.inserted_id:
            logger.info(f"New executive consultation request from {consultation.email} at {consultation.company}")
            
            return ConsultationResponse(
                success=True,
                message="Executive consultation request received successfully. Thank you for your interest in strategic collaboration.",
                consultation_id=consultation_obj.id,
                estimated_response_time="24 hours"
            )
        else:
            raise Exception("Failed to store consultation request")
            
    except Exception as e:
        logger.error(f"Error processing consultation request: {str(e)}")
        return ConsultationResponse(
            success=False,
            message="Unable to process your request at this time. Please try again or contact directly via email.",
            consultation_id=None
        )

@api_router.get("/consultations", response_model=List[ExecutiveConsultation])
async def get_executive_consultations(status: Optional[ConsultationStatus] = None):
    """
    Get executive consultation requests (admin endpoint)
    """
    try:
        query = {}
        if status:
            query["status"] = status.value
            
        consultations = await db.executive_consultations.find(query).sort("submitted_at", -1).to_list(100)
        return [ExecutiveConsultation(**consultation) for consultation in consultations]
    except Exception as e:
        logger.error(f"Error retrieving consultations: {str(e)}")
        return []

@api_router.get("/consultation/{consultation_id}", response_model=ExecutiveConsultation)
async def get_consultation_by_id(consultation_id: str):
    """
    Get specific consultation by ID (admin endpoint)
    """
    try:
        consultation = await db.executive_consultations.find_one({"id": consultation_id})
        if consultation:
            return ExecutiveConsultation(**consultation)
        else:
            raise HTTPException(status_code=404, detail="Consultation not found")
    except Exception as e:
        logger.error(f"Error retrieving consultation {consultation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
