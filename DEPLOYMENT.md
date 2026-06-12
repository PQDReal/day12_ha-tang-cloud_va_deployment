# Thông Tin Triển Khai

## Public URL

https://lab12-final-agent-production.up.railway.app

## Nền tảng

Railway

## Dịch vụ đang chạy

- `lab12-final-agent`: FastAPI production agent.
- `Redis`: backing service dùng để lưu conversation history, rate limiting và cost guard.

## Lệnh kiểm tra

### Health check

```bash
curl https://lab12-final-agent-production.up.railway.app/health
```

Kết quả mong đợi:
```json
{"status":"ok"}
```

### Readiness check

```bash
curl https://lab12-final-agent-production.up.railway.app/ready
```

Kết quả mong đợi:
```json
{"ready":true,"storage":"redis"}
```

### Kiểm tra bắt buộc xác thực

```bash
curl -X POST https://lab12-final-agent-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```

Kết quả mong đợi: `401 Unauthorized`, vì request chưa gửi header `X-API-Key`.

### Kiểm tra API có xác thực

```bash
curl -X POST https://lab12-final-agent-production.up.railway.app/ask \
  -H "X-API-Key: <AGENT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```

Kết quả mong đợi: `200 OK`, có câu trả lời từ agent, thông tin usage và `history_length`.

### Kiểm tra conversation history

```bash
curl https://lab12-final-agent-production.up.railway.app/history/test \
  -H "X-API-Key: <AGENT_API_KEY>"
```

Kết quả mong đợi: trả về các message của user và assistant đã được lưu cho `user_id=test`.

### Kiểm tra rate limit

Gửi hơn 10 request trong vòng 60 giây với cùng một `user_id`.

Kết quả mong đợi:
```text
Request 1-10: 200 OK
Request 11: 429 Too Many Requests
```

## Biến môi trường đã set trên Railway

- `ENVIRONMENT=production`
- `AGENT_API_KEY`
- `REDIS_URL`
- `RATE_LIMIT_PER_MINUTE=10`
- `MONTHLY_BUDGET_USD=10.0`

## Kiểm tra production readiness

```bash
cd 06-lab-complete
python check_production_ready.py
```

Kết quả:
```text
20/20 checks passed
PRODUCTION READY
```

## Ghi chú

- Giá trị thật của `AGENT_API_KEY` được lưu trong Railway variables, không commit vào repository.
- Giá trị thật của `REDIS_URL` được lưu trong Railway variables, không commit vào repository.
- App được deploy từ thư mục `06-lab-complete` bằng lệnh `railway up`.
- Public URL hiện đã hoạt động và sử dụng Redis làm storage backend.
