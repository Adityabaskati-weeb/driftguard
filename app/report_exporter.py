"""report_exporter.py

Export DriftGuard reports to Markdown and PDF formats.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import io


def _generate_sparkline(values: List[float]) -> str:
    """Generate ASCII sparkline from values using block characters.
    
    Args:
        values: List of numeric values
        
    Returns:
        ASCII sparkline string using ▁▂▃▄▅▆▇█ characters
    """
    if not values:
        return ""
    
    # Block characters from lowest to highest
    blocks = "▁▂▃▄▅▆▇█"
    
    # Normalize values to 0-7 range
    min_val = min(values)
    max_val = max(values)
    
    if max_val == min_val:
        # All values are the same
        return blocks[4] * len(values)
    
    # Map each value to a block character
    sparkline = ""
    for val in values:
        normalized = (val - min_val) / (max_val - min_val)
        index = min(int(normalized * 7), 7)
        sparkline += blocks[index]
    
    return sparkline


def _get_status_badge(status: str) -> str:
    """Get colored badge for status in Markdown.
    
    Args:
        status: Status string (CRITICAL, AT_RISK, WATCH, HEALTHY)
        
    Returns:
        Markdown badge string
    """
    badges = {
        "CRITICAL": "![CRITICAL](https://img.shields.io/badge/CRITICAL-red)",
        "AT_RISK": "![AT_RISK](https://img.shields.io/badge/AT__RISK-orange)",
        "WATCH": "![WATCH](https://img.shields.io/badge/WATCH-yellow)",
        "HEALTHY": "![HEALTHY](https://img.shields.io/badge/HEALTHY-green)"
    }
    return badges.get(status, status)


def _format_dimensions_table(dimensions: Dict) -> str:
    """Format dimensions as a Markdown table.
    
    Args:
        dimensions: Dimensions dict from scored file
        
    Returns:
        Markdown table string
    """
    if not dimensions:
        return "N/A"
    
    lines = ["| Dimension | Score |", "|-----------|-------|"]
    for key, value in dimensions.items():
        # Format dimension name (e.g., "churn_rate" -> "Churn Rate")
        name = key.replace("_", " ").title()
        lines.append(f"| {name} | {value:.1f} |")
    
    return "\n".join(lines)


def export_markdown(report: Dict, output_path: str) -> str:
    """Export report to Markdown format.
    
    Args:
        report: DriftReport dict from report_generator
        output_path: Path to save Markdown file
        
    Returns:
        Path to saved Markdown file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract report data
    repo_name = Path(report.get('repo', 'Unknown')).name
    timestamp = report.get('analyzed_at', datetime.now().isoformat())
    summary = report.get('summary', {})
    files = report.get('files', [])
    
    # Format timestamp for display
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except:
        formatted_time = timestamp
    
    # Build Markdown content
    lines = []
    
    # Header
    lines.append(f"# DriftGuard Report — {repo_name} — {formatted_time}")
    lines.append("")
    
    # Summary section
    lines.append("## 📊 Summary")
    lines.append("")
    lines.append(f"- **Total Files Analyzed:** {summary.get('total_files', 0)}")
    lines.append(f"- **Average Health Score:** {summary.get('average_health_score', 0):.1f}/100")
    lines.append("")
    lines.append("### Status Distribution")
    lines.append("")
    lines.append(f"- 🔴 **CRITICAL:** {summary.get('critical_count', 0)} files")
    lines.append(f"- 🟠 **AT_RISK:** {summary.get('at_risk_count', 0)} files")
    lines.append(f"- 🟡 **WATCH:** {summary.get('watch_count', 0)} files")
    lines.append(f"- 🟢 **HEALTHY:** {summary.get('healthy_count', 0)} files")
    lines.append("")
    
    # Filter to only CRITICAL and AT_RISK files for concise report
    critical_and_at_risk = [
        f for f in files 
        if f.get('status') in ['CRITICAL', 'AT_RISK']
    ]
    
    if critical_and_at_risk:
        lines.append("## ⚠️ Files Requiring Attention")
        lines.append("")
        lines.append("*Showing only CRITICAL and AT_RISK files*")
        lines.append("")
        
        for file_data in critical_and_at_risk:
            file_path = file_data.get('file_path', 'Unknown')
            health_score = file_data.get('health_score', 0)
            status = file_data.get('status', 'UNKNOWN')
            dimensions = file_data.get('dimensions', {})
            decay_summary = file_data.get('decay_summary', 'N/A')
            recommendation = file_data.get('recommendation', 'N/A')
            
            # File header with badge
            lines.append(f"### {file_path}")
            lines.append("")
            lines.append(f"**Status:** {_get_status_badge(status)} | **Health Score:** {health_score:.1f}/100")
            lines.append("")
            
            # Dimensions table
            lines.append("**Dimensions:**")
            lines.append("")
            lines.append(_format_dimensions_table(dimensions))
            lines.append("")
            
            # Trend sparkline (if available)
            if 'trend_data' in file_data and file_data['trend_data']:
                trend_values = [t.get('health_score', 0) for t in file_data['trend_data']]
                sparkline = _generate_sparkline(trend_values)
                lines.append(f"**Trend:** `{sparkline}`")
                lines.append("")
            
            # Decay summary
            lines.append(f"**Decay Summary:** {decay_summary}")
            lines.append("")
            
            # Recommendation
            lines.append(f"**Recommendation:** {recommendation}")
            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("## ✅ All Files Healthy")
        lines.append("")
        lines.append("No files require immediate attention.")
        lines.append("")
    
    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by DriftGuard on {formatted_time}*")
    
    # Write to file
    content = "\n".join(lines)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return str(output_path)


