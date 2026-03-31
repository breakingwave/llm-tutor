# Hostinger VPS Deployment

This directory contains production deployment files for `llm_tutor` using Docker Compose and GitHub Actions.

## Files

- `bootstrap_vps.sh` - one-time server bootstrap (Docker, firewall, repo clone, env file seed)
- `deploy.sh` - pull latest code and restart stack
- `nginx.conf` - HTTP reverse proxy config
- `nginx.tls.conf` - HTTPS reverse proxy config (after certs are issued)

## 1) One-Time VPS Setup

SSH into the Hostinger VPS and run:

```bash
bash deploy/bootstrap_vps.sh git@github.com:<your-org>/<your-repo>.git /opt/llm_tutor
```

Then edit `/opt/llm_tutor/.env.production` with real keys:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `TAVILY_API_KEY`
- `CORS_ORIGINS` (for example: `https://your-domain.com`)

## 2) First Manual Deploy

```bash
cd /opt/llm_tutor
bash deploy/deploy.sh
```

Verify:

```bash
curl http://127.0.0.1/health
```

## 3) GitHub Actions CI/CD

### Required GitHub Secrets

Set these repository secrets:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_PORT`

Workflow behavior:

- PRs to `main` run `.github/workflows/ci.yml`
- Pushes to `main` run `.github/workflows/deploy.yml` (CI + remote deploy)

## 4) TLS / HTTPS

After DNS points to your VPS:

1. Request certs with certbot (host machine):
   ```bash
   sudo apt-get install -y certbot
   sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com
   ```
2. Copy `deploy/nginx.tls.conf` over `deploy/nginx.conf` and replace domain placeholders.
3. Ensure cert files are available under `deploy/certs` (or update compose volume paths to your cert location).
4. Restart:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

## 5) Rollback

If a deployment fails:

```bash
cd /opt/llm_tutor
git log --oneline -n 10
git checkout <previous-good-commit-sha>
docker compose -f docker-compose.prod.yml up -d --build
```

When ready, return to mainline deploys:

```bash
git checkout main
git pull --ff-only origin main
```

## 6) Backups

Back up persistent app data daily:

- `data/sessions`
- `data/uploads`
- `data/qdrant`
- `data/logs` (optional but recommended)

Example cron-friendly backup command:

```bash
tar -czf /var/backups/llm_tutor_data_$(date +%F).tar.gz /opt/llm_tutor/data
```

## 7) Post-Deploy Smoke Test

1. Open app UI in browser.
2. Create a session from onboarding.
3. Upload a PDF and confirm it appears in library.
4. Run gathering and verify material cards are produced.
5. Generate curriculum and verify syllabus items appear.
6. Send a chat message and verify streamed response (SSE) is visible.
