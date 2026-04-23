"""
rag.py
──────
Core RAG (Retrieval-Augmented Generation) pipeline.

Flow:
  1. Embed the user's query using Gemini text-embedding-004
  2. Search ChromaDB for the most relevant products + FAQ items
  3. Build a grounded prompt combining user question + retrieved context
  4. Generate a response with Gemini 1.5 Flash
  5. Return the response text
"""

import os
import requests
import chromadb
from embeddings import AppEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
SHOPIFY_STORE_URL  = os.getenv("SHOPIFY_STORE_URL", "")
STORE_NAME         = os.getenv("STORE_NAME", "our mobile covers store")
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
GROQ_API_BASE      = "https://api.groq.com/openai/v1"
GROQ_MODEL         = "llama-3.3-70b-versatile"


def get_doc_embedding_function() -> AppEmbeddingFunction:
    """For indexing documents."""
    return AppEmbeddingFunction()

def get_query_embedding_function() -> AppEmbeddingFunction:
    """For querying."""
    return AppEmbeddingFunction()


# ─────────────────────────────────────────────────────────────
# Retrieval
# ─────────────────────────────────────────────────────────────

def retrieve_context(query: str, n_products: int = 4, n_faq: int = 2) -> dict:
    """
    Query ChromaDB for relevant product docs and FAQ items.

    Returns:
        {
          "products": [{"content": ..., "title": ..., "url": ..., "price": ...}],
          "faq":      ["Question: ...\nAnswer: ...", ...]
        }
    """
    client   = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    embed_fn = get_query_embedding_function()

    product_results = []
    faq_results     = []

    # --- Products ---
    try:
        products_col = client.get_collection("products", embedding_function=embed_fn)
        count = products_col.count()
        if count > 0:
            result = products_col.query(
                query_texts=[query],
                n_results=min(n_products, count),
                include=["documents", "metadatas", "distances"],
            )
            docs      = result.get("documents", [[]])[0]
            metas     = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]

            for doc, meta, dist in zip(docs, metas, distances):
                # Only include results with good similarity (cosine distance < 0.8)
                if dist < 0.8:
                    product_results.append({
                        "content": doc,
                        "title":   meta.get("title", ""),
                        "url":     meta.get("url", ""),
                        "price":   meta.get("price", ""),
                    })
    except Exception as e:
        print(f"[RAG] Products retrieval error: {e}")

    # --- FAQ ---
    try:
        faq_col = client.get_collection("faq", embedding_function=embed_fn)
        count = faq_col.count()
        if count > 0:
            result = faq_col.query(
                query_texts=[query],
                n_results=min(n_faq, count),
                include=["documents", "distances"],
            )
            docs      = result.get("documents", [[]])[0]
            distances = result.get("distances", [[]])[0]

            for doc, dist in zip(docs, distances):
                if dist < 0.6:  # FAQ needs tighter match
                    faq_results.append(doc)
    except Exception as e:
        print(f"[RAG] FAQ retrieval error: {e}")

    return {"products": product_results, "faq": faq_results}


# ─────────────────────────────────────────────────────────────
# Generation
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are a friendly, knowledgeable shopping assistant for {store_name} — an online store specializing in premium mobile phone covers.

Your personality:
- Warm, enthusiastic, and genuinely helpful (like a friendly store associate)
- Concise but thorough — give enough detail to help, not a wall of text
- Honest — never make up products, prices, or policies

YOUR RULES (follow strictly):
1. Only use facts from the CONTEXT provided below. Do NOT invent products, prices, features, or policies.
2. If the answer isn't in the context, say: "I don't have that information right now. You can reach our support team for more help!"
3. When recommending a product, always mention its price and a relevant feature or two.
4. Keep formatting chat-friendly: use short bullet points (•) for lists, avoid markdown headers.
5. If the user asks for a specific phone model, look for compatible covers in the CONTEXT and recommend them.
6. You may include a product link if it's available in the metadata.
7. Reply in the same language the customer uses.
8. Keep responses under 200 words unless a detailed answer is truly needed.

---
CONTEXT FROM STORE:
{context}
---
"""


def build_context_string(retrieved: dict) -> str:
    """Format retrieved documents into a clean context block for the prompt."""
    parts = []

    if retrieved["products"]:
        parts.append("[ PRODUCTS ]")
        for i, p in enumerate(retrieved["products"], 1):
            parts.append(f"\n--- Product {i} ---")
            parts.append(p["content"])
            if p.get("url"):
                parts.append(f"Link: {p['url']}")

    if retrieved["faq"]:
        parts.append("\n[ STORE POLICIES & FAQ ]")
        for item in retrieved["faq"]:
            parts.append(item)

    if not parts:
        return "No relevant products or FAQ found for this query."

    return "\n".join(parts)


def _call_groq(system_prompt: str, contents: list[dict]) -> str:
    """
    Call Groq chat completions API (OpenAI-compatible).
    """
    messages = [{"role": "system", "content": system_prompt}]
    for msg in contents:
        role = "assistant" if msg["role"] == "model" else msg["role"]
        messages.append({"role": role, "content": msg["parts"][0]["text"]})

    for attempt in range(3):
        resp = requests.post(
            f"{GROQ_API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={"model": GROQ_MODEL, "messages": messages, "temperature": 0.3, "max_tokens": 1024},
            timeout=30,
        )
        if resp.status_code in (429, 503):
            import time
            wait = 10 * (attempt + 1)
            print(f"[GROQ] Rate limited, waiting {wait}s (attempt {attempt+1}/3)...")
            time.sleep(wait)
            continue
        if not resp.ok:
            raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:300]}")
        return resp.json()["choices"][0]["message"]["content"].strip()

    raise RuntimeError("Groq API unavailable after 3 retries.")



def generate_response(user_message: str, chat_history: list[dict]) -> str:
    """
    Full RAG pipeline: retrieve -> build prompt -> generate -> return text.
    Uses Gemini v1 REST API directly (bypasses google-generativeai SDK v1beta).
    """
    if not GROQ_API_KEY:
        return "Chatbot is not configured yet. Please set your GROQ_API_KEY."

    # Step 1: Retrieve relevant context
    retrieved = retrieve_context(user_message)
    context   = build_context_string(retrieved)

    # Step 2: Build system prompt
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        store_name=STORE_NAME,
        context=context,
    )

    # Step 3: Build conversation contents (last 10 messages + current)
    contents = []
    for msg in chat_history[-10:]:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({
            "role":  role,
            "parts": [{"text": msg["content"]}],
        })
    # Add current user message
    contents.append({
        "role":  "user",
        "parts": [{"text": user_message}],
    })

    # Step 4: Call Groq API
    return _call_groq(system_prompt, contents)