def export_pdf(report: Dict, output_path: str) -> str:
    """Export report to PDF format using WeasyPrint.
    
    Args:
        report: DriftReport dict from report_generator
        output_path: Path to save PDF file
        
    Returns:
        Path to saved PDF file
    """
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        raise ImportError(
            "WeasyPrint is required for PDF export. "
            "Install it with: pip install weasyprint"
        )
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract report data
    repo_name = Path(report.get('repo', 'Unknown')).name
    timestamp = report.get('analyzed_at', datetime.now().isoformat())
    summary = report.get('summary', {})
    files = report.get('files', [])
    
    # Format timestamp for display
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except:
        formatted_time = timestamp
    
    # Filter to only CRITICAL and AT_RISK files
    critical_and_at_risk = [
        f for f in files 
        if f.get('status') in ['CRITICAL', 'AT_RISK']
    ]
    
    # Build HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>DriftGuard Report - {repo_name}</title>
    </head>
    <body>
        <h1>DriftGuard Report — {repo_name}</h1>
        <p class="timestamp">{formatted_time}</p>
        
        <h2>📊 Summary</h2>
        <div class="summary">
            <p><strong>Total Files Analyzed:</strong> {summary.get('total_files', 0)}</p>
            <p><strong>Average Health Score:</strong> {summary.get('average_health_score', 0):.1f}/100</p>
            
            <h3>Status Distribution</h3>
            <ul>
                <li><span class="badge critical">CRITICAL</span> {summary.get('critical_count', 0)} files</li>
                <li><span class="badge at-risk">AT_RISK</span> {summary.get('at_risk_count', 0)} files</li>
                <li><span class="badge watch">WATCH</span> {summary.get('watch_count', 0)} files</li>
                <li><span class="badge healthy">HEALTHY</span> {summary.get('healthy_count', 0)} files</li>
            </ul>
        </div>
    """
    
    if critical_and_at_risk:
        html_content += """
        <h2>⚠️ Files Requiring Attention</h2>
        <p class="note"><em>Showing only CRITICAL and AT_RISK files</em></p>
        """
        
        for file_data in critical_and_at_risk:
            file_path = file_data.get('file_path', 'Unknown')
            health_score = file_data.get('health_score', 0)
            status = file_data.get('status', 'UNKNOWN')
            dimensions = file_data.get('dimensions', {})
            decay_summary = file_data.get('decay_summary', 'N/A')
            recommendation = file_data.get('recommendation', 'N/A')
            
            status_class = status.lower().replace('_', '-')
            
            html_content += f"""
            <div class="file-section">
                <h3>{file_path}</h3>
                <p>
                    <span class="badge {status_class}">{status}</span>
                    <strong>Health Score:</strong> {health_score:.1f}/100
                </p>
                
                <h4>Dimensions</h4>
                <table>
                    <tr>
                        <th>Dimension</th>
                        <th>Score</th>
                    </tr>
            """
            
            for key, value in dimensions.items():
                name = key.replace("_", " ").title()
                html_content += f"""
                    <tr>
                        <td>{name}</td>
                        <td>{value:.1f}</td>
                    </tr>
                """
            
            html_content += """
                </table>
            """
            
            # Trend sparkline
            if 'trend_data' in file_data and file_data['trend_data']:
                trend_values = [t.get('health_score', 0) for t in file_data['trend_data']]
                sparkline = _generate_sparkline(trend_values)
                html_content += f"""
                <p><strong>Trend:</strong> <code>{sparkline}</code></p>
                """
            
            html_content += f"""
                <p><strong>Decay Summary:</strong> {decay_summary}</p>
                <p><strong>Recommendation:</strong> {recommendation}</p>
            </div>
            """
    else:
        html_content += """
        <h2>✅ All Files Healthy</h2>
        <p>No files require immediate attention.</p>
        """
    
    html_content += f"""
        <div class="footer">
            <hr>
            <p><em>Generated by DriftGuard on {formatted_time}</em></p>
        </div>
    </body>
    </html>
    """
    
    # CSS styling
    css_content = """
    @page {
        size: A4;
        margin: 2cm;
    }
    
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 100%;
    }
    
    h1 {
        color: #2c3e50;
        border-bottom: 3px solid #3498db;
        padding-bottom: 10px;
        margin-bottom: 5px;
    }
    
    h2 {
        color: #34495e;
        margin-top: 30px;
        border-bottom: 2px solid #95a5a6;
        padding-bottom: 5px;
    }
    
    h3 {
        color: #2c3e50;
        margin-top: 20px;
    }
    
    h4 {
        color: #7f8c8d;
        margin-top: 15px;
        margin-bottom: 10px;
    }
    
    .timestamp {
        color: #7f8c8d;
        font-size: 0.9em;
        margin-top: 0;
    }
    
    .summary {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        margin: 20px 0;
    }
    
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 3px;
        font-size: 0.85em;
        font-weight: bold;
        color: white;
        margin-right: 10px;
    }
    
    .badge.critical {
        background-color: #e74c3c;
    }
    
    .badge.at-risk {
        background-color: #e67e22;
    }
    
    .badge.watch {
        background-color: #f39c12;
    }
    
    .badge.healthy {
        background-color: #27ae60;
    }
    
    .note {
        font-style: italic;
        color: #7f8c8d;
        margin-top: 10px;
    }
    
    .file-section {
        background-color: #ffffff;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 15px;
        margin: 20px 0;
        page-break-inside: avoid;
    }
    
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
    }
    
    th, td {
        padding: 8px;
        text-align: left;
        border-bottom: 1px solid #ddd;
    }
    
    th {
        background-color: #f2f2f2;
        font-weight: bold;
    }
    
    code {
        background-color: #f4f4f4;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Courier New', monospace;
        font-size: 1.1em;
    }
    
    .footer {
        margin-top: 40px;
        padding-top: 20px;
        text-align: center;
        color: #7f8c8d;
    }
    
    hr {
        border: none;
        border-top: 1px solid #ddd;
        margin: 20px 0;
    }
    """
    
    # Generate PDF
    html = HTML(string=html_content)
    css = CSS(string=css_content)
    html.write_pdf(output_path, stylesheets=[css])
    
    return str(output_path)


def export_report(report: Dict, format: str, output_dir: str = "output") -> str:
    """Export report in specified format.
    
    Args:
        report: DriftReport dict from report_generator
        format: Export format ('json', 'markdown', 'pdf', or 'all')
        output_dir: Output directory (default: 'output')
        
    Returns:
        Path to exported file(s) or directory if format='all'
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_name = f"report_{timestamp}"
    
    exported_files = []
    
    if format in ['json', 'all']:
        json_path = output_dir / f"{base_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        exported_files.append(str(json_path))
    
    if format in ['markdown', 'all']:
        md_path = output_dir / f"{base_name}.md"
        export_markdown(report, str(md_path))
        exported_files.append(str(md_path))
    
    if format in ['pdf', 'all']:
        pdf_path = output_dir / f"{base_name}.pdf"
        export_pdf(report, str(pdf_path))
        exported_files.append(str(pdf_path))
    
    if format == 'all':
        return f"Exported to: {', '.join(exported_files)}"
    
    return exported_files[0] if exported_files else ""

# Made with Bob
