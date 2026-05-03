# DriftGuard

**DriftGuard tells you which files in your codebase are lying to you.**

## The Problem

Code decays over time. Files grow without tests. Documentation falls out of date. Complexity creeps in. Naming conventions drift. Nobody checks these trends until it's too late — when a "simple" feature takes three weeks instead of three days, when onboarding a new developer becomes a nightmare, when the codebase becomes the thing everyone fears touching.

The cost of technical debt discovery and remediation is exponentially higher when left unchecked. By the time you notice the decay, you're already deep in the hole.

## What is DriftGuard?

**DriftGuard is what SonarQube would be if it understood time** — not just what your code is, but how fast it's decaying.

It's a continuous decay tracking system that analyzes your git history, identifies files showing signs of technical debt accumulation, and alerts you *before* they become critical problems. Think of it as a health monitoring system for your codebase.

**Core Value Proposition:**
- 📊 **Continuous decay tracking** — Monitor file health over time, not just snapshots
- 📈 **Trend analysis** — See which files are improving or deteriorating
- 🚨 **Automated alerts** — Get notified via Slack/Email when files cross critical thresholds
- 🔧 **Actionable remediation** — AI-generated fixes for common decay patterns

## Quick Start

Get DriftGuard running in under 2 minutes:

```bash
# 1. Clone the repository
git clone https://github.com/rohitdecodes/driftguard.git
cd driftguard

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env and set your DRIFTGUARD_API_KEY

# 4. Run your first analysis
python driftguard.py --repo . --days 30

# 5. Start the dashboard
uvicorn app.main:app --reload

# 6. Open in browser
# Navigate to http://127.0.0.1:8000
```

That's it! You now have a complete decay analysis of your repository.

## Features

| Feature | Description | Status |
|---------|-------------|--------|
| **SQLite Persistence** | Store analysis history and track trends over time | ✅ Complete |
| **Parallel Analysis** | Multi-threaded file analysis with intelligent caching | ✅ Complete |
| **Rate Limiting** | Token bucket rate limiter for Bob integration | ✅ Complete |
| **GitHub Support** | Analyze remote GitHub repositories via API | ✅ Complete |
| **Multi-Language** | Python, JavaScript, TypeScript, Java, Go, Ruby, HTML, CSS | ✅ Complete |
| **API Authentication** | Secure API endpoints with key-based auth | ✅ Complete |
| **Watch Mode** | Scheduled automated runs with Docker support | ✅ Complete |
| **Slack/Email Alerts** | Automated notifications for critical decay | ✅ Complete |
| **Remediation Generation** | AI-generated fixes for detected issues | ✅ Complete |
| **Export Formats** | PDF, Markdown, and JSON report exports | ✅ Complete |
| **Language Config** | Configurable language support via JSON | ✅ Complete |
| **Input Validation** | User-friendly error messages and hints | ✅ Complete |
| **Baseline Profiles** | Context-aware scoring based on codebase norms | ✅ Complete |
| **Comprehensive CLI** | Full-featured command-line interface | ✅ Complete |
| **VS Code Extension** | Inline decay warnings in your editor | 🔄 Planned |
| **Team Dashboard** | Multi-repo aggregate views | 🔄 Planned |

## Architecture

DriftGuard follows a pipeline architecture that transforms git history into actionable insights:

```
Local/GitHub Repository
         ↓
    Git Parser
    (fetch diffs & commit history)
         ↓
   [Cache Layer] ←→ SQLite
    (avoid redundant analysis)
         ↓
   Bob Analyzer
   (parallel, rate-limited AI analysis)
         ↓
      Scorer
   (with trend penalties)
         ↓
  SQLite Persistence
   (historical tracking)
         ↓
    ┌────┴────┬──────────┬──────────┐
    ↓         ↓          ↓          ↓
Dashboard  Alerts   Exports   Remediation
(FastAPI)  (Slack)  (PDF/MD)  (AI-generated)
```

## CLI Usage

DriftGuard provides a powerful command-line interface with extensive options:

### Basic Analysis

```bash
# Analyze current directory for last 30 days
python driftguard.py --repo . --days 30

# Analyze with custom file limit
python driftguard.py --repo . --days 30 --max-files 50

# Analyze a specific local repository
python driftguard.py --repo /path/to/repo --days 7
```

### GitHub Repository Analysis

