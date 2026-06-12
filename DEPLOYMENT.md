# Deployment Information

## Public URL

https://lab12-final-agent-production.up.railway.app

## Platform

Railway

## Services

- `lab12-final-agent`: FastAPI production agent
- `Redis`: backing service for conversation history, rate limiting, and cost guard

## Test Commands

### Health Check

```bash
curl https://lab12-final-agent-production.up.railway.app/health
```

Expected:
```json
{"status":"ok"}
```

### Readiness Check

```bash
curl https://lab12-final-agent-production.up.railway.app/ready
```

Expected:
```json
{"ready":true,"storage":"redis"}
```

### Authentication Required

```bash
curl -X POST https://lab12-final-agent-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```

Expected: `401 Unauthorized`

### API Test With Authentication

```bash
curl -X POST https://lab12-final-agent-production.up.railway.app/ask \
  -H "X-API-Key: <AGENT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```

Expected: `200 OK` with an agent response, usage info, and `history_length`.

### History Test

```bash
curl https://lab12-final-agent-production.up.railway.app/history/test \
  -H "X-API-Key: <AGENT_API_KEY>"
```

Expected: stored user and assistant messages for `user_id=test`.

## Environment Variables Set

- `ENVIRONMENT=production`
- `AGENT_API_KEY`
- `REDIS_URL`
- `RATE_LIMIT_PER_MINUTE=10`
- `MONTHLY_BUDGET_USD=10.0`

## Validation

```bash
cd 06-lab-complete
python check_production_ready.py
```

Result:
```text
20/20 checks passed
PRODUCTION READY
```

## Notes

- API key value is stored in Railway variables and is not committed to the repository.
- Redis URL is stored in Railway variables and is not committed to the repository.
- The app was deployed from `06-lab-complete` using `railway up`.
