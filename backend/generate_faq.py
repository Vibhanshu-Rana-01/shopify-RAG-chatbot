"""
generate_faq.py
───────────────
Scrapes policy pages from the Shopify store and uses Groq to generate
100 FAQ questions and answers. Saves output to data/faq.json.

Run once when setting up for a new store:
    python generate_faq.py
"""

import os
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL", "").rstrip("/")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
GROQ_API_BASE     = "https://api.groq.com/openai/v1"
GROQ_MODEL        = "llama-3.3-70b-versatile"
FAQ_PATH          = os.path.join(os.path.dirname(__file__), "data", "faq.json")

POLICY_PAGES = [
    "/policies/refund-policy",
    "/policies/shipping-policy",
    "/policies/privacy-policy",
    "/policies/terms-of-service",
]


KNOWN_SUMMARIZER_MODELS = ["phi3:mini", "mistral", "llama3.2:3b", "llama3"]
OLLAMA_BASE            = "http://localhost:11434"
FALLBACK_TRIM          = 6000


def get_local_model() -> str | None:
    """Return the name of an installed Ollama model, or None if none found."""
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        if not resp.ok:
            return None
        installed = [m["name"] for m in resp.json().get("models", [])]
        for model in KNOWN_SUMMARIZER_MODELS:
            if any(model in name for name in installed):
                print(f"  [LOCAL MODEL] Found: {model}")
                return model
    except requests.ConnectionError as e:
        print(f"  [WARN] Could not connect to Ollama.")
    return None


def prompt_install_model() -> str | None:
    """Ask user if they want to install Phi-3 Mini. Returns model name or None."""
    print("\nNo local summarization model found.")
    choice = input("Install Phi-3 Mini for local summarization? (2.3GB) [Y/N]: ").strip().upper()
    if choice == "Y":
        import subprocess
        print("[DOWNLOAD] Installing phi3:mini via Ollama...")
        subprocess.run(["ollama", "pull", "phi3:mini"], check=True)
        return "phi3:mini"
    print("[SKIP] Using Groq directly with text trimming.")
    return None


def summarize_with_ollama(text: str, model: str) -> str:
    """Summarize text using a local Ollama model."""
    resp = requests.post(
        f"{OLLAMA_BASE}/api/generate",
        json={
            "model": model,
            "prompt": f"Summarize the following store policy text, keeping all important details about shipping, returns, payments, warranties and contact info:\n\n{text}",
            "stream": False,
        },
        timeout=120,
    )
    if not resp.ok:
        raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text[:200]}")
    return resp.json()["response"].strip()


def scrape_page(url: str, local_model: str | None) -> str:
    """Fetch, clean and return text from a URL. Summarizes locally if model available."""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "FAQBot/1.0"})
        if resp.status_code != 200:
            print(f"  [SKIP] {url} returned {resp.status_code}")
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup.find_all(["nav", "header", "footer", "script", "style"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        if local_model:
            print(f"  [SUMMARIZE] Summarizing with {local_model}...")
            return summarize_with_ollama(text, local_model)
        return text[:FALLBACK_TRIM]
    except Exception as e:
        print(f"  [ERROR] Could not scrape {url}: {e}")
        return ""


def scrape_all_policies(local_model: str | None) -> str:
    """Scrape all policy pages and return combined text."""
    combined = []
    for path in POLICY_PAGES:
        url = f"https://{SHOPIFY_STORE_URL}{path}"
        print(f"  [SCRAPE] {url}")
        text = scrape_page(url, local_model)
        if text:
            combined.append(f"--- {path} ---\n{text}")
    return "\n\n".join(combined)


def generate_faq_with_groq(policy_text: str) -> list[dict]:
    """Send policy text to Groq and get back 5 FAQ items."""
    prompt = f"""You are helping build a FAQ for an online mobile phone covers store.

Based on the store policy text below, generate exactly 5 frequently asked questions and answers.
Cover topics like: shipping, returns, refunds, payments, COD, warranty, order tracking, cancellations, product care, bulk orders, and anything else relevant.

Return ONLY a valid JSON array with exactly this format, no extra text:
[
  {{"question": "...", "answer": "..."}},
  ...
]

STORE POLICY TEXT:
{policy_text}
"""

    resp = requests.post(
        f"{GROQ_API_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 8000,
        },
        timeout=60,
    )

    if not resp.ok:
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:300]}")

    content = resp.json()["choices"][0]["message"]["content"].strip()

    print(content)

    # Extract JSON array from response
    start = content.find("[")
    print(start)
    end   = content.rfind("]") + 1
    print(end)
    if start == -1 or end == 0:
        raise ValueError("Groq did not return a valid JSON array.")

    return json.loads(content[start:end])


def save_faq(faq_items: list[dict]):
    """Save FAQ items to data/faq.json."""
    os.makedirs(os.path.dirname(FAQ_PATH), exist_ok=True)
    with open(FAQ_PATH, "w", encoding="utf-8") as f:
        json.dump(faq_items, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] {len(faq_items)} FAQ items written to {FAQ_PATH}")


if __name__ == "__main__":
    print("=" * 50)
    print("  FAQ Generator")
    print("=" * 50)

    if not SHOPIFY_STORE_URL:
        raise ValueError("SHOPIFY_STORE_URL is not set in your .env file.")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in your .env file.")

    print(f"\n[STEP 1] Checking for local summarization model...")
    local_model = get_local_model()
    if local_model is None:
        local_model = prompt_install_model()

    print(f"\n[STEP 2] Scraping policy pages from {SHOPIFY_STORE_URL}...")
    policy_text = scrape_all_policies(local_model)

    if not policy_text:
        print("[WARN] No policy text scraped. Groq will generate generic FAQs.")

    print("\n[STEP 3] Generating 5 FAQs with Groq...")
    faq_items = generate_faq_with_groq(policy_text)

    print(f"\n[STEP 4] Saving to {FAQ_PATH}...")
    save_faq(faq_items)

    print("\n[DONE] FAQ generation complete!")
    print("Run the server or /sync to re-index the new FAQs into ChromaDB.")