```bash
# Analyze a public GitHub repository
python driftguard.py --repo https://github.com/pallets/flask --days 7

# Analyze with GitHub token (for private repos and higher rate limits)
python driftguard.py --repo https://github.com/user/private-repo --github-token YOUR_TOKEN
```

### Export Options

```bash
# Export as JSON (default)
python driftguard.py --repo . --export json

# Export as Markdown
python driftguard.py --repo . --export markdown

# Export as PDF
python driftguard.py --repo . --export pdf

# Export in all formats
python driftguard.py --repo . --export all
```

### Remediation Generation

```bash
# Generate AI-powered remediation files for critical issues
python driftguard.py --repo . --remediate

# Remediation files are saved to remediation/ directory
```

### Watch Mode

```bash
# Run continuous monitoring every 24 hours
python driftguard.py --watch --interval 24h

# Run every 12 hours
python driftguard.py --watch --interval 12h

# Run every 30 minutes
python driftguard.py --watch --interval 30m
```

### Language Configuration

```bash
# Show active language configuration
python driftguard.py --show-languages

# Output shows enabled/disabled extensions and their mappings
```

### Advanced Options

```bash
# Verbose output with detailed analysis
python driftguard.py --repo . --verbose

# Custom output path
python driftguard.py --repo . --output custom_report.json

# Combine multiple options
python driftguard.py --repo . --days 60 --max-files 100 --export all --remediate
```

## API Reference

DriftGuard provides a RESTful API for programmatic access:

| Method | Endpoint | Auth Required | Description |
|--------|----------|---------------|-------------|
| GET | `/` | No | Dashboard web interface |
| GET | `/settings` | No | Configuration view |
| GET | `/api/report` | Yes | Latest analysis report |
| GET | `/api/trends?file=<path>` | Yes | Historical trends for a file |
| GET | `/api/remediation/{file_name}` | Yes | Remediation for a specific file |
| GET | `/api/language-config` | No | Active language configuration |
| POST | `/api/language-config/reload` | Yes | Reload language configuration |
| GET | `/health` | No | Health check endpoint |

### Authentication

Protected endpoints require an API key in the request header:

```bash
curl -H "X-DriftGuard-Key: your-api-key" http://localhost:8000/api/report
```

### Example API Usage

```bash
# Get latest report
curl -H "X-DriftGuard-Key: your-key" http://localhost:8000/api/report

# Get trends for a specific file
curl -H "X-DriftGuard-Key: your-key" \
  "http://localhost:8000/api/trends?file=app/main.py"

# Get remediation suggestions
curl -H "X-DriftGuard-Key: your-key" \
  http://localhost:8000/api/remediation/app_main_py

# Check health
curl http://localhost:8000/health
```

## Configuration & Environment

DriftGuard is configured via environment variables. Copy `.env.example` to `.env` and customize:

### Core Configuration

```bash
# API Key for protected endpoints (required)
DRIFTGUARD_API_KEY=your-secure-api-key-here

# Repository path (for Docker deployments)
HOST_REPO_PATH=./repo
REPO_PATH=/repo

# Analysis parameters
DRIFTGUARD_DAYS=30              # Days of history to analyze
DRIFTGUARD_MAX_FILES=20         # Max files per analysis run
```

### Watch Mode Configuration

```bash
# Interval between automated runs
WATCH_INTERVAL=24h              # Options: 24h, 12h, 6h, 30m, etc.
```

### Performance Tuning

```bash
# Parallel processing
DRIFTGUARD_MAX_WORKERS=8        # Max parallel workers (default: min(8, cpu_count))

# Caching
DRIFTGUARD_CACHE_ENABLED=true   # Enable analysis caching
DRIFTGUARD_CACHE_TTL_HOURS=0    # Cache expiry (0 = never expire)

# Rate limiting
BOB_RATE_LIMIT_PER_MINUTE=30    # Max Bob API calls per minute
BOB_RATE_LIMIT_BURST=5          # Burst capacity for rapid requests
```

### GitHub Integration

```bash
# GitHub token for private repos and higher rate limits
GITHUB_TOKEN=ghp_your_token_here
```

### Logging

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
DRIFTGUARD_LOG_LEVEL=INFO
```

### Alert Configuration (Future)

```bash
# Slack/Email alerts (coming soon)
# ALERT_ENABLED=false
# ALERT_CRITICAL_THRESHOLD=40
# ALERT_EMAIL_TO=team@example.com
# ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Docker Deployment

DriftGuard includes Docker support for production deployments:

