"""
OpenGov AI Assistant - Regulation-Focused Answers
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from datetime import datetime
import os
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from rag_engine import get_rag_engine

app = FastAPI(title="OpenGov AI Assistant", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_engine = get_rag_engine()


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(..., pattern="^(FR|Procurement|Establishment)$")


@app.get("/health")
async def health_check():
    stats = {}
    for cat in ['FR', 'Procurement', 'Establishment']:
        s = rag_engine.get_stats(cat)
        stats[cat] = s['document_count']
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "document_chunks": stats,
        "regulations_found": {cat: s.get('regulations_found', 0) for cat, s in stats.items()}
    }


@app.post("/ask")
async def ask_question(request: AskRequest):
    try:
        logger.info(f"Question: {request.question} | Category: {request.category}")
        
        # Extract regulation number from question
        fr_match = re.search(r'(?:F\.R\.|FR)\s*(\d+(?:\.\d+)?)', request.question, re.IGNORECASE)
        
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
        
        # Build answer
        best = results[0]
        
        # If the best result has a regulation number, format it nicely
        if best.get('regulation'):
            answer = _format_regulation_answer(best)
        else:
            answer = _format_general_answer(best)
        
        sources = []
        for r in results[:3]:
            sources.append({
                "source": r['metadata'].get('source', 'Unknown'),
                "page": r['metadata'].get('page', 'N/A'),
                "relevance_score": round(r['relevance_score'], 2),
                "regulation": r.get('regulation', '')
            })
        
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


def _format_regulation_answer(result: dict) -> str:
    """Format answer when a regulation number is found"""
    content = result['content']
    regulation = result.get('regulation', '')
    page = result['metadata'].get('page', 'N/A')
    
    # Clean the content
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if line and len(line) > 3:
            # Clean up whitespace
            line = re.sub(r'\s+', ' ', line)
            cleaned_lines.append(line)
    
    # Build answer
    answer = f"**{regulation}** (Page {page})\n\n"
    
    # Process each line to highlight key items
    for line in cleaned_lines:
        # Highlight numbered items like (1), (2)
        if re.match(r'\(\d+\)', line):
            answer += f"\n**{line}**"
        # Highlight numbered items like 1., 2.
        elif re.match(r'\d+\.', line):
            answer += f"\n**{line}**"
        else:
            answer += f"\n{line}"
    
    return answer


def _format_general_answer(result: dict) -> str:
    """Format general answer without regulation number"""
    content = result['content']
    page = result['metadata'].get('page', 'N/A')
    source = result['metadata'].get('source', 'Document')
    
    lines = content.split('\n')
    cleaned_lines = [line.strip() for line in lines if line.strip() and len(line.strip()) > 10]
    
    answer = f"**From {source}** (Page {page})\n\n"
    answer += '\n'.join(cleaned_lines[:20])  # Limit to 20 lines
    
    return answer


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
    print("=" * 60)
    print("📚 OpenGov AI Assistant - Regulation-Focused Version")
    print("=" * 60)
    print("📍 Server: http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
