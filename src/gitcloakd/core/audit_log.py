"""
gitcloakd Encrypted Audit Log
All audit events are GPG-encrypted - no plaintext logs ever.

SECURITY NOTICE:
- All log entries are encrypted with your GPG key before storage
- Logs can only be read with your GPG private key
- Audit trail is tamper-evident (chained hashes)
- Logs can be securely wiped at any time
"""

import os
import json
import gnupg
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum


class AuditEventType(Enum):
    """Types of auditable events."""
    # Authentication
    AUTH_UNLOCK = "auth.unlock"
    AUTH_LOCK = "auth.lock"
    AUTH_FAILED = "auth.failed"

    # Repository operations
    REPO_INIT = "repo.init"
    REPO_ENCRYPT = "repo.encrypt"
    REPO_DECRYPT = "repo.decrypt"
    REPO_CLONE = "repo.clone"

    # Dark mode operations
    DARK_MODE_INIT = "dark.init"
    DARK_MODE_ENCRYPT = "dark.encrypt"
    DARK_MODE_DECRYPT = "dark.decrypt"

    # Encryption operations
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"

    # User management
    USER_ADD = "user.add"
    USER_ADDED = "user.added"
    USER_REMOVE = "user.remove"
    USER_KEY_CHANGE = "user.key_change"

    # Security events
    SECURITY_SCAN = "security.scan"
    SECURITY_ALERT = "security.alert"
    SECURITY_WIPE = "security.wipe"

    # Web interface
    WEB_LOGIN = "web.login"
    WEB_LOGOUT = "web.logout"
    WEB_ACTION = "web.action"

    # System
    SYSTEM_START = "system.start"
    SYSTEM_ERROR = "system.error"
    HISTORY_CLEAR = "history.clear"
    CACHE_CLEAR = "cache.clear"


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: str
    event_type: str
    action: str
    details: Dict[str, Any]
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    success: bool = True
    previous_hash: Optional[str] = None  # Chain hash for tamper detection
    entry_hash: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    def compute_hash(self) -> str:
        """Compute hash for tamper detection."""
        data = f"{self.timestamp}|{self.event_type}|{self.action}|{json.dumps(self.details, sort_keys=True)}|{self.previous_hash or ''}"
        return hashlib.sha256(data.encode()).hexdigest()


