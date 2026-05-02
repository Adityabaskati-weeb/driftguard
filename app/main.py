"""main.py

FastAPI application for DriftGuard dashboard.
Serves JSON reports and renders the web dashboard.
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Query, Header, Depends
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from app.config import (
    Config, get_latest_report, load_repos_config,
    get_language_config_info, reload_language_config
)
from app.report_generator import load_report
from app import db
from app.validation import ValidationError, validate_file_path, validate_days, validate_max_files


# Initialize FastAPI app
app = FastAPI(
    title="DriftGuard",
    description="Codebase Decay Monitor",
    version="1.0.0",
)

# Add CORS middleware (allow all origins for local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(Config.TEMPLATES_DIR))


# Custom exception handler for ValidationError
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle ValidationError exceptions with structured JSON response."""
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )


def verify_api_key(x_driftguard_key: Optional[str] = Header(None, alias="X-DriftGuard-Key")):
    """Verify API key from request header.
    
    Args:
        x_driftguard_key: API key from X-DriftGuard-Key header
        
    Raises:
        HTTPException: 401 if API key is missing or invalid
    """
    if not Config.API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API key not configured. Set DRIFTGUARD_API_KEY environment variable."
        )
    
    if not x_driftguard_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include X-DriftGuard-Key header."
        )
    
    if x_driftguard_key != Config.API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key."
        )
    
    return x_driftguard_key


def get_report_data() -> Optional[dict]:
    """Load the most recent report from disk."""
    latest = get_latest_report()
    if latest is None:
        return None
    return load_report(str(latest))


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard(request: Request):
    """Serve the main dashboard HTML."""
    report = get_report_data()
    
    if report is None:
        return """
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <title>DriftGuard — Dashboard</title>
            <style>
              body { background:#1a1a2e; color:#e6eef8; font-family: Arial, sans-serif; padding:24px; margin:0; }
              .container { max-width:1200px; margin:0 auto; }
              .card { background:#16213e; padding:32px; border-radius:8px; text-align:center; }
              h1 { margin:0 0 16px 0; }
              p { margin:8px 0; color:#b0b8c8; }
              code { background:#0f1419; padding:4px 8px; border-radius:4px; }
            </style>
          </head>
          <body>
            <div class="container">
              <div class="card">
                <h1>🔍 DriftGuard</h1>
                <p>No report found yet.</p>
                <p>Run DriftGuard first:</p>
                <code>python driftguard.py --repo . --days 30</code>
                <p style="margin-top:24px; color:#888;">Then refresh this page.</p>
              </div>
            </div>
          </body>
        </html>
        """
    
    # Render dashboard with report data
    return templates.TemplateResponse("dashboard.html", {"request": request, "report": report})


@app.get("/settings", tags=["Settings"])
async def get_settings():
    """Get public settings (no API key required).
    
    Returns repository path, watch interval, and masked API key.
    """
    repos = load_repos_config()
    default_repo = repos[0] if repos else {"path": Config.DEFAULT_REPO_PATH, "days": Config.DEFAULT_DAYS}
    
    # Mask API key (show first 4 and last 4 characters)
    masked_key = ""
    if Config.API_KEY:
        if len(Config.API_KEY) > 8:
            masked_key = Config.API_KEY[:4] + "*" * (len(Config.API_KEY) - 8) + Config.API_KEY[-4:]
        else:
            masked_key = "*" * len(Config.API_KEY)
    
    return {
        "repo_path": default_repo.get("path", Config.DEFAULT_REPO_PATH),
        "watch_interval_days": default_repo.get("days", Config.DEFAULT_DAYS),
        "api_key_configured": bool(Config.API_KEY),
        "api_key_masked": masked_key if masked_key else "Not configured"
    }


@app.get("/api/repos", tags=["API"])
async def get_repos(api_key: str = Depends(verify_api_key)):
    """Get list of all configured repositories (requires API key).
    
    Returns list of repos with name, path, avg_health_score, last_run_date, and file_count.
    """
    repos = load_repos_config()
    
    # Enhance each repo with stats from database
    import sqlite3
    db_conn = sqlite3.connect(db.DEFAULT_DB_PATH)
    
    try:
        result = []
        for repo in repos:
            repo_name = repo.get("name", "unknown")
            repo_path = repo.get("path", "")
            
            # Get latest run stats for this repo
            cursor = db_conn.cursor()
            cursor.execute("""
                SELECT
                    AVG(health_score) as avg_score,
                    MAX(timestamp) as last_run,
                    COUNT(DISTINCT file_path) as file_count
                FROM file_scores
                WHERE run_id IN (
                    SELECT run_id FROM analysis_runs
                    WHERE repo_path = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                )
            """, (repo_path,))
            
            row = cursor.fetchone()
            avg_score = round(row[0], 1) if row[0] else 0.0
            last_run = row[1] if row[1] else "Never"
            file_count = row[2] if row[2] else 0
            
            result.append({
                "name": repo_name,
                "path": repo_path,
                "avg_health_score": avg_score,
                "last_run_date": last_run,
                "file_count": file_count,
                "days": repo.get("days", Config.DEFAULT_DAYS),
                "enabled": repo.get("enabled", True)
            })
        
        return {"repos": result, "total": len(result)}
    finally:
        db_conn.close()


