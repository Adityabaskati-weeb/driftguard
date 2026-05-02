# DriftGuard

> **Automated Codebase Decay Monitor** — Detect technical debt before it becomes a crisis

DriftGuard analyzes your Git commit history using IBM Bob to identify files that are drifting away from maintainability. It measures decay across 4 dimensions: documentation drift, test coverage drift, complexity growth, and naming consistency.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 What Problem Does This Solve?

Codebases decay silently. A module that was clean 3 months ago now has:
- Functions with 0 documentation, but 14 callers
- Logic that has changed 8 times with no corresponding test updates
- Variable names that made sense in v1 but are now misleading
- Complexity that has tripled since the last review

**No one notices until production breaks.**

Static analysis tools catch syntax issues. They don't catch **drift** — the gap between what the code does now and what its documentation, tests, and naming say it does.

**DriftGuard is the first developer tool that measures codebase health as a function of change over time, not just a point-in-time snapshot.**

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Git repository
- IBM Bob CLI (for AI-powered analysis)

### Installation

```bash
# Clone the repository
git clone https://github.com/Adityabaskati-weeb/driftguard.git
cd driftguard

# Install dependencies
pip install -r requirements.txt

# Verify IBM Bob is installed
bob --version
```

### Run Analysis

```bash
# Analyze current repository (last 30 days)
python driftguard.py --repo . --days 30

# Analyze a specific repository
python driftguard.py --repo /path/to/project --days 14 --max-files 10

# With verbose output
python driftguard.py --repo . --days 7 --verbose
```

### View Dashboard

```bash
# Start the FastAPI dashboard
uvicorn app.main:app --reload

# Open in browser
# http://localhost:8000
```

---

## 📊 How It Works

```
Git History → Commit Diffs → IBM Bob Analysis → Decay Score → Dashboard
```

1. **Ingests Git history** — Parses recent commits, extracts per-file diffs
2. **Sends diffs to IBM Bob** — Bob evaluates documentation drift, test drift, complexity growth, naming consistency
3. **Generates Decay Scores** — Structured per-file health scores (0–100) across 4 decay dimensions
4. **Exposes a CLI** — Run `python driftguard.py --repo . --days 30` for instant analysis
5. **Serves a FastAPI Dashboard** — Visual health map, module-level drill-down, trend over time

---

## 🎨 Dashboard Preview

The dashboard provides:
- **Summary Cards**: Quick overview of critical, at-risk, watch, and healthy files
- **Health Score Chart**: Visual bar chart of all files sorted by health score
- **Detailed Table**: File-by-file breakdown with recommendations
- **Color Coding**: 🔴 Critical, 🟠 At Risk, 🟡 Watch, 🟢 Healthy

---

## 📈 Decay Score Explained

Each file receives a **Health Score from 0–100** across 4 dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| **Documentation Drift** | 30% | Documentation staleness vs code changes |
| **Test Coverage Drift** | 30% | Test updates vs implementation changes |
| **Complexity Growth** | 25% | Function length, nesting, param growth over time |
| **Naming Consistency** | 15% | New identifiers vs established conventions |

**Final Health Score = weighted average of all dimensions**

### Status Levels

- 🟢 **80–100: Healthy** — Well maintained
- 🟡 **60–79: Watch** — Monitor closely
- 🟠 **40–59: At Risk** — Requires review
- 🔴 **0–39: Critical** — Needs immediate attention

---

## 🛠️ Project Structure

```
driftguard/
├── driftguard.py              # CLI entrypoint
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── ARCHITECTURE_PLAN.md       # Detailed architecture
├── PHASE_1.md                 # MVP build plan
├── PHASE_2.md                 # Future enhancements
├── app/
│   ├── __init__.py
│   ├── config.py              # Configuration management
│   ├── models.py              # Data schemas (TypedDict)
│   ├── exceptions.py          # Custom exceptions
│   ├── git_parser.py          # Git operations (GitPython)
│   ├── bob_analyzer.py        # IBM Bob Shell integration
│   ├── scorer.py              # Health score calculation
│   ├── report_generator.py    # JSON report builder
│   ├── main.py                # FastAPI app
│   └── templates/
│       └── dashboard.html     # Dashboard UI
├── output/                    # Generated reports (gitignored)
└── bob_sessions/              # Bob task exports (for submission)
```

---

## 🤖 IBM Bob Integration

Bob is the core reasoning engine that does what static analysis cannot:

| Task | Bob's Contribution |
|------|-------------------|
| **Documentation drift** | "Does this diff add logic without updating any docstrings or comments?" |
| **Test drift** | "Were tests modified when implementation changed? What's the signal?" |
| **Complexity growth** | "Did this change increase cyclomatic complexity, nesting, or parameter count?" |
| **Naming consistency** | "Are new identifiers consistent with the naming conventions in the rest of this file?" |

Bob is called via subprocess in non-interactive mode:
```python
subprocess.run(['bob', '-p', prompt], capture_output=True, text=True)
```

---

## 📋 Sample Output

