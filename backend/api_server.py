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

# Response Models
class Case(BaseModel):
    id: int
    user_id: int
    status: str
    category: str
    details: str
    urgency: str
    budget_range: Optional[str] = None
    created_at: str
    updated_at: str

class User(BaseModel):
    id: int
    name: str
    email: str
    company: str
    phone: Optional[str] = None

class Search(BaseModel):
    id: int
    case_id: int
    query: str
    timestamp: str
    results_json: str

class Offer(BaseModel):
    id: int
    case_id: int
    vendor_email: str
    price_quoted: Optional[float] = None
    details: str
    status: str
    received_at: str

class EmailCommunication(BaseModel):
    id: int
    case_id: int
    vendor_email: str
    subject: str
    body: str
    direction: str
    timestamp: str
    thread_id: Optional[str] = None

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
    status: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get all cases, optionally filtered by status"""
    try:
        cursor = db.cursor()
        if status:
            cursor.execute(
                "SELECT * FROM cases WHERE status = ? ORDER BY created_at DESC",
                (status,)
            )
        else:
            cursor.execute("SELECT * FROM cases ORDER BY created_at DESC")

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
        cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
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
            "SELECT * FROM searches WHERE case_id = ? ORDER BY timestamp DESC",
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
            "SELECT * FROM offers WHERE case_id = ? ORDER BY received_at DESC",
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
            "SELECT * FROM email_communications WHERE case_id = ? ORDER BY timestamp DESC",
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
        cursor.execute("""
            SELECT u.* FROM users u
            JOIN cases c ON c.user_id = u.id
            WHERE c.id = ?
        """, (case_id,))
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
