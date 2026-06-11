"""
OpenGov AI Assistant - Production Ready
"""

from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from datetime import datetime
import os
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from rag_engine import get_rag_engine

app = FastAPI(title="OpenGov AI Assistant", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG engine
rag_engine = get_rag_engine()


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(..., pattern="^(FR|Procurement|Establishment)$")


# ==================== API Endpoints ====================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "rag_engine": "active"
    }


@app.post("/ask")
async def ask_question(request: AskRequest):
    try:
        logger.info(f"Question: {request.question[:100]}... | Category: {request.category}")
        
        results = rag_engine.search(
            query=request.question,
            category=request.category,
            k=5
        )
        
        if not results:
            return {
                "answer": "I couldn't find any relevant information. Please ensure PDF documents have been uploaded.",
                "sources": [],
                "category": request.category,
                "timestamp": datetime.now().isoformat()
            }
        
        # Build answer from search results
        answer_parts = []
        sources = []
        
        for i, result in enumerate(results, 1):
            reg_text = result.get('regulation', '')
            page = result['metadata'].get('page', 'N/A')
            content = result['content'][:800]
            
            if reg_text:
                answer_parts.append(f"**{reg_text}** (Page {page})\n{content}")
            else:
                answer_parts.append(f"**Section {page}**\n{content}")
            
            sources.append({
                "source": result['metadata'].get('source', 'Unknown'),
                "page": page,
                "relevance_score": round(result.get('relevance_score', 0.5), 2)
            })
        
        answer = f"**Based on the {rag_engine.CATEGORIES[request.category]}:**\n\n"
        answer += "\n\n---\n\n".join(answer_parts)
        
        return {
            "answer": answer,
            "sources": sources,
            "category": request.category,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"answer": f"Error: {str(e)}", "sources": []}
        )


# ==================== Static File Serving - CRITICAL FOR PRODUCTION ====================

# Get paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PATH = os.path.join(os.path.dirname(CURRENT_DIR), "frontend")

logger.info(f"Frontend path: {FRONTEND_PATH}")
logger.info(f"Frontend exists: {os.path.exists(FRONTEND_PATH)}")

if os.path.exists(FRONTEND_PATH):
    # Mount the entire frontend folder for static files
    app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")
    
    # Serve index.html at root
    @app.get("/")
    async def serve_index():
        index_path = os.path.join(FRONTEND_PATH, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path, media_type="text/html")
        return {"error": "index.html not found"}
    
    # Serve CSS file directly
    @app.get("/style.css")
    async def serve_css():
        css_path = os.path.join(FRONTEND_PATH, "style.css")
        if os.path.exists(css_path):
            return FileResponse(css_path, media_type="text/css")
        logger.error(f"CSS not found at: {css_path}")
        return {"error": "CSS not found"}
    
    # Serve JS file directly
    @app.get("/app.js")
    async def serve_js():
        js_path = os.path.join(FRONTEND_PATH, "app.js")
        if os.path.exists(js_path):
            return FileResponse(js_path, media_type="application/javascript")
        logger.error(f"JS not found at: {js_path}")
        return {"error": "JS not found"}
    
    # Serve any other static files
    @app.get("/{filename}")
    async def serve_other(filename: str):
        file_path = os.path.join(FRONTEND_PATH, filename)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            if filename.endswith('.css'):
                return FileResponse(file_path, media_type="text/css")
            elif filename.endswith('.js'):
                return FileResponse(file_path, media_type="application/javascript")
            elif filename.endswith('.html'):
                return FileResponse(file_path, media_type="text/html")
            return FileResponse(file_path)
        return None
else:
    logger.error(f"Frontend directory not found at: {FRONTEND_PATH}")
    
    @app.get("/")
    async def root():
        return {
            "message": "OpenGov AI Assistant API",
            "status": "running",
            "endpoints": {
                "ask": "/ask",
                "health": "/health"
            }
        }


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("🚀 OpenGov AI Assistant - Production Ready")
    print("=" * 60)
    print(f"📍 Frontend path: {FRONTEND_PATH}")
    print(f"📍 Frontend exists: {os.path.exists(FRONTEND_PATH)}")
    print("📍 Server: http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
