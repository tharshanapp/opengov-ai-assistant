"""
OpenGov AI Assistant - Production Application
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from datetime import datetime
import os
import logging

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from rag_engine import get_rag_engine  # Still works with new implementation

app = FastAPI(title="OpenGov AI Assistant", version="2.0.0")

# CORS for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tharshan.lk", "http://localhost:8000", "https://*.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG engine
try:
    rag_engine = get_rag_engine()
    logger.info("RAG engine initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize RAG engine: {e}")
    rag_engine = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(..., pattern="^(FR|Procurement|Establishment)$")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "rag_engine": "active" if rag_engine else "inactive",
        "environment": os.getenv("ENVIRONMENT", "production")
    }


@app.post("/ask")
async def ask_question(request: AskRequest):
    """Process user question and return relevant information"""
    if not rag_engine:
        return JSONResponse(
            status_code=503,
            content={
                "answer": "System is initializing. Please try again in a moment.",
                "sources": [],
                "category": request.category,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    try:
        logger.info(f"Question received: {request.question[:100]}...")
        
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
        
        answer_parts = []
        sources = []
        
        for i, result in enumerate(results, 1):
            reg_text = result['regulation'] if result['regulation'] else f"Section {result['metadata'].get('page', 'N/A')}"
            answer_parts.append(f"**{reg_text}** (Page {result['metadata'].get('page', 'N/A')})\n{result['content'][:600]}...")
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
        logger.error(f"Error processing question: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "answer": f"An error occurred: {str(e)}",
                "sources": [],
                "category": request.category,
                "timestamp": datetime.now().isoformat()
            }
        )


@app.get("/stats/{category}")
async def get_stats(category: str):
    """Get statistics for a category"""
    if not rag_engine:
        return {"error": "RAG engine not initialized"}
    return rag_engine.get_stats(category)


# Serve Frontend
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PATH = os.path.join(os.path.dirname(CURRENT_DIR), "frontend")

if os.path.exists(FRONTEND_PATH):
    app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")
    
    @app.get("/")
    async def serve_frontend():
        index_path = os.path.join(FRONTEND_PATH, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Frontend not found"}
    
    @app.get("/style.css")
    async def serve_css():
        css_path = os.path.join(FRONTEND_PATH, "style.css")
        if os.path.exists(css_path):
            return FileResponse(css_path, media_type="text/css")
        return {"error": "CSS not found"}
    
    @app.get("/app.js")
    async def serve_js():
        js_path = os.path.join(FRONTEND_PATH, "app.js")
        if os.path.exists(js_path):
            return FileResponse(js_path, media_type="application/javascript")
        return {"error": "JS not found"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
