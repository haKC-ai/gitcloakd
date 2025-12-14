"""
gitcloakd GitHub Client
Interacts with GitHub via gh CLI and API
"""

import subprocess
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class Repository:
    """GitHub repository information."""
    name: str
    full_name: str
    owner: str
    private: bool
    description: str
    url: str
    ssh_url: str
    default_branch: str
    created_at: str
    updated_at: str
    pushed_at: str
    size: int
    language: Optional[str]
    has_issues: bool
    has_wiki: bool
    fork: bool
    archived: bool


@dataclass
class Organization:
    """GitHub organization information."""
    login: str
    name: str
    description: str
    url: str
    repos_count: int


class GitHubClient:
    """Client for GitHub operations using gh CLI."""

    def __init__(self):
        """Initialize GitHub client."""
        self._check_gh_installed()

    def _check_gh_installed(self) -> None:
        """Check if gh CLI is installed and authenticated."""
        try:
            subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                check=True
            )
        except FileNotFoundError:
            raise RuntimeError(
                "GitHub CLI (gh) not found. Install it from: https://cli.github.com/"
            )

    def is_authenticated(self) -> bool:
        """Check if user is authenticated with GitHub."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def authenticate(self) -> bool:
        """Start interactive authentication."""
        try:
            subprocess.run(
                ["gh", "auth", "login"],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def get_current_user(self) -> Dict[str, Any]:
        """Get current authenticated user information."""
        result = subprocess.run(
            ["gh", "api", "user"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)

    def list_repos(
        self,
        owner: Optional[str] = None,
        limit: int = 100,
        include_forks: bool = True,
        include_archived: bool = False
    ) -> List[Repository]:
        """
        List repositories for user or organization.

        Args:
            owner: Username or org (None for current user)
            limit: Maximum number of repos to fetch
            include_forks: Include forked repositories
            include_archived: Include archived repositories

        Returns:
            List of Repository objects
        """
        cmd = ["gh", "repo", "list"]
        if owner:
            cmd.append(owner)
        cmd.extend(["--limit", str(limit), "--json",
                   "name,nameWithOwner,owner,isPrivate,description,url,sshUrl,"
                   "defaultBranchRef,createdAt,updatedAt,pushedAt,diskUsage,"
                   "primaryLanguage,hasIssuesEnabled,hasWikiEnabled,isFork,isArchived"])

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        repos_data = json.loads(result.stdout)

        repos = []
        for r in repos_data:
            # Filter forks and archived if needed
            if not include_forks and r.get("isFork", False):
                continue
            if not include_archived and r.get("isArchived", False):
                continue

            repo = Repository(
                name=r["name"],
                full_name=r["nameWithOwner"],
                owner=r["owner"]["login"],
                private=r["isPrivate"],
                description=r.get("description", "") or "",
                url=r["url"],
                ssh_url=r["sshUrl"],
                default_branch=r.get("defaultBranchRef", {}).get("name", "main"),
                created_at=r["createdAt"],
                updated_at=r["updatedAt"],
                pushed_at=r.get("pushedAt", ""),
                size=r.get("diskUsage", 0),
                language=r.get("primaryLanguage", {}).get("name") if r.get("primaryLanguage") else None,
                has_issues=r.get("hasIssuesEnabled", True),
                has_wiki=r.get("hasWikiEnabled", True),
                fork=r.get("isFork", False),
                archived=r.get("isArchived", False)
            )
            repos.append(repo)

        return repos

    def list_orgs(self) -> List[Organization]:
        """List organizations the user belongs to."""
        result = subprocess.run(
            ["gh", "api", "user/orgs"],
            capture_output=True,
            text=True,
            check=True
        )
        orgs_data = json.loads(result.stdout)

        orgs = []
        for o in orgs_data:
            # Get additional org details
            org_detail = subprocess.run(
                ["gh", "api", f"orgs/{o['login']}"],
                capture_output=True,
                text=True
            )
            detail = json.loads(org_detail.stdout) if org_detail.returncode == 0 else {}

            org = Organization(
                login=o["login"],
                name=detail.get("name", o["login"]),
                description=detail.get("description", "") or "",
                url=o["url"],
                repos_count=detail.get("public_repos", 0) + detail.get("total_private_repos", 0)
            )
            orgs.append(org)

        return orgs

    def get_repo(self, repo_name: str) -> Repository:
        """Get details for a specific repository."""
        result = subprocess.run(
            ["gh", "repo", "view", repo_name, "--json",
             "name,nameWithOwner,owner,isPrivate,description,url,sshUrl,"
             "defaultBranchRef,createdAt,updatedAt,pushedAt,diskUsage,"
             "primaryLanguage,hasIssuesEnabled,hasWikiEnabled,isFork,isArchived"],
            capture_output=True,
            text=True,
            check=True
        )
        r = json.loads(result.stdout)

        return Repository(
            name=r["name"],
            full_name=r["nameWithOwner"],
            owner=r["owner"]["login"],
            private=r["isPrivate"],
            description=r.get("description", "") or "",
            url=r["url"],
            ssh_url=r["sshUrl"],
            default_branch=r.get("defaultBranchRef", {}).get("name", "main"),
            created_at=r["createdAt"],
            updated_at=r["updatedAt"],
            pushed_at=r.get("pushedAt", ""),
            size=r.get("diskUsage", 0),
            language=r.get("primaryLanguage", {}).get("name") if r.get("primaryLanguage") else None,
            has_issues=r.get("hasIssuesEnabled", True),
            has_wiki=r.get("hasWikiEnabled", True),
            fork=r.get("isFork", False),
            archived=r.get("isArchived", False)
        )

    def create_repo(
        self,
        name: str,
        private: bool = True,
        description: str = "",
        org: Optional[str] = None
    ) -> Repository:
        """
        Create a new repository.

        Args:
            name: Repository name
            private: Create as private repository
            description: Repository description
            org: Organization to create in (None for user)

        Returns:
            Created Repository object
        """
        cmd = ["gh", "repo", "create"]
        if org:
            cmd.append(f"{org}/{name}")
        else:
            cmd.append(name)

        if private:
            cmd.append("--private")
        else:
            cmd.append("--public")

        if description:
            cmd.extend(["--description", description])

        cmd.append("--confirm")

        subprocess.run(cmd, check=True)

        # Fetch and return the created repo
        full_name = f"{org}/{name}" if org else name
        return self.get_repo(full_name)

    def clone_repo(self, repo_name: str, target_dir: Optional[str] = None) -> str:
        """
        Clone a repository.

        Args:
            repo_name: Repository name (owner/repo or just repo)
            target_dir: Target directory (None for repo name)

        Returns:
            Path to cloned repository
        """
        cmd = ["gh", "repo", "clone", repo_name]
        if target_dir:
            cmd.append(target_dir)

        subprocess.run(cmd, check=True)

        return target_dir or repo_name.split("/")[-1]

    def get_repo_contributors(self, repo_name: str) -> List[Dict[str, Any]]:
        """Get list of repository contributors."""
        result = subprocess.run(
            ["gh", "api", f"repos/{repo_name}/contributors"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)

    def get_repo_commits(
        self,
        repo_name: str,
        limit: int = 100,
        since: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get repository commits."""
        endpoint = f"repos/{repo_name}/commits?per_page={limit}"
        if since:
            endpoint += f"&since={since}"

        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)

    def get_repo_branches(self, repo_name: str) -> List[Dict[str, Any]]:
        """Get repository branches."""
        result = subprocess.run(
            ["gh", "api", f"repos/{repo_name}/branches"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)

    def setup_webhook(
        self,
        repo_name: str,
        webhook_url: str,
        events: List[str] = None,
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Set up a webhook for repository events.

        Args:
            repo_name: Repository name
            webhook_url: URL to receive webhook events
            events: List of events to trigger on
            secret: Webhook secret for validation

        Returns:
            Created webhook info
        """
        if events is None:
            events = ["push", "pull_request"]

        payload = {
            "name": "web",
            "active": True,
            "events": events,
            "config": {
                "url": webhook_url,
                "content_type": "json",
            }
        }

        if secret:
            payload["config"]["secret"] = secret

        result = subprocess.run(
            ["gh", "api", f"repos/{repo_name}/hooks", "-X", "POST",
             "-f", f"name={payload['name']}",
             "-f", f"active={str(payload['active']).lower()}",
             "-f", f"config[url]={webhook_url}",
             "-f", "config[content_type]=json"] +
            [item for event in events for item in ["-f", f"events[]={event}"]],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)

    def make_repo_private(self, repo_name: str) -> bool:
        """Make a repository private."""
        try:
            subprocess.run(
                ["gh", "repo", "edit", repo_name, "--visibility", "private"],
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def add_collaborator(
        self,
        repo_name: str,
        username: str,
        permission: str = "push"
    ) -> bool:
        """
        Add a collaborator to repository.

        Args:
            repo_name: Repository name
            username: GitHub username to add
            permission: Permission level (pull, push, admin)

        Returns:
            True if successful
        """
        try:
            subprocess.run(
                ["gh", "api", f"repos/{repo_name}/collaborators/{username}",
                 "-X", "PUT", "-f", f"permission={permission}"],
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def remove_collaborator(self, repo_name: str, username: str) -> bool:
        """Remove a collaborator from repository."""
        try:
            subprocess.run(
                ["gh", "api", f"repos/{repo_name}/collaborators/{username}",
                 "-X", "DELETE"],
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
