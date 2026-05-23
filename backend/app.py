"""
OpenGov AI Assistant - Main Application
No External API Required - Local RAG Only
"""

from fastapi import FastAPI, HTTPException
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


# API Endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "rag_engine": "local"
    }


@app.post("/ask")
async def ask_question(request: AskRequest):
    """Process user question and return relevant information"""
    try:
        logger.info(f"Q: {request.question[:100]}... | Cat: {request.category}")
        
        # Search for relevant documents
        results = rag_engine.search(
            query=request.question,
            category=request.category,
            k=5
        )
        
        if not results:
            return {
                "answer": "I couldn't find any relevant information. Please ensure:\n\n1. PDF documents are in data/ folder\n2. Run 'python ingest.py' to process documents\n3. Documents contain readable text",
                "sources": [],
                "category": request.category,
                "timestamp": datetime.now().isoformat()
            }
        
        # Build answer from search results
        answer_parts = []
        sources = []
        
        for i, result in enumerate(results, 1):
            reg_text = f"**{result['regulation']}**" if result['regulation'] else f"**Section {result['metadata'].get('page', 'N/A')}**"
            answer_parts.append(f"{reg_text} (Page {result['metadata'].get('page', 'N/A')})\n{result['content'][:800]}...")
            sources.append({
                "source": result['metadata'].get('source', 'Unknown'),
                "page": result['metadata'].get('page', 'N/A'),
                "relevance_score": round(result['relevance_score'], 3)
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


@app.get("/stats/{category}")
async def get_stats(category: str):
    """Get statistics for a category"""
    return rag_engine.get_stats(category)


# Serve Frontend
FRONTEND_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

@app.get("/")
async def serve_frontend():
    index_path = os.path.join(FRONTEND_PATH, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found"}

# Serve Frontend - Fix the path
FRONTEND_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

# If frontend not found in parent, try local
if not os.path.exists(FRONTEND_PATH):
    FRONTEND_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

# If still not found, try current directory
if not os.path.exists(FRONTEND_PATH):
    FRONTEND_PATH = "frontend"

print(f"Frontend path: {FRONTEND_PATH}")

@app.get("/")
async def serve_frontend():
    index_path = os.path.join(FRONTEND_PATH, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": f"Frontend not found at {index_path}. Please make sure frontend files exist."}

# Also serve static files
if os.path.exists(FRONTEND_PATH):
    app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")








if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("🚀 OpenGov AI Assistant - Local RAG System")
    print("=" * 60)
    print("📍 No External API Required")
    print("📍 Server: http://localhost:8000")
    print("📍 Frontend: http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)