"""
OpenGov AI Assistant - Production Ready with Groq API
Deployable on Render.com
"""

import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import RAG engine
from rag_engine import get_rag_engine

# Initialize Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    logger.info("Groq API initialized successfully")
except Exception as e:
    GROQ_AVAILABLE = False
    logger.warning(f"Groq API not available: {e}")

# ==================== Configuration ====================

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin123")

# ==================== Data Models ====================

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(..., pattern="^(FR|Procurement|Establishment)$")

class AskResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    category: str
    timestamp: str

# ==================== Application Lifespan ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OpenGov AI Assistant starting up...")
    try:
        rag_engine = get_rag_engine()
        logger.info("RAG engine initialized")
    except Exception as e:
        logger.error(f"Error initializing RAG engine: {e}")
    yield
    logger.info("OpenGov AI Assistant shutting down...")

# ==================== FastAPI App ====================

app = FastAPI(
    title="OpenGov AI Assistant",
    description="AI-powered assistant for Sri Lankan government financial regulations",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG engine
rag_engine = get_rag_engine()

# ==================== Helper Functions ====================

def extract_regulation_number(text: str) -> str:
    """Extract regulation/F.R. number from text"""
    patterns = [
        r'(?:F\.R\.|FR)\s*(\d+(?:\.\d+)?)',
        r'(?:Regulation|Reg)\s*(\d+(?:\.\d+)?)',
        r'(?:Section|Sec)\s*(\d+(?:\.\d+)?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"F.R. {match.group(1)}" if 'F.R.' in pattern else match.group(0)
    return ""


def call_groq_api(prompt: str) -> str:
    """Call Groq API for answer generation"""
    if not GROQ_AVAILABLE:
        return None
    
    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",  # Fast and accurate model
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert assistant for Sri Lankan government financial regulations. 
                    Answer based ONLY on the provided context. Be specific, cite regulation numbers, 
                    and provide complete answers. If the answer is not in the context, say so clearly."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower temperature for more accurate, consistent answers
            max_tokens=2000,
            top_p=0.9
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return None


def build_fallback_answer(results: list, question: str) -> str:
    """Build answer from search results when API is unavailable"""
    if not results:
        return "I couldn't find any relevant information. Please try rephrasing your question."
    
    best = results[0]
    content = best['content']
    regulation = best.get('regulation', '')
    page = best['metadata'].get('page', 'N/A')
    source = best['metadata'].get('source', 'Document')
    
    # For F.R. 139 (voucher certifying officer)
    if "voucher certifying officer" in question.lower() or "certifying officer" in question.lower():
        fr139_pattern = r'(F\.R\. 139.*?)(?=F\.R\. \d+|$)'
        match = re.search(fr139_pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            answer = match.group(1).strip()
            return f"**{regulation if regulation else 'F.R. 139'}** (Page {page})\n\n{answer}"
    
    # General fallback
    lines = content.split('\n')
    cleaned_lines = [line.strip() for line in lines if line.strip() and len(line.strip()) > 20]
    
    if regulation:
        header = f"**{regulation}** (Page {page})\n\n"
    else:
        header = f"**From {source}** (Page {page})\n\n"
    
    return header + '\n'.join(cleaned_lines[:30])

# ==================== API Endpoints ====================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "groq_available": GROQ_AVAILABLE
    }

@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """Process user question and return AI-generated answer"""
    try:
        logger.info(f"Question: {request.question[:100]}... | Category: {request.category}")
        
        # Search for relevant documents
        results = rag_engine.search(
            query=request.question,
            category=request.category,
            k=8
        )
        
        if not results:
            return AskResponse(
                answer="I couldn't find any relevant information in the documents. Please try rephrasing your question or ensure PDF documents have been uploaded.",
                sources=[],
                category=request.category,
                timestamp=datetime.now().isoformat()
            )
        
        # Build context from search results
        context_parts = []
        sources = []
        
        for i, result in enumerate(results[:5]):
            content = result['content']
            regulation = result.get('regulation', '')
            metadata = result['metadata']
            
            # Truncate very long content to fit token limits
            if len(content) > 1500:
                content = content[:1500] + "..."
            
            context_parts.append(f"[{regulation if regulation else 'Document'} - Page {metadata.get('page', 'N/A')}]\n{content}")
            
            sources.append({
                "source": metadata.get('source', 'Unknown'),
                "page": metadata.get('page', 'N/A'),
                "relevance_score": round(result['relevance_score'], 2),
                "regulation": regulation
            })
        
        full_context = "\n\n---\n\n".join(context_parts)
        
        # Build prompt for Groq
        prompt = f"""CONTEXT FROM OFFICIAL DOCUMENTS:
{full_context}

USER QUESTION: {request.question}

INSTRUCTIONS:
1. Answer ONLY using information from the context above
2. Cite specific regulation numbers (like F.R. 139) and page numbers
3. If the question asks for responsibilities, list them clearly as numbered items
4. Use the exact wording from the regulations
5. Provide a COMPLETE answer - do not truncate
6. If the answer is not in the context, say "Based on the available documents, I cannot find specific information about this."

ANSWER:"""

        # Try Groq API first
        answer = call_groq_api(prompt)
        
        # If API fails, use fallback
        if not answer:
            logger.warning("Groq API unavailable, using fallback extraction")
            answer = build_fallback_answer(results, request.question)
        
        return AskResponse(
            answer=answer,
            sources=sources,
            category=request.category,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        return AskResponse(
            answer=f"An error occurred while processing your question: {str(e)}",
            sources=[],
            category=request.category,
            timestamp=datetime.now().isoformat()
        )

# ==================== Admin Endpoints ====================

async def verify_admin_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    token = authorization
    if token.startswith("Bearer "):
        token = token[7:]
    
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid authorization token")
    
    return True

@app.post("/admin/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    category: str = Form(...),
    _: bool = Depends(verify_admin_token)
):
    """Upload a PDF file for ingestion (admin only)"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    if category not in ["FR", "Procurement", "Establishment"]:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    try:
        from ingest import PDFIngester
        
        # Create category folder
        category_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "data", 
            category
        )
        os.makedirs(category_folder, exist_ok=True)
        
        # Save file
        file_path = os.path.join(category_folder, file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Process the uploaded PDF
        ingester = PDFIngester()
        result = ingester.ingest_single_file(file_path, category)
        
        if result['status'] == 'success':
            return {
                "status": "success",
                "message": f"Successfully uploaded and processed {file.filename}",
                "documents_processed": result['documents_processed'],
                "chunks_created": result['chunks_created'],
                "filename": file.filename
            }
        else:
            raise HTTPException(status_code=400, detail=result.get('message', 'Processing failed'))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")

# ==================== Frontend Serving ====================

FRONTEND_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

@app.get("/")
async def serve_frontend():
    index_path = os.path.join(FRONTEND_PATH, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found"}

@app.get("/{filename}")
async def serve_static(filename: str):
    file_path = os.path.join(FRONTEND_PATH, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return None

# ==================== Main Entry Point ====================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print("=" * 60)
    print("🚀 OpenGov AI Assistant - Groq API Edition")
    print("=" * 60)
    print(f"📍 Groq API: {'✓ Available' if GROQ_AVAILABLE else '✗ Not Available'}")
    print(f"📍 Server: http://localhost:{port}")
    print(f"📍 API Docs: http://localhost:{port}/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port)
