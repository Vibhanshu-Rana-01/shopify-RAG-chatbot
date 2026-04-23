"""
shopify_client.py
─────────────────
Fetches product data from the public Shopify /products.json endpoint.
No API key or authentication required — works on any public Shopify store.
"""

import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv

load_dotenv()

SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL", "")


def fetch_shopify_products(store_url: str = None) -> list[dict]:
    """
    Fetch all published products from the Shopify public products.json endpoint.
    Handles pagination automatically.

    Args:
        store_url: The Shopify store URL (e.g. 'my-store.myshopify.com').
                   Falls back to SHOPIFY_STORE_URL env variable if not provided.

    Returns:
        List of raw Shopify product dicts.
    """
    url_base = store_url or SHOPIFY_STORE_URL
    if not url_base:
        raise ValueError("SHOPIFY_STORE_URL is not set in your .env file.")

    # Ensure no trailing slash
    url_base = url_base.rstrip("/")

    all_products = []
    page = 1
    limit = 250  # Shopify's max per page

    headers = {
        "User-Agent": "MobileCoversBot/1.0 (product-sync)",
        "Accept": "application/json",
    }

    while True:
        url = f"https://{url_base}/products.json?limit={limit}&page={page}"
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(
                f"Failed to fetch products from Shopify: {e}\n"
                f"Make sure your store URL is correct: {url_base}"
            )

        data = response.json()
        batch = data.get("products", [])

        if not batch:
            break  # No more products

        all_products.extend(batch)
        print(f"  [PAGE {page}] Fetched {len(batch)} products")

        if len(batch) < limit:
            break  # Last page

        page += 1

    return all_products


def strip_html(html_content: str) -> str:
    """Strip HTML tags and return clean plain text."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "lxml")
    # Replace <br> and <p> tags with newlines for readability
    for tag in soup.find_all(["br", "p", "li"]):
        tag.insert_before("\n")
    text = soup.get_text(separator=" ")
    # Clean up excessive whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines)


def format_product_for_indexing(product: dict) -> str:
    """
    Convert a raw Shopify product dict into clean, structured text
    ready for embedding and indexing in ChromaDB.

    Includes: title, type, tags, all variant prices, and cleaned description.
    """
    title = product.get("title", "Unknown Product")
    vendor = product.get("vendor", "")
    product_type = product.get("product_type", "")
    tags = product.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    tags_str = ", ".join(tags) if tags else "None"

    # --- Price / Variant Info ---
    variants = product.get("variants", [])
    price_lines = []
    for variant in variants:
        price = variant.get("price", "0")
        compare_at = variant.get("compare_at_price")
        variant_title = variant.get("title", "")

        price_str = f"₹{price}"
        if compare_at and float(compare_at) > float(price):
            discount_pct = round((1 - float(price) / float(compare_at)) * 100)
            price_str += f" (was ₹{compare_at}, {discount_pct}% off)"

        if variant_title and variant_title.lower() != "default title":
            price_lines.append(f"  - {variant_title}: {price_str}")
        else:
            price_lines.append(f"  - {price_str}")

    prices_text = "\n".join(price_lines) if price_lines else "  - Price not listed"

    # --- Description ---
    body_html = product.get("body_html", "")
    description = strip_html(body_html)
    # Limit description length to avoid oversized chunks
    if len(description) > 1200:
        description = description[:1200] + "..."

    # --- Compose the document ---
    doc = f"""Product Name: {title}
Category/Type: {product_type or "Mobile Cover"}
Brand: {vendor or "Our Brand"}
Tags & Keywords: {tags_str}
Pricing:
{prices_text}
Description & Features:
{description or "No description available."}
"""
    return doc.strip()


def get_product_metadata(product: dict, store_url: str = None) -> dict:
    """Extract key metadata fields for ChromaDB metadata storage."""
    store = (store_url or SHOPIFY_STORE_URL).rstrip("/")
    handle = product.get("handle", str(product.get("id", "")))

    first_variant = product.get("variants", [{}])[0]
    price = first_variant.get("price", "0")
    compare_at = first_variant.get("compare_at_price") or price

    return {
        "title": product.get("title", "Unknown"),
        "handle": handle,
        "price": str(price),
        "compare_at_price": str(compare_at),
        "product_type": product.get("product_type", ""),
        "vendor": product.get("vendor", ""),
        "url": f"https://{store}/products/{handle}",
    }
