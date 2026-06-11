"""
Enhanced RAG Engine - Extracts complete answers from PDFs
No external API needed for basic Q&A
"""

import os
import pickle
import logging
import re
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedRAGEngine:
    CATEGORIES = {
        "FR": "Financial Regulations",
        "Procurement": "Procurement Guidelines",
        "Establishment": "Establishment Code"
    }
    
    def __init__(self):
        self.persist_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vector_store")
        self.documents = {cat: [] for cat in self.CATEGORIES.keys()}
        self.metadatas = {cat: [] for cat in self.CATEGORIES.keys()}
        
        self._load_vector_store()
        
        total_chunks = sum(len(docs) for docs in self.documents.values())
        logger.info(f"Loaded {total_chunks} chunks from vector store")
    
    def _load_vector_store(self):
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
    
    def _extract_regulation_number(self, text: str) -> str:
        patterns = [
            r'(?:F\.R\.|FR)\s*(\d+(?:\.\d+)?)',
            r'(?:Regulation|Reg)\s*(\d+(?:\.\d+)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"F.R. {match.group(1)}"
        return ""
    
    def _extract_complete_section(self, content: str, reg_num: str) -> str:
        """Extract complete regulation section including all bullet points"""
        lines = content.split('\n')
        result_lines = []
        capture = False
        bullet_count = 0
        
        for line in lines:
            if reg_num.lower() in line.lower():
                capture = True
                result_lines.append(line)
                continue
            
            if capture:
                # Check if we've reached a new regulation
                if re.match(r'(?:F\.R\.|FR)\s*\d+', line, re.IGNORECASE):
                    break
                
                # Capture bullet points and numbered items
                if re.match(r'\(\d+\)', line.strip()) or re.match(r'\d+\.', line.strip()):
                    bullet_count += 1
                    result_lines.append(line)
                elif line.strip() and bullet_count > 0:
                    # Continue capturing content after bullet points
                    result_lines.append(line)
                elif line.strip() and not re.match(r'\(?\d+\)?\.?\s*$', line.strip()):
                    if len(result_lines) > 1:  # Only add if we already have regulation
                        result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def search(self, query: str, category: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant documents with improved context extraction"""
        if category not in self.documents or not self.documents[category]:
            return []
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        stop_words = {'what', 'is', 'are', 'the', 'of', 'to', 'and', 'for', 'in', 'on', 'at', 'by', 'with', 'a', 'an', 'be', 'was', 'were', 'has', 'have', 'had'}
        query_keywords = {w for w in query_words if w not in stop_words and len(w) > 2}
        
        # Check if asking about a specific regulation
        reg_match = re.search(r'(?:F\.R\.|FR)\s*(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        target_reg = f"F.R. {reg_match.group(1)}" if reg_match else None
        
        results = []
        for i, doc in enumerate(self.documents[category]):
            doc_lower = doc.lower()
            doc_reg = self._extract_regulation_number(doc)
            
            # Calculate relevance score
            if target_reg and target_reg in doc_lower:
                relevance = 1.0  # Direct regulation match
            else:
                keyword_matches = sum(1 for kw in query_keywords if kw in doc_lower)
                relevance = min(keyword_matches / max(len(query_keywords), 1), 1.0)
            
            if relevance > 0.05:
                # Extract the complete section if it's a regulation
                if doc_reg:
                    content = self._extract_complete_section(doc, doc_reg)
                else:
                    content = doc
                
                results.append({
                    'content': content,
                    'metadata': self.metadatas[category][i],
                    'relevance_score': relevance,
                    'regulation': doc_reg
                })
        
        # Sort by relevance and return top results
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:k]
    
    def get_stats(self, category: str) -> Dict[str, Any]:
        if category not in self.documents:
            return {"category": category, "document_count": 0}
        return {
            "category": category,
            "document_count": len(self.documents[category]),
            "category_name": self.CATEGORIES[category]
        }


_engine_instance = None

def get_rag_engine() -> EnhancedRAGEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = EnhancedRAGEngine()
    return _engine_instance