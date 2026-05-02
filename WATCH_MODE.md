# DriftGuard Watch Mode

DriftGuard now supports continuous monitoring with scheduled analysis runs.

## Features

- **Scheduled Analysis**: Run analysis at regular intervals (e.g., every 24 hours)
- **Persistent Storage**: All runs are saved to SQLite database for trend tracking
- **Rotating Logs**: Logs are written to `logs/driftguard.log` with automatic rotation
- **Alert System**: Configurable alerts for critical health scores (extensible)
- **Graceful Shutdown**: Handles SIGINT/SIGTERM for clean termination
- **Docker Support**: Easy containerization with Docker and docker-compose

## Usage

### Local Execution

```bash
# Install dependencies
pip install -r requirements.txt

# Run watch mode with 24-hour interval
python driftguard.py --watch --interval 24h

# Run with custom settings
python driftguard.py --repo /path/to/repo --days 30 --max-files 20 --watch --interval 12h

# Stop gracefully with Ctrl+C
```

### Interval Formats

The `--interval` flag supports multiple formats:

- **Hours**: `24h`, `12h`, `1h`
- **Minutes**: `30m`, `15m`, `5m`
- **Seconds**: `3600s`, `60s`, `10s`
- **Plain seconds**: `3600`, `86400`

### Docker Deployment

#### Using Docker Compose (Recommended)

1. **Create `.env` file** (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` to configure**:
   ```env
   HOST_REPO_PATH=./repo          # Path to repository on host
   WATCH_INTERVAL=24h             # Analysis interval
   DRIFTGUARD_DAYS=30             # Days of history
   DRIFTGUARD_MAX_FILES=20        # Max files per run
   ```

3. **Start the watcher**:
   ```bash
   docker-compose up -d
   ```

4. **View logs**:
   ```bash
   docker-compose logs -f
   ```

5. **Stop the watcher**:
   ```bash
   docker-compose down
   ```

#### Using Docker Directly

```bash
# Build image
docker build -t driftguard .

# Run container
docker run -d \
  --name driftguard-watcher \
  -v /path/to/repo:/repo:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e REPO_PATH=/repo \
  -e WATCH_INTERVAL=24h \
  driftguard
```

## Output

### Logs

Logs are written to `logs/driftguard.log` with:
- Automatic rotation at 10MB
- 5 backup files retained
- Timestamps and log levels
- Analysis progress and errors

Example log output:
```
2026-05-02 13:20:00 - driftguard - INFO - ======================================================================
2026-05-02 13:20:00 - driftguard - INFO - DriftGuard Watch Mode Started
2026-05-02 13:20:00 - driftguard - INFO - Repository: .
2026-05-02 13:20:00 - driftguard - INFO - Analysis window: 30 days
2026-05-02 13:20:00 - driftguard - INFO - Interval: 86400 seconds (24.0 hours)
2026-05-02 13:20:00 - driftguard - INFO - Database initialized
2026-05-02 13:20:00 - driftguard - INFO - Starting analysis run #1
```

### Database

All runs are persisted to `data/driftguard.db`:
- **runs** table: Metadata for each analysis run
- **file_scores** table: Per-file scores for each run
- Enables trend tracking via `/api/trends` endpoint

### Reports

JSON reports are saved to `output/report_YYYYMMDD_HHMMSS.json` for each run.

## Alert Configuration

The AlertManager is currently a stub but can be extended for:
- Email notifications
- Slack/Discord webhooks
- Custom alert rules
- Alert history tracking

To enable alerts (future):
```python
alert_config = {
    'enabled': True,
    'critical_threshold': 40,
    'email_to': 'team@example.com',
    'webhook_url': 'https://hooks.slack.com/...'
}
```

## Architecture

```
driftguard.py (CLI)
    ↓
watcher() function
    ↓
    ├─→ run_analysis() - Execute analysis pipeline
    │       ↓
    │       ├─→ git_parser.get_file_diffs()
    │       ├─→ bob_analyzer.batch_analyze()
    │       ├─→ scorer.score_all_files()
    │       └─→ report_generator.generate_report()
    │
    ├─→ db.save_run() - Persist to database
    │
    └─→ AlertManager.check_and_alert() - Trigger alerts
```

## Troubleshooting

### Database Locked Error

If you see "database is locked" errors:
- Ensure only one watcher instance is running
- Check that the database file isn't open in another process
- Restart the watcher

### Unicode Encoding Errors (Windows)

The code has been updated to avoid emoji characters that cause encoding issues on Windows terminals.

### Container Not Starting

Check logs:
```bash
docker-compose logs driftguard-watcher
```

Common issues:
- Repository path not mounted correctly
- Missing `.env` file
- Invalid interval format

## Examples

### Development Testing (5-second interval)
```bash
python driftguard.py --repo . --days 7 --max-files 5 --watch --interval 5s
```

### Production Monitoring (24-hour interval)
```bash
python driftguard.py --repo /path/to/production/repo --days 30 --max-files 50 --watch --interval 24h
```

### Docker with Custom Settings
```bash
docker run -d \
  --name driftguard \
  -v /var/repos/myapp:/repo:ro \
  -v ./data:/app/data \
  -v ./logs:/app/logs \
  -e REPO_PATH=/repo \
  -e WATCH_INTERVAL=12h \
  -e DRIFTGUARD_DAYS=60 \
  -e DRIFTGUARD_MAX_FILES=100 \
  driftguard
```

## Integration with Dashboard

The watch mode works seamlessly with the FastAPI dashboard:

1. Start the watcher (populates database)
2. Start the dashboard: `uvicorn app.main:app --reload`
3. View trends at: `http://localhost:8000/api/trends?file=<path>`

The dashboard reads from the same `data/driftguard.db` database that the watcher writes to.

---

Made with Bob