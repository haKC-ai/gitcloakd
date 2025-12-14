"""
gitcloakd Alert Notifier
Sends alerts for repository events
"""

import json
import subprocess
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import requests

from gitcloakd.core.config import Config


@dataclass
class Alert:
    """An alert event."""
    event_type: str  # commit, key_change, decrypt, new_user, security_warning
    severity: str  # info, warning, critical
    repo: str
    message: str
    details: Dict[str, Any]
    timestamp: str
    user: Optional[str] = None


class AlertNotifier:
    """Handles alert notifications for gitcloakd events."""

    def __init__(self, repo_path: Optional[str] = None):
        """Initialize alert notifier."""
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.config = Config.load_repo(str(self.repo_path))
        self.alert_config = self.config.alerts

    def notify(self, alert: Alert) -> Dict[str, bool]:
        """
        Send an alert through all configured channels.

        Args:
            alert: Alert to send

        Returns:
            Dict of channel -> success status
        """
        if not self.alert_config.enabled:
            return {}

        results = {}

        # Check if this event type should trigger notifications
        if not self._should_notify(alert.event_type):
            return results

        # Send to all configured channels
        if self.alert_config.webhook_url:
            results["webhook"] = self._send_webhook(alert)

        if self.alert_config.slack_webhook:
            results["slack"] = self._send_slack(alert)

        if self.alert_config.discord_webhook:
            results["discord"] = self._send_discord(alert)

        if self.alert_config.email_notifications:
            results["email"] = self._send_email(alert)

        # Log alert locally
        self._log_alert(alert)

        return results

    def on_commit(self, commit_sha: str, author: str, message: str, files: List[str]) -> None:
        """Handle commit event."""
        # Check for sensitive files in commit
        sensitive_files = self._check_sensitive_files(files)

        severity = "critical" if sensitive_files else "info"
        alert_message = f"New commit by {author}: {message[:50]}"

        if sensitive_files:
            alert_message = f"WARNING: Commit contains sensitive files! {alert_message}"

        alert = Alert(
            event_type="commit",
            severity=severity,
            repo=self.config.repo_path,
            message=alert_message,
            details={
                "commit": commit_sha,
                "author": author,
                "message": message,
                "files": files,
                "sensitive_files": sensitive_files
            },
            timestamp=datetime.now().isoformat(),
            user=author
        )

        self.notify(alert)

    def on_key_change(self, action: str, user: str, key_id: str) -> None:
        """Handle key change event (add/remove user key)."""
        alert = Alert(
            event_type="key_change",
            severity="warning",
            repo=self.config.repo_path,
            message=f"Key {action}: {user} ({key_id})",
            details={
                "action": action,
                "user": user,
                "key_id": key_id
            },
            timestamp=datetime.now().isoformat(),
            user=user
        )

        self.notify(alert)

    def on_decrypt(self, user: str, files: List[str]) -> None:
        """Handle decrypt event."""
        alert = Alert(
            event_type="decrypt",
            severity="info",
            repo=self.config.repo_path,
            message=f"Files decrypted by {user}",
            details={
                "user": user,
                "files": files,
                "count": len(files)
            },
            timestamp=datetime.now().isoformat(),
            user=user
        )

        self.notify(alert)

    def on_new_user(self, user_name: str, user_email: str, role: str) -> None:
        """Handle new user added event."""
        alert = Alert(
            event_type="new_user",
            severity="warning",
            repo=self.config.repo_path,
            message=f"New user added: {user_name} <{user_email}> as {role}",
            details={
                "name": user_name,
                "email": user_email,
                "role": role
            },
            timestamp=datetime.now().isoformat(),
            user=user_email
        )

        self.notify(alert)

    def on_security_warning(self, warning_type: str, message: str, details: Dict[str, Any]) -> None:
        """Handle security warning event."""
        alert = Alert(
            event_type="security_warning",
            severity="critical",
            repo=self.config.repo_path,
            message=f"SECURITY WARNING: {message}",
            details={
                "warning_type": warning_type,
                **details
            },
            timestamp=datetime.now().isoformat()
        )

        self.notify(alert)

    def _should_notify(self, event_type: str) -> bool:
        """Check if event type should trigger notification."""
        event_map = {
            "commit": self.alert_config.on_commit,
            "key_change": self.alert_config.on_key_change,
            "decrypt": self.alert_config.on_decrypt,
            "new_user": self.alert_config.on_new_user,
            "security_warning": True,  # Always notify on security warnings
        }
        return event_map.get(event_type, True)

    def _send_webhook(self, alert: Alert) -> bool:
        """Send alert to generic webhook."""
        try:
            payload = {
                "event": alert.event_type,
                "severity": alert.severity,
                "repo": alert.repo,
                "message": alert.message,
                "details": alert.details,
                "timestamp": alert.timestamp,
                "user": alert.user
            }

            response = requests.post(
                self.alert_config.webhook_url,
                json=payload,
                timeout=10
            )
            return response.status_code < 400
        except Exception:
            return False

    def _send_slack(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        try:
            # Color based on severity
            color_map = {
                "info": "#36a64f",
                "warning": "#ffc107",
                "critical": "#dc3545"
            }

            payload = {
                "attachments": [{
                    "color": color_map.get(alert.severity, "#6c757d"),
                    "title": f"gitcloakd: {alert.event_type.upper()}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Repository", "value": alert.repo, "short": True},
                        {"title": "Severity", "value": alert.severity.upper(), "short": True},
                    ],
                    "footer": "gitcloakd",
                    "ts": int(datetime.fromisoformat(alert.timestamp).timestamp())
                }]
            }

            if alert.user:
                payload["attachments"][0]["fields"].append({
                    "title": "User",
                    "value": alert.user,
                    "short": True
                })

            response = requests.post(
                self.alert_config.slack_webhook,
                json=payload,
                timeout=10
            )
            return response.status_code < 400
        except Exception:
            return False

    def _send_discord(self, alert: Alert) -> bool:
        """Send alert to Discord."""
        try:
            # Color based on severity (Discord uses decimal colors)
            color_map = {
                "info": 3066993,    # Green
                "warning": 16776960,  # Yellow
                "critical": 15158332  # Red
            }

            payload = {
                "embeds": [{
                    "title": f"gitcloakd: {alert.event_type.upper()}",
                    "description": alert.message,
                    "color": color_map.get(alert.severity, 9807270),
                    "fields": [
                        {"name": "Repository", "value": alert.repo, "inline": True},
                        {"name": "Severity", "value": alert.severity.upper(), "inline": True},
                    ],
                    "footer": {"text": "gitcloakd"},
                    "timestamp": alert.timestamp
                }]
            }

            if alert.user:
                payload["embeds"][0]["fields"].append({
                    "name": "User",
                    "value": alert.user,
                    "inline": True
                })

            response = requests.post(
                self.alert_config.discord_webhook,
                json=payload,
                timeout=10
            )
            return response.status_code < 400
        except Exception:
            return False

    def _send_email(self, alert: Alert) -> bool:
        """Send alert via email (using system mail)."""
        try:
            subject = f"[gitcloakd] {alert.severity.upper()}: {alert.event_type}"
            body = f"""
gitcloakd Alert
================

Event: {alert.event_type}
Severity: {alert.severity}
Repository: {alert.repo}
Time: {alert.timestamp}
User: {alert.user or 'N/A'}

Message:
{alert.message}

Details:
{json.dumps(alert.details, indent=2)}

---
This alert was generated by gitcloakd
"""
            # Use mail command if available
            process = subprocess.run(
                ["mail", "-s", subject, self.config.owner_email],
                input=body,
                text=True,
                capture_output=True
            )
            return process.returncode == 0
        except Exception:
            return False

    def _log_alert(self, alert: Alert) -> None:
        """Log alert to local file."""
        log_dir = self.repo_path / ".gitcloakd" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "alerts.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps({
                "event_type": alert.event_type,
                "severity": alert.severity,
                "repo": alert.repo,
                "message": alert.message,
                "details": alert.details,
                "timestamp": alert.timestamp,
                "user": alert.user
            }) + "\n")

    def _check_sensitive_files(self, files: List[str]) -> List[str]:
        """Check if any files match sensitive patterns."""
        import fnmatch

        sensitive = []
        for file in files:
            for pattern in self.config.auto_encrypt_patterns:
                if fnmatch.fnmatch(file, pattern):
                    sensitive.append(file)
                    break
        return sensitive

    def get_alert_history(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[Alert]:
        """
        Get alert history from log file.

        Args:
            limit: Maximum number of alerts to return
            event_type: Filter by event type
            severity: Filter by severity

        Returns:
            List of Alert objects
        """
        log_file = self.repo_path / ".gitcloakd" / "logs" / "alerts.jsonl"

        if not log_file.exists():
            return []

        alerts = []
        with open(log_file) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    alert = Alert(
                        event_type=data["event_type"],
                        severity=data["severity"],
                        repo=data["repo"],
                        message=data["message"],
                        details=data["details"],
                        timestamp=data["timestamp"],
                        user=data.get("user")
                    )

                    # Apply filters
                    if event_type and alert.event_type != event_type:
                        continue
                    if severity and alert.severity != severity:
                        continue

                    alerts.append(alert)
                except Exception:
                    continue

        # Return most recent alerts first
        return list(reversed(alerts[-limit:]))

    def setup_git_hooks(self) -> None:
        """Set up Git hooks for automatic alerts."""
        hooks_dir = self.repo_path / ".git" / "hooks"

        if not hooks_dir.exists():
            return

        # Post-commit hook
        post_commit = hooks_dir / "post-commit"
        post_commit_content = """#!/bin/bash
# gitcloakd post-commit hook for alerts

if command -v gitcloakd &> /dev/null; then
    # Get commit info
    COMMIT=$(git rev-parse HEAD)
    AUTHOR=$(git log -1 --format='%an')
    MESSAGE=$(git log -1 --format='%s')
    FILES=$(git diff-tree --no-commit-id --name-only -r HEAD | tr '\\n' ',')

    # Trigger alert
    gitcloakd alert commit "$COMMIT" "$AUTHOR" "$MESSAGE" "$FILES" 2>/dev/null || true
fi
"""
        post_commit.write_text(post_commit_content)
        post_commit.chmod(0o755)
