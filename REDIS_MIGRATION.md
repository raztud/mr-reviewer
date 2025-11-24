# Redis Migration Guide

This guide explains how to migrate from JSON file storage to Redis for tracking processed emails.

## Why Redis?

**Benefits of Redis over JSON files:**
- ✅ **Persistence**: AOF (Append-Only File) ensures no data loss
- ✅ **Performance**: In-memory storage with fast lookups
- ✅ **Concurrency**: Safe for multiple clients (if scaling)
- ✅ **Atomicity**: Thread-safe operations
- ✅ **Production-Ready**: Battle-tested for high-availability systems
- ✅ **Docker-Native**: Seamless integration with containerized deployments

## Docker Deployment (Automatic)

If you're using Docker, Redis is **automatically configured** and ready to use!

```bash
# Start with Redis (default)
make docker-up

# Redis data persists in Docker volume: redis-data
docker volume ls | grep redis
```

### Verify Redis is Working

```bash
# Check Redis service
docker ps | grep redis

# Test connection
docker exec gitlab-mr-summarizer-redis redis-cli ping
# Should return: PONG

# Check stored emails
docker exec gitlab-mr-summarizer-redis redis-cli SCARD gitlab_mr_summarizer:processed_emails
```

## Local Development (Optional)

For local development without Docker, you can optionally use Redis:

### 1. Install Redis

**macOS (Homebrew):**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**Windows:**
- Download from: https://github.com/microsoftarchive/redis/releases
- Or use WSL2 with Ubuntu instructions

### 2. Configure for Local Redis

Edit `.env`:
```env
REDIS_URL=redis://localhost:6379/0
USE_REDIS=true
```

### 3. Start Services

```bash
# Install redis Python package
pip install redis

# Start services
make start-all
```

## Migration from JSON to Redis

### Option 1: Fresh Start (Recommended)

Simply start using Redis - old emails will be reprocessed once (safe):

```bash
# Docker
make docker-up

# Local
# Edit .env: USE_REDIS=true
make start-all
```

### Option 2: Migrate Existing Data

If you have a `.processed_emails.json` file and want to preserve it:

```python
# migration_script.py
import json
import redis

# Load from JSON
with open('.processed_emails.json', 'r') as f:
    data = json.load(f)
    email_ids = data.get('processed_ids', [])

# Connect to Redis
r = redis.from_url('redis://localhost:6379/0', decode_responses=True)

# Migrate to Redis
key = 'gitlab_mr_summarizer:processed_emails'
for email_id in email_ids:
    r.sadd(key, email_id)

print(f"Migrated {len(email_ids)} email IDs to Redis")
print(f"Verification: {r.scard(key)} emails in Redis")
```

Run the script:
```bash
python migration_script.py
```

### Option 3: Keep Using JSON Files

Redis is optional! To continue using JSON files:

**Docker:**
```yaml
# docker-compose.yml - comment out redis dependency
depends_on:
  gitlab-server:
    condition: service_healthy
  llm-server:
    condition: service_healthy
  # redis:  # <-- comment this out
  #   condition: service_healthy
```

Set in `.env`:
```env
USE_REDIS=false
```

**Local:**
```env
# .env
USE_REDIS=false
PROCESSED_EMAILS_DB=.processed_emails.json
```

## Redis Configuration

### Connection URL Format

```
redis://[username:password@]host:port/database
```

Examples:
```env
# Local Redis (no auth)
REDIS_URL=redis://localhost:6379/0

# Docker Redis (container name)
REDIS_URL=redis://redis:6379/0

# Redis with password
REDIS_URL=redis://:mypassword@localhost:6379/0

# Redis Cloud
REDIS_URL=redis://:password@redis-12345.cloud.redislabs.com:12345/0
```

### Persistence Configuration

Redis is configured with AOF (Append-Only File) persistence:
- **`appendonly yes`** - Enable AOF
- **`appendfsync everysec`** - Fsync every second (balance between performance and durability)

Data persists across container restarts in the `redis-data` Docker volume.

### Memory Usage

Redis stores email IDs as a Set. Typical memory usage:
- Each email ID: ~50-100 bytes
- 10,000 emails: ~1 MB
- 1,000,000 emails: ~100 MB

Very efficient! 🚀

## Backup and Restore

### Backup Redis Data

**Docker:**
```bash
# Save current state
docker exec gitlab-mr-summarizer-redis redis-cli SAVE

# Copy backup file
docker cp gitlab-mr-summarizer-redis:/data/dump.rdb ./redis-backup-$(date +%Y%m%d).rdb
```

**Local:**
```bash
redis-cli SAVE
cp /var/lib/redis/dump.rdb ~/redis-backup-$(date +%Y%m%d).rdb
```

### Restore Redis Data

**Docker:**
```bash
# Stop Redis
docker-compose stop redis

# Copy backup
docker cp ./redis-backup.rdb gitlab-mr-summarizer-redis:/data/dump.rdb

# Start Redis
docker-compose start redis
```

