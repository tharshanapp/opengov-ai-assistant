"""
Local RAG Engine - No External API Required
Uses TF-IDF for document search and retrieval
"""

import os
import pickle
import logging
import re
from typing import List, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LocalRAGEngine:
    """RAG Engine using local TF-IDF embeddings - No API required"""
    
    CATEGORIES = {
        "FR": "Financial Regulations",
        "Procurement": "Procurement Guidelines",
        "Establishment": "Establishment Code"
    }
    
    def __init__(self, persist_directory: str = None):
        if persist_directory is None:
            persist_directory = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                "vector_store"
            )
        
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        # Storage
        self.documents = {cat: [] for cat in self.CATEGORIES.keys()}
        self.metadatas = {cat: [] for cat in self.CATEGORIES.keys()}
        self.vectorizers = {cat: None for cat in self.CATEGORIES.keys()}
        self.tfidf_vectors = {cat: None for cat in self.CATEGORIES.keys()}
        
        # Load existing data
        self._load()
        logger.info("Local RAG Engine initialized (No API required)")
    
    def _extract_regulation_number(self, text: str) -> str:
        """Extract regulation/F.R. number from text"""
        patterns = [
            r'(?:F\.R\.|FR)\s*(\d+(?:\.\d+)?)',
            r'(?:Regulation|Reg)\s*(\d+(?:\.\d+)?)',
            r'(?:Section|Sec)\s*(\d+(?:\.\d+)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return ""
    
    def _load(self):
        """Load persisted data"""
        for category in self.CATEGORIES.keys():
            doc_path = os.path.join(self.persist_directory, f"{category}_docs.pkl")
            vec_path = os.path.join(self.persist_directory, f"{category}_vectorizer.pkl")
            
            if os.path.exists(doc_path):
                try:
                    with open(doc_path, 'rb') as f:
                        data = pickle.load(f)
                        self.documents[category] = data.get('documents', [])
                        self.metadatas[category] = data.get('metadatas', [])
                except Exception as e:
                    logger.error(f"Error loading {category}: {e}")
            
            if os.path.exists(vec_path) and self.documents[category]:
                try:
                    with open(vec_path, 'rb') as f:
                        self.vectorizers[category] = pickle.load(f)
                        if self.documents[category]:
                            self.tfidf_vectors[category] = self.vectorizers[category].transform(
                                self.documents[category]
                            )
                except Exception as e:
                    logger.error(f"Error loading vectorizer {category}: {e}")
    
    def _save(self, category: str):
        """Save data for a category"""
        doc_path = os.path.join(self.persist_directory, f"{category}_docs.pkl")
        vec_path = os.path.join(self.persist_directory, f"{category}_vectorizer.pkl")
        
        try:
            with open(doc_path, 'wb') as f:
                pickle.dump({
                    'documents': self.documents[category],
                    'metadatas': self.metadatas[category]
                }, f)
            
            if self.vectorizers[category]:
                with open(vec_path, 'wb') as f:
                    pickle.dump(self.vectorizers[category], f)
        except Exception as e:
            logger.error(f"Error saving {category}: {e}")
    
    def add_documents(self, documents: List[Dict], category: str) -> Dict[str, Any]:
        """Add documents to the vector store"""
        if category not in self.documents:
            return {"status": "error", "message": "Invalid category"}
        
        for doc in documents:
            self.documents[category].append(doc['content'])
            self.metadatas[category].append(doc['metadata'])
        
        # Rebuild TF-IDF vectors
        if self.documents[category]:
            self.vectorizers[category] = TfidfVectorizer(
                max_features=2000,
                stop_words='english',
                min_df=1,
                max_df=0.85,
                ngram_range=(1, 2)
            )
            self.tfidf_vectors[category] = self.vectorizers[category].fit_transform(
                self.documents[category]
            )
        
        self._save(category)
        
        return {
            "status": "success",
            "documents_added": len(documents),
            "category": category
        }
    
    def search(self, query: str, category: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant documents"""
        if category not in self.documents or not self.documents[category]:
            return []
        
        if not self.vectorizers[category] or self.tfidf_vectors[category] is None:
            return []
        
        try:
            # Transform query
            query_vec = self.vectorizers[category].transform([query])
            
            # Calculate similarities
            similarities = cosine_similarity(query_vec, self.tfidf_vectors[category]).flatten()
            
            # Get top indices
            top_indices = similarities.argsort()[-k:][::-1]
            
            results = []
            seen_content = set()
            
            for idx in top_indices:
                if similarities[idx] > 0.05:
                    content_key = self.documents[category][idx][:200]
                    if content_key in seen_content:
                        continue
                    seen_content.add(content_key)
                    
                    results.append({
                        'content': self.documents[category][idx],
                        'metadata': self.metadatas[category][idx],
                        'relevance_score': float(similarities[idx]),
                        'regulation': self._extract_regulation_number(
                            self.documents[category][idx]
                        )
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def get_stats(self, category: str) -> Dict[str, Any]:
        """Get collection statistics"""
        if category not in self.documents:
            return {"category": category, "document_count": 0}
        return {
            "category": category,
            "document_count": len(self.documents[category]),
            "category_name": self.CATEGORIES[category]
        }
    
    def clear(self, category: str) -> Dict[str, Any]:
        """Clear all documents"""
        self.documents[category] = []
        self.metadatas[category] = []
        self.vectorizers[category] = None
        self.tfidf_vectors[category] = None
        self._save(category)
        return {"status": "success", "message": f"Cleared {category}"}


_engine_instance = None


def get_rag_engine() -> LocalRAGEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LocalRAGEngine()
    return _engine_instance