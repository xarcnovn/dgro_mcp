from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from typing import List, Optional, Generator
import json
import os

app = FastAPI(title="DGRO API", version="1.0.0")

# CORS for Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "case_search.db")

# Response Models (aligned with MCP server schema)
class Case(BaseModel):
    id: int
    subject: str
    features: str
    location: str
    budget: float
    timeline: str
    additional_features: Optional[str] = None

class User(BaseModel):
    id: int
    case_id: int
    name: str
    email: str
    phone: Optional[str] = None

class Search(BaseModel):
    id: int
    case_id: int
    search_goal: str
    search_query: str
    search_results: str

class Offer(BaseModel):
    offer_id: int
    case_id: int
    status: str
    price: Optional[float] = None
    timeline: str
    accuracy: float
    additional_details: Optional[str] = None
    communication_thread_id: Optional[str] = None
    vendor_email: str
    created_at: str
    updated_at: str

class EmailCommunication(BaseModel):
    id: int
    case_id: int
    vendor_email: str
    vendor_name: Optional[str] = None
    vendor_website: Optional[str] = None
    subject: str
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    email_type: str
    email_content: str
    sent_at: str
    status: Optional[str] = None

# Initialize database with optimal settings
def init_db():
    """Initialize database with WAL mode for better concurrency"""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
    finally:
        conn.close()

# Run on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# Database dependency with automatic cleanup
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Database connection with automatic cleanup.
    Prevents connection leaks by using FastAPI dependency injection.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Endpoints with proper error handling and connection management
@app.get("/api/cases", response_model=List[Case])
def get_cases(
    db: sqlite3.Connection = Depends(get_db)
):
    """Get all cases"""
    try:
        cursor = db.cursor()
        cursor.execute("SELECT id, subject, features, location, budget, timeline, additional_features FROM cases ORDER BY id DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}", response_model=Case)
def get_case(
    case_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get single case by ID"""
    try:
        cursor = db.cursor()
        cursor.execute("SELECT id, subject, features, location, budget, timeline, additional_features FROM cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Case not found")

        return dict(row)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}/searches", response_model=List[Search])
def get_searches(
    case_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get all searches for a case"""
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, case_id, search_goal, search_query, search_results FROM searches WHERE case_id = ? ORDER BY id DESC",
            (case_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}/offers", response_model=List[Offer])
def get_offers(
    case_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get all offers for a case"""
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT offer_id, case_id, status, price, timeline, accuracy, additional_details, communication_thread_id, vendor_email, created_at, updated_at FROM offers WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}/communications", response_model=List[EmailCommunication])
def get_communications(
    case_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get all email communications for a case"""
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, case_id, vendor_email, vendor_name, vendor_website, subject, message_id, thread_id, email_type, email_content, sent_at, status FROM email_communications WHERE case_id = ? ORDER BY sent_at DESC",
            (case_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/users/{case_id}", response_model=User)
def get_user_by_case(
    case_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get user info for a case"""
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, case_id, name, email, phone FROM users WHERE case_id = ?",
            (case_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        return dict(row)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
