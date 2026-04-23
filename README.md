# 📱 Mobile Covers Chatbot — RAG-Powered Shopping Assistant

A fully functional RAG (Retrieval-Augmented Generation) chatbot for your Shopify mobile covers store. Powered by **Google Gemini 1.5 Flash** (free), **ChromaDB**, and **FastAPI**.

---

## 🗂️ Project Structure

```
mobile-covers-chatbot/
├── backend/
│   ├── main.py            ← FastAPI server (run this)
│   ├── rag.py             ← RAG pipeline (retrieve + generate)
│   ├── ingest.py          ← Sync products from Shopify → ChromaDB
│   ├── shopify_client.py  ← Shopify public API helper
│   ├── requirements.txt   ← Python dependencies
│   ├── .env               ← Your secrets (create from .env.example)
│   ├── .env.example       ← Template
│   ├── chroma_db/         ← Auto-created vector database
│   └── data/
│       └── faq.json       ← Store FAQs (edit with your policies)
└── frontend/
    └── chatbot-widget.js  ← Paste this into your Shopify theme
```

---

## ⚡ Quick Setup (Local)

### Step 1 — Clone / open the project

```bash
cd mobile-covers-chatbot/backend
```

### Step 2 — Set up Python virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Create your `.env` file

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # Mac/Linux
```

Open `.env` and fill in:

```env
GEMINI_API_KEY=AIza...your_key_here
SHOPIFY_STORE_URL=your-store.myshopify.com
STORE_NAME=Your Store Name
ALLOWED_ORIGINS=*
SYNC_INTERVAL_HOURS=6
```

### Step 5 — Edit FAQ (optional but recommended)

Open `data/faq.json` and update the answers to match your actual:
- Shipping timeframes
- Return/refund policy
- Payment methods
- Contact details

### Step 6 — Start the server

```bash
uvicorn main:app --reload --port 8000
```

The server will:
1. Automatically fetch all your Shopify products on startup
2. Embed them into ChromaDB
3. Be ready to answer questions!

Visit **http://localhost:8000** → you should see `{"status": "ok"}`

### Step 7 — Test the chatbot

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What covers do you have?", "history": []}'
```

---

## 🛍️ Add the Widget to Shopify

### Option A — Theme Editor (Easiest)

1. In Shopify Admin → **Online Store** → **Themes** → **Customize**
2. Click the **bottom section** → **Add section** → **Custom HTML**
3. Paste the content of `frontend/chatbot-widget.js` inside `<script>` tags:
   ```html
   <script>
     <!-- paste chatbot-widget.js contents here -->
   </script>
   ```
4. Click **Save**

### Option B — Theme Code (Recommended)

1. Shopify Admin → **Online Store** → **Themes** → **⋯** → **Edit code**
2. Open `layout/theme.liquid`
3. Just before `</body>`, add:
   ```html
   <script src="{{ 'chatbot-widget.js' | asset_url }}"></script>
   ```
4. Upload `chatbot-widget.js` to **Assets** folder
5. **Important:** Edit the `apiUrl` in the widget file to point to your deployed backend URL

---

## 🔄 Auto-Sync

Products are automatically re-synced from Shopify every **6 hours** (configurable via `SYNC_INTERVAL_HOURS` in `.env`).

**Manual sync** (when you update products immediately):
```bash
curl -X POST http://localhost:8000/sync
```

**Check sync status:**
```bash
curl http://localhost:8000/status
```

---

## 🚀 Deploy to Render.com (Free)

1. Push your `backend/` folder to a GitHub repository
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Set **Build Command**: `pip install -r requirements.txt`
5. Set **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add **Environment Variables** (same as your `.env` file)
7. Click **Deploy**
8. Copy the Render URL (e.g. `https://mcb-xxx.onrender.com`)
9. Update `apiUrl` in `chatbot-widget.js` to this URL

---

## 💬 What the Chatbot Can Answer

| Query Type | Example |
|---|---|
| Product search | "Do you have a cover for Samsung S24?" |
| Pricing | "What's the price of your iPhone 15 case?" |
| Features | "What features does your rugged case have?" |
| Discounts | "Are any covers on sale?" |
| Compatibility | "Which covers fit OnePlus 12?" |
| Shipping | "How long does delivery take?" |
| Returns | "What is your return policy?" |
| Payment | "Do you accept UPI?" |
| General | "What materials are your covers made of?" |

---

## 🔧 Customization

### Change chatbot colors / branding
Edit `CHATBOT_CONFIG` at the top of `chatbot-widget.js`:
```js
primaryColor:  "#7C3AED",   // your brand color
gradientEnd:   "#EC4899",   // gradient accent
storeName:     "Your Store",
botAvatar:     "🛍️",
```

### Change quick-question chips
```js
quickQuestions: [
  "Covers for iPhone 15?",
  "Do you have COD?",
  // ...
]
```

### Adjust auto-sync frequency
In `.env`:
```env
SYNC_INTERVAL_HOURS=3   # sync every 3 hours instead of 6
```

---

## 📋 Environment Variables Reference

| Variable | Description | Example |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API key | `AIzaSy...` |
| `SHOPIFY_STORE_URL` | Your store's myshopify.com URL | `my-store.myshopify.com` |
| `STORE_NAME` | Display name in chatbot responses | `My Mobile Covers Store` |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `https://my-store.myshopify.com` |
| `SYNC_INTERVAL_HOURS` | Auto-sync frequency | `6` |
| `PORT` | Server port (Render sets this automatically) | `8000` |

---

## 🐛 Troubleshooting

**"No products returned from Shopify"**
- Double-check `SHOPIFY_STORE_URL` — should be `your-store.myshopify.com` (no `https://`)
- Make sure products are published (not draft)

**"GEMINI_API_KEY is not set"**
- Make sure you created `.env` from `.env.example` and filled in the key

**Widget not showing on Shopify**
- Check browser console for errors
- Make sure `apiUrl` in the widget points to the correct backend URL
- If deployed on Render, make sure `ALLOWED_ORIGINS` includes your Shopify domain

**Chatbot gives wrong answers**
- Run `/sync` to refresh the product catalog
- Check that your product descriptions in Shopify are detailed enough
