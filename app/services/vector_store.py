import os
import json
from typing import List, Tuple, Optional, Dict
import numpy as np
import faiss
import logging
from sqlalchemy.orm import Session
from app.models.product import Product

log = logging.getLogger("vector_store")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
INDEX_DIR = os.path.join(BASE_DIR, "data", "faiss")
INDEX_FILE = os.path.join(INDEX_DIR, "products.index")
META_FILE = os.path.join(INDEX_DIR, "products_meta.json")

# Simple in-memory cache to avoid repeated embedding calls for identical text
_EMBED_CACHE: Dict[str, np.ndarray] = {}


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def _get_embedding(text: str) -> np.ndarray:
    api_key = os.getenv("OPENAI_API_KEY")
    key = text.strip().lower()
    # 命中缓存直接返回
    cached = _EMBED_CACHE.get(key)
    if cached is not None:
        return cached

    # 强制要求使用 OpenAI 嵌入，不再提供本地哈希备用方案
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured; embeddings require OpenAI API")

    import openai
    client = openai.OpenAI(api_key=api_key, max_retries=0)
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    vec = np.array(resp.data[0].embedding, dtype=np.float32)
    _EMBED_CACHE[key] = vec
    return vec


def build_index(db: Session) -> Tuple[faiss.IndexFlatIP, List[int]]:
    os.makedirs(INDEX_DIR, exist_ok=True)
    products = db.query(Product).all()
    ids: List[int] = []
    vecs: List[np.ndarray] = []

    for p in products:
        text = (p.description or "") + " " + (p.name or "")
        emb = _get_embedding(text)
        if emb is None:
            continue
        vecs.append(_normalize(emb.astype(np.float32)))
        ids.append(p.id)

    if not vecs:
        raise RuntimeError("No embeddings generated for products")

    mat = np.vstack(vecs)
    d = mat.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(mat)

    faiss.write_index(index, INDEX_FILE)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"ids": ids, "dim": d}, f, ensure_ascii=False)

    log.info(f"Faiss index built: {len(ids)} items, dim={d}")
    return index, ids


def load_index() -> Tuple[Optional[faiss.IndexFlatIP], Optional[List[int]]]:
    if not (os.path.exists(INDEX_FILE) and os.path.exists(META_FILE)):
        return None, None
    try:
        index = faiss.read_index(INDEX_FILE)
        with open(META_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return index, meta.get("ids", [])
    except Exception as e:
        log.exception("Failed to load Faiss index")
        return None, None


def query(db: Session, query_text: str, top_k: int = 5) -> List[Product]:
    # 尝试加载索引，不存在则构建
    index, ids = load_index()
    if index is None or not ids:
        index, ids = build_index(db)

    q = _get_embedding(query_text)
    qn = _normalize(q.astype(np.float32))
    D, I = index.search(np.expand_dims(qn, axis=0), top_k)

    hit_ids = [ids[i] for i in I[0] if i >= 0 and i < len(ids)]
    if not hit_ids:
        return []
    rows = db.query(Product).filter(Product.id.in_(hit_ids)).all()
    # 保留检索顺序
    id_to_row = {r.id: r for r in rows}
    return [id_to_row[i] for i in hit_ids if i in id_to_row]


def query_with_scores(db: Session, query_text: str, top_k: int = 5) -> List[Tuple[Product, float]]:
    """Return products with similarity scores (inner product on normalized vectors).
    The score roughly corresponds to cosine similarity in [0, 1] when vectors are non-negative.
    """
    index, ids = load_index()
    if index is None or not ids:
        index, ids = build_index(db)

    q = _get_embedding(query_text)
    qn = _normalize(q.astype(np.float32))
    D, I = index.search(np.expand_dims(qn, axis=0), top_k)

    hit = []
    if ids:
        rows = db.query(Product).filter(Product.id.in_(ids)).all()
        id_to_row = {r.id: r for r in rows}
        for pos, idx in enumerate(I[0]):
            if idx >= 0 and idx < len(ids):
                pid = ids[idx]
                prod = id_to_row.get(pid)
                if prod is not None:
                    hit.append((prod, float(D[0][pos])))
    return hit