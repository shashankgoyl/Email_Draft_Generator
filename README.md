# Email Draft Generator - Docker Deployment

A containerized Email Draft Generator application with Gmail integration, AWS Bedrock LLM, and SQLite database persistence.

## 🎯 Features

- **Multi-address email support**: Handle multiple email addresses simultaneously
- **Automatic intent extraction**: LLM-powered conversation analysis
- **Gmail integration**: Fetch and analyze email threads
- **AWS Bedrock LLM**: GPT-OSS-20B model for email generation
- **SQLite database**: Persistent storage for email history
- **Full CRUD operations**: Create, read, update, and delete email drafts
- **Dockerized deployment**: Easy setup and scalability

## 📦 What's Included

```
email-draft-generator/
├── api.py                  # FastAPI application
├── database.py             # SQLite database module
├── email_provider.py       # Gmail API integration
├── graph.py                # LangGraph workflow
├── index.html              # Frontend interface
├── Dockerfile              # Container definition
├── docker-compose.yml      # Container orchestration
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
├── .dockerignore          # Docker ignore rules
├── deploy.sh              # Automated deployment script
├── DEPLOYMENT_GUIDE.md    # Detailed deployment guide
├── README.md              # This file
├── data/                  # Database storage (created)
│   └── email_history.db   # SQLite database (auto-created)
└── credentials/           # Gmail OAuth files (created)
    ├── credentials.json   # Gmail OAuth credentials (you provide)
    └── token.json         # OAuth token (auto-generated)
```

## 🏗️ Architecture

### Container Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Docker Container                       │
│  ┌────────────────────────────────────────────────────┐ │
│  │            FastAPI Application                     │ │
│  │         (api.py - Port 8000)                      │ │
│  └────────────────────────────────────────────────────┘ │
│                         │                                │
│         ┌───────────────┼───────────────┐               │
│         ▼               ▼               ▼               │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐       │
│  │database.py│   │ graph.py │   │email_provider│       │
│  │  SQLite  │   │LangGraph │   │  Gmail API   │       │
│  └──────────┘   └──────────┘   └──────────────┘       │
│         │               │               │               │
│         ▼               ▼               ▼               │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐       │
│  │  Volume  │   │AWS Bedrock│   │   Volume    │       │
│  │/app/data/│   │   LLM    │   │/app/creds/  │       │
│  └──────────┘   └──────────┘   └──────────────┘       │
└──────────────────────────────────────────────────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
  ./data/          External Service    ./credentials/
```

### Data Flow

```
1. User Request → FastAPI (api.py)
                     ↓
2. Fetch Emails → email_provider.py → Gmail API
                     ↓
3. Process → graph.py → LangGraph Workflow
                     ↓
4. LLM Analysis → AWS Bedrock (GPT-OSS-20B)
                     ↓
5. Generate Email → Response
                     ↓
6. Save History → database.py → SQLite (./data/email_history.db)
```

### Volume Persistence

Docker volumes ensure data persists across container restarts:

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `./data/` | `/app/data/` | SQLite database storage |
| `./credentials/` | `/app/credentials/` | Gmail OAuth credentials |

## 🚀 Quick Start

### Prerequisites

1. **Docker & Docker Compose** installed
2. **AWS Account** with Bedrock access
3. **Gmail OAuth Credentials** from Google Cloud Console

### One-Command Deployment

```bash
# Make deployment script executable (if not already)
chmod +x deploy.sh

# Run automated deployment
./deploy.sh
```

The script will:
- ✅ Check prerequisites
- ✅ Create required directories
- ✅ Verify all files are present
- ✅ Set up environment variables
- ✅ Build Docker image
- ✅ Start container
- ✅ Verify health status

### Manual Deployment

If you prefer manual control:

```bash
# 1. Create directories
mkdir -p data credentials

# 2. Configure environment
cp .env.example .env
nano .env  # Add your AWS credentials

# 3. Add Gmail credentials
cp /path/to/credentials.json ./credentials/

# 4. Build and start
docker-compose build
docker-compose up -d