class EncryptedAuditLog:
    """
    GPG-encrypted audit logging system.

    All log entries are:
    1. Encrypted with the user's GPG key
    2. Chained with hashes for tamper detection
    3. Never stored in plaintext
    4. Rotatable and wipeable

    Storage: ~/.gitcloakd/audit/
        current.log.gpg     - Current encrypted log
        archive/            - Rotated logs
        chain.json.gpg      - Hash chain state
    """

    LOG_DIR = Path.home() / ".gitcloakd" / "audit"
    CURRENT_LOG = "current.log.gpg"
    CHAIN_STATE = "chain.json.gpg"
    MAX_ENTRIES_PER_FILE = 10000
    MAX_LOG_FILES = 100

    def __init__(self, gpg_key_id: Optional[str] = None):
        """Initialize audit log."""
        self.gpg = gnupg.GPG()
        self.gpg_key_id = gpg_key_id
        self._ensure_dir()
        self._last_hash: Optional[str] = None

    def _ensure_dir(self) -> None:
        """Create audit directory with secure permissions."""
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.chmod(0o700)
        (self.LOG_DIR / "archive").mkdir(exist_ok=True)

    def set_gpg_key(self, key_id: str) -> None:
        """Set the GPG key for encryption."""
        self.gpg_key_id = key_id

    def log(
        self,
        event_type: AuditEventType,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        success: bool = True
    ) -> bool:
        """
        Log an audit event (encrypted).

        Args:
            event_type: Type of event
            action: Human-readable action description
            details: Additional details (will be encrypted)
            source_ip: Source IP if from web interface
            user_agent: User agent if from web interface
            session_id: Session ID for correlation
            success: Whether the action succeeded

        Returns:
            True if logged successfully
        """
        if not self.gpg_key_id:
            return False

        # Load chain state
        self._load_chain_state()

        # Create entry
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            event_type=event_type.value,
            action=action,
            details=details or {},
            source_ip=source_ip,
            user_agent=user_agent,
            session_id=session_id,
            success=success,
            previous_hash=self._last_hash
        )
        entry.entry_hash = entry.compute_hash()
        self._last_hash = entry.entry_hash

        # Append to encrypted log
        self._append_entry(entry)

        # Save chain state
        self._save_chain_state()

        return True

    def get_logs(
        self,
        limit: int = 100,
        event_type: Optional[AuditEventType] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[AuditEntry]:
        """
        Retrieve audit logs (decrypted).

        Args:
            limit: Maximum entries to return
            event_type: Filter by event type
            since: Only entries after this time
            until: Only entries before this time

        Returns:
            List of audit entries
        """
        entries = self._read_all_entries()

        # Filter
        if event_type:
            entries = [e for e in entries if e.event_type == event_type.value]
        if since:
            entries = [e for e in entries if datetime.fromisoformat(e.timestamp) >= since]
        if until:
            entries = [e for e in entries if datetime.fromisoformat(e.timestamp) <= until]

        # Sort by timestamp descending and limit
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def verify_integrity(self) -> Dict[str, Any]:
        """
        Verify audit log integrity (tamper detection).

        Returns:
            Verification result with any issues found
        """
        result = {
            "verified": True,
            "total_entries": 0,
            "issues": [],
            "checked_at": datetime.now().isoformat()
        }

        entries = self._read_all_entries()
        result["total_entries"] = len(entries)

        # Sort by timestamp
        entries.sort(key=lambda e: e.timestamp)

        previous_hash = None
        for i, entry in enumerate(entries):
            # Verify chain
            if entry.previous_hash != previous_hash:
                result["verified"] = False
                result["issues"].append({
                    "entry": i,
                    "timestamp": entry.timestamp,
                    "issue": "Chain hash mismatch - possible tampering"
                })

            # Verify entry hash
            computed = entry.compute_hash()
            if entry.entry_hash != computed:
                result["verified"] = False
                result["issues"].append({
                    "entry": i,
                    "timestamp": entry.timestamp,
                    "issue": "Entry hash mismatch - possible tampering"
                })

            previous_hash = entry.entry_hash

        return result

    def rotate(self) -> bool:
        """
        Rotate current log to archive.

        Returns:
            True if rotation successful
        """
        current_log = self.LOG_DIR / self.CURRENT_LOG
        if not current_log.exists():
            return False

        # Archive with timestamp
        archive_name = f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log.gpg"
        archive_path = self.LOG_DIR / "archive" / archive_name

        current_log.rename(archive_path)

        # Clean old archives
        self._cleanup_old_archives()

        return True

    def wipe_all(self, confirm: bool = False) -> bool:
        """
        Securely wipe ALL audit logs.

        WARNING: This is irreversible!

        Args:
            confirm: Must be True to proceed

        Returns:
            True if wipe successful
        """
        if not confirm:
            raise ValueError("Must set confirm=True to wipe audit logs")

        # Log the wipe event first (will be wiped too, but shows intent)
        self.log(
            AuditEventType.SECURITY_WIPE,
            "Audit logs wiped",
            {"reason": "User requested wipe"}
        )

        # Secure wipe all files
        for log_file in self.LOG_DIR.rglob("*.gpg"):
            self._secure_delete(log_file)

        # Reset chain state
        self._last_hash = None

        return True

    def export_logs(self, output_path: str, encrypted: bool = True) -> bool:
        """
        Export audit logs.

        Args:
            output_path: Where to save export
            encrypted: Keep encrypted (True) or decrypt for export (False)

        Returns:
            True if export successful
        """
        entries = self._read_all_entries()

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "total_entries": len(entries),
            "integrity_verified": self.verify_integrity()["verified"],
            "entries": [e.to_dict() for e in entries]
        }

        if encrypted:
            # Export encrypted
            encrypted_data = self.gpg.encrypt(
                json.dumps(export_data, indent=2),
                [self.gpg_key_id],
                armor=True,
                always_trust=True
            )
            Path(output_path).write_text(str(encrypted_data))
        else:
            # Export decrypted (for authorized review)
            Path(output_path).write_text(json.dumps(export_data, indent=2))

        return True

    def _append_entry(self, entry: AuditEntry) -> None:
        """Append entry to encrypted log."""
        current_log = self.LOG_DIR / self.CURRENT_LOG

        # Read existing entries
        entries = []
        if current_log.exists():
            entries = self._read_entries_from_file(current_log)

        # Check if rotation needed
        if len(entries) >= self.MAX_ENTRIES_PER_FILE:
            self.rotate()
            entries = []

        # Add new entry
        entries.append(entry)

        # Encrypt and write
        log_data = json.dumps([e.to_dict() for e in entries])
        encrypted = self.gpg.encrypt(
            log_data,
            [self.gpg_key_id],
            armor=True,
            always_trust=True
        )

        current_log.write_text(str(encrypted))
        current_log.chmod(0o600)

    def _read_entries_from_file(self, filepath: Path) -> List[AuditEntry]:
        """Read entries from encrypted log file."""
        if not filepath.exists():
            return []

        encrypted_data = filepath.read_text()
        decrypted = self.gpg.decrypt(encrypted_data)

        if not decrypted.ok:
            return []

        try:
            data = json.loads(str(decrypted))
            return [AuditEntry(**e) for e in data]
        except (json.JSONDecodeError, TypeError):
            return []

    def _read_all_entries(self) -> List[AuditEntry]:
        """Read all entries from current and archived logs."""
        entries = []

        # Current log
        current_log = self.LOG_DIR / self.CURRENT_LOG
        if current_log.exists():
            entries.extend(self._read_entries_from_file(current_log))

        # Archived logs
        archive_dir = self.LOG_DIR / "archive"
        if archive_dir.exists():
            for log_file in sorted(archive_dir.glob("*.gpg")):
                entries.extend(self._read_entries_from_file(log_file))

        return entries

    def _load_chain_state(self) -> None:
        """Load hash chain state."""
        chain_file = self.LOG_DIR / self.CHAIN_STATE
        if not chain_file.exists():
            self._last_hash = None
            return

        encrypted_data = chain_file.read_text()
        decrypted = self.gpg.decrypt(encrypted_data)

        if decrypted.ok:
            try:
                data = json.loads(str(decrypted))
                self._last_hash = data.get("last_hash")
            except json.JSONDecodeError:
                self._last_hash = None

    def _save_chain_state(self) -> None:
        """Save hash chain state."""
        if not self.gpg_key_id:
            return

        data = {"last_hash": self._last_hash}
        encrypted = self.gpg.encrypt(
            json.dumps(data),
            [self.gpg_key_id],
            armor=True,
            always_trust=True
        )

        chain_file = self.LOG_DIR / self.CHAIN_STATE
        chain_file.write_text(str(encrypted))
        chain_file.chmod(0o600)

    def _cleanup_old_archives(self) -> None:
        """Remove old archive files beyond MAX_LOG_FILES."""
        archive_dir = self.LOG_DIR / "archive"
        archives = sorted(archive_dir.glob("*.gpg"), reverse=True)

        for old_archive in archives[self.MAX_LOG_FILES:]:
            self._secure_delete(old_archive)

    def _secure_delete(self, filepath: Path) -> None:
        """Securely delete a file by overwriting with random data."""
        if not filepath.exists():
            return

        try:
            size = filepath.stat().st_size
            # Overwrite with random data multiple times
            for _ in range(3):
                filepath.write_bytes(os.urandom(size))
            filepath.unlink()
        except Exception:
            # Fallback to regular delete
            filepath.unlink(missing_ok=True)


# Global audit log instance
_audit_log: Optional[EncryptedAuditLog] = None


def get_audit_log() -> EncryptedAuditLog:
    """Get global audit log instance."""
    global _audit_log
    if _audit_log is None:
        _audit_log = EncryptedAuditLog()
    return _audit_log


def audit(
    event_type: AuditEventType,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    **kwargs
) -> bool:
    """Convenience function to log audit events."""
    log = get_audit_log()
    return log.log(event_type, action, details, **kwargs)
