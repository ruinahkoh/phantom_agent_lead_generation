import json
import os
import sys
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np


PHANTOMS_PATH = os.path.join(os.path.dirname(__file__), 'phantoms.json')


def load_phantoms(path: str) -> List[Dict[str, Any]]:
    with open(path, 'r', encoding='utf-8') as f:
        phantoms = json.load(f)
    # normalize fields for easier search
    for p in phantoms:
        p['search_text'] = ' '.join(filter(None, [p.get('id',''), p.get('description',''), ' '.join(p.get('tags',[]))]))
        
    return phantoms


class PhantomIndex:
    """Simple in-memory "vector" index using TF-IDF (prototype).
    Methods:
        - search(query, k): returns top-k phantoms and similarity scores
    Replace in production with real embeddings + vector database.
    """
    def __init__(self, phantoms: List[Dict[str,Any]]):
        self.phantoms = phantoms
        self.docs = [p['search_text'] for p in phantoms]
        self.retriever = []
        for p in phantoms:
            self.retriever.append({'id': p.get('id',''), 'description': p.get('description',''), 'tags': p.get('tags',[])})
        
        # Step 1: Embedding model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = self.model.encode(self.docs)

        # Step 2: Create FAISS index
        dimension = embeddings.shape[1]  # Vector dimension
        self.index = faiss.IndexFlatL2(dimension)  # L2 similarity

        # Step 3: Add embeddings to the index
        self.index.add(np.array(embeddings))

    def search_index(self, query: str, k: int = 5) -> List[Tuple[Dict[str,Any], float]]:
        query_vec = self.model.encode([query])
        D, I = self.index.search(np.array(query_vec), k=k) 
        return [self.retriever[idx] for idx in I[0]]