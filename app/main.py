"""main.py

FastAPI application for DriftGuard dashboard.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
from typing import Optional

from app.config import Config
from app.report_generator import get_latest_report, load_report


# Initialize FastAPI app
app = FastAPI(
    title="DriftGuard",
    description="Codebase Decay Monitor - Dashboard API",
    version="1.0.0"
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(Config.TEMPLATES_DIR))


@app.on_event("startup")
async def startup_event():
    """Print startup message."""
    print("\n" + "=" * 80)
    print("🔍 DriftGuard Dashboard Starting...")
    print("=" * 80)
    print(f"Dashboard URL: http://{Config.FASTAPI_HOST}:{Config.FASTAPI_PORT}")
    print(f"API Docs: http://{Config.FASTAPI_HOST}:{Config.FASTAPI_PORT}/docs")
    print(f"Output Directory: {Config.OUTPUT_DIR}")
    print("=" * 80)
    print("\n💡 Tip: Run 'python driftguard.py --repo . --days 30' to generate a report first")
    print()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Render the main dashboard with the most recent report.
    """
    # Try to load the latest report
    report = get_latest_report(str(Config.OUTPUT_DIR))
    
    if report is None:
        # No report found - show instructions
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "report": None,
                "no_report": True
            }
        )
    
    # Render dashboard with report data
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "report": report,
            "no_report": False
        }
    )


@app.get("/api/report")
async def get_report():
    """
    Get the most recent report as JSON.
    
    Returns:
        DriftReport JSON
    
    Raises:
        404: If no report exists
    """
    report = get_latest_report(str(Config.OUTPUT_DIR))
    
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "No report found",
                "message": "Run DriftGuard analysis first: python driftguard.py --repo . --days 30",
                "output_dir": str(Config.OUTPUT_DIR)
            }
        )
    
    return JSONResponse(content=report)


@app.get("/api/report/{filename}")
async def get_specific_report(filename: str):
    """
    Get a specific report by filename.
    
    Args:
        filename: Report filename (e.g., "report_20260502_120000.json")
    
    Returns:
        DriftReport JSON
    
    Raises:
        404: If report file not found
    """
    report_path = Config.OUTPUT_DIR / filename
    
    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Report not found",
                "filename": filename,
                "path": str(report_path)
            }
        )
    
    try:
        report = load_report(str(report_path))
        return JSONResponse(content=report)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Invalid report file",
                "message": "Report file is corrupted or not valid JSON"
            }
        )


@app.get("/api/reports")
async def list_reports():
    """
    List all available reports.
    
    Returns:
        List of report metadata (filename, timestamp, file size)
    """
    if not Config.OUTPUT_DIR.exists():
        return JSONResponse(content={"reports": []})
    
    reports = []
    for report_file in Config.OUTPUT_DIR.glob("report_*.json"):
        stat = report_file.stat()
        reports.append({
            "filename": report_file.name,
            "path": str(report_file),
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
            "url": f"/api/report/{report_file.name}"
        })
    
    # Sort by modification time (newest first)
    reports.sort(key=lambda x: x["modified_at"], reverse=True)
    
    return JSONResponse(content={"reports": reports, "count": len(reports)})


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Status information
    """
    latest_report = get_latest_report(str(Config.OUTPUT_DIR))
    
    return JSONResponse(content={
        "status": "ok",
        "version": "1.0.0",
        "service": "DriftGuard Dashboard",
        "has_report": latest_report is not None,
        "output_dir": str(Config.OUTPUT_DIR)
    })


@app.get("/api/summary")
async def get_summary():
    """
    Get just the summary statistics from the latest report.
    
    Returns:
        Summary dict
    
    Raises:
        404: If no report exists
    """
    report = get_latest_report(str(Config.OUTPUT_DIR))
    
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No report found"
        )
    
    return JSONResponse(content={
        "summary": report.get("summary", {}),
        "repo": report.get("repo"),
        "analyzed_at": report.get("analyzed_at"),
        "analysis_window_days": report.get("analysis_window_days")
    })


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Custom 404 handler."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "detail": str(exc.detail) if hasattr(exc, 'detail') else "Resource not found",
            "path": str(request.url)
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    """Custom 500 handler."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
            "path": str(request.url)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=Config.FASTAPI_HOST,
        port=Config.FASTAPI_PORT,
        reload=Config.FASTAPI_RELOAD
    )

# Made with Bob