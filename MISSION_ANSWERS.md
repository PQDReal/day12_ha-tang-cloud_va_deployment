# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. Hardcode secret trực tiếp trong mã nguồn: `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
2. Không có cơ chế cấu hình theo môi trường: `DEBUG`, `MAX_TOKENS`, host và port đều bị cố định trong code thay vì đọc từ biến môi trường.
3. Bật chế độ debug/reload khi chạy app: `reload=True`, phù hợp khi phát triển local nhưng không an toàn cho production.
4. App bind vào `localhost`, nên không thể nhận kết nối từ bên ngoài máy/container.
5. Port bị hardcode là `8000`; các nền tảng cloud thường inject biến môi trường `PORT`.
6. Bản develop không có endpoint `/health` hoặc `/ready`, nên cloud platform không thể kiểm tra liveness/readiness.
7. Dùng `print()` để debug thay vì structured logging.
8. Log cả API key, có thể làm lộ secret trong terminal hoặc cloud logs.
9. Không có graceful shutdown hoặc lifecycle cleanup.

### Exercise 1.2: Output khi chạy bản basic

Lệnh chạy:
```bash
cd 01-localhost-vs-production/develop
python app.py
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

Output server quan sát được:
```text
Starting agent on localhost:8000...
INFO:     Uvicorn running on http://localhost:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [1836] using WatchFiles
INFO:     Started server process [2508]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     127.0.0.1:53236 - "POST /ask HTTP/1.1" 422 Unprocessable Entity
```

Output curl quan sát được:
```json
{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
```

Nhận xét: bản develop có chạy được, nhưng endpoint `/ask` được khai báo là `ask_agent(question: str)`, nên FastAPI hiểu `question` là query parameter. Trong khi đó lệnh curl của lab gửi dữ liệu bằng JSON body, vì vậy request trả về lỗi `422`. Đây là một phát hiện quan trọng về production-readiness: hợp đồng API giữa client và server chưa rõ ràng/chưa nhất quán.

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config | Hardcode trực tiếp trong `app.py` | Đọc từ biến môi trường thông qua `config.py` / `.env` | Cho phép cấu hình khác nhau giữa local/staging/production mà không cần sửa code, đồng thời tránh commit secret |
| Secrets | API key giả và DB URL bị hardcode, thậm chí còn bị log ra | `.env.example` mô tả các secret cần có; giá trị thật lấy từ môi trường | Tránh lộ secret trên Git và cloud logs |
| Host/Port | `host="localhost"`, `port=8000` | Dùng biến môi trường `HOST` và `PORT`, mặc định `0.0.0.0:8000` | Cần thiết cho Docker/Railway/Render vì platform route traffic vào port được inject |
| Request body | Endpoint develop mong đợi query parameter, nên curl gửi JSON trả `422` | Endpoint production đọc JSON body và validate trường `question` | Hợp đồng API rõ ràng giúp tránh mismatch giữa client và server |
| Health check | Không có | `/health` trả status, uptime, version, environment, timestamp | Cloud platform và monitoring có thể phát hiện container lỗi |
| Readiness check | Không có | `/ready` trả trạng thái sẵn sàng hoặc `503` | Load balancer có thể ngừng route traffic khi app chưa khởi tạo xong |
| Logging | Dùng `print()` debug và log cả secret | Structured JSON logging, không log secret | Log dễ parse/tìm kiếm hơn và an toàn hơn trong production |
| Shutdown | Không có lifecycle handling | Có lifespan startup/shutdown và SIGTERM handler | Hỗ trợ graceful shutdown khi deploy/restart |
| CORS | Không cấu hình | Allowed origins có thể cấu hình | Tích hợp browser/API an toàn hơn |
| Debug reload | Luôn `reload=True` | Chỉ reload khi `DEBUG=true` | Tránh reloader process và overhead không cần thiết trong production |

Output khi chạy bản production:
```bash
cd 01-localhost-vs-production/production
cp .env.example .env
pip install -r requirements.txt
python app.py
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

Output server quan sát được:
```text
WARNING:root:OPENAI_API_KEY not set — using mock LLM
INFO:     Started server process [4416]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     127.0.0.1:56795 - "POST /ask HTTP/1.1" 200 OK
```

Output curl quan sát được:
```json
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","model":"gpt-4o-mini"}
```

Kết luận Part 1: bản production khắc phục các anti-pattern chính của bản localhost bằng cách dùng cấu hình từ môi trường, xử lý JSON request đúng hơn, bổ sung health/readiness endpoints, structured logging và graceful lifecycle handling. Bản develop hữu ích để minh họa vì sao "chạy được trên máy mình" vẫn chưa đủ để deploy lên production.

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image: bản develop dùng `python:3.11`. Đây là full Python image nên dễ hiểu và dễ debug, nhưng kích thước lớn.
2. Working directory: `/app`. Đây là thư mục làm việc bên trong container, nơi copy code và chạy ứng dụng.
3. Vì sao copy `requirements.txt` trước: Docker cache theo layer. Nếu dependencies không đổi, layer `pip install` được cache lại; chỉ thay đổi code thì build nhanh hơn.
4. `CMD` vs `ENTRYPOINT`: `CMD` là lệnh mặc định và dễ override khi `docker run`; `ENTRYPOINT` cố định command chính của container hơn, thường dùng khi image luôn chạy một executable cụ thể.

### Exercise 2.2: Build và run basic container

Lệnh build đúng cần chạy từ project root vì Dockerfile dùng path `02-docker/develop/...` và `utils/...`:
```bash
cd day12_ha-tang-cloud_va_deployment
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
```

Output container:
```text
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     172.17.0.1:49384 - "POST /ask HTTP/1.1" 422 Unprocessable Entity
INFO:     172.17.0.1:35744 - "POST /ask HTTP/1.1" 422 Unprocessable Entity
INFO:     172.17.0.1:52794 - "POST /ask HTTP/1.1" 422 Unprocessable Entity
```

Lệnh test theo `CODE_LAB.md`:
```bash
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
```

Output:
```json
{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
```

Nhận xét: container đã chạy thành công, nhưng endpoint vẫn trả `422` khi gửi JSON body vì code bản develop khai báo `question: str`, khiến FastAPI hiểu `question` là query parameter. Docker đóng gói đúng hành vi hiện có của app; nó không tự sửa mismatch trong API contract.

### Exercise 2.3: Multi-stage build

Stage 1 `builder`:
- Dùng `python:3.11-slim AS builder`.
- Cài build dependencies như `gcc`, `libpq-dev`.
- Cài Python packages bằng `pip install --user` vào `/root/.local`.

Stage 2 `runtime`:
- Dùng `python:3.11-slim AS runtime`.
- Tạo non-root user `appuser`.
- Chỉ copy dependencies đã cài từ builder và source code cần thiết.
- Thêm `HEALTHCHECK`.
- Chạy app bằng `uvicorn`.

Vì sao image nhỏ hơn: runtime image không giữ build tools/compiler/cache không cần thiết, chỉ giữ runtime Python, dependencies đã cài và source code.

Lưu ý khi build: Dockerfile production cũng cần build từ project root, không phải từ `02-docker/production`, vì có các dòng `COPY 02-docker/production/...` và `COPY utils/mock_llm.py ...`.

Output kiểm tra image size trong PowerShell:
```powershell
docker images my-agent:develop
```

```text
i Info ->   U  In Use
IMAGE              ID             DISK USAGE   CONTENT SIZE   EXTRA
my-agent:develop   79217902bec3       1.66GB          424MB    U
```

### Exercise 2.3: Image size comparison
- Develop: `1.66GB`
- Production / Advanced: `236MB`
- Difference: giảm khoảng `85.8%` so với image develop.

Output kiểm tra image trong Git Bash:
```bash
docker images | grep my-agent
```

```text
my-agent:advanced   97bac46884b5        236MB         56.6MB
my-agent:develop    79217902bec3       1.66GB          424MB
my-agent:latest     18ec8bd8d8d4       1.66GB          424MB
```

Output kiểm tra riêng image develop trong PowerShell/Docker Desktop:
```powershell
docker images my-agent:develop
```

```text
i Info ->   U  In Use
IMAGE              ID             DISK USAGE   CONTENT SIZE   EXTRA
my-agent:develop   79217902bec3       1.66GB          424MB    U
```

Ghi chú môi trường: trong Git Bash/MINGW64 dùng `grep`; trong PowerShell mới dùng `Select-String`.

### Exercise 2.4: Docker Compose stack

Architecture diagram:
```text
Client
  |
  v
Nginx reverse proxy / load balancer :80
  |
  v
Agent FastAPI service :8000
  |
  +--> Redis :6379, dùng cho cache/session/rate limiting
  |
  +--> Qdrant :6333, vector database cho RAG
```

Các service trong `docker-compose.yml`:
- `agent`: FastAPI AI agent, build từ Dockerfile production.
- `redis`: cache/session/rate limiting.
- `qdrant`: vector database.
- `nginx`: reverse proxy/load balancer, expose port `80` và `443`.

Nhận xét: stack production mô phỏng kiến trúc deploy thực tế hơn bản single container, với reverse proxy phía trước và backing services phía sau.

Output test Docker Compose stack:
```bash
curl http://localhost/health
```

```json
{"status":"ok","uptime_seconds":152.9,"version":"2.0.0","timestamp":"2026-06-12T08:43:20.986226"}
```

```bash
curl http://localhost/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain microservices"}'
```

```json
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Kết luận Exercise 2.4: Docker Compose stack đã chạy thành công qua Nginx tại `http://localhost`. `/health` trả `200 OK`, và `/ask` nhận JSON body đúng ở bản production stack.

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- URL: https://docker-tutorial-production-cace.up.railway.app
- Screenshot: chưa thêm vào repo ở thời điểm ghi nhận này.

Các biến môi trường đã set trên Railway:
```bash
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-secret-key
```

Output:
```text
Set variables PORT
Set variables AGENT_API_KEY
```

Tạo/lấy service domain:
```bash
railway domain
```

Output:
```text
Service Domain created:
https://docker-tutorial-production-cace.up.railway.app
```

Lỗi khi dùng domain mẫu trong tài liệu:
```bash
curl http://student-agent-domain/health
curl http://student-agent-domain/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": ""}'
```

Output:
```text
curl: (6) Could not resolve host: student-agent-domain
```

Nhận xét: `student-agent-domain` chỉ là placeholder trong `CODE_LAB.md`, cần thay bằng domain thật Railway cấp.

Health check với domain thật:
```bash
curl https://docker-tutorial-production-cace.up.railway.app/health
```

Output:
```json
{"status":"ok","uptime_seconds":344.0,"platform":"Railway","timestamp":"2026-06-12T09:12:46.706419+00:00"}
```

Test `/ask` với question rỗng:
```bash
curl https://docker-tutorial-production-cace.up.railway.app/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": ""}'
```

Output:
```json
{"detail":"question required"}
```

Nhận xét: endpoint hoạt động và validate input đúng; question rỗng bị từ chối.

Lỗi quote trong Git Bash:
```bash
curl https://docker-tutorial-production-cace.up.railway.app/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "What's your condition?"}'
```

Kết quả: terminal chuyển sang prompt `>` và phải `Ctrl+C` vì dấu `'` trong `What's` làm vỡ chuỗi single-quote của Bash.

Lỗi sai endpoint:
```bash
curl https://docker-tutorial-production-cace.up.railway.app/askk -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "How are you?"}'
```

Output:
```json
{"detail":"Not Found"}
```

Test `/ask` thành công:
```bash
curl https://docker-tutorial-production-cace.up.railway.app/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "How are you?"}'
```

Output:
```json
{"question":"How are you?","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","platform":"Railway"}
```

Kết luận Exercise 3.1: Railway deployment thành công. Public URL hoạt động, `/health` trả `200 OK`, `/ask` nhận JSON body đúng và trả response từ mock LLM.

### Exercise 3.2: Render deployment

- URL: https://ai-agent-f10k.onrender.com
- Blueprint path dùng trên Render: `03-cloud-deployment/render/render.yaml`
- Ghi chú cấu hình: đã sửa `render.yaml` để thêm `ipAllowList: []` cho Redis và `rootDir: 03-cloud-deployment/railway` cho web service, vì Render build từ root repo nếu không chỉ định root directory.

Health check:
```bash
curl https://ai-agent-f10k.onrender.com/health
```

Output:
```json
{"status":"ok","uptime_seconds":71.7,"platform":"Railway","timestamp":"2026-06-12T09:44:12.988829+00:00"}
```

Lỗi khi POST vào root `/`:
```bash
curl https://ai-agent-f10k.onrender.com -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello from Render"}'
```

Output:
```json
{"detail":"Method Not Allowed"}
```

Nhận xét: root `/` chỉ hỗ trợ `GET`, nên POST vào root trả `405 Method Not Allowed`. Endpoint đúng để hỏi agent là `/ask`.

Test `/ask` thành công:
```bash
curl https://ai-agent-f10k.onrender.com/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello from Render"}'
```

Output:
```json
{"question":"Hello from Render","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","platform":"Railway"}
```

So sánh `render.yaml` và `railway.toml`:
- `railway.toml` cấu hình build/deploy cho một service Railway, dùng `startCommand`, `healthcheckPath`, restart policy và set biến môi trường qua Railway CLI/Dashboard.
- `render.yaml` là Blueprint IaC, có thể khai báo nhiều service cùng lúc như web service `ai-agent` và Redis `agent-cache`.
- Render cần chỉ rõ `rootDir` trong repo dạng monorepo/folder lab; Railway deploy trực tiếp từ folder `03-cloud-deployment/railway`.
- Render Redis yêu cầu `ipAllowList`; Railway example không khai báo Redis service trong `railway.toml`.

Kết luận Exercise 3.2: Render deployment thành công. Public URL hoạt động, `/health` trả `200 OK`, và `/ask` trả response đúng khi gọi đúng endpoint.

## Part 4: API Security

### Exercise 4.1-4.3: Test results
#### Exercise 4.1: API Key authentication

Chạy app trong `04-api-gateway/develop`:
```bash
cd 04-api-gateway/develop
python app.py
```

Output server:
```text
API Key: demo-key-change-in-production
Test: curl -H 'X-API-Key: demo-key-change-in-production' http://localhost:8000/ask?question=hello
INFO:     Will watch for changes in these directories: ['C:\\Users\\ThePake\\Desktop\\Applied AI VinUni\\lab12\\day12_ha-tang-cloud_va_deployment\\04-api-gateway\\develop']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [4672] using WatchFiles
INFO:     Started server process [15108]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     127.0.0.1:54353 - "POST /ask HTTP/1.1" 401 Unauthorized
INFO:     127.0.0.1:54372 - "POST /ask HTTP/1.1" 403 Forbidden
```

Test không có API key:
```bash
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

Output:
```json
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

Kết quả: request không có key bị từ chối với `401 Unauthorized`.

Test với sai API key:
```bash
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

Output:
```json
{"detail":"Invalid API key."}
```

Kết quả: request có key nhưng sai giá trị bị từ chối với `403 Forbidden`.

API key được check trong hàm `verify_api_key()` của `04-api-gateway/develop/app.py`:
- Nếu thiếu header `X-API-Key`, app raise `HTTPException(status_code=401)`.
- Nếu key không khớp `API_KEY`, app raise `HTTPException(status_code=403)`.
- `API_KEY` được đọc từ biến môi trường `AGENT_API_KEY`; nếu không set thì dùng mặc định `demo-key-change-in-production`.

Cách rotate key: thay đổi biến môi trường `AGENT_API_KEY` khi chạy app hoặc trên cloud platform, sau đó restart/redeploy service. Không cần sửa code.

Nhận xét: lần test dùng `secret-key-123` bị `403` vì app hiện đang dùng key mặc định `demo-key-change-in-production`. Muốn request thành công thì cần set env:
```bash
export AGENT_API_KEY=secret-key-123
python app.py
```
hoặc gọi bằng đúng key mặc định:
```bash
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: demo-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

#### Exercise 4.2: JWT authentication

Đọc `auth.py`:
- JWT flow gồm: user gửi username/password tới endpoint login, server tạo JWT chứa `sub`, `role`, `iat`, `exp`, sau đó client gửi token trong header `Authorization: Bearer <token>`.
- Secret ký token lấy từ `JWT_SECRET`, nếu không set thì dùng mặc định `super-secret-change-in-production-please`.
- Token dùng thuật toán `HS256` và hết hạn sau 60 phút.
- Demo users trong code là `student/demo123` role `user` và `teacher/teach456` role `admin`.

Lệnh trong `CODE_LAB.md` dùng endpoint `/token` và credential `admin/secret`, nhưng code hiện tại dùng endpoint thật là `/auth/token` và demo users khác.

Test endpoint theo tài liệu:
```bash
curl http://localhost:8000/token -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'
```

Output:
```json
{"detail":"Not Found"}
```

Nhận xét: `/token` không tồn tại trong app hiện tại nên trả `404 Not Found`.

Lấy token đúng qua `/auth/token`:
```bash
curl http://localhost:8000/auth/token -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "demo123"}'
```

Output:
```json
{"access_token":"<JWT_TOKEN>","token_type":"bearer","expires_in_minutes":60,"hint":"Include in header: Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."}
```

Gọi protected endpoint đúng bằng Bearer token:
```bash
TOKEN="<JWT_TOKEN>"
curl http://localhost:8000/ask -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain JWT"}'
```

Output:
```json
{"question":"Explain JWT","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":9,"budget_remaining_usd":1.6e-05}}
```

Kết luận Exercise 4.2: JWT authentication hoạt động. Token lấy thành công từ `/auth/token`, sau đó dùng header `Authorization: Bearer <token>` để gọi `/ask`. Response có `requests_remaining`, cho thấy request đã đi qua security stack và rate limiter.

#### Exercise 4.3: Rate limiting

Đọc `rate_limiter.py`:
- Algorithm được dùng: Sliding Window Counter.
- Mỗi user có một deque lưu timestamp request trong window 60 giây.
- Mỗi request mới sẽ xóa các timestamp cũ hơn 60 giây, sau đó đếm số request còn lại trong window.
- Nếu số request trong window đạt limit, app raise `HTTPException(status_code=429)`.

Limit:
- User thường: `10 requests / 60 giây`.
- Admin: `100 requests / 60 giây`.

Cách bypass/ưu tiên cho admin:
- Trong `app.py`, app chọn limiter theo role trong JWT:
```python
limiter = rate_limiter_admin if role == "admin" else rate_limiter_user
```
- Admin không bypass hoàn toàn, nhưng có quota cao hơn nhiều (`100 req/min` thay vì `10 req/min`).

Test gọi liên tục 20 lần:
```bash
for i in {1..20}; do
  curl http://localhost:8000/ask -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "Test '$i'"}'
  echo ""
done
```

Output rút gọn:
```json
{"question":"Test 1","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
{"question":"Test 2","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":8,"budget_remaining_usd":3.5e-05}}
{"question":"Test 3","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":7,"budget_remaining_usd":5.1e-05}}
...
{"question":"Test 10","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":0,"budget_remaining_usd":0.000188}}
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":57}}
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":56}}
...
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":54}}
```

Kết luận Exercise 4.3: rate limiting hoạt động đúng. 10 request đầu của user `student` thành công, `requests_remaining` giảm từ 9 xuống 0. Từ request thứ 11 trở đi, app trả lỗi rate limit với limit `10`, window `60` giây và `retry_after_seconds`.

### Exercise 4.4: Cost guard implementation
Đánh giá file ban đầu:
- `04-api-gateway/production/cost_guard.py` ban đầu đã có cost guard, nhưng chưa khớp hoàn toàn với yêu cầu Exercise 4.4.
- Logic cũ dùng in-memory state, budget `$1/ngày/user`, reset theo ngày.
- Trong comment cũng ghi rõ production nên lưu Redis/DB, không nên chỉ lưu in-memory.
- Yêu cầu của `CODE_LAB.md` là `$10/tháng/user`, track spending trong Redis, reset đầu tháng.

Đã cập nhật logic:
- Thêm `check_budget(user_id: str, estimated_cost: float) -> bool` đúng dạng yêu cầu lab.
- Budget mặc định: `$10/tháng/user`, có thể đổi bằng biến môi trường `MONTHLY_BUDGET_USD`.
- Key Redis theo tháng: `budget:{user_id}:{YYYY-MM}:cost`.
- Redis TTL: `32 ngày`, để dữ liệu tự hết hạn sau chu kỳ tháng.
- Nếu có `REDIS_URL`, cost guard dùng Redis để phù hợp stateless/scale.
- Nếu local chưa có Redis hoặc chưa set `REDIS_URL`, module fallback sang in-memory để app vẫn chạy được trong lab.
- `record_usage()` tính cost từ input/output tokens và ghi usage sau khi LLM trả lời.
- `get_usage()` trả về `cost_usd`, `budget_remaining_usd`, `budget_used_pct`, và backend storage đang dùng (`redis` hoặc `memory`).

Các file đã cập nhật:
- `04-api-gateway/production/cost_guard.py`
- `04-api-gateway/production/app.py`
- `04-api-gateway/production/requirements.txt` thêm `redis>=5.0.0`

Test import và logic fallback local:
```bash
python -c "import app; from cost_guard import check_budget, cost_guard; print(app.app.title); print(check_budget('demo-user', 0.01)); print(cost_guard.get_usage('demo-user'))"
```

Output:
```text
Agent — Full Security Stack
True
{'user_id': 'demo-user', 'month': '2026-06', 'requests': 1, 'input_tokens': 66666, 'output_tokens': 0, 'cost_usd': 0.01, 'budget_usd': 10.0, 'budget_remaining_usd': 9.99, 'budget_used_pct': 0.1, 'storage': 'memory'}
Redis not configured - using in-memory cost guard
```

Kết luận Exercise 4.4: cost guard hiện đã đạt yêu cầu logic chính của lab: kiểm tra budget theo user, giới hạn `$10/tháng`, có Redis support để dùng production/stateless, và có fallback memory để chạy local khi chưa bật Redis.

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
#### Exercise 5.1: Health checks

Kiểm tra `05-scaling-reliability/develop/app.py`:
- Đã có endpoint `/health` cho liveness probe.
- Đã có endpoint `/ready` cho readiness probe.
- `/health` trả status, uptime, version, environment, timestamp và memory check bằng `psutil`.
- `/ready` kiểm tra biến `_is_ready`; nếu chưa ready thì trả `503`.

Test trên port riêng `8051`:
```text
HEALTH:
STATUS=200
{"status":"ok","uptime_seconds":51.1,"version":"1.0.0","environment":"development","timestamp":"2026-06-12T10:23:08.317082+00:00","checks":{"memory":{"status":"ok","used_percent":83.7}}}

READY:
STATUS=200
{"ready":true,"in_flight_requests":1}
```

Nhận xét: Exercise 5.1 đã đạt yêu cầu. `in_flight_requests` là `1` vì middleware tính cả request `/ready` hiện tại; không ảnh hưởng chức năng readiness.

#### Exercise 5.2: Graceful shutdown

Kiểm tra `05-scaling-reliability/develop/app.py`:
- Có lifespan startup/shutdown.
- Khi startup, app load dependency giả lập rồi set `_is_ready = True`.
- Khi shutdown, app set `_is_ready = False`, log graceful shutdown và chờ `_in_flight_requests` hoàn thành tối đa 30 giây.
- Có signal handler cho `SIGTERM` và `SIGINT`.

Đoạn code chính:
```python
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)
```

Test trên Windows:
- App chạy được trên port `8052` và log startup/ready thành công.
- Gửi `SIGTERM` bằng Python `os.kill(pid, signal.SIGTERM)` dừng được process.
- Tuy nhiên Windows signal behavior khác Linux/macOS nên log graceful shutdown không thể hiện đầy đủ như lệnh `kill -TERM $PID` trong tài liệu Unix.

Output startup:
```text
2026-06-12 17:27:02,200 INFO Starting agent on port 8052
INFO:     Started server process [5296]
INFO:     Waiting for application startup.
2026-06-12 17:27:02,266 INFO Agent starting up...
2026-06-12 17:27:02,267 INFO Loading model and checking dependencies...
2026-06-12 17:27:02,467 INFO Agent is ready!
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8052 (Press CTRL+C to quit)
```

Kết luận: code graceful shutdown đã có đúng cấu trúc. Việc test signal trên Windows có giới hạn, nhưng trong container/Linux Uvicorn sẽ nhận SIGTERM và gọi lifespan shutdown.

#### Exercise 5.3: Stateless design

Kiểm tra `05-scaling-reliability/production/app.py`:
- Conversation state không lưu trực tiếp trong memory khi có Redis.
- Session/history được lưu qua các hàm `save_session()`, `load_session()`, `append_to_history()`.
- Redis key dạng `session:{session_id}` và có TTL.
- Response trả `served_by` để thấy request có thể được xử lý bởi nhiều instance khác nhau.

Đoạn logic chính:
```python
if USE_REDIS:
    _redis.setex(f"session:{session_id}", ttl_seconds, serialized)
else:
    _memory_store[f"session:{session_id}"] = data
```

Nhận xét: production app hỗ trợ stateless design khi chạy với Redis. Nếu chạy local không Redis thì fallback in-memory để demo, nhưng fallback này không scalable.

#### Exercise 5.4: Load balancing

Chạy stack:
```bash
cd 05-scaling-reliability/production
docker compose up -d --scale agent=3
```

Lưu ý môi trường:
- Folder tên `production` có thể làm Docker Compose project name bị trùng với stack Part 2. Nếu thấy image/container cũ hoặc endpoint `/chat` trả `404`, cần `docker compose down --remove-orphans` rồi chạy lại stack Part 5.
- `docker-compose.yml` có warning `version` obsolete, nhưng không chặn chạy.
- Tạo `.env.local` rỗng nếu Compose yêu cầu file này.

Kết quả `docker compose ps`:
```text
NAME                 IMAGE              COMMAND                  SERVICE   STATUS
production-agent-1   production-agent   "python -m uvicorn a..." agent     Up (healthy)
production-agent-2   production-agent   "python -m uvicorn a..." agent     Up (healthy)
production-agent-3   production-agent   "python -m uvicorn a..." agent     Up (healthy)
production-nginx-1   nginx:alpine       "/docker-entrypoint..."  nginx     Up, 0.0.0.0:8080->80/tcp
production-redis-1   redis:7-alpine     "docker-entrypoint.s..." redis     Up (healthy)
```

Health qua Nginx:
```bash
curl http://localhost:8080/health
```

Output:
```text
HTTP/1.1 200 OK
X-Served-By: 172.19.0.5:8000

{"status":"ok","uptime_seconds":10.4,"version":"2.0.0","timestamp":"2026-06-12T10:33:43.123335"}
```

Kết luận: Nginx load balancer expose `localhost:8080`, route traffic tới các agent instances, Redis healthy.

#### Exercise 5.5: Test stateless

Chạy:
```bash
python test_stateless.py
```

Output chính:
```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 28addfb0-dbaa-49bf-9e6d-d98d042a67ca

Request 1: [instance-e38ae2]
Request 2: [instance-b5423d]
Request 3: [instance-2c2036]
Request 4: [instance-e38ae2]
Request 5: [instance-b5423d]

Total requests: 5
Instances used: {'instance-e38ae2', 'instance-2c2036', 'instance-b5423d'}
All requests served despite different instances!

--- Conversation History ---
Total messages: 10
Session history preserved across all instances via Redis!
```

Test thêm failover nhẹ:
- Dừng một instance:
```bash
docker stop production-agent-2
```
- Gửi tiếp request cùng `session_id`:
```json
{"session_id":"28addfb0-dbaa-49bf-9e6d-d98d042a67ca","question":"Continue after one instance stopped","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","turn":7,"served_by":"instance-e38ae2","storage":"redis"}
```
- Kiểm tra history:
```text
history_count=12
```

Kết luận Exercise 5.5: stateless design hoạt động đúng. Nhiều instance cùng xử lý một session, một instance bị stop thì request tiếp theo vẫn thành công và history vẫn còn nhờ Redis.

Log agent rút gọn:
```text
agent-1 | Connected to Redis
agent-1 | Starting instance instance-b5423d
agent-1 | Storage: Redis
agent-2 | Starting instance instance-2c2036
agent-3 | Starting instance instance-e38ae2
agent-1 | POST /chat HTTP/1.1" 200 OK
agent-2 | POST /chat HTTP/1.1" 200 OK
agent-3 | POST /chat HTTP/1.1" 200 OK
```

Sau khi test xong đã chạy:
```bash
docker compose down
```

## Part 6: Final Project

### Production-ready agent implementation

Đã hoàn thiện final agent trong thư mục `06-lab-complete` theo yêu cầu của `CODE_LAB.md`.

Các thành phần chính:
- `app/main.py`: FastAPI app với `/health`, `/ready`, `/ask`, `/history/{user_id}`, `/metrics`.
- `app/config.py`: cấu hình theo environment variables, validate `AGENT_API_KEY` khi chạy production.
- `app/auth.py`: API key authentication bằng header `X-API-Key`.
- `app/rate_limiter.py`: sliding-window rate limit `10 req/min/user`, dùng Redis khi có `REDIS_URL`.
- `app/cost_guard.py`: cost guard `$10/tháng/user`, key theo tháng và có Redis backend.
- `app/storage.py`: lớp storage Redis với fallback memory cho local development.
- `Dockerfile`: multi-stage build, chạy non-root user, có healthcheck.
- `docker-compose.yml`: stack local gồm agent, Redis, Nginx load balancer.
- `railway.toml`: cấu hình Railway deploy bằng Dockerfile, healthcheck `/health`.

### Validation script

Chạy:
```bash
cd 06-lab-complete
python check_production_ready.py
```

Output:
```text
Result: 20/20 checks passed (100%)
PRODUCTION READY
```

### Local test

Đã chạy app local trên port riêng và test:
- `/health` trả `200 OK`.
- `/ready` trả `200 OK`.
- `/ask` không có API key trả `401`.
- `/ask` có API key trả `200 OK`.
- `/history/{user_id}` lưu và đọc lại được conversation history.

Ghi chú: local Docker validation của Part 6 chưa chạy được ở thời điểm test vì Docker Desktop không kết nối được Docker API pipe. Phần code và readiness script vẫn pass, sau đó đã deploy/test trực tiếp trên Railway.

### Railway deployment

Platform: Railway

Project:
```text
lab12-final-agent
```

Public URL:
```text
https://lab12-final-agent-production.up.railway.app
```

Railway services:
- `lab12-final-agent`: Online.
- `Redis`: Online, dùng làm backing service cho history, rate limit và cost guard.

Biến môi trường đã set trên Railway:
- `ENVIRONMENT=production`
- `AGENT_API_KEY=<set trong Railway variables>`
- `REDIS_URL=<Redis internal URL từ Railway>`
- `RATE_LIMIT_PER_MINUTE=10`
- `MONTHLY_BUDGET_USD=10.0`

Lỗi deploy đã gặp và cách sửa:
- Lần deploy đầu fail vì `startCommand` dùng `--port $PORT`; Railway truyền literal `$PORT` vào Uvicorn nên lỗi: `'$PORT' is not a valid integer`.
- Đã sửa `railway.toml` thành:
```toml
startCommand = "sh -c 'python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2'"
```

Sau khi redeploy:
```text
status: Online
url: https://lab12-final-agent-production.up.railway.app
deployment ID: abb06945-4983-4a76-9177-938d6b923cb1
```

### Public URL tests

Health check:
```bash
curl https://lab12-final-agent-production.up.railway.app/health
```

Output:
```json
{"status":"ok","version":"1.0.0","environment":"production","uptime_seconds":30.6,"total_requests":2,"checks":{"llm":"mock"},"timestamp":"2026-06-12T13:58:55.291756+00:00"}
```

Readiness check:
```bash
curl https://lab12-final-agent-production.up.railway.app/ready
```

Output:
```json
{"ready":true,"storage":"redis"}
```

Auth required:
```bash
curl -X POST https://lab12-final-agent-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"railway-test-nokey","question":"No key test"}'
```

Kết quả:
```text
401 Unauthorized
```

API test có authentication:
```bash
curl -X POST https://lab12-final-agent-production.up.railway.app/ask \
  -H "X-API-Key: <AGENT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"railway-test","question":"Hello from final Railway deploy"}'
```

Output rút gọn:
```json
{"user_id":"railway-test","question":"Hello from final Railway deploy","model":"gpt-4o-mini","history_length":2,"usage":{"user_id":"railway-test","month":"2026-06","cost_usd":0.000021,"budget_usd":10.0,"budget_remaining_usd":9.999979,"budget_used_pct":0.0}}
```

History test:
```bash
curl https://lab12-final-agent-production.up.railway.app/history/railway-test \
  -H "X-API-Key: <AGENT_API_KEY>"
```

Output rút gọn:
```json
{"user_id":"railway-test","count":2,"messages":[{"role":"user","content":"Hello from final Railway deploy"},{"role":"assistant","content":"Deployment là quá trình đưa code từ máy bạn lên server để người khác dùng được."}]}
```

Rate limit test:
```powershell
for ($i=1; $i -le 11; $i++) {
  # POST /ask với cùng user_id railway-limit-test
}
```

Output:
```text
1: 200
2: 200
3: 200
4: 200
5: 200
6: 200
7: 200
8: 200
9: 200
10: 200
11: 429
```

Kết luận Part 6: final agent đã đạt các yêu cầu chính: REST API hoạt động, có conversation history trong Redis, Docker multi-stage, config từ env vars, API key auth, rate limiting, cost guard, health/readiness checks, graceful shutdown, stateless design, structured JSON logging và public URL Railway hoạt động.
