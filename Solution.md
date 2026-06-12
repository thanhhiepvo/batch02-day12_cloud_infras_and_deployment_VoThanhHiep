# Day 12 — Solution (Parts 1–5)

**Student:** Vo Thanh Hiep  
**Repository:** `batch02-day12_cloud_infras_and_deployment_VoThanhHiep`

---

## Part 1: Localhost vs Production

### Exercise 1.1 — Anti-patterns trong `01-localhost-vs-production/develop/app.py`

| # | Vấn đề | Chi tiết |
|---|--------|----------|
| 1 | Hardcoded secrets | `OPENAI_API_KEY`, `DATABASE_URL` với password nằm trong source code |
| 2 | Không có config management | `DEBUG`, `MAX_TOKENS` cố định, không đọc từ env |
| 3 | Logging không an toàn | Dùng `print()` và log ra API key |
| 4 | Không có health check | Platform không biết khi nào container crash |
| 5 | Host/port cố định | `host="localhost"`, `port=8000`, `reload=True` — không chạy được trên cloud |
| 6 | Không graceful shutdown | Không xử lý SIGTERM |

### Exercise 1.2 — Chạy basic version

```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
curl -X POST "http://localhost:8000/ask?question=hello"
```

**Kết quả:** Agent chạy được trên localhost nhưng **không production-ready** (secrets, logging, health check, config).

### Exercise 1.3 — So sánh Basic vs Advanced

| Feature | Basic | Advanced | Tại sao quan trọng? |
|---------|-------|----------|---------------------|
| Config | Hardcode trong code | Environment variables (`config.py`) | Thay đổi theo môi trường, không commit secrets |
| Health check | ❌ Không có | ✅ `/health`, `/ready` | Platform restart/monitoring, load balancer routing |
| Logging | `print()` | Structured JSON logging | Dễ search, parse, tích hợp observability |
| Shutdown | Đột ngột | SIGTERM handler + uvicorn graceful timeout | Không mất request đang xử lý |
| Secrets | Trong source | `.env` + `.env.example` | Bảo mật, rotate key dễ dàng |
| Host binding | `localhost` | `0.0.0.0` | Container/cloud có thể nhận traffic từ bên ngoài |

---

## Part 2: Docker Containerization

### Exercise 2.1 — Dockerfile cơ bản

1. **Base image:** `python:3.11` (full Python image ~1 GB)
2. **Working directory:** `/app`
3. **COPY requirements.txt trước:** Tận dụng Docker layer cache — chỉ rebuild dependencies khi `requirements.txt` thay đổi
4. **CMD vs ENTRYPOINT:** CMD là command mặc định có thể override khi `docker run`; ENTRYPOINT là entry cố định, args từ `docker run` được append vào

### Exercise 2.2 — Build và run

```bash
# Build từ repo root (quan trọng!)
docker build -f 02-docker/develop/Dockerfile -t agent-develop .
docker run -p 8000:8000 agent-develop
```

**Image size:** ~1.67 GB (single-stage, full Python base)

### Exercise 2.3 — Multi-stage build

- **Stage 1 (builder):** Cài dependencies với gcc
- **Stage 2 (runtime):** Chỉ copy packages + code, dùng `python:3.11-slim`, non-root user

```bash
docker build -f 02-docker/production/Dockerfile -t production-agent .
```

**Image size:** ~262 MB (giảm ~85% so với develop)

### Exercise 2.4 — Docker Compose architecture

```
Client → Nginx (:80) → Agent (:8000) → Redis (:6379)
                          ↓
                    Qdrant (vector DB)
```

```bash
cd 02-docker/production
docker compose up -d --build
curl http://localhost/health
```

**Services:** `agent`, `redis`, `qdrant`, `nginx` — agent giao tiếp Redis qua internal network, client chỉ truy cập qua Nginx.

---

## Part 3: Cloud Deployment

### Exercise 3.1 — Railway

```bash
cd 03-cloud-deployment/railway
railway login
railway init
railway variables set AGENT_API_KEY=my-secret-key
railway up
railway domain
```

**Public URL (Part 3):**  
`https://courageous-playfulness-production-a67c.up.railway.app`

```bash
curl https://courageous-playfulness-production-a67c.up.railway.app/health
# {"status":"ok","uptime_seconds":...,"platform":"Railway",...}
```

### Exercise 3.2 — Render

```bash
# Push repo → Render Dashboard → New Blueprint → connect repo
# render.yaml tại 03-cloud-deployment/render/render.yaml
```

**So sánh `render.yaml` vs `railway.toml`:**

| | Railway (`railway.toml`) | Render (`render.yaml`) |
|--|--------------------------|------------------------|
| Format | TOML, minimal | YAML, Infrastructure as Code đầy đủ |
| Services | 1 service (web) | Web + Redis add-on |
| Env vars | CLI hoặc dashboard | Khai báo trong YAML + dashboard |
| Deploy | `railway up` (CLI) | Git push auto-deploy |
| Health check | `healthcheckPath` | `healthCheckPath` |

### Exercise 3.3 — GCP Cloud Run (Optional)

Đọc `03-cloud-deployment/production-cloud-run/cloudbuild.yaml`:
- **CI/CD pipeline:** Git push → Cloud Build → build image → deploy Cloud Run
- `service.yaml` định nghĩa service config (CPU, memory, concurrency)

