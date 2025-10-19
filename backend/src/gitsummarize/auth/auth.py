from dotenv import load_dotenv
from fastapi import Security, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Optional
import os

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")

security_scheme = HTTPBearer(description="Enter your API token")
security_scheme_optional = HTTPBearer(description="Enter your API token", auto_error=False)

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    token = credentials.credentials
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return token

def verify_token_optional(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme_optional)) -> Optional[str]:
    """
    Optional token verification for local usage.
    Returns None if no credentials are provided or API_TOKEN is not set.
    Does not raise HTTPException, allowing endpoints to work without authentication.
    """
    # If API_TOKEN is not set, allow access without authentication
    if not API_TOKEN:
        return None
    
    # If no credentials provided, allow access without authentication
    if not credentials:
        return None
    
    # If credentials provided, verify them
    token = credentials.credentials
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return token