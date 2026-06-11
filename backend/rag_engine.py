
"""
Regulation-Focused RAG Engine - Extracts FR numbers and complete content
"""

import os
import pickle
import logging
import re
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RegulationRAGEngine:
    CATEGORIES = {
        "FR": "Financial Regulations",
        "Procurement": "Procurement Guidelines",
        "Establishment": "Establishment Code"
    }
    
    def __init__(self):
        self.persist_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vector_store")
        self.documents = {cat: [] for cat in self.CATEGORIES.keys()}
        self.metadatas = {cat: [] for cat in self.CATEGORIES.keys()}
        self.regulation_map = {cat: {} for cat in self.CATEGORIES.keys()}
        
        self._load_vector_store()
        self._build_regulation_map()
        
        total_chunks = sum(len(docs) for docs in self.documents.values())
        logger.info(f"Loaded {total_chunks} chunks from vector store")
        for cat, regs in self.regulation_map.items():
            logger.info(f"Found {len(regs)} regulations in {cat}")
    
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
    
    def _extract_fr_number(self, text: str) -> str:
        """Extract FR number like F.R. 139, FR 139, or 139"""
        patterns = [
            r'(?:F\.R\.|FR)\s*(\d+(?:\.\d+)?)',
            r'\((\d+)\)',  # For (1), (2) etc - these are sub-sections
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and 'F.R.' in pattern:
                return f"F.R. {match.group(1)}"
            elif match and pattern == r'\((\d+)\)':
                return f"Section {match.group(1)}"
        return ""
    
    def _build_regulation_map(self):
        """Build a map of regulation numbers to their content"""
        for category in self.CATEGORIES.keys():
            reg_map = {}
            for i, doc in enumerate(self.documents[category]):
                # Find all FR numbers in this chunk
                fr_matches = re.findall(r'(?:F\.R\.|FR)\s*(\d+(?:\.\d+)?)', doc, re.IGNORECASE)
                for fr_num in fr_matches:
                    reg_key = f"F.R. {fr_num}"
                    if reg_key not in reg_map:
                        reg_map[reg_key] = []
                    reg_map[reg_key].append(i)
            self.regulation_map[category] = reg_map
    
    def get_regulation_content(self, category: str, reg_number: str) -> Dict:
        """Get complete content for a specific regulation"""
        reg_number = reg_number.upper()
        if not reg_number.startswith('F.R.'):
            reg_number = f"F.R. {reg_number}"
        
        if reg_number in self.regulation_map[category]:
            indices = self.regulation_map[category][reg_number]
            # Combine all chunks for this regulation
            content_parts = []
            page = None
            source = None
            for idx in indices:
                content_parts.append(self.documents[category][idx])
                if not page:
                    page = self.metadatas[category][idx].get('page', 'N/A')
                    source = self.metadatas[category][idx].get('source', 'Unknown')
            
            # Clean and format the content
            full_content = '\n'.join(content_parts)
            
            # Extract bullet points and numbered items
            lines = full_content.split('\n')
            formatted_lines = []
            for line in lines:
                line = line.strip()
                if line:
                    # Highlight numbered items like (1), (2)
                    if re.match(r'\(\d+\)', line):
                        formatted_lines.append(f"\n**{line}**")
                    elif re.match(r'\d+\.', line):
                        formatted_lines.append(f"\n**{line}**")
                    else:
                        formatted_lines.append(line)
            
            return {
                'content': '\n'.join(formatted_lines),
                'regulation': reg_number,
                'page': page,
                'source': source,
                'found': True
            }
        return {'found': False}
    
    def search(self, query: str, category: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant documents"""
        if category not in self.documents or not self.documents[category]:
            return []
        
        # First, check if user is asking about a specific regulation
        fr_match = re.search(r'(?:F\.R\.|FR)\s*(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if fr_match:
            reg_num = f"F.R. {fr_match.group(1)}"
            reg_content = self.get_regulation_content(category, reg_num)
            if reg_content['found']:
                return [{
                    'content': reg_content['content'],
                    'metadata': {'source': reg_content['source'], 'page': reg_content['page']},
                    'relevance_score': 1.0,
                    'regulation': reg_num,
                    'is_exact_match': True
                }]
        
        # Fallback to keyword search
        query_lower = query.lower()
        query_words = set(re.findall(r'\b\w{3,}\b', query_lower))
        stop_words = {'what', 'is', 'are', 'the', 'of', 'to', 'and', 'for', 'in', 'on', 'at', 'by', 'with', 'a', 'an', 'be', 'was', 'were', 'has', 'have', 'had', 'that', 'this', 'these', 'those', 'from', 'they', 'will', 'can', 'could', 'would', 'should'}
        query_keywords = {w for w in query_words if w not in stop_words}
        
        results = []
        for i, doc in enumerate(self.documents[category]):
            doc_lower = doc.lower()
            keyword_matches = sum(1 for kw in query_keywords if kw in doc_lower)
            relevance = min(keyword_matches / max(len(query_keywords), 1), 1.0)
            
            if relevance > 0.1:
                # Extract FR number if present
                fr_num = self._extract_fr_number(doc)
                results.append({
                    'content': doc[:1500],
                    'metadata': self.metadatas[category][i],
                    'relevance_score': relevance,
                    'regulation': fr_num
                })
        
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:k]
    
    def get_stats(self, category: str) -> Dict[str, Any]:
        if category not in self.documents:
            return {"category": category, "document_count": 0}
        return {
            "category": category,
            "document_count": len(self.documents[category]),
            "regulations_found": len(self.regulation_map[category]),
            "category_name": self.CATEGORIES[category]
        }


_engine_instance = None

def get_rag_engine() -> RegulationRAGEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = RegulationRAGEngine()
    return _engine_instance