### Quick Start with Docker

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with your configuration

# 2. Start the watcher service
docker-compose up -d

# 3. View logs
docker-compose logs -f

# 4. Stop the service
docker-compose down
```

### Docker Compose Configuration

The `docker-compose.yml` file configures a persistent watcher service:

```yaml
services:
  driftguard-watcher:
    build: .
    container_name: driftguard-watcher
    restart: unless-stopped
    volumes:
      - ./repo:/repo:ro          # Mount your repository (read-only)
      - ./data:/app/data         # Persist database
      - ./logs:/app/logs         # Persist logs
      - ./output:/app/output     # Persist reports
    env_file:
      - .env
```

### Manual Docker Build

```bash
# Build the image
docker build -t driftguard .

# Run a one-time analysis
docker run --rm \
  -v $(pwd):/repo:ro \
  -v $(pwd)/data:/app/data \
  driftguard --repo /repo --days 30

# Run in watch mode
docker run -d \
  --name driftguard-watcher \
  -v $(pwd):/repo:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e WATCH_INTERVAL=24h \
  driftguard --watch --interval 24h
```

## Roadmap

### Phase 1 (MVP) ✅ COMPLETE

- [x] Git parser with commit history analysis
- [x] Rule-based decay analyzer
- [x] JSON report generation
- [x] FastAPI dashboard with visualization
- [x] Basic CLI interface

### Phase 2 (Scaling) ✅ MOSTLY COMPLETE

- [x] SQLite persistence and trend tracking
- [x] Parallel file analysis with caching
- [x] Rate-limited Bob integration
- [x] GitHub remote repository support
- [x] Multi-language support (Python, JS, TS, Java, Go, Ruby, HTML, CSS)
- [x] API key authentication
- [x] Scheduled watch mode with Docker
- [x] Slack/Email alert system
- [x] AI-powered remediation generation
- [x] PDF/Markdown export
- [x] Configurable language support
- [x] Input validation with user-friendly errors
- [x] Baseline profiles for context-aware scoring
- [x] Comprehensive CLI with validation

### Phase 3 (Team Features) 🔄 IN PROGRESS

- [ ] VS Code extension with inline warnings
- [ ] Advanced team dashboard with multi-repo views
- [ ] LLM-powered insights and recommendations
- [ ] GitLab and Bitbucket support
- [ ] Custom rule engine for team-specific patterns
- [ ] Integration with CI/CD pipelines
- [ ] Historical comparison and regression detection
- [ ] Team collaboration features (comments, assignments)

## Contributing

We welcome contributions! Here's how you can help:

### Adding New Language Support

1. Update `data/language_config.json` with new file extensions:
```json
{
  "extensions": {
    ".rs": {
      "language": "rust",
      "enabled": true,
      "description": "Rust source files"
    }
  }
}
```

2. Add language-specific prompts in `app/language_prompts.py`:
```python
LANGUAGE_PROMPTS = {
    "rust": "Analyze this Rust file for decay signals..."
}
```

3. Test with `python driftguard.py --show-languages`

### Extending Analyzers

Create custom analyzers in the `app/` directory:

```python
# app/custom_analyzer.py
def analyze_custom_pattern(file_data: dict) -> dict:
    """Your custom analysis logic"""
    return {
        "pattern_detected": True,
        "severity": "high",
        "recommendation": "..."
    }
```

### Adding New Notifiers

Implement the notifier interface in `app/alert_manager.py`:

```python
class CustomNotifier:
    def send_decay_alert(self, file_path, score, risk, url):
        """Send alert via your custom channel"""
        pass
```

### Development Setup

```bash
# Clone the repository
git clone https://github.com/rohitdecodes/driftguard.git
cd driftguard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run with verbose logging
python driftguard.py --repo . --verbose
```

For detailed contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md) (coming soon).

## License

DriftGuard is released under the MIT License. See [LICENSE](LICENSE) for details.

## Contact & Support

- **GitHub Issues**: [Report bugs](https://github.com/rohitdecodes/driftguard/issues)
- **GitHub Discussions**: [Feature requests and questions](https://github.com/rohitdecodes/driftguard/discussions)
- **Project Repository**: [https://github.com/rohitdecodes/driftguard](https://github.com/rohitdecodes/driftguard)

---

**Built with ❤️ by developers who care about code quality.**

*DriftGuard: Because your codebase deserves better than benign neglect.*
