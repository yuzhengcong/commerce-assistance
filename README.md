# Commerce AI Agent (Rufus‑like)

An AI‑powered shopping assistant that supports general conversation, text recommendations, and image‑based product search over a predefined catalog.

## Stack & Rationale
- Backend: `FastAPI` for simple, typed APIs and async IO.
- Runtime: `Uvicorn` for high‑performance ASGI serving.
- Vector search: `FAISS` CPU with a small SQLite catalog for demo data.
- Model client: `openai` SDK; prompts designed for concise, user‑friendly answers.
- Frontend: Minimal HTML (`demo.html`) for quick UX validation.
- Packaging: `Docker` for reproducible deploys; `docker-compose` for local and VM deploy.

## Key Endpoints
- `GET /health` – service health.
- `POST /api/chat` – general chat with tool‑assisted product recommendations.
- `POST /api/products/image-search` – upload image; returns summary + matches (frontend shows summary only).
- `GET /demo.html` – simple frontend to try the agent.

## Quick Start (Local)
1) Copy `.env.example` to `.env` and fill `OPENAI_API_KEY`, `SECRET_KEY`.
2) Run dev server:
   - `uv run uvicorn app.main:app --reload --port 8000`
3) Open `http://localhost:8000/demo.html` and chat or try image search.

## Docker Run (Local/VM)
Build and run:
```
docker build -t commerce-ai-backend:latest .
docker run --env-file .env -p 8000:8000 \
  -v $(pwd)/commerce.db:/app/commerce.db \
  -v $(pwd)/data:/app/data \
  commerce-ai-backend:latest
```
Open `http://<host>:8000/demo.html`.

## Compose (Recommended)
```
OPENAI_API_KEY=sk-...                # required
DATABASE_URL=sqlite:///./commerce.db # default ok
SECRET_KEY=replace_me                # required
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

docker compose up -d --build
```

## Deployment Options
- VM (EC2/DigitalOcean): use the Compose setup above; add a reverse proxy (Nginx/Caddy) if you want TLS. Point DNS to the VM and terminate HTTPS at the proxy.
- PaaS (Render/Fly.io): deploy the Docker image directly; set env vars from `.env`. Expose port `8000`. Persist `commerce.db`/`data` via volumes.
- Cloud Run: push the image to a registry, deploy with `--port 8000` and env vars; use a Cloud Storage bucket if you prefer externalizing `data/`.

## Notes & Limits
- Catalog is demo‑sized; FAISS index is under `data/faiss`. For production, migrate catalog to a managed DB and host vectors in a scalable store.
- Image search currently extracts a short query via a vision prompt and filters matches by similarity; frontend shows only the summary sentence.
- Security: Do not bake `.env` into images; pass secrets via environment. Add HTTPS via a proxy or platform TLS.

## Development
- Code lives under `app/`; adjust prompts or tools in `app/services/agent_service.py`.
- Seed data in `data/products_seed.json`; rebuild index via service utilities if added.

## License
Demo use only.