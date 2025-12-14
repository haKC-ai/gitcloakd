"""
gitcloakd Repository Analyzer
Analyzes GitHub repositories for sensitive data exposure
"""

import subprocess
import json
import re
import fnmatch
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from gitcloakd.github.client import GitHubClient


@dataclass
class SensitivePattern:
    """Pattern for detecting sensitive data."""
    name: str
    pattern: str
    severity: str  # critical, high, medium, low
    description: str
    file_patterns: List[str] = field(default_factory=list)


@dataclass
class Finding:
    """A security finding in a repository."""
    repo: str
    file_path: str
    pattern_name: str
    severity: str
    line_number: Optional[int] = None
    commit: Optional[str] = None
    in_history: bool = False
    recommendation: str = ""


@dataclass
class RepoAnalysis:
    """Analysis results for a repository."""
    repo_name: str
    analyzed_at: str
    total_commits: int
    contributors_count: int
    branches_count: int
    is_private: bool
    findings: List[Finding] = field(default_factory=list)
    sensitive_files: List[str] = field(default_factory=list)
    history_exposure: List[Dict[str, Any]] = field(default_factory=list)
    encryption_status: str = "not_encrypted"  # not_encrypted, partially, fully
    recommendation: str = ""
    risk_score: int = 0  # 0-100


