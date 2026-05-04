# LUNA

LUNA is a public-facing companion app with:

- a React + Vite frontend at the repo root
- a FastAPI backend in `InnerVoice_Jelly`

## Local Run

**One command (API + Vite together):**

```powershell
npm.cmd install
python -m pip install -r .\InnerVoice_Jelly\requirements.txt
npm.cmd run dev
```

Or double‑click **`run-luna-local.cmd`** in the repo root (runs `npm install` then **`npm.cmd run dev`**).

- Web: `http://127.0.0.1:5173` — dev mode proxies `/luna-backend` → API on **`http://127.0.0.1:8000`**.

**Separate terminals (optional):**

```powershell
npm.cmd run dev:vite
```

```powershell
cd .\InnerVoice_Jelly
python -m uvicorn backend:app --reload --host 127.0.0.1 --port 8000
```

## Public Deployment

This repo now includes a root `Dockerfile` that:

- builds the Vite frontend
- packages it into the Python container
- serves both the UI and API from one public URL

The backend also exposes `GET /health` for hosting checks.

## Persistent Diary Storage

Diary entries can now persist in Azure Blob Storage per user account when these backend env vars are set:

```env
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_STORAGE_CONTAINER=luna-data
```

If those vars are missing, the backend falls back to local files.

## Explainable AI And Non-Judgmental Validation

LUNA is explainable at the application level. Each chat response is tagged on the backend with:

- detected mood and whether it came from text or voice tone
- response path, such as casual friend, deep companion, spiritual knowledge, or critical distress
- whether wisdom-source context was used
- a non-judgmental language audit

LUNA is intentionally not framed as a therapist. The generation prompt asks for a friendly, jolly, close-friend tone first, then emotional understanding, then a small wisdom touch only when it suits the user's context. For emotional/opinion/relationship/confusion messages, the backend retrieves one relevant thread from the Ancient Indian Wisdom dataset or curated wisdom sources and asks Luna to translate it into normal friend-like language, often as a tiny example rather than a lecture.

The non-judgmental claim is validated with an automated response audit before the reply is returned. The audit penalizes blame, shame, invalidation, moral scoring, and harsh command patterns, and rewards emotionally safe validation markers. If a generated reply fails the audit, the backend runs a repair pass that rewrites the response to remove judgmental phrasing while preserving warmth and meaning.

For demonstration/review:

- `GET /xai/nonjudgmental-rubric` shows the scoring rubric.
- `POST /xai/audit-reply` with `{ "reply": "..." }` returns the non-judgmental audit for any sample reply.

Reviewer answer:

> We do not claim the model is inherently non-judgmental just because it is an AI. We validate LUNA's final response with a rule-based XAI audit. For every reply, the system records the detected mood, response route, whether external wisdom context was used, and a non-judgmental score. The score checks for blame/shame/invalidating language such as "your fault", "stop overreacting", harsh "you should" commands, or moral labels. If those appear, the reply is repaired before the user sees it. This gives us a measurable and explainable basis for saying LUNA is designed and validated to respond without judgment.

## Azure

For an Azure student subscription, the cleanest setup is:

- Azure Container Apps for the public app
- Azure Storage Account (Blob Storage) for diary persistence

Detailed steps are in [AZURE_DEPLOY.md](/c:/Users/sandh/luna-ui/AZURE_DEPLOY.md).
