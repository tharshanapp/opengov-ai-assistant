"""
Advanced RAG Engine - Semantic Search with Regulation Detection
Finds the MOST RELEVANT regulation for ANY question automatically
"""

import os
import pickle
import logging
import re
import numpy as np
from typing import List, Dict, Any, Tuple
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdvancedRAGEngine:
    CATEGORIES = {
        "FR": "Financial Regulations",
        "Procurement": "Procurement Guidelines",
        "Establishment": "Establishment Code"
    }
    
    def __init__(self):
        self.persist_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vector_store")
        self.documents = {cat: [] for cat in self.CATEGORIES.keys()}
        self.metadatas = {cat: [] for cat in self.CATEGORIES.keys()}
        self.regulation_chunks = {cat: {} for cat in self.CATEGORIES.keys()}
        
        self._load_vector_store()
        self._build_regulation_index()
        
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
                            self.documents[category] = data
                        logger.info(f"Loaded {len(self.documents[category])} chunks for {category}")
                except Exception as e:
                    logger.error(f"Error loading {category}: {e}")
    
    def _save_vector_store(self, category: str):
        """Save vector store to disk"""
        docs_path = os.path.join(self.persist_directory, f"{category}_docs.pkl")
        
        with open(docs_path, 'wb') as f:
            pickle.dump({
                'documents': self.documents[category],
                'metadatas': self.metadatas[category]
            }, f)
    
    def add_documents(self, documents: List[Dict], category: str) -> Dict[str, Any]:
        """Add documents to the vector store (for ingestion)"""
        if category not in self.documents:
            return {"status": "error", "message": "Invalid category"}
        
        for doc in documents:
            self.documents[category].append(doc['content'])
            self.metadatas[category].append(doc['metadata'])
        
        # Save to disk
        self._save_vector_store(category)
        
        # Rebuild regulation index for this category
        self._build_regulation_index_for_category(category)
        
        return {
            "status": "success",
            "documents_added": len(documents),
            "category": category
        }
    
    def _extract_regulation_number(self, text: str) -> str:
        """Extract regulation/F.R. number from text"""
        patterns = [
            r'(?:F\.R\.|FR)\s*(\d+(?:\.\d+)?)',
            r'(?:Regulation|Reg)\s*(\d+(?:\.\d+)?)',
            r'(?:Section|Sec)\s*(\d+(?:\.\d+)?)',
            r'\[(\d+(?:\.\d+)?)\]',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if 'F.R.' in pattern or 'FR' in pattern:
                    return f"F.R. {match.group(1)}"
                return match.group(0)
        return ""
    
    def _build_regulation_index_for_category(self, category: str):
        """Build regulation index for a single category"""
        regulations = {}
        
        for i, doc in enumerate(self.documents[category]):
            reg_num = self._extract_regulation_number(doc)
            if reg_num and reg_num not in regulations:
                # Get full regulation content (combine consecutive chunks)
                content = doc
                for j in range(i+1, min(i+5, len(self.documents[category]))):
                    next_reg = self._extract_regulation_number(self.documents[category][j])
                    if not next_reg:
                        content += " " + self.documents[category][j]
                    else:
                        break
                
                regulations[reg_num] = {
                    'content': content,
                    'metadata': self.metadatas[category][i],
                    'chunk_index': i
                }
        
        self.regulation_chunks[category] = regulations
        logger.info(f"Found {len(regulations)} regulations in {category}")
    
    def _build_regulation_index(self):
        """Build an index of regulations with their content"""
        for category in self.CATEGORIES.keys():
            self._build_regulation_index_for_category(category)
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract important key phrases from question"""
        stop_words = {'what', 'is', 'are', 'the', 'of', 'to', 'and', 'for', 'in', 'on', 'at', 'by', 'with', 
                      'without', 'about', 'against', 'between', 'through', 'during', 'before', 'after', 
                      'above', 'below', 'from', 'up', 'down', 'off', 'over', 'under', 'again', 'further', 
                      'then', 'once', 'here', 'there', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 
                      'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 
                      'that', 'these', 'those', 'too', 'very', 'just', 'but', 'do', 'does', 'did', 'doing',
                      'explain', 'describe', 'tell', 'me', 'about'}
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        key_phrases = [w for w in words if w not in stop_words]
        return key_phrases
    
    def _score_regulation_relevance(self, question: str, reg_content: str, reg_num: str) -> float:
        """Score how relevant a regulation is to the question"""
        question_lower = question.lower()
        content_lower = reg_content.lower()
        
        # Extract key phrases from question
        question_keywords = self._extract_key_phrases(question)
        
        if not question_keywords:
            return 0
        
        # Calculate keyword matches
        keyword_matches = sum(1 for kw in question_keywords if kw in content_lower)
        keyword_score = keyword_matches / len(question_keywords)
        
        # Check if question keywords appear in regulation number
        reg_num_score = 1.0 if any(kw in reg_num.lower() for kw in question_keywords) else 0
        
        # Check for phrase matches (exact or partial)
        phrase_score = 0
        if len(question) > 10:
            question_parts = question_lower.split()
            for i in range(len(question_parts) - 2):
                phrase = ' '.join(question_parts[i:i+3])
                if phrase in content_lower:
                    phrase_score += 0.5
        
        # Check for specific responsibility indicators
        responsibility_keywords = ['responsibility', 'responsible', 'duty', 'role', 'function', 'task', 'obligation']
        is_responsibility_question = any(kw in question_lower for kw in responsibility_keywords)
        has_responsibility_content = any(kw in content_lower for kw in responsibility_keywords)
        responsibility_score = 0.3 if is_responsibility_question and has_responsibility_content else 0
        
        # Calculate final score (weighted)
        final_score = (keyword_score * 3) + reg_num_score + phrase_score + responsibility_score
        
        return final_score
    
    def _get_best_regulation(self, question: str, category: str) -> Tuple[str, Dict, float]:
        """Find the most relevant regulation for the question"""
        best_score = 0
        best_reg = None
        best_content = None
        
        for reg_num, reg_data in self.regulation_chunks[category].items():
            score = self._score_regulation_relevance(question, reg_data['content'], reg_num)
            if score > best_score:
                best_score = score
                best_reg = reg_num
                best_content = reg_data
        
        return best_reg, best_content, best_score
    
    def search(self, query: str, category: str, k: int = 3) -> List[Dict[str, Any]]:
        """Search for the most relevant regulation(s)"""
        
        if category not in self.documents:
            return []
        
        # First, try to find the best regulation match
        best_reg, best_content, best_score = self._get_best_regulation(query, category)
        
        if best_content and best_score > 0.3:
            # Return the single best regulation with full content
            logger.info(f"Best match: {best_reg} (score: {best_score:.2f})")
            return [{
                'content': best_content['content'],
                'metadata': best_content['metadata'],
                'relevance_score': min(best_score, 1.0),
                'regulation': best_reg,
                'is_exact_match': True
            }]
        
        # Fallback to chunk-based search if no good regulation match
        query_keywords = self._extract_key_phrases(query)
        
        if not query_keywords:
            return []
        
        results = []
        for i, doc in enumerate(self.documents[category]):
            doc_lower = doc.lower()
            keyword_matches = sum(1 for kw in query_keywords if kw in doc_lower)
            
            if keyword_matches > 0:
                reg_num = self._extract_regulation_number(doc)
                results.append({
                    'content': doc,
                    'metadata': self.metadatas[category][i],
                    'relevance_score': min(keyword_matches / len(query_keywords), 1.0),
                    'regulation': reg_num,
                    'is_exact_match': False
                })
        
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:k]
    
    def get_stats(self, category: str) -> Dict[str, Any]:
        if category not in self.documents:
            return {"category": category, "document_count": 0}
        return {
            "category": category,
            "document_count": len(self.documents[category]),
            "regulation_count": len(self.regulation_chunks.get(category, {})),
            "category_name": self.CATEGORIES[category]
        }


_engine_instance = None

def get_rag_engine() -> AdvancedRAGEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AdvancedRAGEngine()
    return _engine_instance