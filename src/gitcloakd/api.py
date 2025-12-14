"""
gitcloakd API - Simple programmatic interface for encrypting files.

Use this module to integrate gitcloakd into your own code, CI/CD pipelines,
or git hooks.

Example usage in code:
    from gitcloakd import encrypt_files, encrypt_matching

    # Encrypt specific files
    encrypt_files([".env", "config/secrets.yaml"])

    # Encrypt all files matching patterns
    encrypt_matching(["*.env", "*.key", "*.pem"])

Example pre-commit hook (.git/hooks/pre-commit):
    #!/usr/bin/env python3
    from gitcloakd import encrypt_staged

    # Encrypt any staged files that match patterns
    encrypt_staged()
"""

import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

from gitcloakd.core.encryption import GitCrypted, GPGNotInstalledException


def encrypt_files(
    files: List[str],
    repo_path: Optional[str] = None,
    recipients: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Encrypt specific files.

    Args:
        files: List of file paths to encrypt
        repo_path: Repository path (default: current directory)
        recipients: GPG key IDs to encrypt for (default: all repo users)

    Returns:
        Dict with 'encrypted', 'skipped', and 'errors' lists

    Example:
        from gitcloakd import encrypt_files

        result = encrypt_files([".env", "config/api_keys.json"])
        print(f"Encrypted {len(result['encrypted'])} files")
    """
    gc = GitCrypted(repo_path)

    results = {
        "encrypted": [],
        "skipped": [],
        "errors": []
    }

    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            results["errors"].append({"file": str(path), "error": "File not found"})
            continue

        # Skip already encrypted files
        if path.suffix == ".gpg":
            results["skipped"].append(str(path))
            continue

        try:
            gc.encrypt_file(str(path), recipients)
            results["encrypted"].append(str(path))
        except Exception as e:
            results["errors"].append({"file": str(path), "error": str(e)})

    return results


def encrypt_matching(
    patterns: Optional[List[str]] = None,
    repo_path: Optional[str] = None,
    recipients: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Encrypt all files matching patterns.

    Args:
        patterns: Glob patterns to match (default: use repo config patterns)
        repo_path: Repository path (default: current directory)
        recipients: GPG key IDs to encrypt for (default: all repo users)

    Returns:
        Dict with 'encrypted', 'skipped', and 'errors' lists

    Example:
        from gitcloakd import encrypt_matching

        # Encrypt all .env and .key files
        result = encrypt_matching(["*.env", "*.key", "**/*.pem"])
        print(f"Encrypted {len(result['encrypted'])} files")
    """
    gc = GitCrypted(repo_path)
    repo = Path(repo_path) if repo_path else Path.cwd()

    # Use config patterns if not specified
    if patterns is None:
        patterns = gc.config.auto_encrypt_patterns

    results = {
        "encrypted": [],
        "skipped": [],
        "errors": []
    }

    for pattern in patterns:
        for path in repo.glob(f"**/{pattern}"):
            # Skip already encrypted
            if path.suffix == ".gpg":
                results["skipped"].append(str(path))
                continue

            # Skip gitcloakd internals
            if ".gitcloakd" in str(path):
                continue

            try:
                gc.encrypt_file(str(path), recipients)
                results["encrypted"].append(str(path))
            except Exception as e:
                results["errors"].append({"file": str(path), "error": str(e)})

    return results


def encrypt_staged(
    repo_path: Optional[str] = None,
    patterns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Encrypt staged files that match encryption patterns.
    Designed for use in pre-commit hooks.

    Args:
        repo_path: Repository path (default: current directory)
        patterns: Patterns to match (default: use repo config)

    Returns:
        Dict with 'encrypted', 'skipped', and 'errors' lists

    Example pre-commit hook:
        #!/usr/bin/env python3
        from gitcloakd import encrypt_staged
        import sys

        result = encrypt_staged()
        if result['encrypted']:
            print(f"Auto-encrypted {len(result['encrypted'])} files")
            # Re-add encrypted files to staging
            for f in result['encrypted']:
                subprocess.run(["git", "add", f + ".gpg"])
        if result['errors']:
            print(f"Encryption errors: {result['errors']}")
            sys.exit(1)
    """
    repo = Path(repo_path) if repo_path else Path.cwd()
    gc = GitCrypted(str(repo))

    # Get staged files
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True
        )
        staged_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except subprocess.CalledProcessError:
        return {"encrypted": [], "skipped": [], "errors": [{"file": "", "error": "Not a git repo"}]}

    # Use config patterns if not specified
    if patterns is None:
        patterns = gc.config.auto_encrypt_patterns

    results = {
        "encrypted": [],
        "skipped": [],
        "errors": []
    }

    import fnmatch

    for staged_file in staged_files:
        path = repo / staged_file

        # Check if matches any pattern
        matches = False
        for pattern in patterns:
            if fnmatch.fnmatch(staged_file, pattern) or fnmatch.fnmatch(path.name, pattern):
                matches = True
                break

        if not matches:
            continue

        # Skip already encrypted
        if path.suffix == ".gpg":
            results["skipped"].append(str(path))
            continue

        # Skip if encrypted version already staged
        if (repo / (staged_file + ".gpg")).exists():
            results["skipped"].append(str(path))
            continue

        try:
            gc.encrypt_file(str(path))
            results["encrypted"].append(str(path))
        except Exception as e:
            results["errors"].append({"file": str(path), "error": str(e)})

    return results


def decrypt_files(
    files: List[str],
    repo_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Decrypt specific files.

    Args:
        files: List of .gpg file paths to decrypt
        repo_path: Repository path (default: current directory)

    Returns:
        Dict with 'decrypted', 'skipped', and 'errors' lists

    Example:
        from gitcloakd import decrypt_files

        result = decrypt_files([".env.gpg", "config/secrets.yaml.gpg"])
        print(f"Decrypted {len(result['decrypted'])} files")
    """
    gc = GitCrypted(repo_path)

    results = {
        "decrypted": [],
        "skipped": [],
        "errors": []
    }

    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            results["errors"].append({"file": str(path), "error": "File not found"})
            continue

        if path.suffix != ".gpg":
            results["skipped"].append(str(path))
            continue

        try:
            gc.decrypt_file(str(path))
            results["decrypted"].append(str(path))
        except Exception as e:
            results["errors"].append({"file": str(path), "error": str(e)})

    return results


def is_initialized(repo_path: Optional[str] = None) -> bool:
    """
    Check if gitcloakd is initialized in the repository.

    Args:
        repo_path: Repository path (default: current directory)

    Returns:
        True if gitcloakd is initialized

    Example:
        from gitcloakd import is_initialized

        if not is_initialized():
            print("Run 'gitcloakd init' first!")
    """
    try:
        gc = GitCrypted(repo_path)
        return gc.is_initialized()
    except GPGNotInstalledException:
        return False


def get_encryption_patterns(repo_path: Optional[str] = None) -> List[str]:
    """
    Get the encryption patterns configured for the repository.

    Args:
        repo_path: Repository path (default: current directory)

    Returns:
        List of glob patterns that will be auto-encrypted

    Example:
        from gitcloakd import get_encryption_patterns

        patterns = get_encryption_patterns()
        print(f"Auto-encrypting: {patterns}")
    """
    gc = GitCrypted(repo_path)
    return gc.config.auto_encrypt_patterns


def check_gpg() -> bool:
    """
    Check if GPG is installed and available.

    Returns:
        True if GPG is available

    Example:
        from gitcloakd import check_gpg

        if not check_gpg():
            print("Install GPG: brew install gnupg")
    """
    import shutil
    return shutil.which("gpg") is not None
