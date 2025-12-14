"""
gitcloakd Security Scanner
Integrates with gitleaks, trufflehog, and built-in patterns
"""

import subprocess
import json
import re
import shutil
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from enum import Enum


class ScannerType(Enum):
    """Available scanner types."""
    BUILTIN = "builtin"
    GITLEAKS = "gitleaks"
    TRUFFLEHOG = "trufflehog"


@dataclass
class SecretFinding:
    """A detected secret/sensitive data."""
    scanner: str
    rule_id: str
    description: str
    file_path: str
    line_number: Optional[int] = None
    secret_preview: str = ""  # Redacted preview
    severity: str = "high"  # critical, high, medium, low
    commit: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    in_history: bool = False


@dataclass
class ScanResult:
    """Results from a security scan."""
    scanner: str
    success: bool
    findings: List[SecretFinding] = field(default_factory=list)
    files_scanned: int = 0
    duration: float = 0.0
    error: Optional[str] = None


class SecurityScanner:
    """
    Unified security scanner that integrates multiple detection tools.

    Supports:
    - Built-in regex patterns (always available)
    - gitleaks (if installed)
    - trufflehog (if installed)
    """

    # Built-in detection patterns
    BUILTIN_PATTERNS = {
        "aws-access-key": {
            "pattern": r"AKIA[0-9A-Z]{16}",
            "description": "AWS Access Key ID",
            "severity": "critical",
        },
        "aws-secret-key": {
            "pattern": r"(?i)aws[_\-\.]?secret[_\-\.]?(?:access[_\-\.]?)?key['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})",
            "description": "AWS Secret Access Key",
            "severity": "critical",
        },
        "github-token": {
            "pattern": r"gh[pousr]_[A-Za-z0-9_]{36,}",
            "description": "GitHub Personal Access Token",
            "severity": "critical",
        },
        "github-oauth": {
            "pattern": r"gho_[A-Za-z0-9_]{36,}",
            "description": "GitHub OAuth Token",
            "severity": "critical",
        },
        "anthropic-api-key": {
            "pattern": r"sk-ant-[a-zA-Z0-9\-_]{32,}",
            "description": "Anthropic API Key",
            "severity": "critical",
        },
        "openai-api-key": {
            "pattern": r"sk-[a-zA-Z0-9]{48,}",
            "description": "OpenAI API Key",
            "severity": "critical",
        },
        "google-api-key": {
            "pattern": r"AIza[0-9A-Za-z\-_]{35}",
            "description": "Google API Key",
            "severity": "high",
        },
        "slack-token": {
            "pattern": r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}",
            "description": "Slack Token",
            "severity": "high",
        },
        "slack-webhook": {
            "pattern": r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+",
            "description": "Slack Webhook URL",
            "severity": "high",
        },
        "discord-webhook": {
            "pattern": r"https://discord(?:app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+",
            "description": "Discord Webhook URL",
            "severity": "high",
        },
        "private-key": {
            "pattern": r"-----BEGIN (RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY( BLOCK)?-----",
            "description": "Private Key",
            "severity": "critical",
        },
        "jwt-token": {
            "pattern": r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
            "description": "JSON Web Token",
            "severity": "medium",
        },
        "generic-api-key": {
            "pattern": r"(?i)(api[_\-\.]?key|apikey)['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9]{16,})['\"]?",
            "description": "Generic API Key",
            "severity": "high",
        },
        "generic-secret": {
            "pattern": r"(?i)(secret|password|passwd|pwd)['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})['\"]?",
            "description": "Generic Secret/Password",
            "severity": "high",
        },
        "database-url": {
            "pattern": r"(?i)(mysql|postgres|postgresql|mongodb|redis|mssql)://[^\s]+:[^\s]+@[^\s]+",
            "description": "Database Connection String",
            "severity": "critical",
        },
        "stripe-key": {
            "pattern": r"sk_live_[a-zA-Z0-9]{24,}",
            "description": "Stripe Live Secret Key",
            "severity": "critical",
        },
        "stripe-publishable": {
            "pattern": r"pk_live_[a-zA-Z0-9]{24,}",
            "description": "Stripe Live Publishable Key",
            "severity": "medium",
        },
        "twilio-api-key": {
            "pattern": r"SK[a-f0-9]{32}",
            "description": "Twilio API Key",
            "severity": "high",
        },
        "sendgrid-api-key": {
            "pattern": r"SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}",
            "description": "SendGrid API Key",
            "severity": "high",
        },
        "npm-token": {
            "pattern": r"npm_[a-zA-Z0-9]{36}",
            "description": "NPM Access Token",
            "severity": "high",
        },
        "pypi-token": {
            "pattern": r"pypi-[a-zA-Z0-9_-]{50,}",
            "description": "PyPI API Token",
            "severity": "high",
        },
        "heroku-api-key": {
            "pattern": r"(?i)heroku[_\-\.]?api[_\-\.]?key['\"]?\s*[:=]\s*['\"]?([a-f0-9-]{36})",
            "description": "Heroku API Key",
            "severity": "high",
        },
    }

    def __init__(self, repo_path: Optional[str] = None):
        """Initialize scanner."""
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self._check_tools()

    def _check_tools(self) -> None:
        """Check which external tools are available."""
        self.has_gitleaks = shutil.which("gitleaks") is not None
        self.has_trufflehog = shutil.which("trufflehog") is not None

    def available_scanners(self) -> List[str]:
        """Get list of available scanners."""
        scanners = ["builtin"]
        if self.has_gitleaks:
            scanners.append("gitleaks")
        if self.has_trufflehog:
            scanners.append("trufflehog")
        return scanners

    def scan(
        self,
        scanners: Optional[List[str]] = None,
        scan_history: bool = False,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict[str, ScanResult]:
        """
        Run security scan with specified scanners.

        Args:
            scanners: List of scanners to use (default: all available)
            scan_history: Whether to scan git history
            include_patterns: File patterns to include
            exclude_patterns: File patterns to exclude

        Returns:
            Dict of scanner name -> ScanResult
        """
        if scanners is None:
            scanners = self.available_scanners()

        results = {}

        for scanner in scanners:
            if scanner == "builtin":
                results["builtin"] = self._scan_builtin(
                    include_patterns, exclude_patterns
                )
            elif scanner == "gitleaks" and self.has_gitleaks:
                results["gitleaks"] = self._scan_gitleaks(scan_history)
            elif scanner == "trufflehog" and self.has_trufflehog:
                results["trufflehog"] = self._scan_trufflehog(scan_history)

        return results

    def _scan_builtin(
        self,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> ScanResult:
        """Scan using built-in regex patterns."""
        import time
        start_time = time.time()

        findings = []
        files_scanned = 0

        # Default exclude patterns
        default_excludes = [
            ".git/*", "node_modules/*", "__pycache__/*", "*.pyc",
            ".venv/*", "venv/*", "*.min.js", "*.min.css",
            "*.lock", "package-lock.json", "yarn.lock",
        ]
        excludes = (exclude_patterns or []) + default_excludes

        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Check excludes
            rel_path = str(file_path.relative_to(self.repo_path))
            if any(self._match_pattern(rel_path, p) for p in excludes):
                continue

            # Check includes
            if include_patterns:
                if not any(self._match_pattern(rel_path, p) for p in include_patterns):
                    continue

            files_scanned += 1

            try:
                content = file_path.read_text(errors="ignore")
                for rule_id, rule in self.BUILTIN_PATTERNS.items():
                    matches = re.finditer(rule["pattern"], content)
                    for match in matches:
                        line_num = content[:match.start()].count("\n") + 1

                        # Create redacted preview
                        matched_text = match.group(0)
                        if len(matched_text) > 10:
                            preview = matched_text[:4] + "****" + matched_text[-4:]
                        else:
                            preview = "****"

                        findings.append(SecretFinding(
                            scanner="builtin",
                            rule_id=rule_id,
                            description=rule["description"],
                            file_path=rel_path,
                            line_number=line_num,
                            secret_preview=preview,
                            severity=rule["severity"],
                        ))
            except Exception:
                pass

        return ScanResult(
            scanner="builtin",
            success=True,
            findings=findings,
            files_scanned=files_scanned,
            duration=time.time() - start_time,
        )

    def _scan_gitleaks(self, scan_history: bool = False) -> ScanResult:
        """Scan using gitleaks."""
        import time
        start_time = time.time()

        try:
            cmd = ["gitleaks", "detect", "--source", str(self.repo_path), "--report-format", "json", "--report-path", "/dev/stdout"]

            if not scan_history:
                cmd.append("--no-git")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            findings = []
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    for item in data:
                        findings.append(SecretFinding(
                            scanner="gitleaks",
                            rule_id=item.get("RuleID", "unknown"),
                            description=item.get("Description", ""),
                            file_path=item.get("File", ""),
                            line_number=item.get("StartLine"),
                            secret_preview=item.get("Secret", "")[:8] + "****" if item.get("Secret") else "",
                            severity=self._gitleaks_severity(item.get("RuleID", "")),
                            commit=item.get("Commit"),
                            author=item.get("Author"),
                            date=item.get("Date"),
                            in_history=scan_history and item.get("Commit") is not None,
                        ))
                except json.JSONDecodeError:
                    pass

            return ScanResult(
                scanner="gitleaks",
                success=True,
                findings=findings,
                duration=time.time() - start_time,
            )

        except subprocess.TimeoutExpired:
            return ScanResult(
                scanner="gitleaks",
                success=False,
                error="Scan timed out",
                duration=time.time() - start_time,
            )
        except Exception as e:
            return ScanResult(
                scanner="gitleaks",
                success=False,
                error=str(e),
                duration=time.time() - start_time,
            )

    def _scan_trufflehog(self, scan_history: bool = False) -> ScanResult:
        """Scan using trufflehog."""
        import time
        start_time = time.time()

        try:
            if scan_history:
                cmd = ["trufflehog", "git", str(self.repo_path), "--json"]
            else:
                cmd = ["trufflehog", "filesystem", str(self.repo_path), "--json"]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            findings = []
            # trufflehog outputs one JSON object per line
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    source = item.get("SourceMetadata", {}).get("Data", {})
                    findings.append(SecretFinding(
                        scanner="trufflehog",
                        rule_id=item.get("DetectorName", "unknown"),
                        description=item.get("DetectorType", ""),
                        file_path=source.get("Filesystem", {}).get("file", "") or source.get("Git", {}).get("file", ""),
                        line_number=source.get("Filesystem", {}).get("line") or source.get("Git", {}).get("line"),
                        secret_preview=item.get("Raw", "")[:8] + "****" if item.get("Raw") else "",
                        severity="high",
                        commit=source.get("Git", {}).get("commit"),
                        in_history=scan_history and source.get("Git", {}).get("commit") is not None,
                    ))
                except json.JSONDecodeError:
                    pass

            return ScanResult(
                scanner="trufflehog",
                success=True,
                findings=findings,
                duration=time.time() - start_time,
            )

        except subprocess.TimeoutExpired:
            return ScanResult(
                scanner="trufflehog",
                success=False,
                error="Scan timed out",
                duration=time.time() - start_time,
            )
        except Exception as e:
            return ScanResult(
                scanner="trufflehog",
                success=False,
                error=str(e),
                duration=time.time() - start_time,
            )

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches a glob pattern."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.lower(), pattern.lower())

    def _gitleaks_severity(self, rule_id: str) -> str:
        """Map gitleaks rule to severity."""
        critical_rules = [
            "aws", "private-key", "github", "stripe-live", "database",
        ]
        high_rules = [
            "api-key", "token", "secret", "password", "credential",
        ]

        rule_lower = rule_id.lower()
        if any(r in rule_lower for r in critical_rules):
            return "critical"
        if any(r in rule_lower for r in high_rules):
            return "high"
        return "medium"

    def generate_report(
        self,
        results: Dict[str, ScanResult],
        format: str = "text",
    ) -> str:
        """
        Generate a report from scan results.

        Args:
            results: Scan results from scan()
            format: Output format (text, json, markdown)

        Returns:
            Formatted report
        """
        all_findings = []
        for scanner, result in results.items():
            all_findings.extend(result.findings)

        # Deduplicate by file+line
        unique_findings = {}
        for f in all_findings:
            key = f"{f.file_path}:{f.line_number}:{f.rule_id}"
            if key not in unique_findings:
                unique_findings[key] = f

        findings = list(unique_findings.values())

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        findings.sort(key=lambda x: severity_order.get(x.severity, 4))

        if format == "json":
            return json.dumps({
                "total_findings": len(findings),
                "by_severity": {
                    "critical": sum(1 for f in findings if f.severity == "critical"),
                    "high": sum(1 for f in findings if f.severity == "high"),
                    "medium": sum(1 for f in findings if f.severity == "medium"),
                    "low": sum(1 for f in findings if f.severity == "low"),
                },
                "findings": [
                    {
                        "scanner": f.scanner,
                        "rule_id": f.rule_id,
                        "description": f.description,
                        "file": f.file_path,
                        "line": f.line_number,
                        "severity": f.severity,
                        "in_history": f.in_history,
                    }
                    for f in findings
                ],
            }, indent=2)

        if format == "markdown":
            lines = [
                "# Security Scan Report",
                "",
                f"**Total Findings:** {len(findings)}",
                "",
                "| Severity | Count |",
                "|----------|-------|",
                f"| Critical | {sum(1 for f in findings if f.severity == 'critical')} |",
                f"| High | {sum(1 for f in findings if f.severity == 'high')} |",
                f"| Medium | {sum(1 for f in findings if f.severity == 'medium')} |",
                f"| Low | {sum(1 for f in findings if f.severity == 'low')} |",
                "",
                "## Findings",
                "",
            ]

            for f in findings:
                sev_badge = {
                    "critical": "[CRIT]",
                    "high": "[HIGH]",
                    "medium": "[MED]",
                    "low": "[LOW]",
                }.get(f.severity, "[?]")

                lines.append(f"### {sev_badge} {f.rule_id}")
                lines.append(f"- **File:** `{f.file_path}`:{f.line_number or '?'}")
                lines.append(f"- **Description:** {f.description}")
                lines.append(f"- **Scanner:** {f.scanner}")
                if f.in_history:
                    lines.append(f"- **In History:** Yes (commit: {f.commit})")
                lines.append("")

            return "\n".join(lines)

        # Default text format
        lines = [
            "=" * 60,
            "Security Scan Report",
            "=" * 60,
            f"Total Findings: {len(findings)}",
            f"  Critical: {sum(1 for f in findings if f.severity == 'critical')}",
            f"  High: {sum(1 for f in findings if f.severity == 'high')}",
            f"  Medium: {sum(1 for f in findings if f.severity == 'medium')}",
            f"  Low: {sum(1 for f in findings if f.severity == 'low')}",
            "",
            "Findings:",
            "-" * 60,
        ]

        for f in findings:
            lines.append(f"[{f.severity.upper()}] {f.rule_id}")
            lines.append(f"  File: {f.file_path}:{f.line_number or '?'}")
            lines.append(f"  {f.description}")
            if f.in_history:
                lines.append(f"  In git history (commit: {f.commit})")
            lines.append("")

        return "\n".join(lines)
