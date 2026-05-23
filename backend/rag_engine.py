"""
Simple RAG Engine - No scikit-learn required
Uses basic keyword matching for document search
"""

import os
import logging
import pickle
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
        self.persist_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vector_store")
        self.documents = {cat: [] for cat in self.CATEGORIES.keys()}
        self.metadatas = {cat: [] for cat in self.CATEGORIES.keys()}
        
        # Load existing vector store if available
        self._load_vector_store()
        
        if not any(self.documents.values()):
            logger.warning("No existing vector store found. Please run python ingest.py first.")
        else:
            total_chunks = sum(len(docs) for docs in self.documents.values())
            logger.info(f"Loaded {total_chunks} chunks from vector store")
    
    def _load_vector_store(self):
        """Load existing vector store files"""
        for category in self.CATEGORIES.keys():
            docs_path = os.path.join(self.persist_directory, f"{category}_docs.pkl")
            
            if os.path.exists(docs_path):
                try:
                    with open(docs_path, 'rb') as f:
                        data = pickle.load(f)
                        if isinstance(data, dict):
                            self.documents[category] = data.get('documents', [])
                            self.metadatas[category] = data.get('metadatas', [])
                        else:
                            # Legacy format
                            self.documents[category] = data
                        logger.info(f"Loaded {len(self.documents[category])} chunks for {category}")
                except Exception as e:
                    logger.error(f"Error loading {category}: {e}")
    
    def add_documents(self, documents: List[Dict], category: str) -> Dict[str, Any]:
        """Add documents to the vector store (for ingestion)"""
        if category not in self.documents:
            return {"status": "error", "message": "Invalid category"}
        
        for doc in documents:
            self.documents[category].append(doc['content'])
            self.metadatas[category].append(doc['metadata'])
        
        # Save after adding
        self._save_vector_store(category)
        
        return {
            "status": "success",
            "documents_added": len(documents),
            "category": category
        }
    
    def _save_vector_store(self, category: str):
        """Save vector store to disk"""
        os.makedirs(self.persist_directory, exist_ok=True)
        docs_path = os.path.join(self.persist_directory, f"{category}_docs.pkl")
        
        with open(docs_path, 'wb') as f:
            pickle.dump({
                'documents': self.documents[category],
                'metadatas': self.metadatas[category]
            }, f)
    
    def search(self, query: str, category: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant documents"""
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
                    'metadata': self.metadatas[category][i] if i < len(self.metadatas[category]) else {},
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
