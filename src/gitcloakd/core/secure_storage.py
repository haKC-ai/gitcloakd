"""
gitcloakd Secure Local Storage
Encrypts all local gitcloakd data with user's GPG key.

This ensures that if a laptop is stolen, the attacker cannot:
- See what repos are managed by gitcloakd
- View command history or session data
- Access any cached credentials or tokens
- Understand the structure of encrypted repos

All local data is encrypted at rest with the user's GPG key.
"""

import os
import json
import gnupg
from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Dict
from dataclasses import dataclass


@dataclass
class SecureSession:
    """Represents a locked/unlocked session."""
    gpg_key_id: str
    unlocked_at: Optional[str] = None
    expires_at: Optional[str] = None
    is_unlocked: bool = False


class SecureStorage:
    """
    GPG-encrypted local storage for gitcloakd.

    All data stored locally is encrypted with the user's GPG key.
    User must "unlock" gitcloakd with their GPG passphrase to work.

    Storage structure:
    ~/.gitcloakd/
        config.gpg          - Encrypted global config
        repos.gpg           - Encrypted list of managed repos
        history.gpg         - Encrypted command history
        session.json        - Unencrypted session state (lock status)
        keys/               - Public keys of collaborators (not encrypted)
    """

    DEFAULT_PATH = Path.home() / ".gitcloakd"
    SESSION_TIMEOUT_MINUTES = 30

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize secure storage."""
        self.path = storage_path or self.DEFAULT_PATH
        self.gpg = gnupg.GPG()
        self.session: Optional[SecureSession] = None
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        """Create storage directory with secure permissions."""
        self.path.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions (owner only)
        self.path.chmod(0o700)

        # Create subdirectories
        (self.path / "keys").mkdir(exist_ok=True)
        (self.path / "cache").mkdir(exist_ok=True)

    def is_initialized(self) -> bool:
        """Check if secure storage is initialized with a GPG key."""
        config_file = self.path / "config.gpg"
        return config_file.exists()

    def initialize(self, gpg_key_id: str) -> bool:
        """
        Initialize secure storage with a GPG key.

        All future storage operations will use this key for encryption.

        Args:
            gpg_key_id: The GPG key ID to use for encryption

        Returns:
            True if initialization successful
        """
        # Verify the key exists
        keys = self.gpg.list_keys(keys=[gpg_key_id], secret=True)
        if not keys:
            raise ValueError(f"GPG secret key not found: {gpg_key_id}")

        # Create initial config
        config = {
            "gpg_key_id": gpg_key_id,
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "repos": [],
            "settings": {
                "session_timeout_minutes": self.SESSION_TIMEOUT_MINUTES,
                "auto_lock": True,
                "require_unlock_for_commands": True,
            }
        }

        # Encrypt and save config
        self._write_encrypted("config.gpg", config, gpg_key_id)

        # Initialize empty repos list
        self._write_encrypted("repos.gpg", {"repos": []}, gpg_key_id)

        # Initialize empty history
        self._write_encrypted("history.gpg", {"history": []}, gpg_key_id)

        # Create session file (unencrypted - just tracks lock state)
        session = {
            "gpg_key_id": gpg_key_id,
            "is_unlocked": False,
            "unlocked_at": None,
        }
        (self.path / "session.json").write_text(json.dumps(session))

        return True

    def unlock(self, passphrase: Optional[str] = None) -> bool:
        """
        Unlock gitcloakd for this session.

        User must provide GPG passphrase to decrypt local data.
        This is required before any gitcloakd operations.

        Args:
            passphrase: GPG passphrase (if not using gpg-agent)

        Returns:
            True if unlock successful
        """
        session_file = self.path / "session.json"
        if not session_file.exists():
            raise RuntimeError("Secure storage not initialized. Run: gitcloakd secure init")

        session_data = json.loads(session_file.read_text())
        gpg_key_id = session_data["gpg_key_id"]

        # Try to decrypt config to verify passphrase/key access
        try:
            config = self._read_encrypted("config.gpg")
            if config is None:
                return False
        except Exception:
            return False

        # Update session
        now = datetime.now()
        timeout = config.get("settings", {}).get("session_timeout_minutes", self.SESSION_TIMEOUT_MINUTES)
        expires = now.replace(minute=now.minute + timeout)

        self.session = SecureSession(
            gpg_key_id=gpg_key_id,
            unlocked_at=now.isoformat(),
            expires_at=expires.isoformat(),
            is_unlocked=True,
        )

        # Save session state
        session_data["is_unlocked"] = True
        session_data["unlocked_at"] = now.isoformat()
        session_data["expires_at"] = expires.isoformat()
        session_file.write_text(json.dumps(session_data))

        return True

    def lock(self) -> None:
        """
        Lock gitcloakd, requiring unlock for future operations.
        """
        session_file = self.path / "session.json"
        if session_file.exists():
            session_data = json.loads(session_file.read_text())
            session_data["is_unlocked"] = False
            session_data["unlocked_at"] = None
            session_data["expires_at"] = None
            session_file.write_text(json.dumps(session_data))

        self.session = None

    def is_unlocked(self) -> bool:
        """Check if gitcloakd is currently unlocked."""
        session_file = self.path / "session.json"
        if not session_file.exists():
            return False

        session_data = json.loads(session_file.read_text())

        if not session_data.get("is_unlocked"):
            return False

        # Check if session has expired
        expires_at = session_data.get("expires_at")
        if expires_at:
            try:
                expires = datetime.fromisoformat(expires_at)
                if datetime.now() > expires:
                    self.lock()
                    return False
            except ValueError:
                pass

        return True

    def require_unlock(self) -> None:
        """Raise error if not unlocked. Call at start of protected operations."""
        if not self.is_unlocked():
            raise RuntimeError(
                "gitcloakd is locked. Run: gitcloakd unlock\n"
                "This protects your encrypted repos from unauthorized access."
            )

    def get_gpg_key_id(self) -> Optional[str]:
        """Get the configured GPG key ID."""
        session_file = self.path / "session.json"
        if session_file.exists():
            session_data = json.loads(session_file.read_text())
            return session_data.get("gpg_key_id")
        return None

    # === Encrypted Data Operations ===

    def add_repo(self, repo_path: str, full_name: str, encryption_type: str = "full") -> None:
        """
        Register a repo with secure storage.

        Args:
            repo_path: Local path to the repository
            full_name: Full name (owner/repo)
            encryption_type: "full" or "selective"
        """
        self.require_unlock()

        repos_data = self._read_encrypted("repos.gpg") or {"repos": []}

        # Check if already registered
        for repo in repos_data["repos"]:
            if repo["path"] == repo_path:
                # Update existing
                repo["full_name"] = full_name
                repo["encryption_type"] = encryption_type
                repo["last_accessed"] = datetime.now().isoformat()
                break
        else:
            # Add new
            repos_data["repos"].append({
                "path": repo_path,
                "full_name": full_name,
                "encryption_type": encryption_type,
                "added_at": datetime.now().isoformat(),
                "last_accessed": datetime.now().isoformat(),
            })

        self._write_encrypted("repos.gpg", repos_data)

    def remove_repo(self, repo_path: str) -> bool:
        """Remove a repo from secure storage."""
        self.require_unlock()

        repos_data = self._read_encrypted("repos.gpg") or {"repos": []}
        original_count = len(repos_data["repos"])
        repos_data["repos"] = [r for r in repos_data["repos"] if r["path"] != repo_path]

        if len(repos_data["repos"]) < original_count:
            self._write_encrypted("repos.gpg", repos_data)
            return True
        return False

    def list_repos(self) -> list:
        """List all registered repos."""
        self.require_unlock()

        repos_data = self._read_encrypted("repos.gpg") or {"repos": []}
        return repos_data["repos"]

    def log_command(self, command: str, repo_path: Optional[str] = None) -> None:
        """
        Log a command to encrypted history.

        Args:
            command: The command executed
            repo_path: Optional repo path for context
        """
        self.require_unlock()

        history_data = self._read_encrypted("history.gpg") or {"history": []}

        history_data["history"].append({
            "command": command,
            "repo_path": repo_path,
            "timestamp": datetime.now().isoformat(),
        })

        # Keep only last 1000 entries
        history_data["history"] = history_data["history"][-1000:]

        self._write_encrypted("history.gpg", history_data)

    def get_history(self, limit: int = 50, repo_path: Optional[str] = None) -> list:
        """
        Get command history.

        Args:
            limit: Max entries to return
            repo_path: Filter by repo path

        Returns:
            List of history entries
        """
        self.require_unlock()

        history_data = self._read_encrypted("history.gpg") or {"history": []}
        history = history_data["history"]

        if repo_path:
            history = [h for h in history if h.get("repo_path") == repo_path]

        return history[-limit:]

    def store_secret(self, key: str, value: str) -> None:
        """
        Store a secret value (API keys, tokens, etc.) encrypted.

        Args:
            key: Secret identifier
            value: Secret value
        """
        self.require_unlock()

        secrets_file = self.path / "secrets.gpg"
        secrets = {}

        if secrets_file.exists():
            secrets = self._read_encrypted("secrets.gpg") or {}

        secrets[key] = {
            "value": value,
            "stored_at": datetime.now().isoformat(),
        }

        self._write_encrypted("secrets.gpg", secrets)

    def get_secret(self, key: str) -> Optional[str]:
        """
        Retrieve a stored secret.

        Args:
            key: Secret identifier

        Returns:
            Secret value or None if not found
        """
        self.require_unlock()

        secrets_file = self.path / "secrets.gpg"
        if not secrets_file.exists():
            return None

        secrets = self._read_encrypted("secrets.gpg") or {}
        secret_data = secrets.get(key)

        if secret_data:
            return secret_data.get("value")
        return None

    def delete_secret(self, key: str) -> bool:
        """Delete a stored secret."""
        self.require_unlock()

        secrets_file = self.path / "secrets.gpg"
        if not secrets_file.exists():
            return False

        secrets = self._read_encrypted("secrets.gpg") or {}
        if key in secrets:
            del secrets[key]
            self._write_encrypted("secrets.gpg", secrets)
            return True
        return False

    def get_settings(self) -> Dict[str, Any]:
        """Get global settings."""
        self.require_unlock()
        config = self._read_encrypted("config.gpg") or {}
        return config.get("settings", {})

    def update_settings(self, settings: Dict[str, Any]) -> None:
        """Update global settings."""
        self.require_unlock()
        config = self._read_encrypted("config.gpg") or {}
        config["settings"] = {**config.get("settings", {}), **settings}
        self._write_encrypted("config.gpg", config)

    # === Internal Encryption Methods ===

    def _write_encrypted(
        self,
        filename: str,
        data: Any,
        gpg_key_id: Optional[str] = None
    ) -> None:
        """Write data encrypted with GPG."""
        if gpg_key_id is None:
            gpg_key_id = self.get_gpg_key_id()

        if not gpg_key_id:
            raise RuntimeError("No GPG key configured")

        json_data = json.dumps(data, indent=2)

        encrypted = self.gpg.encrypt(
            json_data,
            [gpg_key_id],
            armor=True,
            always_trust=True
        )

        if not encrypted.ok:
            raise RuntimeError(f"Encryption failed: {encrypted.status}")

        filepath = self.path / filename
        filepath.write_text(str(encrypted))
        filepath.chmod(0o600)  # Owner read/write only

    def _read_encrypted(self, filename: str) -> Optional[Any]:
        """Read and decrypt GPG-encrypted data."""
        filepath = self.path / filename

        if not filepath.exists():
            return None

        encrypted_data = filepath.read_text()
        decrypted = self.gpg.decrypt(encrypted_data)

        if not decrypted.ok:
            raise RuntimeError(
                f"Decryption failed: {decrypted.status}\n"
                "Make sure your GPG key is available and you have the passphrase."
            )

        try:
            return json.loads(str(decrypted))
        except json.JSONDecodeError:
            return str(decrypted)

    def wipe_all(self, confirm: bool = False) -> bool:
        """
        Securely wipe all local gitcloakd data.

        WARNING: This is irreversible!

        Args:
            confirm: Must be True to proceed

        Returns:
            True if wipe successful
        """
        if not confirm:
            raise ValueError("Must set confirm=True to wipe all data")

        import shutil

        # Overwrite files with random data before deleting
        for filepath in self.path.rglob("*"):
            if filepath.is_file():
                try:
                    # Overwrite with random bytes
                    size = filepath.stat().st_size
                    filepath.write_bytes(os.urandom(size))
                    filepath.unlink()
                except Exception:
                    pass

        # Remove directory
        shutil.rmtree(self.path, ignore_errors=True)

        return True


# Global instance
_storage: Optional[SecureStorage] = None


def get_secure_storage() -> SecureStorage:
    """Get the global secure storage instance."""
    global _storage
    if _storage is None:
        _storage = SecureStorage()
    return _storage
