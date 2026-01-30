# 🏗️ Email Draft Generator - Architecture Diagrams

## 📊 High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                         USER'S BROWSER                             │
│                  http://localhost:8000                             │
└────────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP Request
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                      DOCKER CONTAINER                              │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                   FastAPI Application                        │ │
│  │                  (api.py - Port 8000)                       │ │
│  │                                                              │ │
│  │  Endpoints:                                                  │ │
│  │  • /fetch-threads     → Fetch Gmail conversations          │ │
│  │  • /generate-email    → Generate email with LLM            │ │
│  │  • /history          → Retrieve saved emails               │ │
│  │  • /stats            → Get statistics                      │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│         ┌────────────────────┼────────────────────┐              │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌─────────────┐     ┌──────────────┐    ┌─────────────────┐   │
│  │ database.py │     │  graph.py    │    │email_provider.py│   │
│  │             │     │              │    │                 │   │
│  │ • Save      │     │ • LangGraph  │    │ • Gmail API     │   │
│  │ • Update    │     │ • Intent     │    │ • OAuth         │   │
│  │ • Retrieve  │     │ • Generate   │    │ • Fetch threads │   │
│  │ • Delete    │     │   email      │    │ • Parse emails  │   │
│  └─────────────┘     └──────────────┘    └─────────────────┘   │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌─────────────┐     ┌──────────────┐    ┌─────────────────┐   │
│  │   SQLite    │     │ AWS Bedrock  │    │  Gmail API      │   │
│  │  Database   │     │     LLM      │    │  (External)     │   │
│  │             │     │  (External)  │    │                 │   │
│  │ /app/data/  │     │              │    │/app/credentials/│   │
│  └─────────────┘     └──────────────┘    └─────────────────┘   │
│         │                    │                    │              │
│         │ Volume Mount       │ Internet           │ Volume Mount│
└─────────┼────────────────────┼────────────────────┼─────────────┘
          │                    │                    │
          ▼                    │                    ▼
    ┌──────────┐              │              ┌──────────────┐
    │  ./data/ │              │              │./credentials/│
    │    ├─email_history.db   │              │  ├─credentials.json
    │                          │              │  └─token.json
    └──────────┘              │              └──────────────┘
                              │
                              │
                    ┌─────────┴─────────┐
                    │                   │
              ┌─────▼──────┐    ┌──────▼─────┐
              │  AWS       │    │  Google    │
              │  Bedrock   │    │  Gmail API │
              └────────────┘    └────────────┘
```

---

## 🔄 Data Flow Diagram

### 1️⃣ Email Fetching Flow

```
┌─────────┐
│  User   │
└────┬────┘
     │ POST /fetch-threads
     │ email_addresses: "john@example.com"
     │
     ▼
┌────────────────┐
│  api.py        │
│  FastAPI       │
└────┬───────────┘
     │
     │ fetch_threads(email, provider)
     │
     ▼
┌────────────────────┐
│ email_provider.py  │
│                    │
│ 1. Read credentials│──→ /app/credentials/credentials.json
│ 2. Check OAuth     │──→ /app/credentials/token.json
│                    │     (if missing, start OAuth)
│ 3. Call Gmail API  │──→ Internet → Gmail API
│ 4. Fetch emails    │
│ 5. Group threads   │
└────┬───────────────┘
     │
     │ Return: [threads array]
     │
     ▼
┌────────────────┐
│  api.py        │
│  FastAPI       │
└────┬───────────┘
     │
     │ JSON Response
     │
     ▼
┌─────────┐
│  User   │
└─────────┘
```

### 2️⃣ Email Generation Flow

```
┌─────────┐
│  User   │
└────┬────┘
     │ POST /generate-email
     │ thread_id: "abc123"
     │ email_goal: "Follow up on meeting"
     │
     ▼
┌────────────────┐
│  api.py        │
│  FastAPI       │
└────┬───────────┘
     │
     │ generate_email_from_thread(...)
     │
     ▼
┌────────────────┐
│  graph.py      │
│  LangGraph     │
│                │
│ 1. Get thread  │──→ email_provider.py
│ 2. Extract     │
│    intent      │
│ 3. Format      │
│    context     │
│ 4. Call LLM    │──→ AWS Bedrock API
│                │    (GPT-OSS-20B)
│ 5. Parse       │
│    response    │
└────┬───────────┘
     │
     │ Return: {subject, email, intent}
     │
     ▼
┌────────────────┐
│  api.py        │
│  FastAPI       │
└────┬───────────┘
     │
     │ save_generation(...)
     │
     ▼
┌────────────────┐
│  database.py   │
│                │
│ 1. Open DB     │──→ /app/data/email_history.db
│ 2. Insert      │    (SQLite)
│    session     │
│ 3. Update      │
│    stats       │
│ 4. Commit      │
└────┬───────────┘
     │
     │ session_id
     │
     ▼
┌────────────────┐
│  api.py        │
│  FastAPI       │
└────┬───────────┘
     │
     │ JSON Response
     │ {subject, email, session_id}
     │
     ▼
