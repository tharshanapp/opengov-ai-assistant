cd /Users/mac/Documents/Open_AI_Assistant/OpenGov_AI_Assistant

# Check the current status of your rag_engine.py
cat backend/rag_engine.py | head -20

# If it still shows "from sklearn...", you need to update it
# Create the correct version (no sklearn)
cat > backend/rag_engine.py << 'EOF'
"""
Simple RAG Engine - No scikit-learn required
Uses basic keyword matching for document search
"""

import os
import logging
import re
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleRAGEngine:
    CATEGORIES = {
        "FR": "Financial Regulations",
        "Procurement": "Procurement Guidelines",
        "Establishment": "Establishment Code"
    }
    
    def __init__(self):
        self.documents = {cat: [] for cat in self.CATEGORIES.keys()}
        self.metadatas = {cat: [] for cat in self.CATEGORIES.keys()}
        logger.info("Simple RAG Engine initialized (no scikit-learn)")
    
    def add_documents(self, documents: List[Dict], category: str) -> Dict[str, Any]:
        if category not in self.documents:
            return {"status": "error", "message": "Invalid category"}
        
        for doc in documents:
            self.documents[category].append(doc['content'])
            self.metadatas[category].append(doc['metadata'])
        
        return {
            "status": "success",
            "documents_added": len(documents),
            "category": category
        }
    
    def search(self, query: str, category: str, k: int = 5) -> List[Dict[str, Any]]:
        if category not in self.documents or not self.documents[category]:
            return []
        
        query_words = set(query.lower().split())
        results = []
        
        for i, doc in enumerate(self.documents[category]):
            doc_words = set(doc.lower().split())
            matches = len(query_words.intersection(doc_words))
            score = matches / max(len(query_words), 1)
            
            if score > 0:
                results.append({
                    'content': doc[:800],
                    'metadata': self.metadatas[category][i],
                    'relevance_score': score,
                    'regulation': self._extract_regulation(doc)
                })
        
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:k]
    
    def _extract_regulation(self, text: str) -> str:
        match = re.search(r'(?:F\.R\.|FR|Regulation)\s*\d+(?:\.\d+)?', text, re.IGNORECASE)
        return match.group(0) if match else ""
    
    def get_stats(self, category: str) -> Dict[str, Any]:
        if category not in self.documents:
            return {"category": category, "document_count": 0}
        return {
            "category": category,
            "document_count": len(self.documents[category]),
            "category_name": self.CATEGORIES[category]
        }


_engine_instance = None

def get_rag_engine() -> SimpleRAGEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SimpleRAGEngine()
    return _engine_instance