### CLI Output
```
================================================================================
🔍 DriftGuard — Codebase Decay Monitor
================================================================================
Repository: ./my-project
Analysis window: Last 30 days
Max files: 20
================================================================================

📂 Step 1/4: Parsing Git history...
✅ Found 18 modified files

🤖 Step 2/4: Analyzing with IBM Bob...
[1/18] Analyzing: auth.py... ✅ (score: 85)
[2/18] Analyzing: login.py... 🔴 (score: 34)
...

📊 Step 3/4: Calculating health scores...
✅ Scored 18 files

📝 Step 4/4: Generating report...
✅ Report saved to: output/report_20260502_120000.json

================================================================================
File                                               Score    Status        Top Risk
================================================================================
app/auth/login.py                                  34       🔴 CRITICAL   No documentation updates
app/utils/helpers.py                               48       🟠 AT_RISK    Test coverage declining
app/models/user.py                                 72       🟡 WATCH      Complexity increasing
app/views/dashboard.py                             88       🟢 HEALTHY    None
================================================================================

📊 Summary:
   Total files: 18
   🔴 Critical: 3
   🟠 At Risk: 5
   🟡 Watch: 4
   🟢 Healthy: 6
   Average health score: 64.2/100
```

### JSON Report Structure
```json
{
  "repo": "./my-project",
  "analysis_window_days": 30,
  "analyzed_at": "2026-05-02T12:00:00Z",
  "files": [
    {
      "file_path": "app/auth/login.py",
      "health_score": 34,
      "status": "CRITICAL",
      "status_emoji": "🔴",
      "total_commits": 12,
      "documentation_drift_score": 18,
      "test_drift_score": 22,
      "complexity_growth_score": 45,
      "naming_consistency_score": 71,
      "decay_summary": "This file has changed 12 times in 30 days...",
      "top_risk": "No docstring updates detected",
      "recommendation": "Prioritize test update and documentation review"
    }
  ],
  "summary": {
    "total_files": 18,
    "critical_count": 3,
    "at_risk_count": 5,
    "watch_count": 4,
    "healthy_count": 6,
    "average_health_score": 64.2
  }
}
```

---

## 🔧 Configuration

Configuration is managed via environment variables (`.env` file) or defaults in `app/config.py`:

```bash
# Analysis defaults
DRIFTGUARD_DAYS=30
DRIFTGUARD_MAX_FILES=20
DRIFTGUARD_REPO=.

# FastAPI server
DRIFTGUARD_HOST=127.0.0.1
DRIFTGUARD_PORT=8000
DRIFTGUARD_RELOAD=true

# Logging
DRIFTGUARD_LOG_LEVEL=INFO
```

---

## 🧪 Testing

```bash
# Test git parser
python -m app.git_parser

# Test Bob analyzer
python -m app.bob_analyzer

# Test scorer
python -m app.scorer

# Test report generator
python -m app.report_generator
```

---

## 📚 API Documentation

Once the server is running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

### Available Endpoints

- `GET /` — Dashboard UI
- `GET /api/report` — Latest report JSON
- `GET /api/report/{filename}` — Specific report
- `GET /api/reports` — List all reports
- `GET /api/summary` — Summary statistics only
- `GET /health` — Health check

---

## 🎯 Use Cases

### For Individual Developers
- **Pre-commit checks**: Run before major commits to catch decay early
- **Code review prep**: Identify files that need attention before PR
- **Refactoring prioritization**: Focus on files with lowest health scores

### For Teams
- **Sprint planning**: Allocate tech debt tickets based on decay scores
- **Onboarding**: New developers see which files are risky to touch
- **Quality gates**: Block merges if critical files are introduced

### For Tech Leads
- **Health dashboards**: Track codebase health over time
- **Team metrics**: Identify patterns in decay across modules
- **Architecture decisions**: Data-driven refactoring priorities

---

## 🚧 Limitations & Future Work

### Current Limitations
- **Language support**: Currently optimized for Python, JavaScript, TypeScript, Java
- **Bob dependency**: Requires IBM Bob CLI to be installed
- **Local only**: Analyzes local repositories only (no GitHub API integration yet)
- **No historical trends**: Each run is independent (no time-series tracking)

### Planned Enhancements (Phase 2)
- ✨ Historical trend tracking with SQLite
- 📧 Slack/email alerts for critical decay
- ⏰ Scheduled automated runs
- 🔗 GitHub/GitLab remote repository support
- 🧠 Bob context memory (baseline profiles)
- 🌍 Multi-language support improvements
- 🔐 Team dashboard with authentication
- 📄 PDF/Markdown report export
- 🔌 VS Code extension integration
- 🤖 Bob-generated remediation tasks

See [PHASE_2.md](PHASE_2.md) for detailed roadmap.

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone the repo
git clone https://github.com/Adityabaskati-weeb/driftguard.git
cd driftguard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Start development server
uvicorn app.main:app --reload
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **IBM Bob** — Core AI analysis engine
- **GitPython** — Git repository parsing
- **FastAPI** — Web framework
- **Chart.js** — Dashboard visualizations

---

## 📞 Contact

- **Author**: Aditya Baskati
- **GitHub**: [@Adityabaskati-weeb](https://github.com/Adityabaskati-weeb)
- **Project**: [DriftGuard](https://github.com/Adityabaskati-weeb/driftguard)

---

## 🎓 Why This Matters

> "DriftGuard tells you which files are lying to you."

Every codebase decays. The question is: **do you know which parts are decaying fastest?**

DriftGuard gives you the answer, backed by AI-powered analysis that understands not just syntax, but **semantic drift** — the gap between what your code does and what everyone thinks it does.

**Built with IBM Bob as the core development partner.**

---

*Made with ❤️ and IBM Bob*
