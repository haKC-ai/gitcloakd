"""
gitcloakd Core Encryption Engine
Handles GPG encryption/decryption for Git repositories
"""

import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import gnupg

from gitcloakd.core.config import Config, UserConfig, AgentConfig


class GPGNotInstalledException(Exception):
    """Raised when GPG is not installed on the system."""
    pass


class GitCrypted:
    """Main encryption engine for Git repositories."""

    def __init__(self, repo_path: Optional[str] = None):
        """Initialize gitcloakd for a repository."""
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.config_dir = self.repo_path / ".gitcloakd"
        try:
            self.gpg = gnupg.GPG()
        except OSError as e:
            if "Unable to run gpg" in str(e):
                raise GPGNotInstalledException(
                    "GPG is not installed. Please install GPG and try again.\n"
                    "  macOS:   brew install gnupg\n"
                    "  Ubuntu:  sudo apt install gnupg\n"
                    "  Windows: winget install GnuPG.GnuPG"
                ) from e
            raise
        self.config = Config.load_repo(str(self.repo_path))

    def is_initialized(self) -> bool:
        """Check if repo is initialized with gitcloakd."""
        return self.config_dir.exists() and (self.config_dir / "config.yaml").exists()

    def initialize(
        self,
        owner_key_id: str,
        owner_email: str,
        patterns: Optional[List[str]] = None
    ) -> bool:
        """
        Initialize a repository for gitcloakd encryption.

        Args:
            owner_key_id: GPG key ID of the repository owner
            owner_email: Email of the repository owner
            patterns: File patterns to auto-encrypt

        Returns:
            True if initialization successful
        """
        # Create config directory
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Set up configuration
        self.config.initialized = True
        self.config.repo_path = str(self.repo_path)
        self.config.owner_key_id = owner_key_id
        self.config.owner_email = owner_email
        self.config.created_date = datetime.now().isoformat()
        self.config.last_modified = datetime.now().isoformat()

        if patterns:
            self.config.auto_encrypt_patterns = patterns

        # Add owner as first user
        owner = UserConfig(
            name=self._get_gpg_name(owner_key_id),
            email=owner_email,
            gpg_key_id=owner_key_id,
            role="owner",
            added_date=datetime.now().isoformat()
        )
        self.config.add_user(owner)

        # Save config
        self.config.save_repo(str(self.repo_path))

        # Create .gitattributes for encryption patterns
        self._create_gitattributes()

        # Create .gitignore additions
        self._update_gitignore()

        # Create agent instructions template
        self._create_agent_instructions()

        # Initialize git-crypt if available
        self._init_git_crypt()

        return True

    def encrypt_file(self, file_path: str, recipients: Optional[List[str]] = None) -> bool:
        """
        Encrypt a single file with GPG.

        Args:
            file_path: Path to file to encrypt
            recipients: List of GPG key IDs to encrypt for (default: all users)

        Returns:
            True if encryption successful
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get recipients
        if recipients is None:
            recipients = [u.gpg_key_id for u in self.config.users if u.can_decrypt]

        if not recipients:
            raise ValueError("No recipients specified for encryption")

        # Read file
        with open(path, "rb") as f:
            data = f.read()

        # Encrypt
        encrypted = self.gpg.encrypt(
            data,
            recipients,
            armor=True,
            always_trust=True
        )

        if not encrypted.ok:
            raise RuntimeError(f"Encryption failed: {encrypted.status}")

        # Write encrypted file
        encrypted_path = path.with_suffix(path.suffix + ".gpg")
        with open(encrypted_path, "w") as f:
            f.write(str(encrypted))

        # Remove original (optional, controlled by config)
        # path.unlink()

        return True

    def decrypt_file(self, file_path: str, output_path: Optional[str] = None) -> bool:
        """
        Decrypt a GPG-encrypted file.

        Args:
            file_path: Path to encrypted file
            output_path: Where to write decrypted file (default: remove .gpg extension)

        Returns:
            True if decryption successful
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read encrypted file
        with open(path, "rb") as f:
            data = f.read()

        # Decrypt
        decrypted = self.gpg.decrypt(data)

        if not decrypted.ok:
            raise RuntimeError(f"Decryption failed: {decrypted.status}")

        # Determine output path
        if output_path is None:
            if path.suffix == ".gpg":
                output_path = str(path.with_suffix(""))
            else:
                output_path = str(path) + ".decrypted"

        # Write decrypted file
        with open(output_path, "wb") as f:
            f.write(decrypted.data)

        return True

    def encrypt_repo(self, force: bool = False) -> Dict[str, Any]:
        """
        Encrypt all sensitive files in the repository.

        Args:
            force: Re-encrypt already encrypted files

        Returns:
            Summary of encryption results
        """
        results = {
            "encrypted": [],
            "skipped": [],
            "errors": []
        }

        for pattern in self.config.auto_encrypt_patterns:
            for path in self.repo_path.glob(f"**/{pattern}"):
                # Skip already encrypted
                if path.suffix == ".gpg" and not force:
                    results["skipped"].append(str(path))
                    continue

                # Skip gitcloakd internals
                if ".gitcloakd" in str(path):
                    continue

                try:
                    self.encrypt_file(str(path))
                    results["encrypted"].append(str(path))
                except Exception as e:
                    results["errors"].append({"file": str(path), "error": str(e)})

        return results

    def decrypt_repo(self) -> Dict[str, Any]:
        """
        Decrypt all encrypted files in the repository.

        Returns:
            Summary of decryption results
        """
        results = {
            "decrypted": [],
            "skipped": [],
            "errors": []
        }

        for path in self.repo_path.glob("**/*.gpg"):
            # Skip gitcloakd internals
            if ".gitcloakd" in str(path):
                continue

            try:
                self.decrypt_file(str(path))
                results["decrypted"].append(str(path))
            except Exception as e:
                results["errors"].append({"file": str(path), "error": str(e)})

        return results

    def add_user(
        self,
        email: str,
        gpg_key_id: str,
        name: Optional[str] = None,
        role: str = "collaborator"
    ) -> bool:
        """
        Add a user who can decrypt repository contents.

        Args:
            email: User's email
            gpg_key_id: User's GPG key ID
            name: User's name (auto-detected from GPG if not provided)
            role: User role (owner, admin, collaborator, readonly)

        Returns:
            True if user added successfully
        """
        if name is None:
            name = self._get_gpg_name(gpg_key_id)

        user = UserConfig(
            name=name,
            email=email,
            gpg_key_id=gpg_key_id,
            role=role,
            added_date=datetime.now().isoformat()
        )

        self.config.add_user(user)
        self.config.last_modified = datetime.now().isoformat()
        self.config.save_repo(str(self.repo_path))

        # Re-encrypt files to include new user
        self._reencrypt_for_users()

        return True

    def remove_user(self, email: str) -> bool:
        """
        Remove a user's access to encrypted content.

        Args:
            email: User's email to remove

        Returns:
            True if user removed successfully
        """
        if not self.config.remove_user(email):
            return False

        self.config.last_modified = datetime.now().isoformat()
        self.config.save_repo(str(self.repo_path))

        # Re-encrypt files to exclude removed user
        self._reencrypt_for_users()

        return True

    def add_agent(
        self,
        name: str,
        agent_type: str,
        can_decrypt: bool = False,
        gpg_key_id: Optional[str] = None,
        allowed_paths: Optional[List[str]] = None,
        denied_paths: Optional[List[str]] = None
    ) -> bool:
        """
        Add an AI coding agent configuration.

        Args:
            name: Agent name (e.g., "claude-code", "copilot")
            agent_type: Agent type (claude, gemini, copilot, custom)
            can_decrypt: Whether agent can decrypt content
            gpg_key_id: Agent's GPG key ID (if can_decrypt=True)
            allowed_paths: Paths agent can access
            denied_paths: Paths agent cannot access

        Returns:
            True if agent added successfully
        """
        agent = AgentConfig(
            name=name,
            type=agent_type,
            gpg_key_id=gpg_key_id,
            can_decrypt=can_decrypt,
            allowed_paths=allowed_paths or ["*"],
            denied_paths=denied_paths or [".gitcloakd/*", "*.key", "*.pem"]
        )

        self.config.add_agent(agent)
        self.config.save_repo(str(self.repo_path))

        # Create/update agent instructions
        self._create_agent_instructions()

        return True

    def purge_history(self, confirm: bool = False) -> bool:
        """
        Purge Git history to remove any unencrypted sensitive data.

        WARNING: This is destructive and cannot be undone!

        Args:
            confirm: Must be True to proceed

        Returns:
            True if history purged successfully
        """
        if not confirm:
            raise ValueError("Must set confirm=True to purge history")

        # Create backup branch first
        backup_branch = f"backup-pre-purge-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        subprocess.run(
            ["git", "branch", backup_branch],
            cwd=str(self.repo_path),
            check=True
        )

        # Get list of sensitive patterns
        patterns = self.config.auto_encrypt_patterns

        # Use git filter-repo or BFG to remove sensitive files from history
        for pattern in patterns:
            try:
                # Try git filter-repo first (modern approach)
                subprocess.run(
                    ["git", "filter-repo", "--path-glob", pattern, "--invert-paths", "--force"],
                    cwd=str(self.repo_path),
                    check=True,
                    capture_output=True
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to git filter-branch (older but more available)
                subprocess.run(
                    [
                        "git", "filter-branch", "--force", "--index-filter",
                        f"git rm --cached --ignore-unmatch '{pattern}'",
                        "--prune-empty", "--tag-name-filter", "cat", "--", "--all"
                    ],
                    cwd=str(self.repo_path),
                    check=False  # May fail if no matches
                )

        # Force garbage collection
        subprocess.run(
            ["git", "reflog", "expire", "--expire=now", "--all"],
            cwd=str(self.repo_path),
            check=True
        )
        subprocess.run(
            ["git", "gc", "--prune=now", "--aggressive"],
            cwd=str(self.repo_path),
            check=True
        )

        return True

    def analyze_exposure(self) -> Dict[str, Any]:
        """
        Analyze repository for potential exposure of sensitive data.

        Returns:
            Analysis results including exposure metrics and recommendations
        """
        results = {
            "sensitive_files": [],
            "unencrypted_secrets": [],
            "history_exposure": [],
            "commit_count": 0,
            "contributors": [],
            "recommendations": []
        }

        # Directories to skip during scanning (cloud storage, temp, etc)
        skip_dirs = {
            'CloudStorage', 'Library', '.Trash', 'node_modules', '.git',
            '__pycache__', '.cache', 'venv', '.venv', 'env', '.env',
            'dist', 'build', '.tox', '.pytest_cache', '.mypy_cache'
        }

        def safe_glob(base_path: Path, pattern: str):
            """Safe glob that skips problematic directories."""
            import os
            for root, dirs, files in os.walk(str(base_path)):
                # Skip cloud storage, library dirs, and other problematic paths
                dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
                # Check depth - don't go too deep
                depth = root.replace(str(base_path), '').count(os.sep)
                if depth > 10:
                    dirs.clear()
                    continue
                import fnmatch
                for f in files:
                    if fnmatch.fnmatch(f, pattern):
                        yield Path(root) / f

        # Check current files
        for pattern in self.config.auto_encrypt_patterns:
            try:
                for path in safe_glob(self.repo_path, pattern):
                    if path.suffix != ".gpg":
                        results["sensitive_files"].append({
                            "path": str(path.relative_to(self.repo_path)),
                            "encrypted": False,
                            "recommendation": "Encrypt this file"
                        })
            except (OSError, TimeoutError, PermissionError):
                continue  # Skip inaccessible paths

        # Check git history for sensitive files
        try:
            log_output = subprocess.check_output(
                ["git", "log", "--all", "--pretty=format:%H", "--name-only"],
                cwd=str(self.repo_path),
                text=True
            )

            commits = log_output.split("\n\n")
            results["commit_count"] = len([c for c in commits if c.strip()])

            for pattern in self.config.auto_encrypt_patterns:
                # Simple pattern matching in history
                import fnmatch
                for line in log_output.split("\n"):
                    if fnmatch.fnmatch(line.strip(), pattern):
                        results["history_exposure"].append({
                            "pattern": pattern,
                            "found_in_history": True
                        })
                        break

            # Get contributors
            contributors = subprocess.check_output(
                ["git", "log", "--all", "--format=%ae", "--no-merges"],
                cwd=str(self.repo_path),
                text=True
            )
            results["contributors"] = list(set(contributors.strip().split("\n")))

        except subprocess.CalledProcessError:
            pass  # Not a git repo or git not available

        # Generate recommendations
        if results["sensitive_files"]:
            results["recommendations"].append({
                "priority": "HIGH",
                "action": "Encrypt sensitive files",
                "details": f"{len(results['sensitive_files'])} unencrypted sensitive files found"
            })

        if results["history_exposure"]:
            results["recommendations"].append({
                "priority": "CRITICAL",
                "action": "Purge Git history",
                "details": "Sensitive files found in Git history - use 'gitcloakd purge-history'"
            })

        return results

    def unencrypt(self, confirm: bool = False) -> bool:
        """
        Fully unencrypt the repository (undo gitcloakd).

        WARNING: This removes encryption and exposes all files!

        Args:
            confirm: Must be True to proceed

        Returns:
            True if unencryption successful
        """
        if not confirm:
            raise ValueError("Must set confirm=True to unencrypt")

        # Decrypt all files
        self.decrypt_repo()

        # Remove .gpg files (now that we have decrypted versions)
        for path in self.repo_path.glob("**/*.gpg"):
            if ".gitcloakd" not in str(path):
                path.unlink()

        # Remove gitcloakd configuration
        shutil.rmtree(self.config_dir, ignore_errors=True)

        # Update .gitattributes
        gitattributes = self.repo_path / ".gitattributes"
        if gitattributes.exists():
            lines = gitattributes.read_text().split("\n")
            lines = [line for line in lines if "gitcloakd" not in line.lower()]
            gitattributes.write_text("\n".join(lines))

        return True

    def _get_gpg_name(self, key_id: str) -> str:
        """Get name associated with a GPG key."""
        keys = self.gpg.list_keys(keys=[key_id])
        if keys:
            uids = keys[0].get("uids", [])
            if uids:
                # Extract name from UID (format: "Name <email>")
                uid = uids[0]
                if "<" in uid:
                    return uid.split("<")[0].strip()
                return uid
        return "Unknown"

    def _create_gitattributes(self) -> None:
        """Create or update .gitattributes for encryption."""
        gitattributes = self.repo_path / ".gitattributes"

        existing = ""
        if gitattributes.exists():
            existing = gitattributes.read_text()

        # Add patterns for git-crypt
        additions = [
            "\n# gitcloakd - encrypted files",
        ]
        for pattern in self.config.auto_encrypt_patterns:
            additions.append(f"{pattern} filter=git-crypt diff=git-crypt")

        new_content = existing + "\n".join(additions)
        gitattributes.write_text(new_content)

    def _update_gitignore(self) -> None:
        """Update .gitignore with gitcloakd patterns."""
        gitignore = self.repo_path / ".gitignore"

        existing = ""
        if gitignore.exists():
            existing = gitignore.read_text()

        if "gitcloakd" not in existing:
            additions = """
# gitcloakd - do not commit these
.gitcloakd/keys/
*.gpg.key
"""
            gitignore.write_text(existing + additions)

    def _create_agent_instructions(self) -> None:
        """Create instructions file for AI coding agents."""
        instructions_file = self.config_dir / "agent-instructions.md"

        content = """# gitcloakd Agent Instructions

This repository uses gitcloakd for encryption. Follow these guidelines:

## Encrypted Files

The following patterns are encrypted and should not be committed in plaintext:
"""
        for pattern in self.config.auto_encrypt_patterns:
            content += f"- `{pattern}`\n"

        content += """
## Access Rules

### Allowed Operations
- Read and modify non-encrypted source code
- Create new files (except in denied paths)
- Run tests and builds

### Denied Operations
- Do not access or modify files matching encrypted patterns
- Do not commit decrypted secrets
- Do not expose encryption keys
- Do not modify .gitcloakd/ configuration

## Configured Agents
"""
        for agent in self.config.agents:
            content += f"\n### {agent.name} ({agent.type})\n"
            content += f"- Can decrypt: {agent.can_decrypt}\n"
            content += f"- Can commit: {agent.can_commit}\n"
            if agent.denied_paths:
                content += f"- Denied paths: {', '.join(agent.denied_paths)}\n"

        instructions_file.write_text(content)

    def _init_git_crypt(self) -> None:
        """Initialize git-crypt if available."""
        try:
            subprocess.run(
                ["git-crypt", "init"],
                cwd=str(self.repo_path),
                check=True,
                capture_output=True
            )

            # Add owner key
            subprocess.run(
                ["git-crypt", "add-gpg-user", self.config.owner_key_id],
                cwd=str(self.repo_path),
                check=True,
                capture_output=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # git-crypt not available, use pure GPG approach
            pass

    def _reencrypt_for_users(self) -> None:
        """Re-encrypt all files for current user list."""
        recipients = [u.gpg_key_id for u in self.config.users if u.can_decrypt]

        for path in self.repo_path.glob("**/*.gpg"):
            if ".gitcloakd" in str(path):
                continue

            # Decrypt and re-encrypt with new recipient list
            try:
                decrypted_path = str(path.with_suffix(""))
                self.decrypt_file(str(path), decrypted_path)
                path.unlink()  # Remove old encrypted file
                self.encrypt_file(decrypted_path, recipients)
                Path(decrypted_path).unlink()  # Remove decrypted file
            except Exception:
                pass  # Skip files we can't re-encrypt
