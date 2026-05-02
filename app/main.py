"""main.py

FastAPI application for DriftGuard dashboard.
Serves JSON reports and renders the web dashboard.
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from app.config import Config, get_latest_report
from app.report_generator import load_report


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


@app.get("/api/report", tags=["API"])
async def get_report():
    """Return the most recent report as JSON."""
    report = get_report_data()
    
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No report found. Run 'python driftguard.py --repo . --days 30' first."
        )
    
    return report


@app.get("/api/report/{filename}", tags=["API"])
async def get_report_by_filename(filename: str):
    """Return a specific report by filename."""
    report_path = Config.OUTPUT_DIR / filename
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report {filename} not found")
    
    if not str(report_path).endswith('.json'):
        raise HTTPException(status_code=400, detail="Only JSON reports are supported")
    
    return load_report(str(report_path))


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
