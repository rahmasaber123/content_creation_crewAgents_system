# Kayfa Content Marketing Crew

3-agent CrewAI pipeline (Strategist-Researcher, Writer-Editor, Publisher) with MongoDB Atlas-persisted memory + knowledge, FastAPI backend, human-in-the-loop approval, and a vanilla HTML/JS chat UI.
![image](https://github.com/user-attachments/assets/your-image-id)

## Setup

```bash
cp .env.example .env       # fill in your keys + MONGODB_URI
pip install -r requirements.txt
python -m kayfa_content_crew.seed_knowledge   # embeds knowledge/*.md into MongoDB, run once
```

## Run

```bash
PYTHONPATH=src uvicorn api.main:app --reload
```

Open http://localhost:8000 for the chat UI.

## Or with Docker

```bash
docker compose up --build
```

## How it works

1. Type a topic in the chat UI, pick marketing blog or technical guide.
2. `/generate` runs Strategist-Researcher -> Writer-Editor, returns a draft.
3. You review it in the UI -- nothing publishes without your click.
4. Approve -> PDF generated, emailed (if `ENABLE_EMAIL_SEND=true`), and (for marketing content) Publisher creates social captions.
5. Reject -> nothing happens, draft is discarded.

## Persistence

- **Memory** (short/long-term/entity): `src/kayfa_content_crew/storage/mongo_storage.py` -- one MongoDB collection, filtered by scope, backed by Atlas Vector Search.
- **Knowledge** (brand voice, approved claims, technical style): `src/kayfa_content_crew/knowledge/mongo_knowledge_store.py` -- separate collection, re-seed after editing `knowledge/*.md`.

Both attempt automatic Atlas Vector Search index creation on first run; if your Atlas tier/role blocks that, the exact index JSON is logged so it can be pasted into Atlas UI > Search Indexes manually.
