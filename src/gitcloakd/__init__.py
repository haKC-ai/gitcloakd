"""
gitcloakd - Encrypt Git repositories with GPG

A comprehensive tool for securing Git repositories using GPG encryption,
with support for GitHub integration, AI coding agents, and team collaboration.

SECURITY NOTICE:
================
This software provides encryption for Git repositories using GPG.
While we strive to implement security best practices, please note:

1. ENCRYPTION STRENGTH depends on your GPG key:
   - Use RSA 4096-bit or ED25519 keys minimum
   - Store your passphrase in a proper password manager
   - Back up your private key securely (offline, encrypted)

2. LOCAL DATA PROTECTION:
   - Enable 'gitcloakd secure init' to encrypt local data
   - Use full-disk encryption on your system for maximum security
   - Data may persist in OS swap files, SSD wear leveling

3. LIMITATIONS:
   - Cannot protect against compromised systems
   - Cannot prevent authorized users from sharing decrypted content
   - Network metadata (timing, size) may leak information
   - System logs outside gitcloakd control may contain traces

4. THREAT MODEL:
   - Designed for: protecting code from unauthorized repo access
   - NOT designed for: military-grade secrecy, nation-state adversaries

5. NO WARRANTY:
   This software is provided "as is" without warranty of any kind.
   The authors are not liable for any damages arising from its use.
   Use at your own risk.

For maximum security, combine gitcloakd with:
- Full-disk encryption (LUKS, FileVault, BitLocker)
- Secure boot
- Hardware security keys (YubiKey)
- Air-gapped key generation

MODES:
======
- Selective: Encrypt specific files matching patterns (default)
- Full: Encrypt entire codebase into single GPG blob
- Dark: Maximum privacy - encrypts everything including git history,
        uses UUID naming so real project name is hidden

Usage:
  gitcloakd init [--full|--dark]  # Initialize encryption
  gitcloakd encrypt               # Encrypt files
  gitcloakd decrypt               # Decrypt files
  gitcloakd add-user              # Add collaborator
  gitcloakd status                # Show status
  gitcloakd secure init           # Protect local data
"""

__version__ = "1.0.9"
__author__ = "HaKC.dev"
__license__ = "MIT"

# Core exports
from gitcloakd.core.encryption import GitCrypted, GPGNotInstalledException
from gitcloakd.core.config import Config
from gitcloakd.core.full_encryption import FullRepoEncryption
from gitcloakd.core.dark_mode import DarkMode
from gitcloakd.core.secure_storage import SecureStorage, get_secure_storage
from gitcloakd.core.audit_log import EncryptedAuditLog, AuditEventType, audit
from gitcloakd.core.memory_cleaner import MemoryCleaner, get_memory_cleaner

# Simple API functions for programmatic use
from gitcloakd.api import (
    encrypt_files,
    encrypt_matching,
    encrypt_staged,
    decrypt_files,
    is_initialized,
    get_encryption_patterns,
    check_gpg,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # Core classes
    "GitCrypted",
    "GPGNotInstalledException",
    "Config",
    "FullRepoEncryption",
    "DarkMode",
    "SecureStorage",
    "get_secure_storage",
    "EncryptedAuditLog",
    "AuditEventType",
    "audit",
    "MemoryCleaner",
    "get_memory_cleaner",
    # Simple API functions
    "encrypt_files",
    "encrypt_matching",
    "encrypt_staged",
    "decrypt_files",
    "is_initialized",
    "get_encryption_patterns",
    "check_gpg",
]
