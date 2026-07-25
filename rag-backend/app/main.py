from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import docs, chat
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
# Mount under /api
app.include_router(docs.router, prefix="/api", tags=["docs"])
app.include_router(chat.router, prefix="/api", tags=["chat"])

@app.get("/api/status")
async def get_system_status():
    """
    Check system readiness status
    """
    from app.core.config import get_settings
    settings = get_settings()
    
    return {
        "is_model_ready": bool(settings.DASHSCOPE_API_KEY),
        "api_key_configured": bool(settings.DASHSCOPE_API_KEY)
    }

@app.get("/")
async def root():
    return {"message": "RAG Backend Service is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