# 5. Check status
docker-compose ps
curl http://localhost:8000/health
```

## 🔧 Configuration

### Environment Variables

Edit `.env` file:

```bash
# AWS Configuration (Required)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=eu-west-2

# LLM Configuration
LLM_MODEL=gpt-oss-20b

# Database
DB_FILE=/app/data/email_history.db

# Gmail OAuth
GOOGLE_CREDENTIALS_PATH=/app/credentials/credentials.json
GOOGLE_TOKEN_PATH=/app/credentials/token.json
```

### Gmail Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Gmail API**
4. Create **OAuth 2.0 credentials** (Desktop app type)
5. Download as `credentials.json`
6. Place in `./credentials/` directory

**First Run Authentication:**
- Container will generate an OAuth URL
- Check logs: `docker-compose logs -f`
- Open URL in browser
- Grant permissions
- Token saved to `./credentials/token.json`

## 📡 API Endpoints

Once deployed, access these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info and available endpoints |
| `/health` | GET | Health check |
| `/fetch-threads` | POST | Fetch email threads for addresses |
| `/generate-email` | POST | Generate email from thread |
| `/generate-multiple` | POST | Generate emails for multiple addresses |
| `/history` | GET | Retrieve email history |
| `/history/{id}` | GET | Get specific session |
| `/history/{id}` | PUT | Update session |
| `/history/{id}` | DELETE | Delete session |
| `/history/clear` | POST | Clear all history |
| `/stats` | GET | Get statistics |

## 🌐 Access Points

After successful deployment:

- **API:** http://localhost:8000
- **Interactive Docs:** http://localhost:8000/docs (Swagger UI)
- **Frontend:** http://localhost:8000/index.html
- **Health Check:** http://localhost:8000/health

## 🐳 Docker Commands

### Basic Operations

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs (real-time)
docker-compose logs -f

# View logs (last 100 lines)
docker-compose logs --tail=100
```

### Container Management

```bash
# Check status
docker-compose ps

# Shell into container
docker exec -it email-draft-generator bash

# View resource usage
docker stats email-draft-generator
```

### Database Operations

```bash
# Backup database
docker exec email-draft-generator \
  cp /app/data/email_history.db /app/data/backup_$(date +%Y%m%d).db

# Copy database to host
docker cp email-draft-generator:/app/data/email_history.db \
  ./email_history_backup.db

# View database
docker exec -it email-draft-generator \
  sqlite3 /app/data/email_history.db
```

## 🔍 How It Works

### 1. Email Fetching
```
User provides email address
  ↓
Gmail API fetches conversations
  ↓
Emails grouped into threads
  ↓
Threads organized by date
```

### 2. Intent Extraction
```
Thread conversation history
  ↓
LLM analyzes context
  ↓
Auto-extracts intent (reply/follow_up/reminder/inquiry)
  ↓
No manual selection needed
```

### 3. Email Generation
```
Thread context + User goal
  ↓
LangGraph workflow
  ↓
AWS Bedrock LLM (GPT-OSS-20B)
  ↓
Generated email with subject & body
```

### 4. Database Storage
```
Generated email
  ↓
SQLite database (email_history.db)
  ↓
Persistent storage in Docker volume
  ↓
Survives container restarts
```

## 📊 Database Schema

### Sessions Table
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    email_address TEXT NOT NULL,
    thread_subject TEXT,
    intent TEXT,
    subject TEXT,
    email_body TEXT,
    tone TEXT DEFAULT 'professional',
    selected_email_index INTEGER,
    email_goal TEXT,
    thread_email_count INTEGER DEFAULT 0,
    last_modified TEXT NOT NULL,
    is_new_email BOOLEAN DEFAULT 0
);
```

### Statistics Table
```sql
CREATE TABLE statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_generations INTEGER DEFAULT 0
);
```

## 🔐 Security

### Best Practices

1. **Never commit credentials:**
   ```bash
   echo ".env" >> .gitignore
   echo "credentials/" >> .gitignore
   ```

2. **Restrict permissions:**
   ```bash
   chmod 600 credentials/credentials.json
   chmod 600 credentials/token.json
   ```

3. **Use secrets management** (production):
   - AWS Secrets Manager
   - Docker Secrets
   - Kubernetes Secrets

4. **Limit network access** (production):
   ```yaml
   ports:
     - "127.0.0.1:8000:8000"  # localhost only
   ```

## 🐛 Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs

# Common issues:
# 1. Port 8000 in use
sudo lsof -i :8000  # Find process
sudo kill -9 <PID>   # Kill process

# 2. Invalid environment variables
docker-compose config  # Validate
```

