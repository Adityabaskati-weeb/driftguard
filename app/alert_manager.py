"""alert_manager.py

Alert management for DriftGuard watch mode.
Checks health scores and triggers alerts based on configured thresholds.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alerts for DriftGuard analysis runs.
    
    Future enhancements:
    - Email notifications
    - Slack/Discord webhooks
    - Custom alert rules
    - Alert history tracking
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize AlertManager with optional configuration.
        
        Args:
            config: Optional dict with alert settings:
                - enabled: bool (default: False)
                - critical_threshold: int (default: 40)
                - email_to: str (optional)
                - webhook_url: str (optional)
        """
        self.config = config or {}
        self.enabled = self.config.get('enabled', False)
        self.critical_threshold = self.config.get('critical_threshold', 40)
        
        logger.info(f"AlertManager initialized (enabled={self.enabled})")
    
    def check_and_alert(self, report: Dict) -> None:
        """Check report for issues and trigger alerts if needed.
        
        Args:
            report: DriftReport dict from report_generator.generate_report()
        """
        if not self.enabled:
            logger.debug("Alerts disabled, skipping check")
            return
        
        # Extract critical files
        critical_files = self._find_critical_files(report)
        
        if critical_files:
            self._trigger_alert(report, critical_files)
        else:
            logger.info("No critical issues found, no alerts triggered")
    
    def _find_critical_files(self, report: Dict) -> List[Dict]:
        """Find files with health scores below critical threshold.
        
        Args:
            report: DriftReport dict
            
        Returns:
            List of file dicts with critical health scores
        """
        critical_files = []
        files = report.get('files', [])
        
        for file_data in files:
            health_score = file_data.get('health_score', 100)
            if health_score < self.critical_threshold:
                critical_files.append(file_data)
        
        return critical_files
    
    def _trigger_alert(self, report: Dict, critical_files: List[Dict]) -> None:
        """Trigger alert for critical files.
        
        Args:
            report: DriftReport dict
            critical_files: List of file dicts with critical health scores
        """
        timestamp = report.get('analyzed_at', datetime.now().isoformat())
        repo = report.get('repo', 'unknown')
        
        alert_message = self._format_alert_message(repo, timestamp, critical_files)
        
        # Log alert (future: send email, webhook, etc.)
        logger.warning(f"ALERT TRIGGERED: {len(critical_files)} critical files found")
        logger.warning(alert_message)
        
        # Future: Send email, webhook, etc.
        # self._send_email(alert_message)
        # self._send_webhook(alert_message)
    
    def _format_alert_message(self, repo: str, timestamp: str, critical_files: List[Dict]) -> str:
        """Format alert message for critical files.
        
        Args:
            repo: Repository path
            timestamp: Analysis timestamp
            critical_files: List of critical file dicts
            
        Returns:
            Formatted alert message string
        """
        lines = [
            "=" * 70,
            "🚨 DriftGuard CRITICAL ALERT",
            "=" * 70,
            f"Repository: {repo}",
            f"Timestamp: {timestamp}",
            f"Critical Files: {len(critical_files)}",
            "",
            "Files requiring immediate attention:",
            ""
        ]
        
        for file_data in critical_files[:10]:  # Limit to top 10
            file_path = file_data.get('file_path', 'unknown')
            health_score = file_data.get('health_score', 0)
            lines.append(f"  🔴 {file_path} (score: {health_score:.1f})")
        
        if len(critical_files) > 10:
            lines.append(f"  ... and {len(critical_files) - 10} more")
        
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)


# Made with Bob