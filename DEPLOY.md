# Deployment guide

## TL;DR

For a portfolio demo, **deploy the Next.js frontend to Vercel** and keep the
backend local. Recruiters watch the recorded demo video; if they want to
explore, they clone the repo and run it themselves. Zero monthly cost.

For a paying-customer deployment, host the full Docker Compose stack on a
single VM with a GPU and a reverse proxy in front. The architecture is
designed to run that way out of the box.

---

## Option A — Vercel for frontend only (recommended for portfolio)

The frontend is configured to read its API URL from `NEXT_PUBLIC_API_BASE`.
Set it to your tunneled local backend (via ngrok / cloudflared) or to a static
landing page that explains the demo is local-only.

### One-time setup

1. **Install Vercel CLI**
   ```bash
   npm i -g vercel
   ```
2. **Link the project**
   ```bash
   cd web
   vercel login          # follow browser prompt
   vercel link           # creates .vercel/project.json
   ```
3. **Set the API base env var**
   ```bash
   vercel env add NEXT_PUBLIC_API_BASE
   # paste e.g. https://yourname.ngrok.app
   # choose: Production
   ```
4. **Deploy production**
   ```bash
   vercel deploy --prod
   ```
   Vercel returns a `https://lastenheft.vercel.app`-style URL.
5. **(Optional) Custom domain.** Vercel → Project → Settings → Domains.

### When you give a live demo

1. Start backend locally: `uvicorn api.main:app --port 8000`
2. Expose it via tunnel: `ngrok http 8000` → copy the https URL
3. Update Vercel env: `vercel env rm NEXT_PUBLIC_API_BASE production && vercel env add NEXT_PUBLIC_API_BASE` with the new ngrok URL
4. Redeploy: `vercel deploy --prod`

That's the cheapest way to have a stable public URL pointing at your local GPU.

---

## Option B — Full self-hosted stack on a GPU VM

For when you need 24/7 uptime (real users, not portfolio).

### Sizing

- **vCPU:** 4+
- **RAM:** 16 GB
- **GPU:** ≥ 6 GB VRAM (RTX 3060 Laptop = bare minimum; A10 / L4 / 4070 = comfortable)
- **Disk:** 50 GB (models + corpus + Postgres data)

### Providers

| Provider | GPU | Approx. cost | Notes |
|---|---|---|---|
| Hetzner Cloud GPU | RTX 4000 SFF | ~€60–€100 / mo | Best EU price, ideal for "sovereign in Europe" story |
| Render | L4 | ~$60 / mo | Easy, auto-deploys from git |
| Fly.io | A10 | ~$0.20 / hr | Pay only when running |
| RunPod | RTX 4090 | ~$0.30 / hr | Cheapest per-hour, manual ops |

### Steps

```bash
# On the VM
git clone https://github.com/Ekansh1605/Lastenheft.git
cd Lastenheft
cp .env.example .env
# Edit .env:
#   ALLOW_API_LLM=false             ← lock to local Qwen3 only
#   RATE_LIMIT_PER_MINUTE=5         ← tighter for public
#   CORS_ORIGINS=https://your-domain.com
#   POSTGRES_PASSWORD=<strong-random>

docker compose -f docker/docker-compose.yml --env-file .env up -d \
  postgres langfuse-db langfuse

uv sync
uv run python scripts/prefetch_models.py
ollama pull qwen3:4b
uv run python scripts/download_sample_pdfs.py
uv run python -m ml.ingest.cli ingest-dir data/pdfs

# Run uvicorn behind nginx/caddy
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Then point a domain at the VM and put Caddy / nginx in front for TLS.
Frontend on Vercel as in Option A, with `NEXT_PUBLIC_API_BASE=https://api.your-domain.com`.

---

## Option C — Just record the video

Many of the highest-impact AI projects on GitHub have **no live demo URL.**
A 3-minute video + clean repo + reproducible local instructions is enough
for a senior engineer to evaluate the work. See [DEMO.md](DEMO.md).

---

## Pre-deploy checklist

- [ ] `ALLOW_API_LLM=false` if the URL will be public (prevents API-cost drain)
- [ ] `RATE_LIMIT_PER_MINUTE` set to your tolerance
- [ ] Postgres password rotated from `lastenheft:lastenheft`
- [ ] CORS_ORIGINS pinned to your exact frontend domain
- [ ] No API keys committed (`.env` is gitignored — verify with `git ls-files | grep -i env`)
- [ ] Backend uvicorn has `--workers 1` (only one process loads ColPali into VRAM)
- [ ] Caddy / nginx in front with TLS termination
- [ ] DB volume backed up before each deploy
- [ ] Test the rate-limit 429 message in browser devtools network tab
