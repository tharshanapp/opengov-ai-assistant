"""
PDF Ingestion Script - No API Required
"""

import os
import sys
from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rag_engine import get_rag_engine


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file"""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text += f"\n[Page {page_num}]\n{page_text}\n"
        return text
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return ""


def chunk_text(text: str, source: str, chunk_size: int = 1000, overlap: int = 200) -> list:
    """Split text into overlapping chunks"""
    if not text:
        return []
    
    chunks = []
    # Split by pages first
    pages = text.split('[Page ')
    
    for page in pages:
        if not page.strip():
            continue
        
        # Extract page number
        page_match = page.split(']', 1)
        page_num = page_match[0] if page_match else "1"
        content = page_match[1] if len(page_match) > 1 else page
        
        # Split content into chunks
        words = content.split()
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            if chunk_words:
                chunk_text = ' '.join(chunk_words)
                chunks.append({
                    'content': chunk_text,
                    'metadata': {
                        'source': source,
                        'page': page_num,
                        'chunk_id': len(chunks)
                    }
                })
    
    return chunks


def ingest_all():
    """Ingest all PDFs from data folders"""
    engine = get_rag_engine()
    categories = ['FR', 'Procurement', 'Establishment']
    
    print("=" * 60)
    print("OpenGov AI Assistant - PDF Ingestion")
    print("=" * 60)
    
    total_chunks = 0
    
    for category in categories:
        folder_path = os.path.join('data', category)
        if not os.path.exists(folder_path):
            print(f"\nCreating folder: {folder_path}")
            os.makedirs(folder_path, exist_ok=True)
            continue
        
        pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
        if not pdf_files:
            print(f"\n⚠️ No PDF files in {folder_path}")
            print(f"   Please add PDF files to: {folder_path}")
            continue
        
        print(f"\n📁 Processing {category}: {len(pdf_files)} PDF(s)")
        all_chunks = []
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(folder_path, pdf_file)
            print(f"   📄 {pdf_file}")
            
            text = extract_text_from_pdf(pdf_path)
            if text:
                chunks = chunk_text(text, pdf_file)
                all_chunks.extend(chunks)
                print(f"      ✓ Created {len(chunks)} chunks")
            else:
                print(f"      ⚠️ No text extracted")
        
        if all_chunks:
            result = engine.add_documents(all_chunks, category)
            total_chunks += result['documents_added']
            print(f"   ✅ Added {result['documents_added']} chunks")
    
    print("\n" + "=" * 60)
    print("Ingestion Complete!")
    print("=" * 60)
    
    for cat in categories:
        stats = engine.get_stats(cat)
        print(f"   {cat}: {stats['document_count']} chunks")
    
    print("=" * 60)
    print("✅ Ready to run: python app.py")
    print("=" * 60)


if __name__ == "__main__":
    ingest_all()