┌─────────┐
│  User   │
└─────────┘
```

### 3️⃣ Database Persistence Flow

```
┌──────────────────────────────────────────────────┐
│              INSIDE CONTAINER                    │
│                                                  │
│  Application writes to:                          │
│  /app/data/email_history.db                     │
│                                                  │
└──────────────────┬───────────────────────────────┘
                   │
                   │ Docker Volume Mount
                   │ (Bidirectional sync)
                   │
┌──────────────────▼───────────────────────────────┐
│              ON HOST MACHINE                     │
│                                                  │
│  File appears at:                                │
│  ./data/email_history.db                        │
│                                                  │
│  Changes are:                                    │
│  • Instant                                       │
│  • Bidirectional                                 │
│  • Persistent (survives container restart)       │
│                                                  │
└──────────────────────────────────────────────────┘

  Even if container is deleted:
  ────────────────────────────────
  ✓ ./data/email_history.db remains
  ✓ New container can use existing DB
  ✓ No data loss!
```

---

## 🎭 Container Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    CONTAINER LIFECYCLE                      │
└─────────────────────────────────────────────────────────────┘

1. BUILD IMAGE
   │
   ├─→ docker-compose build
   │
   ├─→ Reads Dockerfile
   │   ├─→ FROM python:3.11-slim
   │   ├─→ COPY requirements.txt
   │   ├─→ RUN pip install
   │   ├─→ COPY application files
   │   └─→ CMD ["python", "api.py"]
   │
   └─→ Image created: email-draft-generator_email-generator

2. CREATE CONTAINER
   │
   ├─→ docker-compose up -d
   │
   ├─→ Reads docker-compose.yml
   │   ├─→ Uses image from step 1
   │   ├─→ Mounts volumes
   │   │   ├─→ ./data → /app/data
   │   │   └─→ ./credentials → /app/credentials
   │   ├─→ Maps ports: 8000:8000
   │   ├─→ Loads .env variables
   │   └─→ Connects to network
   │
   └─→ Container created: email-draft-generator

3. START APPLICATION
   │
   ├─→ Container runs: python api.py
   │
   ├─→ Application initializes
   │   ├─→ Load environment variables
   │   ├─→ Initialize database (/app/data/)
   │   ├─→ Setup Gmail API client
   │   ├─→ Connect to AWS Bedrock
   │   └─→ Start uvicorn server (0.0.0.0:8000)
   │
   └─→ Application ready

4. RUNTIME
   │
   ├─→ Accepts HTTP requests on port 8000
   ├─→ Processes API calls
   ├─→ Writes to database (persisted to host)
   ├─→ Reads credentials (from host)
   └─→ Logs visible via: docker-compose logs

5. STOP/RESTART
   │
   ├─→ docker-compose down
   │   ├─→ Container stops
   │   ├─→ Container removed
   │   └─→ Volumes remain (data persists!)
   │
   ├─→ docker-compose up -d (restart)
   │   ├─→ New container created
   │   ├─→ Mounts existing volumes
   │   └─→ Finds existing DB & credentials
   │
   └─→ No data loss!

6. UPDATE/REBUILD
   │
   ├─→ Code changes on host
   ├─→ docker-compose up -d --build
   │   ├─→ Rebuilds image with new code
   │   ├─→ Stops old container
   │   ├─→ Creates new container
   │   └─→ Mounts same volumes (data preserved)
   │
   └─→ Updated application with preserved data!
```

---

## 🗂️ File System Structure

### Inside Container
```
/app/                              (Working directory)
├── api.py                         (Copied from host)
├── database.py                    (Copied from host)
├── email_provider.py              (Copied from host)
├── graph.py                       (Copied from host)
├── index.html                     (Copied from host)
├── requirements.txt               (Copied from host)
├── data/                          (Volume mounted)
│   └── email_history.db           ← Created by application
└── credentials/                   (Volume mounted)
    ├── credentials.json           ← Provided by user
    └── token.json                 ← Generated after OAuth
```

### On Host
```
./email-draft-generator/
├── api.py                         ← Your code
├── database.py                    ← Your code
├── email_provider.py              ← Your code
├── graph.py                       ← Your code
├── index.html                     ← Your code
├── Dockerfile                     ← Docker config
├── docker-compose.yml             ← Docker config
├── requirements.txt               ← Dependencies
├── .env                           ← Secrets (create from .env.example)
├── .env.example                   ← Template
├── data/                          ← Persistent data
│   └── email_history.db           ← SQLite database
└── credentials/                   ← OAuth files
    ├── credentials.json           ← Gmail OAuth (you provide)
    └── token.json                 ← Generated
```

---

## 🔐 Network & Security Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                        HOST NETWORK                            │
│                                                                │
│  localhost:8000 ←─────── Port Mapping ─────┐                 │
│                                             │                 │
└─────────────────────────────────────────────┼─────────────────┘
                                              │
                                              │
