# Deployment Plan

This plan outlines moving PharmAssist to production with staged environments.

## 1. Environments
- Staging: Mirrors production DB schema, smaller data set. Used for pre-release verification.
- Production: Full scale data, performance thresholds enforced.

## 2. Core Components
- Backend (Flask): Containerized. Run behind reverse proxy (Fly.io / AWS ALB / Nginx). Expose port 5000.
- Frontend (Next.js App Router): Deploy on Vercel (or Netlify). Set `NEXT_PUBLIC_API_URL` to backend base URL.
- Database: Neon Postgres (Pooler endpoint). PITR enabled.
- Cache / Rate Limiting (Optional): Redis (Upstash / AWS ElastiCache) for product/inventory caching & token buckets.

## 3. Required Secrets / Env Vars
Backend:
- `DATABASE_URL` (Neon connection string)
- `SECRET_KEY` (Long random string for JWT)
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`
- `ADMIN_EMAILS` or `ADMIN_EMAIL_DOMAIN`
- `OAUTH_AUTO_CUSTOMER_TYPE` (Default customer type when OAuth user created)
Frontend:
- `NEXT_PUBLIC_API_URL` (https://api.yourdomain.com)
- `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID`

## 4. Build & Release Flow
1. Developer pushes feature branch → PR.
2. CI (workflow added) runs smoke + build checks.
3. Merge to `main` triggers container build & push (registry) + optional staging deploy.
4. Promotion to production via manual approval (workflow job `deploy-prod`).

## 5. Database Migrations
- Use Alembic: `alembic upgrade head` on deploy hook.
- Pre-deploy step (staging): backup snapshot.
- Validate `SELECT 1` and run lightweight integrity queries (counts table presence).

## 6. Observability
- Structured logs (JSON) aggregated (e.g., Fly logs / CloudWatch).
- Health endpoints: `/ready` for readiness.
- Add metrics later (Prometheus sidecar or OpenTelemetry).

## 7. Scaling & Resilience
- Backend horizontal scaling: stateless; connection pool sized for concurrency (adjust `DB_POOL_MAX`).
- Rate limiting endpoints (`/api/login`, `/api/oauth/google/exchange`) tuned to prevent brute force.
- Automatic retry for transient Neon disconnects already implemented.

## 8. Security Hardening (Post MVP)
- Enable HTTPS everywhere (Vercel auto, backend behind TLS terminator).
- Set `SECURE_COOKIES` if token ever moves to cookie storage.
- Add CSP headers on admin interface.
- Add MFA or secondary approval for admin critical actions.
 - Tighten CORS: allow only `app.yourdomain.com`, `admin.yourdomain.com` origins.
 - Rate limit `/api/login` and `/api/oauth/google/exchange` with token buckets.

## 9. Rollback Strategy
- Maintain previous container image tag `prev-<sha>`.
- Rollback: redeploy earlier image; run post-rollback DB health checks.
- Neon: use PITR or restore from nightly snapshot if migration corrupted data.

## 10. Deployment Domains
- `app.yourdomain.com` (Frontend)
- `api.yourdomain.com` (Backend API)
- Optional: `admin.yourdomain.com` (Admin UI with stricter CSP & rate limits).

## 11. Manual Verification Post-Deploy
- Login via password & OAuth.
- Create inventory batch (admin).
- Checkout order (customer).
- Verify dashboard stats endpoint returns expected keys.
- Confirm discount logic (add Pricing_Rules row) still functional.

## 12. Future Enhancements
- Add blue/green deployment (two Fly apps or two ECS task sets) with traffic shifting.
- Performance budget enforcement (e.g., automated Locust run gating deploy).
- Tag releases automatically and generate changelog.

## 14. Fly.io Quick Commands
Authenticate and create app:
```bash
fly auth login
fly apps create pharmassist-backend
```

Set secrets (replace with real values):
```bash
fly secrets set DATABASE_URL="postgres://..." SECRET_KEY="generate_a_long_random_string" \
	GOOGLE_OAUTH_CLIENT_ID="..." GOOGLE_OAUTH_CLIENT_SECRET="..." GOOGLE_OAUTH_REDIRECT_URI="https://app.yourdomain.com/login/google/callback" \
	ADMIN_EMAILS="admin@yourdomain.com" OAUTH_AUTO_CUSTOMER_TYPE="retail"
```

Build & deploy:
```bash
fly deploy --remote-only
fly status
fly logs
```

Rollback to previous image:
```bash
fly deploy --image prev-<sha>
```

## 15. Vercel Frontend Setup
- Add project on Vercel and set env vars:
	- `NEXT_PUBLIC_API_URL=https://<fly-app>.fly.dev` (or custom domain)
	- `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID=<your client id>`
- Trigger build with `npm run build` locally first; ensure it passes.
- Optional `vercel.json` can define headers for CSP on admin routes.

## 13. Quick Commands
Backend container build locally:
```bash
docker build -t pharmassist-backend:latest .
```
Run locally:
```bash
docker run -p 5000:5000 --env-file .env pharmassist-backend:latest python -m backend.app
```
Alembic migrate:
```bash
alembic upgrade head
```

Keep this file updated as infrastructure decisions evolve.