class RepoAnalyzer:
    """Analyzes repositories for sensitive data and encryption needs."""

    # Default sensitive patterns
    SENSITIVE_PATTERNS = [
        SensitivePattern(
            name="AWS Access Key",
            pattern=r"AKIA[0-9A-Z]{16}",
            severity="critical",
            description="AWS Access Key ID",
        ),
        SensitivePattern(
            name="AWS Secret Key",
            pattern=r"['\"][0-9a-zA-Z/+]{40}['\"]",
            severity="critical",
            description="Potential AWS Secret Access Key",
        ),
        SensitivePattern(
            name="Private Key",
            pattern=r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----",
            severity="critical",
            description="Private key file",
        ),
        SensitivePattern(
            name="GitHub Token",
            pattern=r"gh[pousr]_[A-Za-z0-9_]{36,}",
            severity="critical",
            description="GitHub Personal Access Token",
        ),
        SensitivePattern(
            name="Anthropic API Key",
            pattern=r"sk-ant-[a-zA-Z0-9\-]{32,}",
            severity="critical",
            description="Anthropic API Key",
        ),
        SensitivePattern(
            name="OpenAI API Key",
            pattern=r"sk-[a-zA-Z0-9]{48}",
            severity="critical",
            description="OpenAI API Key",
        ),
        SensitivePattern(
            name="Generic API Key",
            pattern=r"['\"]?api[_-]?key['\"]?\s*[:=]\s*['\"][a-zA-Z0-9]{16,}['\"]",
            severity="high",
            description="Generic API key pattern",
        ),
        SensitivePattern(
            name="Password in Config",
            pattern=r"(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{4,}['\"]",
            severity="high",
            description="Password in configuration",
        ),
        SensitivePattern(
            name="Database URL",
            pattern=r"(mysql|postgres|mongodb|redis)://[^\s]+:[^\s]+@",
            severity="high",
            description="Database connection string with credentials",
        ),
        SensitivePattern(
            name="Slack Token",
            pattern=r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}",
            severity="high",
            description="Slack API Token",
        ),
        SensitivePattern(
            name="JWT Token",
            pattern=r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
            severity="medium",
            description="JSON Web Token",
        ),
    ]

    # Sensitive file patterns
    SENSITIVE_FILES = [
        "*.env", ".env.*", "*.key", "*.pem", "*.p12", "*.pfx",
        "id_rsa*", "id_ed25519*", "id_dsa*",
        "credentials.json", "secrets.json", "secrets.yaml", "secrets.yml",
        "service-account*.json", "*.keystore", "*.jks",
        ".aws/credentials", ".netrc", ".npmrc", ".pypirc",
    ]

    def __init__(self, github_client: Optional[GitHubClient] = None):
        """Initialize analyzer."""
        self.github = github_client or GitHubClient()

    def analyze_all_repos(
        self,
        include_orgs: bool = True,
        include_forks: bool = False
    ) -> List[RepoAnalysis]:
        """
        Analyze all repositories for the authenticated user.

        Args:
            include_orgs: Include organization repositories
            include_forks: Include forked repositories

        Returns:
            List of analysis results
        """
        results = []

        # Get user repos
        user_repos = self.github.list_repos(include_forks=include_forks)
        for repo in user_repos:
            analysis = self.analyze_repo(repo.full_name)
            results.append(analysis)

        # Get org repos
        if include_orgs:
            orgs = self.github.list_orgs()
            for org in orgs:
                org_repos = self.github.list_repos(
                    owner=org.login,
                    include_forks=include_forks
                )
                for repo in org_repos:
                    analysis = self.analyze_repo(repo.full_name)
                    results.append(analysis)

        return results

    def analyze_repo(self, repo_name: str, deep_scan: bool = False) -> RepoAnalysis:
        """
        Analyze a single repository.

        Args:
            repo_name: Repository name (owner/repo)
            deep_scan: If True, scan git history (slower)

        Returns:
            Analysis results
        """
        repo = self.github.get_repo(repo_name)

        analysis = RepoAnalysis(
            repo_name=repo_name,
            analyzed_at=datetime.now().isoformat(),
            total_commits=0,
            contributors_count=0,
            branches_count=0,
            is_private=repo.private,
        )

        # Get repo stats
        try:
            commits = self.github.get_repo_commits(repo_name, limit=1000)
            analysis.total_commits = len(commits)

            contributors = self.github.get_repo_contributors(repo_name)
            analysis.contributors_count = len(contributors)

            branches = self.github.get_repo_branches(repo_name)
            analysis.branches_count = len(branches)
        except Exception:
            pass

        # Check for sensitive files in current state
        analysis.sensitive_files = self._find_sensitive_files(repo_name)

        # Check for gitcloakd initialization
        analysis.encryption_status = self._check_encryption_status(repo_name)

        # Scan for sensitive patterns (requires local clone for deep scan)
        if deep_scan:
            findings, history = self._deep_scan(repo_name)
            analysis.findings = findings
            analysis.history_exposure = history

        # Calculate risk score
        analysis.risk_score = self._calculate_risk_score(analysis)

        # Generate recommendation
        analysis.recommendation = self._generate_recommendation(analysis)

        return analysis

    def _find_sensitive_files(self, repo_name: str) -> List[str]:
        """Find sensitive files in repository."""
        sensitive = []

        try:
            # Get repository tree
            result = subprocess.run(
                ["gh", "api", f"repos/{repo_name}/git/trees/HEAD?recursive=1"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                for item in data.get("tree", []):
                    if item["type"] == "blob":
                        path = item["path"]
                        for pattern in self.SENSITIVE_FILES:
                            if fnmatch.fnmatch(path.lower(), pattern.lower()):
                                sensitive.append(path)
                                break
        except Exception:
            pass

        return sensitive

    def _check_encryption_status(self, repo_name: str) -> str:
        """Check if repository is using gitcloakd."""
        try:
            # Check for .gitcloakd directory
            result = subprocess.run(
                ["gh", "api", f"repos/{repo_name}/contents/.gitcloakd"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return "fully"

            # Check for .gitattributes with git-crypt
            result = subprocess.run(
                ["gh", "api", f"repos/{repo_name}/contents/.gitattributes"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if "git-crypt" in (data.get("content", "") or ""):
                    return "partially"
        except Exception:
            pass

        return "not_encrypted"

    def _deep_scan(
        self,
        repo_name: str
    ) -> Tuple[List[Finding], List[Dict[str, Any]]]:
        """
        Deep scan repository including git history.

        Requires cloning the repository locally.
        """
        findings = []
        history_exposure = []

        # Clone to temp directory
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                subprocess.run(
                    ["gh", "repo", "clone", repo_name, tmpdir],
                    capture_output=True,
                    check=True
                )

                # Scan current files
                findings.extend(self._scan_directory(tmpdir, repo_name))

                # Scan git history
                history_exposure = self._scan_history(tmpdir, repo_name)

            except Exception:
                pass

        return findings, history_exposure

    def _scan_directory(self, directory: str, repo_name: str) -> List[Finding]:
        """Scan directory for sensitive patterns."""
        findings = []
        dir_path = Path(directory)

        for file_path in dir_path.rglob("*"):
            if file_path.is_file() and ".git" not in str(file_path):
                try:
                    content = file_path.read_text(errors="ignore")
                    for pattern in self.SENSITIVE_PATTERNS:
                        matches = re.finditer(pattern.pattern, content, re.IGNORECASE)
                        for match in matches:
                            # Find line number
                            line_num = content[:match.start()].count("\n") + 1
                            relative_path = str(file_path.relative_to(dir_path))

                            findings.append(Finding(
                                repo=repo_name,
                                file_path=relative_path,
                                pattern_name=pattern.name,
                                severity=pattern.severity,
                                line_number=line_num,
                                in_history=False,
                                recommendation=f"Encrypt or remove: {pattern.description}"
                            ))
                except Exception:
                    pass

        return findings

    def _scan_history(self, directory: str, repo_name: str) -> List[Dict[str, Any]]:
        """Scan git history for sensitive data exposure."""
        exposure = []

        try:
            # Get list of all files ever in the repo
            result = subprocess.run(
                ["git", "log", "--all", "--pretty=format:", "--name-only", "--diff-filter=A"],
                cwd=directory,
                capture_output=True,
                text=True
            )

            historical_files = set(result.stdout.strip().split("\n"))

            for pattern in self.SENSITIVE_FILES:
                for file_path in historical_files:
                    if file_path and fnmatch.fnmatch(file_path.lower(), pattern.lower()):
                        # Check if file still exists
                        current_exists = (Path(directory) / file_path).exists()

                        # Get commit info
                        commit_result = subprocess.run(
                            ["git", "log", "--all", "-1", "--pretty=format:%H|%an|%ae|%ai",
                             "--", file_path],
                            cwd=directory,
                            capture_output=True,
                            text=True
                        )

                        if commit_result.stdout:
                            parts = commit_result.stdout.strip().split("|")
                            exposure.append({
                                "file": file_path,
                                "commit": parts[0] if len(parts) > 0 else "",
                                "author": parts[1] if len(parts) > 1 else "",
                                "email": parts[2] if len(parts) > 2 else "",
                                "date": parts[3] if len(parts) > 3 else "",
                                "still_exists": current_exists,
                                "risk": "HIGH" if not current_exists else "CRITICAL"
                            })
        except Exception:
            pass

        return exposure

    def _calculate_risk_score(self, analysis: RepoAnalysis) -> int:
        """Calculate risk score (0-100) based on analysis."""
        score = 0

        # Public repo with sensitive files is high risk
        if not analysis.is_private and analysis.sensitive_files:
            score += 50

        # Sensitive files present
        score += min(len(analysis.sensitive_files) * 10, 30)

        # Findings from pattern scan
        critical = sum(1 for f in analysis.findings if f.severity == "critical")
        high = sum(1 for f in analysis.findings if f.severity == "high")
        score += critical * 15 + high * 5

        # History exposure
        score += min(len(analysis.history_exposure) * 5, 20)

        # Not encrypted
        if analysis.encryption_status == "not_encrypted":
            score += 10

        return min(score, 100)

    def _generate_recommendation(self, analysis: RepoAnalysis) -> str:
        """Generate recommendation based on analysis."""
        recommendations = []

        if analysis.risk_score >= 70:
            recommendations.append("URGENT: High risk repository. Immediate action required.")

        if not analysis.is_private and analysis.sensitive_files:
            recommendations.append("Consider making this repository private.")

        if analysis.sensitive_files:
            recommendations.append(
                f"Encrypt {len(analysis.sensitive_files)} sensitive files with gitcloakd."
            )

        if analysis.history_exposure:
            recommendations.append(
                "Sensitive files found in git history. Consider purging history."
            )

        if analysis.encryption_status == "not_encrypted":
            recommendations.append("Initialize gitcloakd for this repository.")

        if not recommendations:
            recommendations.append("Repository appears secure. Continue monitoring.")

        return " ".join(recommendations)

    def generate_report(
        self,
        analyses: List[RepoAnalysis],
        format: str = "text"
    ) -> str:
        """
        Generate a report from analysis results.

        Args:
            analyses: List of analysis results
            format: Output format (text, json, markdown)

        Returns:
            Formatted report
        """
        if format == "json":
            return json.dumps([
                {
                    "repo": a.repo_name,
                    "risk_score": a.risk_score,
                    "private": a.is_private,
                    "encrypted": a.encryption_status,
                    "sensitive_files": len(a.sensitive_files),
                    "findings": len(a.findings),
                    "recommendation": a.recommendation,
                }
                for a in analyses
            ], indent=2)

        # Sort by risk score
        sorted_analyses = sorted(analyses, key=lambda x: x.risk_score, reverse=True)

        if format == "markdown":
            lines = [
                "# gitcloakd Security Analysis Report",
                f"\nGenerated: {datetime.now().isoformat()}",
                f"\nRepositories Analyzed: {len(analyses)}",
                "\n## Summary by Risk Level\n",
                "| Repository | Risk | Private | Encrypted | Sensitive Files | Recommendation |",
                "|------------|------|---------|-----------|-----------------|----------------|"
            ]

            for a in sorted_analyses:
                risk_indicator = "[CRIT]" if a.risk_score >= 70 else "[WARN]" if a.risk_score >= 40 else "[OK]"
                lines.append(
                    f"| {a.repo_name} | {risk_indicator} {a.risk_score} | "
                    f"{'Yes' if a.is_private else 'No'} | {a.encryption_status} | "
                    f"{len(a.sensitive_files)} | {a.recommendation[:50]}... |"
                )

            return "\n".join(lines)

        # Default text format
        lines = [
            "=" * 60,
            "gitcloakd Security Analysis Report",
            "=" * 60,
            f"Generated: {datetime.now().isoformat()}",
            f"Repositories Analyzed: {len(analyses)}",
            "",
        ]

        for a in sorted_analyses:
            risk_level = "CRITICAL" if a.risk_score >= 70 else "WARNING" if a.risk_score >= 40 else "OK"
            lines.extend([
                "-" * 60,
                f"Repository: {a.repo_name}",
                f"Risk Score: {a.risk_score}/100 ({risk_level})",
                f"Private: {'Yes' if a.is_private else 'No'}",
                f"Encryption: {a.encryption_status}",
                f"Sensitive Files: {len(a.sensitive_files)}",
                f"Recommendation: {a.recommendation}",
            ])

        lines.append("=" * 60)
        return "\n".join(lines)
