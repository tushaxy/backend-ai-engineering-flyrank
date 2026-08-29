import os
import time
import requests
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, status, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import datetime

# -------------------------------------------------------------------
# Configuration & Database Setup
# -------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/widget_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# -------------------------------------------------------------------
# Database Models (Tenant Isolation & Schemas)
# -------------------------------------------------------------------
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=False)

class Widget(Base):
    __tablename__ = "widgets"
    id = Column(String, primary_key=True, index=True) # UUID/String ID
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    title = Column(String, nullable=False)
    allowed_domains = Column(String, default="*") # Allowed Origins
    is_active = Column(Boolean, default=True)

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    widget_id = Column(String, ForeignKey("widgets.id"), nullable=False)
    ip_address = Column(String, nullable=True)
    payload = Column(JSON, nullable=False)
    geo_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Database Session Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------------------------
# Pydantic Ingestion Schemas
# -------------------------------------------------------------------
class PublicSubmissionPayload(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    message: Optional[str] = None
    website_hp: Optional[str] = Field(None, description="Honeypot anti-spam field") # Must be empty

# -------------------------------------------------------------------
# Geo Enrichment Fallback Chain (Degrade, Never Fail)
# -------------------------------------------------------------------
def enrich_ip_location(ip: str) -> Dict[str, Any]:
    """
    Tries Provider A (ip-api.com) -> Provider B (ipapi.co) -> Graceful Fallback
    """
    if not ip or ip in ("127.0.0.1", "localhost", "::1"):
        return {"country": "Localhost", "city": "Local Dev"}

    # Provider A: ip-api.com
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}", timeout=2.5)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                return {"country": data.get("country"), "city": data.get("city"), "provider": "ip-api"}
    except Exception:
        pass # Fallthrough to Provider B

    # Provider B: ipapi.co
    try:
        res = requests.get(f"https://ipapi.co/{ip}/json/", timeout=2.5)
        if res.status_code == 200:
            data = res.json()
            return {"country": data.get("country_name"), "city": data.get("city"), "provider": "ipapi"}
    except Exception:
        pass # Fallthrough to empty fallback

    # All Providers Down / Failed -> Graceful Degradation
    return {"country": "Unknown", "city": "Unknown", "provider": "none"}

def safe_notification_side_effect(widget_id: str, submission_id: int):
    """
    Side effect (Email/Webhook). Failures MUST NOT block core execution path.
    """
    try:
        # Simulate background email dispatch
        time.sleep(0.5)
        print(f"[NOTIFICATION LOG] Triggered alert for Widget {widget_id}, Submission #{submission_id}")
    except Exception as e:
        print(f"[NOTIFICATION ERROR] Non-critical notification failed: {e}")

# -------------------------------------------------------------------
# FastAPI App & Dynamic CORS Config
# -------------------------------------------------------------------
app = FastAPI(
    title="Embeddable Widget & Lead-Capture API",
    version="1.0.0"
)

# Enable Dynamic Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Public internet ingestion
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Core Ingestion & Delivery Routes
# -------------------------------------------------------------------

@app.get("/widget.js", summary="Public Versioned Widget Script")
def get_widget_script():
    """
    Serves static widget snippet with long max-age caching.
    """
    script_path = os.path.join(os.path.dirname(__file__), "static", "widget.js")
    if not os.path.exists(script_path):
        return Response(content="// Widget Script Initializing...", media_type="application/javascript")
    
    return FileResponse(
        script_path,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"} # 1 Year CDN Cache
    )

@app.get("/api/v1/public/widgets/{widget_id}/config", summary="Fetch Widget Configuration")
def get_widget_config(widget_id: str, db: Session = Depends(get_db)):
    """
    Public config endpoint served with short max-age caching.
    """
    widget = db.query(Widget).filter(Widget.id == widget_id, Widget.is_active == True).first()
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found or inactive")
    
    return JSONResponse(
        content={
            "id": widget.id,
            "title": widget.title,
            "fields": ["email", "full_name", "message"]
        },
        headers={"Cache-Control": "public, max-age=300"} # 5 Minutes Cache
    )

@app.post("/api/v1/public/widgets/{widget_id}/submit", status_code=status.HTTP_201_CREATED, summary="Public Lead Submission")
def submit_lead(
    widget_id: str,
    payload: PublicSubmissionPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # 1. Verify Widget Existence
    widget = db.query(Widget).filter(Widget.id == widget_id, Widget.is_active == True).first()
    if not widget:
        raise HTTPException(status_code=404, detail="Widget missing or disabled")

    # 2. Anti-Spam Check (Honeypot Field Detection)
    if payload.website_hp is not None and len(payload.website_hp.strip()) > 0:
        # Silently reject bot submissions with 200/201 without storing
        return {"status": "success", "detail": "Submission received"}

    # 3. Extract IP Address & Perform Fallback Geo-Enrichment
    client_ip = request.client.host if request.client else "127.0.0.1"
    geo_data = enrich_ip_location(client_ip)

    # 4. Store Submission
    submission = Submission(
        widget_id=widget.id,
        ip_address=client_ip,
        payload=payload.model_dump(exclude={"website_hp"}),
        geo_data=geo_data
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # 5. Non-Blocking Side Effect Execution (Background Task)
    background_tasks.add_task(safe_notification_side_effect, widget.id, submission.id)

    return {"status": "success", "submission_id": submission.id, "geo_enriched": geo_data.get("provider") != "none"}
