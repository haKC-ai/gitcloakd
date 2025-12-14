"""
gitcloakd Full Repository Encryption
Encrypts the ENTIRE codebase so unauthorized users only see GPG files.
"""

import os
import subprocess
import tarfile
import io
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import gnupg
import hashlib
import json

from gitcloakd.core.config import Config, UserConfig


class FullRepoEncryption:
    """
    Full repository encryption - encrypts ALL files in the repo.

    When enabled, unauthorized users pulling the repo will only see:
    - .gitcloakd/ directory with public config
    - encrypted.gpg (the entire codebase as single encrypted blob)
    - README.md explaining how to get access

    Authorized users can:
    - Clone and auto-decrypt with their GPG key
    - Work normally with decrypted files locally
    - Push encrypted changes back
    """

    # Files that should never be encrypted (stay public)
    PUBLIC_FILES = [
        ".gitcloakd/",
        ".git/",
        "README.md",
        "LICENSE",
        ".gitignore",
        ".gitattributes",
    ]

    # The encrypted blob filename
    ENCRYPTED_BLOB = "encrypted.gpg"
    MANIFEST_FILE = ".gitcloakd/manifest.json"

    def __init__(self, repo_path: Optional[str] = None):
        """Initialize full encryption for a repository."""
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.config_dir = self.repo_path / ".gitcloakd"
        self.gpg = gnupg.GPG()
        self.config = Config.load_repo(str(self.repo_path))

    def is_encrypted(self) -> bool:
        """Check if repo is in fully encrypted state."""
        encrypted_blob = self.repo_path / self.ENCRYPTED_BLOB
        return encrypted_blob.exists()

    def is_decrypted(self) -> bool:
        """Check if repo is in decrypted working state."""
        manifest = self.repo_path / self.MANIFEST_FILE
        if not manifest.exists():
            return False
        try:
            data = json.loads(manifest.read_text())
            return data.get("state") == "decrypted"
        except (json.JSONDecodeError, FileNotFoundError):
            return False

    def initialize_full_encryption(
        self,
        owner_key_id: str,
        owner_email: str,
    ) -> bool:
        """
        Initialize repository for FULL encryption mode.

        Args:
            owner_key_id: GPG key ID of the repository owner
            owner_email: Email of the repository owner

        Returns:
            True if initialization successful
        """
        # Create config directory
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Set up configuration for full encryption
        self.config.initialized = True
        self.config.repo_path = str(self.repo_path)
        self.config.owner_key_id = owner_key_id
        self.config.owner_email = owner_email
        self.config.created_date = datetime.now().isoformat()
        self.config.last_modified = datetime.now().isoformat()
        self.config.full_encryption = True  # Mark as full encryption mode

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

        # Create manifest
        self._create_manifest("decrypted")

        # Create public README explaining encryption
        self._create_public_readme()

        # Set up git hooks for auto encrypt/decrypt
        self._setup_git_hooks()

        # Update gitignore
        self._update_gitignore()

        return True

    def encrypt_all(self, recipients: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Encrypt the ENTIRE repository into a single GPG blob.

        All files (except PUBLIC_FILES) are packed into a tarball,
        encrypted with GPG, and stored as encrypted.gpg.
        Original files are then removed.

        Args:
            recipients: List of GPG key IDs (default: all users with decrypt access)

        Returns:
            Summary of encryption results
        """
        results = {
            "files_encrypted": 0,
            "total_size_before": 0,
            "encrypted_size": 0,
            "errors": [],
            "state": "encrypted"
        }

        # Get recipients
        if recipients is None:
            recipients = [u.gpg_key_id for u in self.config.users if u.can_decrypt]

        if not recipients:
            results["errors"].append("No recipients specified")
            return results

        # Collect all files to encrypt
        files_to_encrypt = []
        for item in self.repo_path.rglob("*"):
            if not item.is_file():
                continue

            # Check if this file should stay public
            rel_path = item.relative_to(self.repo_path)
            if self._is_public_file(str(rel_path)):
                continue

            # Skip the encrypted blob itself
            if item.name == self.ENCRYPTED_BLOB:
                continue

            files_to_encrypt.append(item)
            results["total_size_before"] += item.stat().st_size

        if not files_to_encrypt:
            results["errors"].append("No files to encrypt")
            return results

        # Create tarball in memory
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            for file_path in files_to_encrypt:
                rel_path = file_path.relative_to(self.repo_path)
                tar.add(str(file_path), arcname=str(rel_path))
                results["files_encrypted"] += 1

        tar_data = tar_buffer.getvalue()

        # Encrypt the tarball
        encrypted = self.gpg.encrypt(
            tar_data,
            recipients,
            armor=True,
            always_trust=True
        )

        if not encrypted.ok:
            results["errors"].append(f"GPG encryption failed: {encrypted.status}")
            return results

        # Write encrypted blob
        encrypted_blob = self.repo_path / self.ENCRYPTED_BLOB
        encrypted_blob.write_text(str(encrypted))
        results["encrypted_size"] = encrypted_blob.stat().st_size

        # Create file hash manifest for integrity checking
        self._create_file_manifest(files_to_encrypt)

        # Remove original files
        for file_path in files_to_encrypt:
            try:
                file_path.unlink()
            except Exception as e:
                results["errors"].append(f"Failed to remove {file_path}: {e}")

        # Remove empty directories
        self._cleanup_empty_dirs()

        # Update manifest state
        self._create_manifest("encrypted")

        return results

    def decrypt_all(self) -> Dict[str, Any]:
        """
        Decrypt the repository from the GPG blob.

        Extracts all files from encrypted.gpg and removes the blob.

        Returns:
            Summary of decryption results
        """
        results = {
            "files_decrypted": 0,
            "errors": [],
            "state": "decrypted"
        }

        encrypted_blob = self.repo_path / self.ENCRYPTED_BLOB
        if not encrypted_blob.exists():
            results["errors"].append("No encrypted blob found - repo may already be decrypted")
            return results

        # Read and decrypt the blob
        encrypted_data = encrypted_blob.read_text()
        decrypted = self.gpg.decrypt(encrypted_data)

        if not decrypted.ok:
            results["errors"].append(f"GPG decryption failed: {decrypted.status}")
            results["errors"].append("Make sure your GPG key is available and you have access")
            return results

        # Extract tarball
        tar_buffer = io.BytesIO(decrypted.data)
        try:
            with tarfile.open(fileobj=tar_buffer, mode="r:gz") as tar:
                # Security: check for path traversal
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in member.name:
                        results["errors"].append(f"Suspicious path in archive: {member.name}")
                        return results

                tar.extractall(path=str(self.repo_path))
                results["files_decrypted"] = len(tar.getmembers())
        except tarfile.TarError as e:
            results["errors"].append(f"Failed to extract archive: {e}")
            return results

        # Verify integrity if manifest exists
        integrity_ok = self._verify_integrity()
        if not integrity_ok:
            results["errors"].append("WARNING: File integrity check failed - some files may be corrupted")

        # Remove encrypted blob
        encrypted_blob.unlink()

        # Update manifest state
        self._create_manifest("decrypted")

        return results

    def add_user(
        self,
        email: str,
        gpg_key_id: str,
        name: Optional[str] = None,
        role: str = "collaborator"
    ) -> bool:
        """
        Add a user who can decrypt the repository.

        The repository must be re-encrypted after adding a user.
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

        # If currently encrypted, need to re-encrypt with new user
        if self.is_encrypted():
            self._reencrypt_for_users()

        return True

    def remove_user(self, email: str) -> bool:
        """
        Remove a user's access. Repository must be re-encrypted.
        """
        if not self.config.remove_user(email):
            return False

        self.config.last_modified = datetime.now().isoformat()
        self.config.save_repo(str(self.repo_path))

        # If currently encrypted, need to re-encrypt without removed user
        if self.is_encrypted():
            self._reencrypt_for_users()

        return True

    def get_status(self) -> Dict[str, Any]:
        """Get current encryption status."""
        status = {
            "full_encryption_enabled": getattr(self.config, "full_encryption", False),
            "state": "unknown",
            "users": [],
            "encrypted_blob_exists": (self.repo_path / self.ENCRYPTED_BLOB).exists(),
        }

        if self.is_encrypted():
            status["state"] = "encrypted"
            blob = self.repo_path / self.ENCRYPTED_BLOB
            status["blob_size"] = blob.stat().st_size
        elif self.is_decrypted():
            status["state"] = "decrypted"

        for user in self.config.users:
            status["users"].append({
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "can_decrypt": user.can_decrypt
            })

        return status

    def _is_public_file(self, rel_path: str) -> bool:
        """Check if a file should remain public (unencrypted)."""
        for public in self.PUBLIC_FILES:
            if rel_path.startswith(public) or rel_path == public.rstrip("/"):
                return True
        return False

    def _create_manifest(self, state: str) -> None:
        """Create/update manifest file."""
        manifest = {
            "state": state,
            "full_encryption": True,
            "last_updated": datetime.now().isoformat(),
            "version": "1.0"
        }
        manifest_file = self.repo_path / self.MANIFEST_FILE
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        manifest_file.write_text(json.dumps(manifest, indent=2))

    def _create_file_manifest(self, files: List[Path]) -> None:
        """Create manifest with file hashes for integrity checking."""
        hashes = {}
        for file_path in files:
            rel_path = str(file_path.relative_to(self.repo_path))
            file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            hashes[rel_path] = file_hash

        hash_file = self.config_dir / "file_hashes.json"
        hash_file.write_text(json.dumps(hashes, indent=2))

    def _verify_integrity(self) -> bool:
        """Verify file integrity against stored hashes."""
        hash_file = self.config_dir / "file_hashes.json"
        if not hash_file.exists():
            return True  # No hashes to verify against

        try:
            stored_hashes = json.loads(hash_file.read_text())
        except json.JSONDecodeError:
            return False

        for rel_path, expected_hash in stored_hashes.items():
            file_path = self.repo_path / rel_path
            if not file_path.exists():
                return False
            actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                return False

        return True

    def _cleanup_empty_dirs(self) -> None:
        """Remove empty directories after encryption."""
        for dirpath, dirnames, filenames in os.walk(str(self.repo_path), topdown=False):
            dir_path = Path(dirpath)

            # Skip protected directories
            if ".git" in str(dir_path) or ".gitcloakd" in str(dir_path):
                continue

            # Remove if empty
            if dir_path != self.repo_path and not any(dir_path.iterdir()):
                try:
                    dir_path.rmdir()
                except OSError:
                    pass

    def _create_public_readme(self) -> None:
        """Create public README explaining the encryption."""
        readme_path = self.repo_path / "README.md"

        # Preserve existing README content if present
        existing_content = ""
        if readme_path.exists():
            existing_content = readme_path.read_text()

        encryption_notice = """
---

## [!] This Repository is Encrypted

This repository uses **gitcloakd** for full codebase encryption.

### What You See

If you're seeing this message and only see `encrypted.gpg`, you don't have
access to decrypt the repository contents.

### Getting Access

1. Generate a GPG key if you don't have one:
   ```bash
   gpg --full-generate-key
   ```

2. Export your public key and send it to the repository owner:
   ```bash
   gpg --armor --export your@email.com > my-key.pub
   ```

3. Once added, clone and decrypt:
   ```bash
   git clone <repo-url>
   cd <repo>
   gitcloakd decrypt
   ```

### For Repository Owners

Add users with:
```bash
gitcloakd add-user --email user@example.com --key-id KEYID
gitcloakd encrypt  # Re-encrypt with new user
```

---
Secured with [gitcloakd](https://github.com/haKC-ai/gitcloakd)
"""

        if "gitcloakd" not in existing_content:
            readme_path.write_text(existing_content + encryption_notice)

    def _setup_git_hooks(self) -> None:
        """Set up git hooks for auto encrypt/decrypt."""
        hooks_dir = self.repo_path / ".git" / "hooks"
        if not hooks_dir.exists():
            return  # Not a git repo

        # Pre-push hook: encrypt before pushing
        pre_push = hooks_dir / "pre-push"
        pre_push.write_text("""#!/bin/bash
# gitcloakd pre-push hook - encrypt before pushing

# Check if gitcloakd is installed
if ! command -v gitcloakd &> /dev/null; then
    echo "[gitcloakd] Warning: gitcloakd not installed, skipping auto-encrypt"
    exit 0
fi

# Check if in decrypted state
if [ -f ".gitcloakd/manifest.json" ]; then
    state=$(python3 -c "import json; print(json.load(open('.gitcloakd/manifest.json')).get('state', ''))" 2>/dev/null)
    if [ "$state" = "decrypted" ]; then
        echo "[gitcloakd] Encrypting repository before push..."
        gitcloakd encrypt --full
        git add -A
        git commit -m "gitcloakd: auto-encrypt before push" --no-verify
    fi
fi

exit 0
""")
        pre_push.chmod(0o755)

        # Post-merge hook: decrypt after pulling
        post_merge = hooks_dir / "post-merge"
        post_merge.write_text("""#!/bin/bash
# gitcloakd post-merge hook - decrypt after pulling

# Check if gitcloakd is installed
if ! command -v gitcloakd &> /dev/null; then
    echo "[gitcloakd] Warning: gitcloakd not installed"
    exit 0
fi

# Check if encrypted blob exists
if [ -f "encrypted.gpg" ]; then
    echo "[gitcloakd] Decrypting repository after pull..."
    gitcloakd decrypt --full
fi

exit 0
""")
        post_merge.chmod(0o755)

        # Post-checkout hook: decrypt after checkout
        post_checkout = hooks_dir / "post-checkout"
        post_checkout.write_text("""#!/bin/bash
# gitcloakd post-checkout hook - decrypt after checkout

# Check if gitcloakd is installed
if ! command -v gitcloakd &> /dev/null; then
    exit 0
fi

# Check if encrypted blob exists
if [ -f "encrypted.gpg" ]; then
    echo "[gitcloakd] Decrypting repository..."
    gitcloakd decrypt --full
fi

exit 0
""")
        post_checkout.chmod(0o755)

    def _update_gitignore(self) -> None:
        """Update .gitignore for full encryption mode."""
        gitignore = self.repo_path / ".gitignore"

        existing = ""
        if gitignore.exists():
            existing = gitignore.read_text()

        additions = """
# gitcloakd full encryption mode
# These patterns help prevent accidental commits of decrypted content
# when working locally

# Local decrypted working files are tracked differently
# The encrypted.gpg blob is the source of truth
"""

        if "gitcloakd full encryption" not in existing:
            gitignore.write_text(existing + additions)

    def _reencrypt_for_users(self) -> None:
        """Re-encrypt the blob for current user list."""
        if not self.is_encrypted():
            return

        # Decrypt first
        decrypt_result = self.decrypt_all()
        if decrypt_result["errors"]:
            raise RuntimeError(f"Failed to decrypt for re-encryption: {decrypt_result['errors']}")

        # Re-encrypt with updated user list
        encrypt_result = self.encrypt_all()
        if encrypt_result["errors"]:
            raise RuntimeError(f"Failed to re-encrypt: {encrypt_result['errors']}")

    def _get_gpg_name(self, key_id: str) -> str:
        """Get name associated with a GPG key."""
        keys = self.gpg.list_keys(keys=[key_id])
        if keys:
            uids = keys[0].get("uids", [])
            if uids:
                uid = uids[0]
                if "<" in uid:
                    return uid.split("<")[0].strip()
                return uid
        return "Unknown"


def clone_and_decrypt(repo_url: str, dest_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Clone an encrypted repository and decrypt it.

    Args:
        repo_url: Git repository URL
        dest_path: Destination path (default: repo name)

    Returns:
        Result summary
    """
    result = {
        "cloned": False,
        "decrypted": False,
        "path": "",
        "errors": []
    }

    # Extract repo name from URL
    repo_name = repo_url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    dest = Path(dest_path) if dest_path else Path.cwd() / repo_name
    result["path"] = str(dest)

    # Clone
    try:
        subprocess.run(
            ["git", "clone", repo_url, str(dest)],
            check=True,
            capture_output=True
        )
        result["cloned"] = True
    except subprocess.CalledProcessError as e:
        result["errors"].append(f"Clone failed: {e.stderr.decode()}")
        return result

    # Check if it's a gitcloakd repo
    encrypted_blob = dest / FullRepoEncryption.ENCRYPTED_BLOB
    if not encrypted_blob.exists():
        result["errors"].append("Not a gitcloakd full-encryption repository")
        return result

    # Decrypt
    encryptor = FullRepoEncryption(str(dest))
    decrypt_result = encryptor.decrypt_all()

    if decrypt_result["errors"]:
        result["errors"].extend(decrypt_result["errors"])
    else:
        result["decrypted"] = True
        result["files"] = decrypt_result["files_decrypted"]

    return result
