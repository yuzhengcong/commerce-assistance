import os
import json
from typing import List, Tuple, Optional
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


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def _get_embedding(text: str) -> Optional[np.ndarray]:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return np.array(resp.data[0].embedding, dtype=np.float32)
        except Exception as e:
            log.exception("Embedding API failed; falling back to local hash embedding")

    # 本地回退：基于分词的哈希向量（稳定、快速）
    dim = 384
    vec = np.zeros(dim, dtype=np.float32)
    for tok in text.lower().split():
        idx = (hash(tok) % dim)
        vec[idx] += 1.0
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