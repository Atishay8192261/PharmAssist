# Performance Threshold Tuning Guide

This guide explains how to tune latency thresholds and interpret the observability and cache metrics now present in the PharmAssist backend.

## Key Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `LOG_TIMING` | (unset) | Enable per-request timing headers (`X-Request-Duration`, `X-DB-Time`, `Server-Timing`). |
| `SLOW_REQUEST_MS` | 500 | Log a `SLOW_REQUEST` warning when total request duration exceeds this. |
| `SLOW_DB_MS` | 400 | Log a `SLOW_DB` warning when accumulated DB time exceeds this. |
| `LOG_CACHE` | (unset) | When `1`, log cache hits/misses/sets/invalidations. |
| `CACHE_TTL_PRODUCTS` | 30 | TTL for products responses. |
| `CACHE_TTL_INVENTORY` | 30 | TTL for inventory admin responses. |
| `CACHE_TTL_DASHBOARD` | 60 | TTL for dashboard stats. |
| `PRODUCTS_PREWARM` | (unset) | When `1`, background thread pre-populates common product cache keys. |
| `PRODUCTS_PREWARM_INTERVAL` | 120 | Seconds between pre-warm passes. |
| `METRICS_PROMETHEUS` | (unset) | When `1`, `/metrics` returns Prometheus exposition text; otherwise JSON. |

## Headers & Meanings
- `X-Request-Duration`: Total elapsed time (ms) from Flask `before_request` to `after_request`.
- `X-DB-Time`: Sum of time spent inside `get_connection()` context blocks for that request (ms). Indicates actual database work + network latency.
- `Server-Timing`: Browser-friendly timing hint (e.g., `app;dur=447.12, db;dur=357.93`).

## Cache Metrics (`/metrics`)
JSON format returns:
```json
{
  "cache": { "hits": <int>, "misses": <int>, "expired": <int> }
}
```
Prometheus format:
```
app_cache_hits_total <n>
app_cache_misses_total <n>
app_cache_expired_total <n>
```

## Recommended Baseline Thresholds
After optimization you typically see:
- Cold `/api/products` (first request after restart): ~350–450ms DB, ~450–650ms total.
- Warm cached `/api/products`: near 0ms DB, <50ms total.
- Other lightweight endpoints (e.g., `/health`): ~150–300ms total (remote DB network adds noise).

Suggested adjustments:
| Stage | `SLOW_REQUEST_MS` | `SLOW_DB_MS` | Rationale |
|-------|-------------------|-------------|-----------|
| Initial (current) | 500 | 400 | Captures cold product path; useful for baseline. |
| Post cache validation | 450 | 325 | Flags any product requests not served from cache or with unusually slow discount resolution. |
| After future network or pooling improvements | 350 | 250 | Tightens performance budget toward <350ms cold. |

Set via:
```bash
export LOG_TIMING=1
export SLOW_REQUEST_MS=450
export SLOW_DB_MS=325
python -m backend.app
```

## Tuning Process
1. Run representative traffic (mix cold/warm) for ~5 minutes.
2. Capture metrics: `curl -s http://localhost:5000/metrics`.
3. Review logs for `SLOW_REQUEST` and `SLOW_DB` frequency.
4. If >10% of requests trigger slow warnings, raise thresholds slightly; if <1% and you want stricter monitoring, lower them.
5. Repeat after each performance change (e.g., new index, adjusting TTLs, enabling Redis).

## Identifying True Hotspots
- High `X-DB-Time` but low total duration: DB-bound operations; consider query refactor or additional indexes.
- High total duration with moderate `X-DB-Time`: application layer, serialization, network latency, or cache miss overhead.
- Frequent cache misses for identical URLs: verify consistent query parameters / search normalization.

## Pre-Warm Strategy Expansion
Add more specs (e.g., `quantity=5`, `limit=50`, common search tokens) by editing the pre-warm key list in `backend/app.py` under `PRODUCTS_PREWARM` block.

## When to Increase TTLs
Increase TTLs if:
- Inventory / pricing changes are relatively infrequent.
- High ratio of cache misses on stable endpoints.
Keep TTL modest (30–120s) if near real-time stock/price accuracy is critical.

## Safe Threshold Changes Checklist
- Use production-like traffic (not a single curl) before lowering thresholds.
- Ensure Redis (if enabled) is stable; avoid using lowered thresholds during Redis connection churn.
- Combine threshold changes with log sampling: if log volume spikes dramatically, raise thresholds.

## Quick Commands Reference
```bash
# Start with tuned thresholds and logging
export LOG_TIMING=1
export SLOW_REQUEST_MS=450
export SLOW_DB_MS=325
export LOG_CACHE=1
python -m backend.app

# Hit products twice (cold + warm)
curl -s 'http://localhost:5000/api/products?page=1&limit=20' > /dev/null
curl -i 'http://localhost:5000/api/products?page=1&limit=20' | grep -i x-request-duration

# Metrics JSON
curl -s http://localhost:5000/metrics | jq

# Prometheus format (restart with METRICS_PROMETHEUS=1 first)
curl -s http://localhost:5000/metrics
```

## Troubleshooting
| Symptom | Possible Cause | Action |
|---------|----------------|--------|
| Hits stay at 0 | Debug reloader reset counters | Run with `FLASK_ENV=production` or disable debug. |
| DB time high even when cached | Did not use identical params / cache key mismatch | Inspect cache key pattern in logs; normalize query params. |
| Expired counter never grows | TTL too high or not enough time elapsed | Reduce TTL or wait; confirm expiration logic in `cache.py`. |
| Frequent SLOW_DB on products | Discount subquery or network latency | Consider caching discount per (sku_id, quantity, customer) or batching requests. |

## Future Enhancements (Optional)
- Percentile latency tracking (p50, p90, p99) for dynamic threshold suggestions.
- Separate counters for hits by endpoint key class (products vs inventory).
- Adaptive TTL based on volatility (shorter during high write, longer off-peak).

---
Use this guide as living documentation; update after major performance changes.
