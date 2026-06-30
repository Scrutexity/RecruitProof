# Deployment Guide

## 15-minute production deployment

RecruitProof runs as a Docker container on a single VM. No Kubernetes required
for the standard 500K-resume tier.

## Prerequisites

- A Linux VM (Ubuntu 22.04+ recommended) with:
  - 16 vCPU
  - 64 GB RAM
  - 200 GB NVMe disk
  - Docker 24+ and Docker Compose 2+
- Outbound HTTPS for the initial model download (one-time, ~440 MB)
- A reverse proxy (Caddy / nginx) if exposing to the network

## Step-by-step

```bash
# 1. SSH into your VM
ssh ubuntu@your-vm

# 2. Clone RecruitProof
git clone https://github.com/Scrutexity/RecruitProof
cd RecruitProof

# 3. Configure environment
cp .env.example .env
# Edit .env: set RECRUITPROOF_LICENSE, RECRUITPROOF_ADMIN_PASSWORD,
#            RECRUITPROOF_DATA_DIR=/data

# 4. Start the stack
docker-compose up -d

# 5. Verify health
curl http://localhost:8000/health
# {"status":"ok","version":"0.3.0","index_loaded":false}

# 6. Open the dashboard
open http://your-vm:8000
# Log in with admin / <your-password>

# 7. (Pilot) Import your first batch of resumes
# Use the Import Center UI, or:
docker-compose exec recruitproof python ingest_encore.py \
    --input /data/imports/encore_export.zip \
    --output /data/runs/proof_run_001/

# 8. Build the index
docker-compose exec recruitproof python precompute.py \
    --candidates /data/runs/proof_run_001/candidates.jsonl \
    --output /data/runs/proof_run_001/output/ \
    --model mini --index flat --hybrid

# 9. Run your first search
docker-compose exec recruitproof python search.py \
    --jd /data/jds/senior_backend.txt --top 100 --hybrid \
    --index /data/runs/proof_run_001/output/
```

**Total elapsed time: 12–15 minutes.**

## Docker Compose stack

```yaml
version: "3.9"
services:
  recruitproof:
    image: scrutexity/recruitproof:0.3.0
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
      - ./.env:/app/.env:ro
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "16"
          memory: 60G
```

## Backup

```bash
# Daily backup (cron)
0 2 * * * docker-compose exec recruitproof python backup.py --output /backups/$(date +\%F).tar.gz

# Retention: 30 days
find /backups/ -mtime +30 -delete
```

## Upgrades

```bash
git pull
docker-compose pull
docker-compose up -d
# RecruitProof auto-migrates the index format on first start
```

## Monitoring

- Health: `GET /health` → 200 OK
- Metrics: `GET /metrics` → Prometheus format
- Logs: `docker-compose logs -f recruitproof`

## Troubleshooting

| Symptom | Fix |
|---|---|
| Model download fails | Set `HF_HOME=/data/.hf_cache` in .env, retry |
| OOM during precompute | Reduce `--batch-size` to 32 |
| Search latency high | Switch to `--index ivf` |
| Disk full | Clean `/data/runs/` (old proof runs) |

## Need help?

Email: support@scrutexity.com
SLA: 24×7 for enterprise customers, 4-hour response.
