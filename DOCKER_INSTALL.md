# 🐳 EMBEd - Docker Installation Guide

## Quick Start (3 Steps!)

### Prerequisites
- Docker Desktop installed ([Download here](https://www.docker.com/products/docker-desktop))
- At least 8GB RAM available
- 10GB free disk space

### Step 1: Clone Repository
```bash
git clone https://github.com/Himanshu8881212/EMBEd.git
cd EMBEd
```

### Step 2: Build and Start
```bash
docker-compose up -d
```

### Step 3: Access Application
- **Frontend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

That's it! 🎉

---

## Detailed Instructions

### First Time Setup

1. **Build the Docker image** (this will take 10-15 minutes on first run):
   ```bash
   docker-compose build
   ```

2. **Start the application**:
   ```bash
   docker-compose up -d
   ```

3. **Check logs** to ensure everything started correctly:
   ```bash
   docker-compose logs -f
   ```

4. **Wait for initialization** (first run takes ~2 minutes to download models):
   ```
   Look for: "Application startup complete"
   ```

5. **Access the application**:
   - Open browser: http://localhost:8000
   - You should see the EMBEd dashboard

---

## Common Commands

### Start Application
```bash
docker-compose up -d
```

### Stop Application
```bash
docker-compose down
```

### View Logs
```bash
# All logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Only errors
docker-compose logs | grep ERROR
```

### Restart Application
```bash
docker-compose restart
```

### Rebuild After Code Changes
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Check Status
```bash
docker-compose ps
```

### Access Container Shell
```bash
docker-compose exec embed bash
```

---

## Data Persistence

All data is stored in Docker volumes and persists across restarts:

- **Vector Database**: `embed-chroma` volume
- **Uploaded Files**: `embed-uploads` volume
- **Analytics Database**: `embed-analytics` volume
- **Model Cache**: `embed-models` volume
- **Logs**: `embed-logs` volume

### View Volumes
```bash
docker volume ls | grep embed
```

### Backup Data
```bash
# Backup all volumes
docker run --rm -v embed-chroma:/data -v $(pwd):/backup alpine tar czf /backup/chroma-backup.tar.gz /data
docker run --rm -v embed-uploads:/data -v $(pwd):/backup alpine tar czf /backup/uploads-backup.tar.gz /data
docker run --rm -v embed-analytics:/data -v $(pwd):/backup alpine tar czf /backup/analytics-backup.tar.gz /data
```

### Restore Data
```bash
# Restore volumes
docker run --rm -v embed-chroma:/data -v $(pwd):/backup alpine tar xzf /backup/chroma-backup.tar.gz -C /
docker run --rm -v embed-uploads:/data -v $(pwd):/backup alpine tar xzf /backup/uploads-backup.tar.gz -C /
docker run --rm -v embed-analytics:/data -v $(pwd):/backup alpine tar xzf /backup/analytics-backup.tar.gz -C /
```

### Clean Up All Data (⚠️ WARNING: Deletes everything!)
```bash
docker-compose down -v
```

---

## Troubleshooting

### Application Won't Start

1. **Check Docker is running**:
   ```bash
   docker ps
   ```

2. **Check logs for errors**:
   ```bash
   docker-compose logs
   ```

3. **Rebuild from scratch**:
   ```bash
   docker-compose down -v
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Port Already in Use

If port 8000 is already in use, edit `docker-compose.yml`:
```yaml
ports:
  - "8080:8000"  # Change 8000 to any available port
```

Then access at http://localhost:8080

### Out of Memory

Increase Docker memory limit:
- Docker Desktop → Settings → Resources → Memory
- Increase to at least 8GB

Or reduce workers in `docker-compose.yml`:
```yaml
environment:
  - WORKERS=1  # Reduce from 4 to 1
```

### Slow First Startup

First run downloads ~2GB of models. This is normal and only happens once.

Check progress:
```bash
docker-compose logs -f | grep "Loading"
```

### Frontend Not Loading

1. **Check if frontend was built**:
   ```bash
   docker-compose exec embed ls -la /app/frontend/build
   ```

2. **Rebuild if missing**:
   ```bash
   docker-compose build --no-cache
   ```

---

## Production Deployment

### Using Docker Compose (Recommended)

1. **Update environment variables** in `docker-compose.yml`:
   ```yaml
   environment:
     - ENVIRONMENT=production
     - CORS_ORIGINS=https://yourdomain.com
     - WORKERS=4
   ```

2. **Use production-ready settings**:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '8'
         memory: 16G
   ```

3. **Enable HTTPS** (use nginx reverse proxy):
   ```nginx
   server {
       listen 443 ssl;
       server_name yourdomain.com;
       
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

### Using Docker Swarm

```bash
docker stack deploy -c docker-compose.yml embed
```

### Using Kubernetes

Convert docker-compose.yml to Kubernetes manifests:
```bash
kompose convert -f docker-compose.yml
kubectl apply -f .
```

---

## Performance Tuning

### CPU Optimization
```yaml
deploy:
  resources:
    limits:
      cpus: '8'  # Adjust based on your CPU
```

### Memory Optimization
```yaml
deploy:
  resources:
    limits:
      memory: 16G  # Adjust based on your RAM
```

### Worker Processes
```yaml
environment:
  - WORKERS=4  # 2x CPU cores recommended
```

---

## Monitoring

### Health Check
```bash
curl http://localhost:8000/api/health
```

### Resource Usage
```bash
docker stats embed-app
```

### Disk Usage
```bash
docker system df
```

---

## Updates

### Pull Latest Code
```bash
git pull origin main
docker-compose down
docker-compose build
docker-compose up -d
```

### Update Dependencies Only
```bash
docker-compose build --no-cache
docker-compose up -d
```

---

## Support

- **Issues**: https://github.com/Himanshu8881212/EMBEd/issues
- **Documentation**: See README.md
- **API Docs**: http://localhost:8000/docs

---

## Architecture

```
┌─────────────────────────────────────────┐
│         Docker Container                │
│                                         │
│  ┌──────────────┐  ┌─────────────────┐ │
│  │   Frontend   │  │    Backend      │ │
│  │  (React TS)  │  │   (FastAPI)     │ │
│  │              │  │                 │ │
│  │  Port: 8000  │  │  Port: 8000     │ │
│  └──────────────┘  └─────────────────┘ │
│         │                   │           │
│         └───────┬───────────┘           │
│                 │                       │
│  ┌──────────────▼──────────────┐       │
│  │   Persistent Volumes        │       │
│  │  - ChromaDB (vectors)       │       │
│  │  - Uploads (files)          │       │
│  │  - Analytics (SQLite)       │       │
│  │  - Models (cache)           │       │
│  └─────────────────────────────┘       │
└─────────────────────────────────────────┘
```

---

**Ready to deploy! 🚀**