---

## Part 4: API Security

### Exercise 4.1 — API Key authentication

- **Check ở đâu:** `verify_api_key()` dependency, header `X-API-Key`
- **Sai key:** HTTP 401 Unauthorized
- **Rotate key:** Đổi `AGENT_API_KEY` env var, restart/redeploy — không cần sửa code

```bash
cd 04-api-gateway/develop
AGENT_API_KEY=my-secret-key python test_auth.py
# ✓ All auth tests passed
```

### Exercise 4.2 — JWT authentication (Advanced)

```bash
cd 04-api-gateway/production
python test_advanced.py
```

**Flow:**
1. `POST /auth/token` với `{"username":"student","password":"demo123"}` → nhận JWT
2. Gọi `POST /ask` với `Authorization: Bearer <token>`

**Demo users:** `student/demo123` (10 req/min), `teacher/teach456` (admin, 100 req/min)

### Exercise 4.3 — Rate limiting

- **Algorithm:** Sliding window counter (deque timestamps trong memory)
- **Limit:** 10 requests/minute (user), 100 requests/minute (admin)
- **Admin bypass:** Dùng `rate_limiter_admin` thay vì `rate_limiter_user` trong `app.py`

### Exercise 4.4 — Cost guard

Logic trong `04-api-gateway/production/cost_guard.py`:
- Track input/output tokens per user per day
- Per-user budget: $1/day, global: $10/day
- HTTP 402 khi vượt user budget, HTTP 503 khi vượt global budget

```python
# Redis version (Part 6):
key = f"budget:{user_id}:{month_key}"
current = float(r.get(key) or 0)
if current + estimated_cost > MONTHLY_BUDGET:
    raise HTTPException(402, ...)
r.incrbyfloat(key, estimated_cost)
```

---

## Part 5: Scaling & Reliability

### Exercise 5.1 — Health checks

```python
@app.get("/health")   # Liveness — process còn sống
@app.get("/ready")    # Readiness — sẵn sàng nhận traffic (check Redis)
```

```bash
cd 05-scaling-reliability/develop
python test_health.py
# ✓ All health tests passed
```

### Exercise 5.2 — Graceful shutdown

- `signal.signal(signal.SIGTERM, handler)` log shutdown event
- FastAPI `lifespan` context manager: startup → ready → shutdown cleanup
- `uvicorn` `timeout_graceful_shutdown=30` — chờ requests hiện tại hoàn thành

### Exercise 5.3 — Stateless design

**Anti-pattern:** `conversation_history = {}` trong memory  
**Correct:** Lưu session trong Redis (`session:{id}`) — mọi instance đọc được

### Exercise 5.4 — Load balancing

```bash
cd 05-scaling-reliability/production
docker compose up -d --scale agent=3 --build
# Nginx :8080 → 3 agent instances
```

### Exercise 5.5 — Test stateless

```bash
python test_stateless.py
```

**Kết quả:** 5 requests qua 3 instances khác nhau (`instance-df7ae1`, `instance-9dcae6`, `instance-381c87`), conversation history vẫn đầy đủ 10 messages nhờ Redis.

---

## Tổng kết Parts 1–5

| Part | Status | Evidence |
|------|--------|----------|
| 1 | ✅ | So sánh develop vs production, chạy localhost |
| 2 | ✅ | Docker build, multi-stage, compose stack |
| 3 | ✅ | Railway URL hoạt động |
| 4 | ✅ | `test_auth.py`, `test_advanced.py` pass |
| 5 | ✅ | `test_health.py`, `test_stateless.py` pass |

**Part 6 (Final Project):** Xem `06-lab-complete/README.md`.

---

## Part 6: Final Project (Bonus trong Solution)

### Architecture

```
Client → Nginx (:80) → Agent x3 (:8000) → Redis (:6379)
```

### Local verification

```bash
cd 06-lab-complete
docker compose up -d --scale agent=3 --build
python3.12 test_lab_complete.py
python3.12 check_production_ready.py   # 20/20 checks
```

**Kết quả test (đã chạy):**
- ✅ `/health`, `/ready`
- ✅ API Key auth (401 without key)
- ✅ Conversation history qua Redis (stateless)
- ✅ Load balancing (2+ instances)
- ✅ Rate limiting (429 sau 10 req/min)
- ✅ Production readiness: 20/20

### Cloud deployment (Part 6 — LIVE)

| | |
|--|--|
| **URL** | https://courageous-playfulness-production-a67c.up.railway.app |
| **API Key** | `lab-complete-secret-key` (header `X-API-Key`) |
| **Platform** | Railway (deploy từ `06-lab-complete/`) |

```bash
# Health (public)
curl https://courageous-playfulness-production-a67c.up.railway.app/health

# Ask (requires API key)
curl -H "X-API-Key: lab-complete-secret-key" \
  -X POST https://courageous-playfulness-production-a67c.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello from production agent"}'

# Local (Docker Compose + Nginx)
curl http://localhost/health
curl -H "X-API-Key: lab-complete-secret-key" \
  -X POST http://localhost/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello from production agent"}'
```

**Lưu ý:** Trên Railway chạy 1 instance (không có Redis add-on) → `storage: in-memory`. Local Docker Compose dùng Redis + 3 instances + Nginx.