┌─────────────────────────────────────────────┼─────────────────┐
│              DOCKER BRIDGE NETWORK          │                 │
│         (email-draft-generator_email-network)                 │
│                                             │                 │
│  ┌───────────────────────────────────────┐ │                 │
│  │        Container                      │ │                 │
│  │   email-draft-generator              │ │                 │
│  │                                       │ │                 │
│  │   Listens on: 0.0.0.0:8000 ──────────┘                    │
│  │                                       │                    │
│  │   Outbound connections:               │                    │
│  │   ├─→ gmail.googleapis.com (443)      │───┐               │
│  │   ├─→ bedrock-runtime.*.amazonaws.com │   │               │
│  │   └─→ Other internet services         │   │               │
│  │                                       │   │               │
│  └───────────────────────────────────────┘   │               │
│                                               │               │
└───────────────────────────────────────────────┼───────────────┘
                                                │
                                                │
                                         ┌──────▼──────┐
                                         │  INTERNET   │
                                         │             │
                                         │ • Gmail API │
                                         │ • AWS       │
                                         └─────────────┘
```

### Security Layers

1. **Container Isolation**
   - Application runs in isolated environment
   - Cannot access host filesystem (except volumes)
   - Own network namespace

2. **Volume Mounts** (Controlled Access)
   - Only ./data and ./credentials mapped
   - Read/write controlled by Docker
   - Other host files inaccessible

3. **Port Mapping**
   - Only port 8000 exposed
   - Other container ports not accessible from host
   - Can restrict to localhost only

4. **Secrets Management**
   - Credentials in .env (not in image)
   - OAuth tokens in volume (not in image)
   - Environment variables isolated per container

---

## 📊 Resource Usage

```
┌────────────────────────────────────────────────────────────────┐
│                    RESOURCE ALLOCATION                         │
└────────────────────────────────────────────────────────────────┘

Memory:
├─→ Base OS (Python + dependencies): ~200MB
├─→ Application code: ~50MB
├─→ Runtime overhead: ~100MB
└─→ Working memory: ~150MB
    ────────────────────────────────
    Total: ~500MB typical usage

Disk:
├─→ Docker image: ~1.5GB
├─→ Database: Grows with usage (~10MB per 1000 emails)
├─→ Logs: Depends on retention
└─→ Temporary files: Minimal
    ────────────────────────────────
    Total: ~2GB + database size

CPU:
├─→ Idle: <1% CPU
├─→ Processing request: 10-30% CPU
├─→ LLM call (waiting): Minimal
└─→ Concurrent requests: Scales with requests

Network:
├─→ Inbound: HTTP requests from user
├─→ Outbound: Gmail API + AWS Bedrock
└─→ Bandwidth: ~1-5MB per email generation
```

---

## 🎯 Component Interactions

```
┌────────────────────────────────────────────────────────────────┐
│                   COMPONENT INTERACTION MAP                    │
└────────────────────────────────────────────────────────────────┘

api.py (FastAPI Server)
  │
  ├─→ Calls: email_provider.py
  │   └─→ Returns: Email threads
  │
  ├─→ Calls: graph.py
  │   ├─→ Calls: email_provider.py (for context)
  │   ├─→ Calls: AWS Bedrock (external)
  │   └─→ Returns: Generated email
  │
  ├─→ Calls: database.py
  │   ├─→ Opens: /app/data/email_history.db
  │   ├─→ Executes: SQL queries
  │   └─→ Returns: Session data
  │
  └─→ Serves: index.html (static file)

email_provider.py (Gmail Integration)
  │
  ├─→ Reads: /app/credentials/credentials.json
  ├─→ Reads: /app/credentials/token.json
  ├─→ Calls: Gmail API (external)
  └─→ Returns: Processed email data

graph.py (LangGraph Workflow)
  │
  ├─→ Uses: LangChain libraries
  ├─→ Calls: AWS Bedrock (external)
  └─→ Returns: LLM-generated content

database.py (SQLite Operations)
  │
  ├─→ Opens: /app/data/email_history.db
  ├─→ Executes: SQL operations
  └─→ Returns: Query results

Environment Variables (from .env)
  │
  ├─→ Read by: api.py
  ├─→ Read by: graph.py (AWS credentials)
  └─→ Read by: email_provider.py (OAuth paths)
```

---

## 🔄 OAuth Flow Diagram

```
First Time Gmail Authentication:
════════════════════════════════

1. User starts container
   │
   ▼
2. Application checks /app/credentials/token.json
   │
   ├─→ Found? → Use existing token → Done! ✓
   │
   └─→ Not found? → Start OAuth flow ↓

3. Generate OAuth URL
   │
   ├─→ Read /app/credentials/credentials.json
   ├─→ Create authorization URL
   └─→ Print to logs: "Visit this URL..."

4. User copies URL
   │
   └─→ Opens in browser

5. Google Login Page
   │
   ├─→ User signs in
   └─→ Grant permissions

6. Google redirects to localhost
   │
   └─→ Application receives code

7. Application exchanges code for token
   │
   ├─→ Calls Google OAuth endpoint
   ├─→ Receives access + refresh tokens
   └─→ Saves to /app/credentials/token.json
       (persisted via volume mount)

8. Authentication complete ✓
   │
   └─→ Future runs use saved token
```

---

This comprehensive architecture documentation shows how all components interact within the Docker environment and with external services!