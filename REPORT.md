# BÁO CÁO LAB — DAY 12: CLOUD INFRASTRUCTURE & DEPLOYMENT

| | |
|---|---|
| **Họ và tên** | Võ Thanh Hiệp |
| **Mã số sinh viên** | 2A202600836 |
| **Môn học** | AICB-P1 — AI & Cloud Basics |
| **Trường** | VinUniversity |
| **Lab** | Day 12 — Đưa AI Agent lên Production |
| **Repository** | [batch02-day12_cloud_infras_and_deployment_VoThanhHiep](https://github.com/thanhhiepvos/batch02-day12_cloud_infras_and_deployment_VoThanhHiep) |
| **Ngày nộp** | 12/06/2026 |

---

## 1. Mục tiêu

Lab Day 12 hướng đến việc đưa một AI Agent từ môi trường phát triển local lên môi trường production trên cloud, bao gồm:

- Hiểu sự khác biệt giữa development và production (12-Factor App)
- Containerize ứng dụng bằng Docker (multi-stage build, Docker Compose)
- Deploy lên nền tảng cloud (Railway, Render)
- Bảo mật API (authentication, rate limiting, cost guard)
- Thiết kế hệ thống scalable và reliable (stateless, health checks, load balancing)
- Xây dựng production-ready agent hoàn chỉnh (Part 6)

---

## 2. Tóm tắt kết quả

| Phần | Nội dung | Trạng thái |
|------|----------|------------|
| Part 1 | Localhost vs Production | ✅ Hoàn thành |
| Part 2 | Docker Containerization | ✅ Hoàn thành |
| Part 3 | Cloud Deployment (Railway, Render) | ✅ Hoàn thành |
| Part 4 | API Security | ✅ Hoàn thành |
| Part 5 | Scaling & Reliability | ✅ Hoàn thành |
| Part 6 | Final Production Agent | ✅ Hoàn thành + Deploy |

**Public API (Part 6):** https://courageous-playfulness-production-a67c.up.railway.app  
**API Key:** `lab-complete-secret-key` (header `X-API-Key`)

---

## 3. Chi tiết từng phần

### 3.1 Part 1 — Localhost vs Production

**Mục tiêu:** Nhận diện anti-patterns trong code “localhost” và so sánh với phiên bản production.

**Công việc đã thực hiện:**
- Phân tích `01-localhost-vs-production/develop/app.py` và liệt kê 6 vấn đề: hardcoded secrets, thiếu config management, logging không an toàn, không có health check, host/port cố định, không graceful shutdown.
- Chạy thử basic version trên `localhost:8000`.
- So sánh với advanced version trong `production/`: config từ env vars, JSON logging, `/health` + `/ready`, SIGTERM handler, bind `0.0.0.0`.

**Bài học rút ra:** Code chạy được trên máy cá nhân chưa đủ điều kiện deploy production. Cần tách config, secrets, logging và health probes ngay từ đầu.

---

### 3.2 Part 2 — Docker Containerization

**Mục tiêu:** Đóng gói agent vào container, tối ưu image size, chạy full stack với Docker Compose.

**Công việc đã thực hiện:**
- Build single-stage image (`agent-develop`) từ repo root: ~1.67 GB.
- Build multi-stage image (`production-agent`): ~262 MB (giảm ~85%).
- Chạy production stack: Agent + Redis + Qdrant + Nginx.

**Kiến trúc:**

```
Client → Nginx (:80) → Agent (:8000) → Redis / Qdrant
```

**Lệnh build quan trọng:**

```bash
docker build -f 02-docker/develop/Dockerfile -t agent-develop .
docker build -f 02-docker/production/Dockerfile -t production-agent .
cd 02-docker/production && docker compose up -d --build
```

---

### 3.3 Part 3 — Cloud Deployment

**Mục tiêu:** Deploy agent lên cloud và có public URL hoạt động.

**Công việc đã thực hiện:**
- Deploy lên **Railway** qua CLI (`railway login`, `railway init`, `railway up`, `railway domain`).
- Cấu hình **Render** với `render.yaml` (Blueprint, web service + Redis add-on).
- So sánh Railway (`railway.toml`, TOML, CLI deploy) và Render (`render.yaml`, YAML IaC, Git auto-deploy).

**Kết quả kiểm tra:**

```bash
curl https://courageous-playfulness-production-a67c.up.railway.app/health
# {"status":"ok", ...}
```

---

### 3.4 Part 4 — API Security

**Mục tiêu:** Bảo vệ API khỏi truy cập trái phép và chi phí LLM không kiểm soát.

**Công việc đã thực hiện:**

| Tính năng | Develop | Production |
|-----------|---------|------------|
| Authentication | API Key (`X-API-Key`) | JWT (`/auth/token`) |
| Rate limiting | — | Sliding window: 10 req/min (user), 100 req/min (admin) |
| Cost guard | — | Budget tracking, HTTP 402/503 |

**Kết quả test:**

```bash
cd 04-api-gateway/develop && AGENT_API_KEY=my-secret-key python test_auth.py      # ✅ Pass
cd 04-api-gateway/production && python test_advanced.py                            # ✅ Pass
```

---

### 3.5 Part 5 — Scaling & Reliability

**Mục tiêu:** Thiết kế agent stateless, có health probes, graceful shutdown và load balancing.

**Công việc đã thực hiện:**
- Implement `/health` (liveness) và `/ready` (readiness, kiểm tra Redis).
- SIGTERM handler + FastAPI lifespan cho graceful shutdown.
- Lưu conversation history trong Redis thay vì in-memory.
- Scale 3 agent instances phía sau Nginx (`docker compose up --scale agent=3`).

**Kết quả `test_stateless.py`:**
- 5 requests được phân phối qua 3 instances khác nhau.
- Conversation history (10 messages) được giữ nguyên nhờ Redis.

---

### 3.6 Part 6 — Final Production Agent

**Mục tiêu:** Kết hợp tất cả concepts vào một project production-ready, deploy lên cloud.

**Cấu trúc project (`06-lab-complete/`):**

```
06-lab-complete/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── config.py        # 12-factor config
│   ├── auth.py          # API Key authentication
│   ├── session.py       # Redis session / conversation history
│   ├── rate_limiter.py  # Redis sliding window (10 req/min)
│   └── cost_guard.py    # Monthly budget ($10/user)
├── utils/mock_llm.py
├── Dockerfile           # Multi-stage, non-root, < 500 MB
├── docker-compose.yml   # Agent x3 + Redis + Nginx
├── railway.toml / render.yaml
└── test_lab_complete.py
```

**Kiến trúc production:**

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       ▼
┌─────────────────┐
│  Nginx (LB)     │  :80
└──────┬──────────┘
       ├─────────┬─────────┐
       ▼         ▼         ▼
   Agent 1   Agent 2   Agent 3
       │         │         │
       └─────────┴─────────┘
                 ▼
           ┌──────────┐
           │  Redis   │
           └──────────┘
```

**Tính năng đã implement:**

| Yêu cầu | Trạng thái |
|---------|------------|
| REST API `/ask` + conversation history | ✅ |
| Docker multi-stage build | ✅ |
| Config từ environment variables | ✅ |
| API Key authentication | ✅ |
| Rate limiting (10 req/min) | ✅ |
| Cost guard ($10/month) | ✅ |
| `/health` + `/ready` | ✅ |
| Graceful shutdown (SIGTERM) | ✅ |
| Stateless design (Redis) | ✅ (local); in-memory trên Railway 1 instance |
| Structured JSON logging | ✅ |
| Deploy cloud + public URL | ✅ |

**Kết quả test local:**

```bash
cd 06-lab-complete
docker compose up -d --scale agent=3 --build
python3.12 test_lab_complete.py        # ✅ All tests passed
python3.12 check_production_ready.py   # ✅ 20/20 checks
```

**Deploy Railway (Part 6):**

| Thông tin | Giá trị |
|-----------|---------|
| URL | https://courageous-playfulness-production-a67c.up.railway.app |
| Platform | Railway |
| API Key | `lab-complete-secret-key` |
| Health check | `GET /health` → 200 |

```bash
# Kiểm tra production
curl https://courageous-playfulness-production-a67c.up.railway.app/health

curl -H "X-API-Key: lab-complete-secret-key" \
  -X POST https://courageous-playfulness-production-a67c.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is cloud deployment?"}'
```

---

## 4. Khó khăn gặp phải và cách xử lý

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-------------|-----------|
| Docker build fail | Build context sai (không chạy từ repo root) | `docker build -f <path/Dockerfile> -t <tag> .` từ root |
| Agent container restart loop | Python packages copy sai path (`/home/agent` vs `/app`) | Copy packages vào `/app/.local`, set `PATH` đúng |
| Railway deploy fail | `$PORT` không expand trong `startCommand` | Dùng shell form: `sh -c "uvicorn ... --port ${PORT:-8000}"` |
| Rate limit không hoạt động trên Redis | Redis ZADD key collision cùng timestamp | Thêm UUID vào member key |
| Port conflict giữa các parts | Part 2 dùng :80, Part 5 dùng :8080 | Chạy từng stack riêng, `docker compose down` khi chuyển part |

---

## 5. Kết luận

Qua lab Day 12, em đã hoàn thành đầy đủ 6 phần từ nhận diện anti-patterns localhost đến deploy production agent lên Railway. Các kỹ năng chính đạt được:

1. **Production mindset** — Config qua env vars, không hardcode secrets, structured logging.
2. **Containerization** — Multi-stage Docker, image tối ưu, Docker Compose orchestration.
3. **Cloud deployment** — Railway CLI, Render Blueprint, public URL hoạt động.
4. **Security** — API Key, JWT, rate limiting, cost guard.
5. **Scalability** — Stateless design với Redis, Nginx load balancing, health/readiness probes.

Final project (`06-lab-complete/`) kết hợp toàn bộ concepts trên và đã được verify bằng automated tests cũng như deploy thực tế lên cloud.

---

## 6. Tài liệu tham khảo

- `CODE_LAB.md` — Hướng dẫn lab chi tiết
- `Solution.md` — Đáp án exercises Parts 1–5
- `06-lab-complete/README.md` — Hướng dẫn chạy và deploy final project
- [Railway Docs](https://docs.railway.app/)
- [Render Blueprint Spec](https://render.com/docs/blueprint-spec)
- [12-Factor App](https://12factor.net/)

---

**Võ Thanh Hiệp — 2A202600836**
