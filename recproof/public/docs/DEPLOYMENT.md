# Deployment

## Local demo

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Production demo

Deploy to Vercel or any Next.js host. The app is a static enterprise demo shell and does not require backend services for the Rudy walkthrough.

## Production engine

The Python RecruitProof engine remains local-first. The dashboard should call generated JSON artifacts from `search.py`, `precompute.py`, benchmark outputs, and proof reports when wired to a real Encore export.
