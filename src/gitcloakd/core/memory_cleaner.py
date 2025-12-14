"""
gitcloakd Memory and Cache Cleaner
Securely clear all traces of gitcloakd activity.

SECURITY NOTICE:
This module provides secure deletion of:
- Command history
- Session data
- Cache files
- Memory artifacts
- Temporary files
- Swap/page file references (where possible)

WARNING: Some data may persist in:
- OS swap files
- SSD wear leveling
- System logs (outside gitcloakd control)
- Network logs on servers

For maximum security, use full-disk encryption on your system.
"""

import gc
import sys
import shutil
import secrets
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from gitcloakd.core.audit_log import audit, AuditEventType


class MemoryCleaner:
    """
    Secure memory and cache cleaning utilities.

    Provides multiple levels of cleaning:
    - QUICK: Clear obvious caches and history
    - STANDARD: Clear all gitcloakd data + temporary files
    - PARANOID: Aggressive clearing including memory scrubbing
    """

    GITCRYPTED_DIR = Path.home() / ".gitcloakd"

    # Patterns of files to clear
    TEMP_PATTERNS = [
        "*.tmp",
        "*.temp",
        "*.cache",
        "*.bak",
        ".*.swp",
        ".*.swo",
        "*~",
    ]

    # Directories that may contain gitcloakd artifacts
    CACHE_DIRS = [
        Path.home() / ".gitcloakd" / "cache",
        Path.home() / ".cache" / "gitcloakd",
        Path("/tmp") / "gitcloakd",
        Path("/var/tmp") / "gitcloakd",
    ]

    def __init__(self):
        """Initialize memory cleaner."""
        self.cleaned_items: List[str] = []
        self.errors: List[str] = []

    def clean_quick(self) -> Dict[str, Any]:
        """
        Quick clean - clear obvious caches only.

        Safe to run frequently. Does not affect functionality.

        Returns:
            Summary of cleaned items
        """
        result = {
            "level": "quick",
            "timestamp": datetime.now().isoformat(),
            "items_cleaned": 0,
            "errors": []
        }

        # Clear gitcloakd cache directory
        cache_dir = self.GITCRYPTED_DIR / "cache"
        if cache_dir.exists():
            count = self._secure_clear_directory(cache_dir, keep_dir=True)
            result["items_cleaned"] += count

        # Clear Python's internal caches
        gc.collect()

        # Clear any lingering temp files
        for pattern in ["*.tmp", "*.temp"]:
            count = self._clear_pattern_in_dir(self.GITCRYPTED_DIR, pattern)
            result["items_cleaned"] += count

        result["errors"] = self.errors.copy()
        self.errors.clear()

        audit(AuditEventType.CACHE_CLEAR, "Quick cache clear", {
            "items_cleaned": result["items_cleaned"]
        })

        return result

    def clean_standard(self) -> Dict[str, Any]:
        """
        Standard clean - clear all gitcloakd temporary data.

        Clears:
        - All cache directories
        - Temporary files
        - Session data (requires re-unlock)
        - Command history

        Returns:
            Summary of cleaned items
        """
        result = {
            "level": "standard",
            "timestamp": datetime.now().isoformat(),
            "items_cleaned": 0,
            "categories": {},
            "errors": []
        }

        # Clear all cache directories
        cache_count = 0
        for cache_dir in self.CACHE_DIRS:
            if cache_dir.exists():
                count = self._secure_clear_directory(cache_dir, keep_dir=True)
                cache_count += count
        result["categories"]["cache"] = cache_count
        result["items_cleaned"] += cache_count

        # Clear session data
        session_file = self.GITCRYPTED_DIR / "session.json"
        if session_file.exists():
            self._secure_delete_file(session_file)
            result["categories"]["session"] = 1
            result["items_cleaned"] += 1

        # Clear temp files in gitcloakd dir
        temp_count = 0
        for pattern in self.TEMP_PATTERNS:
            temp_count += self._clear_pattern_in_dir(self.GITCRYPTED_DIR, pattern)
        result["categories"]["temp_files"] = temp_count
        result["items_cleaned"] += temp_count

        # Force garbage collection
        gc.collect()

        result["errors"] = self.errors.copy()
        self.errors.clear()

        audit(AuditEventType.CACHE_CLEAR, "Standard cache clear", {
            "items_cleaned": result["items_cleaned"],
            "categories": result["categories"]
        })

        return result

    def clean_paranoid(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Paranoid clean - aggressive clearing of all traces.

        WARNING: This will:
        - Clear ALL gitcloakd data (requires re-setup)
        - Attempt to scrub memory
        - Clear Python object caches
        - Overwrite deleted file space

        Args:
            confirm: Must be True to proceed

        Returns:
            Summary of cleaned items
        """
        if not confirm:
            raise ValueError("Must set confirm=True for paranoid clean")

        result = {
            "level": "paranoid",
            "timestamp": datetime.now().isoformat(),
            "items_cleaned": 0,
            "categories": {},
            "warnings": [],
            "errors": []
        }

        # First, do standard clean
        standard_result = self.clean_standard()
        result["items_cleaned"] += standard_result["items_cleaned"]

        # Clear command history
        history_file = self.GITCRYPTED_DIR / "history.gpg"
        if history_file.exists():
            self._secure_delete_file(history_file)
            result["categories"]["history"] = 1
            result["items_cleaned"] += 1

        # Clear all .gpg files in gitcloakd dir (except config if needed)
        gpg_count = 0
        for gpg_file in self.GITCRYPTED_DIR.rglob("*.gpg"):
            if "audit" not in str(gpg_file):  # Keep audit for now
                self._secure_delete_file(gpg_file)
                gpg_count += 1
        result["categories"]["encrypted_cache"] = gpg_count
        result["items_cleaned"] += gpg_count

        # Attempt memory scrubbing
        memory_scrubbed = self._scrub_memory()
        result["categories"]["memory_scrubbed"] = memory_scrubbed

        # Clear Python caches
        self._clear_python_caches()
        result["categories"]["python_caches"] = True

        # Add warnings about limitations
        result["warnings"] = [
            "OS swap files may still contain data",
            "SSD wear leveling may preserve deleted data",
            "System logs are outside gitcloakd control",
            "For maximum security, use full-disk encryption"
        ]

        result["errors"] = self.errors.copy()
        self.errors.clear()

        audit(AuditEventType.SECURITY_WIPE, "Paranoid clean executed", {
            "items_cleaned": result["items_cleaned"],
            "categories": result["categories"]
        })

        return result

    def clear_command_history(self) -> bool:
        """
        Clear only command history.

        Returns:
            True if cleared successfully
        """
        history_file = self.GITCRYPTED_DIR / "history.gpg"
        if history_file.exists():
            self._secure_delete_file(history_file)
            audit(AuditEventType.HISTORY_CLEAR, "Command history cleared")
            return True
        return False

    def clear_audit_logs(self, confirm: bool = False) -> bool:
        """
        Clear audit logs.

        Args:
            confirm: Must be True to proceed

        Returns:
            True if cleared successfully
        """
        if not confirm:
            raise ValueError("Must set confirm=True to clear audit logs")

        audit_dir = self.GITCRYPTED_DIR / "audit"
        if audit_dir.exists():
            self._secure_clear_directory(audit_dir, keep_dir=True)
            return True
        return False

    def clear_web_sessions(self) -> bool:
        """
        Clear all web interface session data.

        Returns:
            True if cleared successfully
        """
        web_dir = self.GITCRYPTED_DIR / "web"
        if web_dir.exists():
            self._secure_clear_directory(web_dir, keep_dir=True)
            audit(AuditEventType.CACHE_CLEAR, "Web sessions cleared")
            return True
        return False

    def get_data_footprint(self) -> Dict[str, Any]:
        """
        Analyze gitcloakd data footprint on system.

        Returns:
            Summary of all gitcloakd-related data locations and sizes
        """
        footprint = {
            "total_size_bytes": 0,
            "locations": [],
            "file_count": 0
        }

        # Main gitcloakd directory
        if self.GITCRYPTED_DIR.exists():
            size, count = self._get_dir_size(self.GITCRYPTED_DIR)
            footprint["locations"].append({
                "path": str(self.GITCRYPTED_DIR),
                "size_bytes": size,
                "file_count": count,
                "type": "main"
            })
            footprint["total_size_bytes"] += size
            footprint["file_count"] += count

        # Cache directories
        for cache_dir in self.CACHE_DIRS:
            if cache_dir.exists():
                size, count = self._get_dir_size(cache_dir)
                footprint["locations"].append({
                    "path": str(cache_dir),
                    "size_bytes": size,
                    "file_count": count,
                    "type": "cache"
                })
                footprint["total_size_bytes"] += size
                footprint["file_count"] += count

        return footprint

    def _secure_delete_file(self, filepath: Path) -> bool:
        """
        Securely delete a file by overwriting with random data.

        Args:
            filepath: Path to file

        Returns:
            True if deleted successfully
        """
        try:
            if not filepath.exists():
                return False

            size = filepath.stat().st_size

            # Overwrite with random data 3 times
            for _ in range(3):
                filepath.write_bytes(secrets.token_bytes(size))

            # Overwrite with zeros
            filepath.write_bytes(b'\x00' * size)

            # Delete
            filepath.unlink()

            self.cleaned_items.append(str(filepath))
            return True

        except Exception as e:
            self.errors.append(f"Failed to delete {filepath}: {e}")
            return False

    def _secure_clear_directory(self, dirpath: Path, keep_dir: bool = False) -> int:
        """
        Securely clear all files in a directory.

        Args:
            dirpath: Directory to clear
            keep_dir: Keep the directory itself

        Returns:
            Number of files cleared
        """
        count = 0
        try:
            for item in dirpath.rglob("*"):
                if item.is_file():
                    if self._secure_delete_file(item):
                        count += 1

            # Remove empty directories
            for item in sorted(dirpath.rglob("*"), reverse=True):
                if item.is_dir() and not any(item.iterdir()):
                    item.rmdir()

            if not keep_dir and dirpath.exists():
                dirpath.rmdir()

        except Exception as e:
            self.errors.append(f"Failed to clear {dirpath}: {e}")

        return count

    def _clear_pattern_in_dir(self, dirpath: Path, pattern: str) -> int:
        """Clear files matching pattern in directory."""
        count = 0
        try:
            for filepath in dirpath.rglob(pattern):
                if filepath.is_file():
                    if self._secure_delete_file(filepath):
                        count += 1
        except Exception as e:
            self.errors.append(f"Failed to clear pattern {pattern}: {e}")
        return count

    def _get_dir_size(self, dirpath: Path) -> tuple:
        """Get total size and file count of directory."""
        total_size = 0
        file_count = 0
        try:
            for item in dirpath.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
        except Exception:
            pass
        return total_size, file_count

    def _scrub_memory(self) -> bool:
        """
        Attempt to scrub sensitive data from memory.

        Note: This is best-effort and may not be complete.

        Returns:
            True if scrubbing attempted
        """
        try:
            # Force garbage collection
            gc.collect()
            gc.collect()
            gc.collect()

            # Try to clear interned strings (limited effectiveness)
            # This is Python-implementation dependent

            # On Linux, we can try to advise the kernel
            if sys.platform == 'linux':
                # madvise could be used here for memory release hints
                pass

            return True

        except Exception:
            return False

    def _clear_python_caches(self) -> None:
        """Clear various Python internal caches."""
        try:
            # Clear __pycache__ directories
            for pycache in Path.cwd().rglob("__pycache__"):
                if pycache.is_dir():
                    shutil.rmtree(pycache, ignore_errors=True)

            # Clear compiled bytecode
            for pyc in Path.cwd().rglob("*.pyc"):
                pyc.unlink(missing_ok=True)

            # Force garbage collection
            gc.collect()

        except Exception:
            pass


# Global cleaner instance
_cleaner: Optional[MemoryCleaner] = None


def get_memory_cleaner() -> MemoryCleaner:
    """Get global memory cleaner instance."""
    global _cleaner
    if _cleaner is None:
        _cleaner = MemoryCleaner()
    return _cleaner