@app.get("/api/report", tags=["API"])
async def get_report(api_key: str = Depends(verify_api_key)):
    """Return the most recent report as JSON with sparkline data (requires API key)."""
    report = get_report_data()
    
    if report is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": "No report found",
                "hint": "Run 'python driftguard.py --repo . --days 30' to generate a report first.",
                "code": "NO_REPORT_FOUND"
            }
        )
    
    # Enhance report with sparkline data for each file
    from app.trends import compute_trends
    import sqlite3
    
    db_conn = sqlite3.connect(db.DEFAULT_DB_PATH)
    
    try:
        files = report.get('files', [])
        for file_data in files:
            file_path = file_data.get('file_path', '')
            if file_path:
                # Compute trends and add sparkline data
                trend_data = compute_trends(file_path, db_conn, n=6)
                file_data['sparkline'] = trend_data.get('last_n_scores', [])
                file_data['trend_direction'] = trend_data.get('trend_direction', 'stable')
                file_data['score_change'] = trend_data.get('score_change', 0.0)
    finally:
        db_conn.close()
    
    return report


@app.get("/api/report/{filename}", tags=["API"])
async def get_report_by_filename(filename: str, api_key: str = Depends(verify_api_key)):
    """Return a specific report by filename (requires API key)."""
    report_path = Config.OUTPUT_DIR / filename
    
    if not report_path.exists():
        return JSONResponse(
            status_code=404,
            content={
                "error": f"Report not found: {filename}",
                "hint": f"Check available reports in the output directory. Run 'python driftguard.py' to generate a report.",
                "code": "REPORT_NOT_FOUND"
            }
        )
    
    if not str(report_path).endswith('.json'):
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid report format",
                "hint": "Only JSON reports are supported. Use .json extension.",
                "code": "INVALID_REPORT_FORMAT"
            }
        )
    
    return load_report(str(report_path))


@app.get("/api/trends", tags=["API"])
async def get_file_trends(file: str = Query(..., description="File path to get trends for"), api_key: str = Depends(verify_api_key)):
    """Get historical trend data for a specific file (requires API key).
    
    Returns all runs where this file was analyzed, sorted by timestamp ascending.
    Useful for tracking how a file's health score has changed over time.
    
    Args:
        file: relative path to the file (e.g., "app/main.py")
    
    Returns:
        List of trend data points with run_id, timestamp, health_score, and dimension scores
    """
    # Validate file path
    try:
        validate_file_path(file)
    except ValidationError as e:
        return JSONResponse(
            status_code=400,
            content=e.to_dict()
        )
    
    trends = db.get_file_trends(file)
    
    if not trends:
        return JSONResponse(
            status_code=404,
            content={
                "error": f"No trend data found for file: {file}",
                "hint": "Ensure the file has been analyzed in at least one run. Check the file path is correct.",
                "code": "FILE_NOT_FOUND"
            }
        )
    
    return {
        "file_path": file,
        "data_points": len(trends),
        "trends": trends
    }


@app.get("/api/remediation/{file_name}", tags=["API"])
async def get_remediation(file_name: str, api_key: str = Depends(verify_api_key)):
    """Get remediation markdown for a specific file (requires API key).
    
    Args:
        file_name: Sanitized file name (e.g., "app_main_py_remediation")
        
    Returns:
        JSON with remediation markdown content
    """
    # Ensure file_name ends with _remediation.md
    if not file_name.endswith("_remediation.md"):
        file_name = f"{file_name}_remediation.md"
    
    remediation_path = Path("remediation") / file_name
    
    if not remediation_path.exists():
        return JSONResponse(
            status_code=404,
            content={
                "error": f"Remediation file not found: {file_name}",
                "hint": "Run 'python driftguard.py --remediate' to generate remediation files for CRITICAL and AT_RISK files.",
                "code": "REMEDIATION_NOT_FOUND"
            }
        )
    
    try:
        with open(remediation_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "file_name": file_name,
            "content": content
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Error reading remediation file: {str(e)}",
                "hint": "Check file permissions and ensure the remediation directory is accessible.",
                "code": "REMEDIATION_READ_ERROR"
            }
        )



@app.get("/api/language-config", tags=["API"])
async def get_language_config():
    """Get active language configuration (no API key required).
    
    Returns information about enabled and disabled file extensions,
    their language mappings, and configuration file path.
    """
    try:
        config_info = get_language_config_info()
        return config_info
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Failed to load language configuration: {str(e)}",
                "hint": "Check that language_config.json exists and is valid JSON.",
                "code": "LANGUAGE_CONFIG_ERROR"
            }
        )


@app.post("/api/language-config/reload", tags=["API"])
async def reload_language_config_endpoint(api_key: str = Depends(verify_api_key)):
    """Reload language configuration from disk (requires API key).
    
    Useful after manually editing the language_config.json file.
    Clears all caches and reloads the configuration.
    """
    success, message = reload_language_config()
    
    if success:
        return {
            "status": "success",
            "message": message
        }
    else:
        return JSONResponse(
            status_code=500,
            content={
                "error": message,
                "code": "RELOAD_FAILED"
            }
        )


@app.on_event("startup")
async def startup_event():
    """Print startup information."""
    port = Config.FASTAPI_PORT
    host = Config.FASTAPI_HOST
    print()
    print("=" * 70)
    print("DriftGuard Dashboard")
    print("=" * 70)
    print(f"Dashboard: http://{host}:{port}/")
    print(f"API: http://{host}:{port}/api/report")
    print(f"Trends: http://{host}:{port}/api/trends?file=<path>")
    print(f"Docs: http://{host}:{port}/docs")
    print("=" * 70)
    print()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=Config.FASTAPI_HOST,
        port=Config.FASTAPI_PORT,
        reload=Config.FASTAPI_RELOAD,
    )