### Export to JSON

```bash
# Export from Redis to JSON format
docker exec gitlab-mr-summarizer-redis redis-cli SMEMBERS gitlab_mr_summarizer:processed_emails > redis_export.txt

# Convert to JSON
python -c "
import json
import sys
emails = [line.strip() for line in open('redis_export.txt') if line.strip()]
data = {'processed_ids': emails, 'exported': '$(date -Iseconds)'}
print(json.dumps(data, indent=2))
" > .processed_emails.json
```

## Monitoring Redis

### Check Status

```bash
# Docker
docker exec gitlab-mr-summarizer-redis redis-cli INFO server
docker exec gitlab-mr-summarizer-redis redis-cli INFO memory
docker exec gitlab-mr-summarizer-redis redis-cli INFO persistence

# Local
redis-cli INFO server
```

### View Processed Emails

```bash
# Count
docker exec gitlab-mr-summarizer-redis redis-cli SCARD gitlab_mr_summarizer:processed_emails

# List first 10
docker exec gitlab-mr-summarizer-redis redis-cli SRANDMEMBER gitlab_mr_summarizer:processed_emails 10

# Check if specific email processed
docker exec gitlab-mr-summarizer-redis redis-cli SISMEMBER gitlab_mr_summarizer:processed_emails "8817"
```

### Clear All Processed Emails

⚠️ **Warning**: This will cause all emails to be reprocessed!

```bash
# Docker
docker exec gitlab-mr-summarizer-redis redis-cli DEL gitlab_mr_summarizer:processed_emails

# Local
redis-cli DEL gitlab_mr_summarizer:processed_emails
```

## Troubleshooting

### Connection Refused

**Error**: `Cannot connect to Redis: [Errno 111] Connection refused`

**Solutions**:
```bash
# Check if Redis is running
docker ps | grep redis

# Check Redis logs
docker logs gitlab-mr-summarizer-redis

# Test connection
docker exec gitlab-mr-summarizer-redis redis-cli ping
```

### Client Falls Back to JSON

**Log message**: `Failed to initialize Redis storage: ... Falling back to JSON storage`

This is expected behavior! The system automatically falls back to JSON if Redis is unavailable. No data loss occurs.

### Data Not Persisting

**Check AOF status**:
```bash
docker exec gitlab-mr-summarizer-redis redis-cli CONFIG GET appendonly
# Should return: appendonly yes
```

**Check volume**:
```bash
docker volume inspect gitlab-mr-summarizer_redis-data
```

### High Memory Usage

```bash
# Check memory
docker stats gitlab-mr-summarizer-redis

# If too high, clear old data
docker exec gitlab-mr-summarizer-redis redis-cli MEMORY PURGE
```

## Advanced Configuration

### Use Different Redis Database

```env
# Use database 1 instead of 0
REDIS_URL=redis://redis:6379/1
```

### Custom Key Prefix

Edit `src/utils/email_storage.py`:
```python
RedisEmailStorage(redis_url, key_prefix="my_custom_prefix")
```

### Redis Password

**docker-compose.yml:**
```yaml
redis:
  command: redis-server --appendonly yes --appendfsync everysec --requirepass mypassword
```

**.env:**
```env
REDIS_URL=redis://:mypassword@redis:6379/0
```

### Redis Clustering (Production)

For high-availability production:
- Use Redis Sentinel or Redis Cluster
- Update `REDIS_URL` to sentinel or cluster URL
- Consider managed Redis (AWS ElastiCache, Redis Cloud)

## Performance Comparison

| Operation | JSON File | Redis |
|-----------|-----------|-------|
| Check if processed | O(n) linear scan | O(1) constant time |
| Add email | O(n) read + write | O(1) append |
| Concurrent access | ❌ File locks | ✅ Thread-safe |
| Persistence | Manual save | Automatic |
| Memory usage | Load all to RAM | In-memory native |

**Verdict**: Redis is significantly faster and more reliable! 🚀

## FAQ

**Q: Do I have to use Redis?**  
A: No! JSON file storage still works. Redis is optional but recommended.

**Q: Will I lose my processed emails history?**  
A: No. If Redis fails, the system automatically falls back to JSON files.

**Q: What happens if Redis crashes?**  
A: Data persists in the `redis-data` volume and AOF file. On restart, Redis reloads all data.

**Q: Can I switch back to JSON files?**  
A: Yes! Set `USE_REDIS=false` in `.env` and restart.

**Q: How do I backup Redis data?**  
A: See "Backup and Restore" section above.

## Next Steps

- ✅ Redis is ready to use with Docker!
- 📖 See [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md) to get started
- 📚 Read [DOCKER.md](DOCKER.md) for advanced Docker usage
- 🔧 Configure Redis settings in `.env` as needed

For production deployments, consider:
- Regular Redis backups
- Redis password authentication
- Monitoring Redis memory and performance
- Using managed Redis service (AWS ElastiCache, Redis Cloud, etc.)