### Database issues

```bash
# Check volume mount
docker inspect email-draft-generator | grep Mounts -A 20

# Verify database exists
docker exec email-draft-generator ls -la /app/data/

# Check permissions
docker exec email-draft-generator ls -la /app/data/email_history.db
```

### Gmail authentication

```bash
# Check credentials
docker exec email-draft-generator ls -la /app/credentials/

# Re-authenticate
rm ./credentials/token.json
docker-compose restart
docker-compose logs -f  # Watch for OAuth URL
```

### AWS Bedrock errors

```bash
# Test AWS connection
docker exec email-draft-generator \
  python -c "import boto3; print(boto3.client('bedrock-runtime', region_name='eu-west-2'))"

# Verify environment
docker exec email-draft-generator env | grep AWS
```

## 📈 Monitoring

### Health Checks

```bash
# Manual health check
curl http://localhost:8000/health | jq

# Continuous monitoring
watch -n 30 'curl -s http://localhost:8000/health | jq'

# Check container health
docker-compose ps
```

### Logs

```bash
# Real-time logs
docker-compose logs -f email-generator

# Filter by error
docker-compose logs email-generator | grep ERROR

# Last hour of logs
docker-compose logs --since 1h email-generator
```

### Resource Usage

```bash
# CPU, Memory, Network, Disk I/O
docker stats email-draft-generator

# Disk usage
docker system df
```

## 🔄 Updating

### Update Application Code

```bash
# 1. Stop container
docker-compose down

# 2. Update code files (api.py, etc.)

# 3. Rebuild and restart
docker-compose up -d --build

# 4. Verify
curl http://localhost:8000/health
```

### Update Dependencies

```bash
# Edit requirements.txt
nano requirements.txt

# Rebuild without cache
docker-compose build --no-cache

# Restart
docker-compose up -d
```

## 💾 Backup & Restore

### Automated Backup Script

```bash
#!/bin/bash
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup database
docker cp email-draft-generator:/app/data/email_history.db "$BACKUP_DIR/"

# Backup credentials
cp -r credentials "$BACKUP_DIR/"

# Backup environment
cp .env "$BACKUP_DIR/"

echo "Backup completed: $BACKUP_DIR"
```

### Restore

```bash
# Stop container
docker-compose down

# Restore files
cp backups/20240130_120000/email_history.db ./data/
cp -r backups/20240130_120000/credentials ./

# Start container
docker-compose up -d
```

## 🌍 Production Deployment

### With Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### With SSL (Let's Encrypt)

```bash
sudo certbot --nginx -d yourdomain.com
```

### Scaling

For production scaling:
- Use **Docker Swarm** for multi-node deployment
- Or **Kubernetes** for complex orchestration
- Add **load balancer** for multiple instances
- Use **external database** (PostgreSQL) instead of SQLite

## 📚 Documentation

- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Detailed deployment instructions
- [API Documentation](http://localhost:8000/docs) - Interactive API docs
- [Docker Documentation](https://docs.docker.com/)
- [Gmail API Guide](https://developers.google.com/gmail/api)
- [AWS Bedrock Docs](https://docs.aws.amazon.com/bedrock/)

## 🤝 Support

### Common Issues

1. **Port 8000 in use**: Change port in `docker-compose.yml`
2. **Permission denied**: Run `chmod 755 data credentials`
3. **Database locked**: Only run one container instance
4. **Gmail auth fails**: Regenerate `credentials.json`

### Debug Mode

```yaml
# docker-compose.yml
environment:
  - LOG_LEVEL=DEBUG

---

**Made with using FastAPI, LangGraph, and Docker**