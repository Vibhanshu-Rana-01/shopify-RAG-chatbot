"""
ingest.py
─────────
Fetches products from Shopify and FAQ data from faq.json,
then indexes them into ChromaDB using Gemini embeddings.

Run this script once to populate the vector database.
It is also called automatically by the scheduler in main.py.
"""

import os
import json
import chromadb
from dotenv import load_dotenv
from embeddings import AppEmbeddingFunction
from shopify_client import fetch_shopify_products, format_product_for_indexing, get_product_metadata

load_dotenv()

GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
SHOPIFY_STORE_URL  = os.getenv("SHOPIFY_STORE_URL", "")
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
FAQ_PATH           = os.path.join(os.path.dirname(__file__), "data", "faq.json")


def get_embedding_function() -> AppEmbeddingFunction:
    return AppEmbeddingFunction()


def get_chroma_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)


# ─────────────────────────────────────────────────────────────
# Products
# ─────────────────────────────────────────────────────────────

def ingest_products() -> int:
    """
    Pull all products from the public Shopify endpoint, embed them,
    and upsert into the 'products' ChromaDB collection.
    Returns the number of products indexed.
    """
    print(f"\n[SYNC] Fetching products from Shopify ({SHOPIFY_STORE_URL})...")
    raw_products = fetch_shopify_products(SHOPIFY_STORE_URL)

    if not raw_products:
        print("[WARN] No products returned from Shopify. Check your store URL.")
        return 0

    print(f"[OK] Fetched {len(raw_products)} products. Indexing into ChromaDB...")

    client     = get_chroma_client()
    embed_fn   = get_embedding_function()

    # Always do a full fresh sync
    try:
        client.delete_collection("products")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name="products",
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    documents  = []
    ids        = []
    metadatas  = []

    for product in raw_products:
        doc_text = format_product_for_indexing(product)
        prod_id  = str(product["id"])
        meta     = get_product_metadata(product, SHOPIFY_STORE_URL)

        documents.append(doc_text)
        ids.append(prod_id)
        metadatas.append(meta)

    # Upsert in batches of 50 to avoid rate limits
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        collection.add(
            documents=documents[i : i + batch_size],
            ids=ids[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )
        print(f"  [OK] Indexed batch {i // batch_size + 1} ({min(i + batch_size, len(documents))}/{len(documents)} products)")

    print(f"[DONE] Products indexed: {len(documents)}")
    return len(documents)


# ─────────────────────────────────────────────────────────────
# FAQ
# ─────────────────────────────────────────────────────────────

def ingest_faq() -> int:
    """
    Read FAQ from data/faq.json, embed each Q&A pair,
    and upsert into the 'faq' ChromaDB collection.
    Returns the number of FAQ items indexed.
    """
    if not os.path.exists(FAQ_PATH):
        print(f"[WARN] FAQ file not found at {FAQ_PATH}. Skipping FAQ ingestion.")
        return 0

    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        faq_items = json.load(f)

    if not faq_items:
        print("[WARN] FAQ file is empty. Skipping.")
        return 0

    print(f"[FAQ] Indexing {len(faq_items)} FAQ items...")

    client   = get_chroma_client()
    embed_fn = get_embedding_function()

    try:
        client.delete_collection("faq")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name="faq",
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    documents = []
    ids       = []

    for idx, item in enumerate(faq_items):
        question = item.get("question", "")
        answer   = item.get("answer", "")
        if not question or not answer:
            continue
        # Store both Q and A so retrieval matches on question phrasing
        doc_text = f"Question: {question}\nAnswer: {answer}"
        documents.append(doc_text)
        ids.append(f"faq_{idx}")

    collection.add(documents=documents, ids=ids)
    print(f"[DONE] FAQ items indexed: {len(documents)}")
    return len(documents)


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

def run_full_sync() -> dict:
    """Run a full sync of products + FAQ. Called by scheduler and /sync endpoint."""
    n_products = ingest_products()
    n_faq      = ingest_faq()
    return {"products": n_products, "faq": n_faq}


if __name__ == "__main__":
    print("=" * 50)
    print("  Mobile Covers Chatbot - Data Ingestion")
    print("=" * 50)
    result = run_full_sync()
    print("\n" + "=" * 50)
    print(f"[OK] Sync complete!")
    print(f"   Products indexed : {result['products']}")
    print(f"   FAQ items indexed: {result['faq']}")
    print(f"   ChromaDB saved to: {CHROMA_PERSIST_DIR}")
    print("=" * 50)
    print("\nKnowledge base ready. Start the server with: uvicorn main:app --reload")
