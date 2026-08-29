import os
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("SUPABASE_URL and SUPABASE_KEY environment variables must be set.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
security = HTTPBearer()

app = FastAPI(
    title="Auth API with Supabase & JWT Protection",
    version="3.0",
    description="Secure API managing user sign up, log in, log out, and protected routes for FlyRank BE-03"
)

# Request Body Models
class AuthPayload(BaseModel):
    email: EmailStr
    password: str

# Reusable Middleware Dependency for Token Verification
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        return user_response.user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

# 1. Sign Up Endpoint
@app.post("/auth/signup", status_code=status.HTTP_201_CREATED, summary="Register new user")
def signup(payload: AuthPayload):
    if not payload.email or not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email and password are required")
    try:
        response = supabase.auth.sign_up({"email": payload.email, "password": payload.password})
        if not response.user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signup failed")
        return {"id": response.user.id, "email": response.user.email, "created_at": response.user.created_at}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# 2. Login Endpoint
@app.post("/auth/login", status_code=status.HTTP_200_OK, summary="Authenticate user & return JWT")
def login(payload: AuthPayload):
    if not payload.email or not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email and password are required")
    try:
        response = supabase.auth.sign_in_with_password({"email": payload.email, "password": payload.password})
        if not response.session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login credentials")
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer"
        }
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login credentials")

# 3. Logout Endpoint (Protected)
@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Terminate active user session")
def logout(credentials: HTTPAuthorizationCredentials = Depends(security), user = Depends(get_current_user)):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    return None

# 4. Public Unprotected Endpoint
@app.get("/public/info", status_code=status.HTTP_200_OK, summary="Read public open data")
def get_public_info():
    return {"message": "Welcome stranger! This info is public."}

# 5. Protected Profile Endpoint
@app.get("/protected/profile", status_code=status.HTTP_200_OK, summary="Read private user profile")
def get_profile(user = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at
    }

# 6. Additional Protected Endpoint (Proof of Middleware Reuse)
@app.get("/protected/dashboard", status_code=status.HTTP_200_OK, summary="Access protected user dashboard")
def get_dashboard(user = Depends(get_current_user)):
    return {
        "message": f"Welcome back, {user.email}! This is your private dashboard.",
        "user_id": user.id
    }
  
