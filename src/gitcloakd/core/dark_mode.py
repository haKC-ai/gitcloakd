"""
gitcloakd Dark Mode
Complete repository obfuscation - nothing is visible without authorization.

DARK MODE is the ultimate privacy mode where:
- The entire codebase is encrypted
- Git history is hidden (single encrypted commit visible)
- Repository names are obfuscated with UUIDs
- Branch names are meaningless
- Commit messages are hidden
- File structure is completely hidden
- Contributors are not visible

An unauthorized viewer sees ONLY:
- A UUID-named repository (real name is encrypted)
- A single encrypted.gpg file
- A generic README explaining it's encrypted
- A .gitcloakd/ folder with public config

The real git history and project name are stored INSIDE the encrypted blob.
"""

import os
import subprocess
import shutil
import tarfile
import io
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import gnupg


class DarkMode:
    """
    Dark Mode - TOTAL encryption including git history and repo naming.

    How it works:
    1. Your real project name is mapped to a random UUID
    2. The REAL repository (with full git history) is stored encrypted
    3. A "wrapper" git repo contains only the encrypted blob
    4. Only authorized users can see the real project name
    5. Unauthorized users see meaningless UUIDs and encrypted blobs

    Structure when encrypted (what unauthorized users see):
    /550e8400-e29b-41d4-a716-446655440000/   # UUID, not real name
        .git/                   # Single opaque commit
        .gitcloakd/
            config.yaml         # Public config (no real names)
            public_key.asc      # Owner's public key
        encrypted.gpg           # EVERYTHING (code, history, real name)
        README.md               # Generic "this is encrypted" message

    Structure when decrypted (local working for authorized users):
    /my-secret-project/         # Real name visible locally
        .git/                   # REAL git history
        .gitcloakd/
            ...
        <all your actual files>
    """

    ENCRYPTED_BLOB = "encrypted.gpg"
    WRAPPER_BACKUP = ".gitcloakd-wrapper"
    MANIFEST_FILE = ".gitcloakd/manifest.json"
    NAME_MAP_FILE = ".gitcloakd/name_map.gpg"  # Encrypted name mapping

    # Files that stay in the wrapper (public)
    WRAPPER_FILES = [
        ".gitcloakd/",
        "README.md",
        "LICENSE",
        ".gitignore",
    ]

    def __init__(self, repo_path: Optional[str] = None, passphrase: Optional[str] = None):
        """Initialize dark mode repository.

        Args:
            repo_path: Path to repository (default: current directory)
            passphrase: GPG passphrase for decryption operations (optional,
                       uses gpg-agent if not provided)
        """
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.config_dir = self.repo_path / ".gitcloakd"
        self.gpg = gnupg.GPG()
        self._passphrase = passphrase
        self._config = None

    @property
    def config(self):
        """Config accessor with initialized flag."""
        if self._config is None:
            manifest = self._read_manifest()
            self._config = type('Config', (), {
                'initialized': manifest is not None and manifest.get('mode') == 'dark',
                'mode': manifest.get('mode') if manifest else None,
                'state': manifest.get('state') if manifest else None,
            })()
        return self._config

    def is_initialized(self) -> bool:
        """Check if dark mode has been initialized."""
        return (self.repo_path / self.MANIFEST_FILE).exists()

    def is_wrapper_state(self) -> bool:
        """Check if repo is in encrypted wrapper state (what unauthorized users see)."""
        return (self.repo_path / self.ENCRYPTED_BLOB).exists()

    def is_working_state(self) -> bool:
        """Check if repo is in decrypted working state."""
        return (
            (self.repo_path / ".git").exists()
            and not (self.repo_path / self.ENCRYPTED_BLOB).exists()
            and self.is_initialized()
        )

    def initialize_dark_mode(
        self,
        real_name: str,
        owner_key_id: str,
        owner_email: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initialize a Dark Mode encrypted repository.

        Args:
            real_name: The REAL project name (will be encrypted, never exposed)
            owner_key_id: GPG key ID of the repository owner
            owner_email: Email of the repository owner
            description: Optional project description (also encrypted)

        Returns:
            Dict with UUID and initialization details
        """
        # Generate random UUID for public repo name
        public_uuid = str(uuid.uuid4())

        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Create public manifest (NO sensitive info)
        public_manifest = {
            "mode": "dark",
            "version": "2.0",
            "public_id": public_uuid,
            "created_at": datetime.now().isoformat(),
            "state": "working",
            "owner_key_fingerprint": owner_key_id[-8:],  # Only last 8 chars
            "users": [
                {
                    "key_fingerprint": owner_key_id[-8:],
                    "role": "owner",
                    "added_at": datetime.now().isoformat(),
                    "can_see_name": True,  # Owner can see real name
                }
            ]
        }

        self._write_manifest(public_manifest)

        # Create ENCRYPTED name mapping (only authorized users can read)
        name_mapping = {
            "real_name": real_name,
            "description": description,
            "public_uuid": public_uuid,
            "owner_email": owner_email,
            "owner_key_id": owner_key_id,
            "created_at": datetime.now().isoformat(),
            "users": [
                {
                    "email": owner_email,
                    "key_id": owner_key_id,
                    "role": "owner",
                    "can_see_name": True,
                    "added_at": datetime.now().isoformat()
                }
            ]
        }

        self._write_encrypted_name_map(name_mapping, owner_key_id)

        # Create public README (no real name)
        self._create_wrapper_readme(public_uuid)

        # Export owner's public key
        self._export_public_key(owner_key_id)

        # Create .gitignore for wrapper
        self._create_wrapper_gitignore()

        return {
            "success": True,
            "public_uuid": public_uuid,
            "real_name": real_name,
            "message": f"Dark mode initialized. Public ID: {public_uuid}"
        }

    def get_real_name(self) -> Optional[str]:
        """
        Get the real project name (only works if you have GPG access).

        Returns:
            Real project name or None if not authorized
        """
        name_map = self._read_encrypted_name_map()
        if name_map:
            return name_map.get("real_name")
        return None

    def get_public_id(self) -> Optional[str]:
        """Get the public UUID (visible to everyone)."""
        manifest = self._read_manifest()
        if manifest:
            return manifest.get("public_id")
        return None

    def encrypt_to_wrapper(self, rename_to_uuid: bool = False) -> Dict[str, Any]:
        """
        Encrypt the ENTIRE repository (including .git and real name) into wrapper state.

        Args:
            rename_to_uuid: If True, rename the repository folder to the UUID after encryption

        Returns:
            Summary of encryption
        """
        results = {
            "success": False,
            "files_encrypted": 0,
            "real_commits": 0,
            "public_uuid": None,
            "new_path": None,
            "errors": []
        }

        name_map = self._read_encrypted_name_map()
        if not name_map:
            results["errors"].append("Not initialized. Run: gitcloakd init --dark")
            return results

        # Get recipients from name map
        recipients = [u["key_id"] for u in name_map.get("users", []) if u.get("key_id")]
        if not recipients:
            results["errors"].append("No authorized users configured")
            return results

        results["public_uuid"] = name_map.get("public_uuid")

        # Count real commits before encrypting
        try:
            commit_count = subprocess.check_output(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=str(self.repo_path),
                text=True
            ).strip()
            results["real_commits"] = int(commit_count)
        except subprocess.CalledProcessError:
            results["real_commits"] = 0

        # Create tarball of EVERYTHING except wrapper files
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            for item in self.repo_path.rglob("*"):
                if not item.is_file():
                    continue

                rel_path = item.relative_to(self.repo_path)

                # Skip wrapper files
                if self._is_wrapper_file(str(rel_path)):
                    continue

                # Skip the encrypted blob itself
                if item.name == self.ENCRYPTED_BLOB:
                    continue

                # Skip wrapper backup
                if self.WRAPPER_BACKUP in str(rel_path):
                    continue

                tar.add(str(item), arcname=str(rel_path))
                results["files_encrypted"] += 1

        tar_data = tar_buffer.getvalue()

        # Encrypt
        encrypted = self.gpg.encrypt(
            tar_data,
            recipients,
            armor=True,
            always_trust=True
        )

        if not encrypted.ok:
            results["errors"].append(f"GPG encryption failed: {encrypted.status}")
            return results

        # Clear any existing wrapper backup (we don't need it - .git is in the tarball)
        wrapper_backup = self.repo_path / self.WRAPPER_BACKUP
        if wrapper_backup.exists():
            shutil.rmtree(wrapper_backup)

        # Remove current .git (it's already packed in the tarball)
        real_git = self.repo_path / ".git"
        if real_git.exists():
            shutil.rmtree(real_git)

        # Write encrypted blob
        encrypted_blob = self.repo_path / self.ENCRYPTED_BLOB
        encrypted_blob.write_text(str(encrypted))

        # Remove all files except wrapper files
        for item in self.repo_path.rglob("*"):
            if not item.is_file():
                continue
            rel_path = item.relative_to(self.repo_path)
            if self._is_wrapper_file(str(rel_path)):
                continue
            if item.name == self.ENCRYPTED_BLOB:
                continue
            if self.WRAPPER_BACKUP in str(rel_path):
                continue
            try:
                item.unlink()
            except Exception as e:
                results["errors"].append(f"Failed to remove {rel_path}: {e}")

        # Clean up empty directories
        self._cleanup_empty_dirs()

        # Initialize clean wrapper git
        self._init_wrapper_git()

        # Update manifest state
        manifest = self._read_manifest()
        if manifest:
            manifest["state"] = "encrypted"
            manifest["last_encrypted"] = datetime.now().isoformat()
            self._write_manifest(manifest)

        results["success"] = True

        # Rename folder to UUID if requested
        if rename_to_uuid and results["public_uuid"]:
            parent_dir = self.repo_path.parent
            original_name = self.repo_path.name
            new_path = parent_dir / results["public_uuid"]
            if new_path.exists():
                results["errors"].append(f"Cannot rename: {new_path} already exists")
            else:
                try:
                    # Record original folder name in encrypted name_map (only visible to authorized users)
                    name_map = self._read_encrypted_name_map()
                    if name_map:
                        name_map["original_folder_name"] = original_name
                        recipients = [u["key_id"] for u in name_map.get("users", []) if u.get("key_id")]
                        if recipients:
                            self._write_encrypted_name_map(name_map, recipients)

                    shutil.move(str(self.repo_path), str(new_path))
                    results["new_path"] = str(new_path)
                    results["original_name"] = original_name
                    # Update internal path reference
                    self.repo_path = new_path
                    self.config_dir = new_path / ".gitcloakd"
                except Exception as e:
                    results["errors"].append(f"Failed to rename folder: {e}")

        return results

    def decrypt_from_wrapper(self) -> Dict[str, Any]:
        """
        Decrypt from wrapper state to full working repository.

        Returns:
            Summary of decryption including real name
        """
        results = {
            "success": False,
            "files_decrypted": 0,
            "commits_restored": 0,
            "real_name": None,
            "errors": []
        }

        encrypted_blob = self.repo_path / self.ENCRYPTED_BLOB
        if not encrypted_blob.exists():
            results["errors"].append("No encrypted blob found")
            return results

        # Remove wrapper .git (will be replaced by real .git from tarball)
        current_git = self.repo_path / ".git"
        if current_git.exists():
            shutil.rmtree(current_git)

        # Decrypt the blob
        encrypted_data = encrypted_blob.read_text()
        if self._passphrase:
            decrypted = self.gpg.decrypt(encrypted_data, passphrase=self._passphrase)
        else:
            decrypted = self.gpg.decrypt(encrypted_data)

        if not decrypted.ok:
            results["errors"].append(f"GPG decryption failed: {decrypted.status}")
            results["errors"].append("Make sure your GPG key is available and passphrase is correct")
            return results

        # Extract tarball (includes .git with full history)
        tar_buffer = io.BytesIO(decrypted.data)
        try:
            with tarfile.open(fileobj=tar_buffer, mode="r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in member.name:
                        results["errors"].append(f"Suspicious path: {member.name}")
                        return results

                tar.extractall(path=str(self.repo_path))
                results["files_decrypted"] = len(tar.getmembers())
        except tarfile.TarError as e:
            results["errors"].append(f"Failed to extract: {e}")
            return results

        # Count restored commits
        try:
            commit_count = subprocess.check_output(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=str(self.repo_path),
                text=True
            ).strip()
            results["commits_restored"] = int(commit_count)
        except subprocess.CalledProcessError:
            pass

        # Remove encrypted blob
        encrypted_blob.unlink()

        # Update manifest
        manifest = self._read_manifest()
        if manifest:
            manifest["state"] = "working"
            manifest["last_decrypted"] = datetime.now().isoformat()
            self._write_manifest(manifest)

        # Get real name for authorized users
        name_map = self._read_encrypted_name_map()
        if name_map:
            results["real_name"] = name_map.get("real_name")

        results["success"] = True
        return results

    def add_user(
        self,
        email: str,
        key_id: str,
        role: str = "collaborator",
        can_see_name: bool = True
    ) -> bool:
        """
        Add a user who can decrypt the repository.

        Args:
            email: User's email
            key_id: User's GPG key ID
            role: User role
            can_see_name: Whether user can see real project name

        Returns:
            True if added successfully
        """
        name_map = self._read_encrypted_name_map()
        if not name_map:
            return False

        # Check if already exists
        for user in name_map.get("users", []):
            if user["email"] == email:
                user["key_id"] = key_id
                user["can_see_name"] = can_see_name
                break
        else:
            name_map["users"].append({
                "email": email,
                "key_id": key_id,
                "role": role,
                "can_see_name": can_see_name,
                "added_at": datetime.now().isoformat()
            })

        # Re-encrypt name map with all user keys
        all_keys = [u["key_id"] for u in name_map["users"] if u.get("key_id")]
        self._write_encrypted_name_map(name_map, all_keys)

        # Update public manifest
        manifest = self._read_manifest()
        if manifest:
            found = False
            for user in manifest.get("users", []):
                if user.get("key_fingerprint") == key_id[-8:]:
                    user["can_see_name"] = can_see_name
                    found = True
                    break
            if not found:
                manifest["users"].append({
                    "key_fingerprint": key_id[-8:],
                    "role": role,
                    "can_see_name": can_see_name,
                    "added_at": datetime.now().isoformat()
                })
            self._write_manifest(manifest)

        # If currently encrypted, re-encrypt with new user
        if self.is_wrapper_state():
            self._reencrypt_for_users()

        return True

    def remove_user(self, email: str) -> bool:
        """Remove a user's access."""
        name_map = self._read_encrypted_name_map()
        if not name_map:
            return False

        original_count = len(name_map.get("users", []))
        name_map["users"] = [u for u in name_map["users"] if u["email"] != email]

        if len(name_map["users"]) < original_count:
            # Re-encrypt with remaining users
            all_keys = [u["key_id"] for u in name_map["users"] if u.get("key_id")]
            self._write_encrypted_name_map(name_map, all_keys)

            # Re-encrypt to revoke access
            if self.is_wrapper_state():
                self._reencrypt_for_users()

            return True
        return False

    def list_users(self) -> List[Dict[str, Any]]:
        """
        List users with access to this dark mode repository.

        Returns:
            List of user information dictionaries
        """
        name_map = self._read_encrypted_name_map()
        if not name_map:
            return []

        return name_map.get("users", [])

    def get_name_info(self) -> Optional[Dict[str, Any]]:
        """
        Get name mapping info (only works if you have GPG access).

        Returns:
            Dict with real_name, public_uuid, description or None if not authorized
        """
        name_map = self._read_encrypted_name_map()
        if name_map:
            return {
                "real_name": name_map.get("real_name"),
                "public_uuid": name_map.get("public_uuid"),
                "description": name_map.get("description"),
                "created_at": name_map.get("created_at"),
                "owner_email": name_map.get("owner_email"),
            }
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the dark mode repo."""
        manifest = self._read_manifest()
        name_map = self._read_encrypted_name_map()

        status = {
            "mode": "dark",
            "state": "unknown",
            "public_id": None,
            "real_name": None,  # Only if authorized
            "users": [],
            "is_wrapper": self.is_wrapper_state(),
            "is_working": self.is_working_state()
        }

        if manifest:
            status["state"] = manifest.get("state", "unknown")
            status["public_id"] = manifest.get("public_id")

        if name_map:
            # Only show real name to authorized users
            status["real_name"] = name_map.get("real_name")
            status["users"] = [
                {
                    "email": u.get("email"),
                    "role": u.get("role"),
                    "can_see_name": u.get("can_see_name", True)
                }
                for u in name_map.get("users", [])
            ]

        if self.is_wrapper_state():
            blob = self.repo_path / self.ENCRYPTED_BLOB
            status["blob_size"] = blob.stat().st_size

        return status

    # === Private Methods ===

    def _is_wrapper_file(self, rel_path: str) -> bool:
        """Check if file should stay in wrapper (public)."""
        for wrapper in self.WRAPPER_FILES:
            if rel_path.startswith(wrapper) or rel_path == wrapper.rstrip("/"):
                return True
        return False

    def _read_manifest(self) -> Optional[Dict]:
        """Read the public manifest file."""
        manifest_file = self.repo_path / self.MANIFEST_FILE
        if not manifest_file.exists():
            return None
        try:
            return json.loads(manifest_file.read_text())
        except json.JSONDecodeError:
            return None

    def _write_manifest(self, manifest: Dict) -> None:
        """Write the public manifest file."""
        manifest_file = self.repo_path / self.MANIFEST_FILE
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        manifest_file.write_text(json.dumps(manifest, indent=2))

    def _read_encrypted_name_map(self) -> Optional[Dict]:
        """Read the encrypted name mapping (requires GPG key)."""
        name_map_file = self.repo_path / self.NAME_MAP_FILE
        if not name_map_file.exists():
            return None

        try:
            encrypted_data = name_map_file.read_text()
            # Use passphrase if provided, otherwise rely on gpg-agent
            if self._passphrase:
                decrypted = self.gpg.decrypt(
                    encrypted_data,
                    passphrase=self._passphrase
                )
            else:
                decrypted = self.gpg.decrypt(encrypted_data)

            if not decrypted.ok:
                return None

            return json.loads(str(decrypted))
        except (json.JSONDecodeError, Exception):
            return None

    def _write_encrypted_name_map(self, name_map: Dict, recipients) -> None:
        """Write encrypted name mapping."""
        if isinstance(recipients, str):
            recipients = [recipients]

        encrypted = self.gpg.encrypt(
            json.dumps(name_map, indent=2),
            recipients,
            armor=True,
            always_trust=True
        )

        name_map_file = self.repo_path / self.NAME_MAP_FILE
        name_map_file.parent.mkdir(parents=True, exist_ok=True)
        name_map_file.write_text(str(encrypted))
        name_map_file.chmod(0o600)

    def _create_wrapper_readme(self, public_uuid: str) -> None:
        """Create the public README for wrapper state."""
        readme = self.repo_path / "README.md"

        content = f"""# {public_uuid}

This repository is protected with **gitcloakd** Dark Mode.

## What You Can See

If you're seeing only this README and `encrypted.gpg`, you don't have access.

**Everything is hidden:**
- Real project name
- All source code
- Complete git history
- All commits and branches
- File structure
- Contributors

## Getting Access

1. Generate a GPG key:
   ```bash
   gpg --full-generate-key
   ```

2. Send your public key to the repository owner:
   ```bash
   gpg --armor --export your@email.com > my-key.pub
   ```

3. Once authorized, clone and decrypt:
   ```bash
   gitcloakd clone <repo-url>
   # Your GPG passphrase will be requested
   ```

## Security

- Dark Mode: Maximum privacy encryption
- Real project name is encrypted
- Git history is not visible without decryption
- Commit messages are encrypted
- Contributors cannot be determined

---
Protected with [gitcloakd](https://github.com/haKC-ai/gitcloakd) Dark Mode
"""

        readme.write_text(content)

    def _create_wrapper_gitignore(self) -> None:
        """Create .gitignore for wrapper repo."""
        gitignore = self.repo_path / ".gitignore"

        content = """# gitcloakd Dark Mode
# Only the encrypted blob and wrapper files are committed

# Backup of real repo state (never commit)
.gitcloakd-wrapper/

# Temporary decryption files
*.decrypted
*.tmp

# OS files
.DS_Store
Thumbs.db
"""

        gitignore.write_text(content)

    def _export_public_key(self, key_id: str) -> None:
        """Export owner's public key for easy sharing."""
        pub_key = self.gpg.export_keys(key_id)
        key_file = self.config_dir / "owner_public_key.asc"
        key_file.write_text(pub_key)

    def _init_wrapper_git(self) -> None:
        """Initialize/reset wrapper git with single commit."""
        git_dir = self.repo_path / ".git"

        # Check if .git exists AND is a valid git repo (has HEAD file)
        # After encryption, .git exists but is empty, so we need to reinit
        git_head = git_dir / "HEAD"
        if not git_dir.exists() or not git_head.exists():
            # Remove empty .git dir if it exists
            if git_dir.exists():
                shutil.rmtree(git_dir)
            subprocess.run(
                ["git", "init"],
                cwd=str(self.repo_path),
                check=True,
                capture_output=True
            )

        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(self.repo_path),
            check=True,
            capture_output=True
        )

        subprocess.run(
            ["git", "commit", "-m", "gitcloakd: encrypted state", "--allow-empty"],
            cwd=str(self.repo_path),
            check=False,
            capture_output=True
        )

    def _cleanup_empty_dirs(self) -> None:
        """Remove empty directories and OS junk files."""
        # First pass: remove OS junk files
        junk_files = ['.DS_Store', 'Thumbs.db', 'desktop.ini']
        for dirpath, dirnames, filenames in os.walk(str(self.repo_path)):
            dir_path = Path(dirpath)

            if ".git" in str(dir_path) or ".gitcloakd" in str(dir_path):
                continue
            if self.WRAPPER_BACKUP in str(dir_path):
                continue

            for junk in junk_files:
                junk_path = dir_path / junk
                if junk_path.exists():
                    try:
                        junk_path.unlink()
                    except OSError:
                        pass

        # Second pass: remove empty directories
        for dirpath, dirnames, filenames in os.walk(str(self.repo_path), topdown=False):
            dir_path = Path(dirpath)

            if ".git" in str(dir_path) or ".gitcloakd" in str(dir_path):
                continue
            if self.WRAPPER_BACKUP in str(dir_path):
                continue

            if dir_path != self.repo_path and not any(dir_path.iterdir()):
                try:
                    dir_path.rmdir()
                except OSError:
                    pass

    def _reencrypt_for_users(self) -> None:
        """Re-encrypt blob with current user list."""
        if not self.is_wrapper_state():
            return

        self.decrypt_from_wrapper()
        self.encrypt_to_wrapper()


def security_checklist() -> Dict[str, Any]:
    """
    Comprehensive security checklist for gitcloakd.

    Returns analysis and recommendations.
    """
    checklist = {
        "passed": [],
        "warnings": [],
        "critical": [],
        "recommendations": []
    }

    gpg = gnupg.GPG()
    secret_keys = gpg.list_keys(secret=True)

    if not secret_keys:
        checklist["critical"].append("No GPG secret keys found - cannot encrypt/decrypt")
    else:
        checklist["passed"].append(f"GPG configured with {len(secret_keys)} secret key(s)")

        for key in secret_keys:
            key_length = key.get("length", 0)
            if int(key_length) < 2048:
                checklist["warnings"].append(f"Key {key['keyid']} has weak length ({key_length} bits)")
            else:
                checklist["passed"].append(f"Key {key['keyid']} has strong length ({key_length} bits)")

            expires = key.get("expires")
            if expires:
                try:
                    exp_date = datetime.fromtimestamp(int(expires))
                    if exp_date < datetime.now():
                        checklist["critical"].append(f"Key {key['keyid']} has EXPIRED")
                    elif (exp_date - datetime.now()).days < 30:
                        checklist["warnings"].append(f"Key {key['keyid']} expires in < 30 days")
                except ValueError:
                    pass

    storage_path = Path.home() / ".gitcloakd"
    if storage_path.exists():
        mode = storage_path.stat().st_mode
        if mode & 0o077:
            checklist["warnings"].append("~/.gitcloakd has loose permissions (should be 700)")
        else:
            checklist["passed"].append("~/.gitcloakd has secure permissions")

        if (storage_path / "config.gpg").exists():
            checklist["passed"].append("Local storage is GPG-encrypted")
        else:
            checklist["warnings"].append("Local storage may not be encrypted")
    else:
        checklist["recommendations"].append("Run 'gitcloakd secure init' to protect local data")

    checklist["recommendations"].extend([
        "Store GPG passphrase in a password manager (Proton Pass, 1Password, etc.)",
        "Back up your GPG key securely (paper backup, encrypted USB)",
        "Use 'gitcloakd lock' when leaving your laptop",
        "Use Dark Mode for maximum privacy (hides everything)",
        "Regularly rotate GPG keys (yearly)",
        "Never share your private key",
        "Use gpg-agent for caching passphrase (avoid typing repeatedly)",
    ])

    return checklist
