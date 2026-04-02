import json
import os
import pickle
import re
import time

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from config import VECTOR_STORE_DIR
from services.embedding_service import get_embeddings


def _index_path(doc_id: str) -> str:
    return os.path.join(VECTOR_STORE_DIR, f"{doc_id}.faiss")


def _chunks_path(doc_id: str) -> str:
    return os.path.join(VECTOR_STORE_DIR, f"{doc_id}_chunks.pkl")


def _meta_path(doc_id: str) -> str:
    return os.path.join(VECTOR_STORE_DIR, f"{doc_id}_meta.json")


def _bm25_path(doc_id: str) -> str:
    return os.path.join(VECTOR_STORE_DIR, f"{doc_id}_bm25.pkl")


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer for BM25."""
    return re.findall(r"\w+", text.lower())


def build_vector_store(doc_id: str, chunks: list[dict], filename: str, session_id: str = ""):
    """Embed chunks and store them in a FAISS index + BM25 index.
    
    chunks: list of {"text": str, "pages": [int, ...]}
    """
    texts = [c["text"] for c in chunks]
    
    # Dense index (FAISS)
    embeddings = get_embeddings(texts)
    dimension = len(embeddings[0])
    vectors = np.array(embeddings, dtype="float32")

    index = faiss.IndexFlatL2(dimension)
    index.add(vectors)

    faiss.write_index(index, _index_path(doc_id))

    # Sparse index (BM25)
    tokenized_chunks = [_tokenize(t) for t in texts]
    bm25 = BM25Okapi(tokenized_chunks)

    with open(_bm25_path(doc_id), "wb") as f:
        pickle.dump(bm25, f)

    # Store chunks with metadata
    with open(_chunks_path(doc_id), "wb") as f:
        pickle.dump(chunks, f)

    with open(_meta_path(doc_id), "w") as f:
        json.dump({
            "doc_id": doc_id,
            "filename": filename,
            "num_chunks": len(chunks),
            "session_id": session_id,
            "created_at": time.time(),
        }, f)


def _rrf(rankings: list[list[int]], k: int = 60) -> list[int]:
    """Reciprocal Rank Fusion across multiple ranked lists."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc_idx in enumerate(ranking):
            scores[doc_idx] = scores.get(doc_idx, 0.0) + 1.0 / (k + rank + 1)
    return [idx for idx, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def search_vector_store(doc_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Hybrid search: FAISS (dense) + BM25 (sparse) fused via RRF.
    
    Returns list of {"text": str, "pages": [int, ...]} dicts.
    Backward-compatible: old stores with plain string chunks still work.
    """
    idx_path = _index_path(doc_id)
    if not os.path.exists(idx_path):
        raise FileNotFoundError(f"No vector store found for document {doc_id}")

    index = faiss.read_index(idx_path)

    with open(_chunks_path(doc_id), "rb") as f:
        chunks = pickle.load(f)

    # Backward compat: old stores have list[str], new ones have list[dict]
    if chunks and isinstance(chunks[0], str):
        chunks = [{"text": c, "pages": []} for c in chunks]

    n_chunks = len(chunks)
    fetch_k = min(top_k * 3, n_chunks)

    texts = [c["text"] for c in chunks]

    # --- Dense retrieval (FAISS L2) ---
    query_embedding = get_embeddings([query])
    query_vector = np.array(query_embedding, dtype="float32")
    _, dense_indices = index.search(query_vector, fetch_k)
    dense_ranking = [int(i) for i in dense_indices[0] if i != -1]

    # --- Sparse retrieval (BM25) ---
    bm25_file = _bm25_path(doc_id)
    if os.path.exists(bm25_file):
        with open(bm25_file, "rb") as f:
            bm25 = pickle.load(f)
        tokenized_query = _tokenize(query)
        bm25_scores = bm25.get_scores(tokenized_query)
        sparse_ranking = list(np.argsort(bm25_scores)[::-1][:fetch_k])
    else:
        sparse_ranking = dense_ranking

    # --- Reciprocal Rank Fusion ---
    fused = _rrf([dense_ranking, sparse_ranking])

    results = []
    for idx in fused[:top_k]:
        if 0 <= idx < n_chunks:
            results.append(chunks[idx])
    return results


def get_indexed_documents() -> list[dict]:
    """List all documents that have been indexed."""
    docs = []
    for f in os.listdir(VECTOR_STORE_DIR):
        if f.endswith("_meta.json"):
            with open(os.path.join(VECTOR_STORE_DIR, f)) as fp:
                docs.append(json.load(fp))
    return docs


def delete_vector_store(doc_id: str):
    """Delete all vector store files for a document."""
    for path in [_index_path(doc_id), _chunks_path(doc_id), _meta_path(doc_id), _bm25_path(doc_id)]:
        if os.path.exists(path):
            os.remove(path)
