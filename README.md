# EnlargeImage

Web app that upscales low-resolution images to higher resolution using SwinIR.

- **Design spec:** `docs/superpowers/specs/2026-06-05-image-enlarge-4k-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-06-05-image-enlarge-4k.md`

## Quick start

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
pnpm install
pnpm dev
```
