```
░▒█▀▀█▒░:'######::'##::::::::'#######:::::'###::::'##:::'##:'########::
░▒█░▄▄▒░'##... ##: ##:::::::'##.... ##:::'## ##::: ##::'##:: ##.... ##:
░▒█▄▄▀▒░ ##:::..:: ##::::::: ##:::: ##::'##:. ##:: ##:'##::: ##:::: ##:
░▒▀█▀▒▒░ ##::::::: ##::::::: ##:::: ##:'##:::. ##: #####:::: ##:::: ##:
░▒▒█░▒▒░ ##::::::: ##::::::: ##:::: ##: #########: ##. ##::: ##:::: ##:
░▒▄█▄▒▒░ ##::: ##: ##::::::: ##:::: ##: ##.... ##: ##:. ##:: ##:::: ##:
░▀▀█▀▀▒░. ######:: ########:. #######:: ##:::: ##: ##::. ##: ########::
░░▒█░░▒░:......:::........:::.......:::..:::::..::..::::..::........:::
```

<p align="center">
  <img src="https://raw.githubusercontent.com/haKC-ai/gitcloakd/main/img/gitcloakd.gif" alt="gitcloakd demo" width="640">
</p>

```
        ┌──────────────────────── [ R E L E A S E   I N F O ] ──────────────────────────┐
        │                                                                               │
        │  NAME................................................gitcloakd                │
        │  TYPE.......................................GPG Encryption for Git Repos      │
        │  VERSION........................................................v1.0.10       │
        │  PLATFORM............................................Python 3.9+ / Cross-OS   │
        │  CATEGORY..............................................Security / Encryption  │
        │  ENCRYPTION MODES........................................................3x   │
        │                                                                               │
        │  Hide ya repos. Hide ya code. They out here hacking everybody.               │
        │                                                                               │
        │  [*] SELECTIVE - Encrypt specific files (.env, keys, secrets)                 │
        │  [*] FULL - Encrypt entire codebase into single blob                          │
        │  [*] DARK - Encrypt EVERYTHING including git history + UUID repo name         │
        │                                                                               │
        └───────────────────────────────────────────────────────────────────────────────┘
```

![Python](https://img.shields.io/badge/python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyPI](https://img.shields.io/badge/PyPI-v1.0.10-blue?style=for-the-badge&logo=pypi)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)
![GPG](https://img.shields.io/badge/encryption-GPG-red?style=for-the-badge&logo=gnuprivacyguard&logoColor=white)

---

## [::: TRY IT NOW :::]

![Colab](https://img.shields.io/badge/INTERACTIVE-NOTEBOOKS-F9AB00?style=for-the-badge&logo=googlecolab)
![Live Demo](https://img.shields.io/badge/LIVE-ENCRYPTED%20REPO-181717?style=for-the-badge&logo=github)

| Resource | Description |
|----------|-------------|
| [![Demo](https://img.shields.io/badge/Colab-Interactive_Demo-F9AB00?style=flat-square&logo=googlecolab&logoColor=white)](https://drive.google.com/file/d/1MFmQCljP1cs57bwpMDW14MxEfOUzGTgC/view?usp=drive_link) | Clone and decrypt an encrypted repo |
| [![Guide](https://img.shields.io/badge/Colab-Complete_Guide-F9AB00?style=flat-square&logo=googlecolab&logoColor=white)](https://drive.google.com/file/d/1f2hGf3aZbrgN7_nqeAbtMthtjs_rlAWi/view?usp=sharing) | All modes, commands, Python API |
| [![Troubleshooting](https://img.shields.io/badge/Colab-Troubleshooting-F9AB00?style=flat-square&logo=googlecolab&logoColor=white)](https://drive.google.com/file/d/1MmbopbuhXvHo6gW0D0c_uyZCwrFywCzr/view?usp=drive_link) | User management, GPG keys, common issues |
| [![Encrypted Repo](https://img.shields.io/badge/GitHub-Live_Encrypted_Repo-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/haKC-ai/07bf37a1-ce68-4bd1-8e71-7767f7b0d07a) | See what unauthorized users see |

```mermaid
graph LR
    subgraph Notebooks
        A[Demo] --> D[Clone Encrypted Repo]
        B[Guide] --> D
        C[Troubleshooting]
    end

    subgraph Encrypted
        D --> E[07bf37a1-...<br/>UUID Name]
        E --> F[encrypted.gpg]
    end

    subgraph Decrypted
        F -->|gitcloakd decrypt| G[Real Project Name]
        G --> H[Full Source Code]
        G --> I[Git History]
    end

    style Notebooks fill:#F9AB00,stroke:#fff,color:#000
    style Encrypted fill:#1a1a2e,stroke:#ff7edb,color:#ff7edb
    style Decrypted fill:#72f1b8,stroke:#72f1b8,color:#1a1a2e
```

```
════════════════════════════════════════════════════════════════════════════════
  [*] Notebooks are view-only - click "File > Save a copy in Drive" to run
  [*] The encrypted demo repo shows EXACTLY what unauthorized users see
  [*] With the GPG key, you decrypt and see the real gitcloakd source
════════════════════════════════════════════════════════════════════════════════
```

---

## [::: WHAT IT DOES :::]

![Modes](https://img.shields.io/badge/ENCRYPTION%20MODES-3-00D9FF?style=for-the-badge)
![GPG](https://img.shields.io/badge/POWERED%20BY-GPG-FF10F0?style=for-the-badge)

gitcloakd encrypts Git repositories using GPG. Three modes for different threat models:

| Mode | What's Encrypted | Git History | Repo Name | Use Case |
|------|------------------|-------------|-----------|----------|
| ![Selective](https://img.shields.io/badge/-Selective-blue?style=flat-square) | Specific files only | Visible | Visible | Open source with private secrets |
| ![Full](https://img.shields.io/badge/-Full-orange?style=flat-square) | Entire codebase | Visible | Visible | Private codebase, team access only |
| ![Dark](https://img.shields.io/badge/-Dark-black?style=flat-square) | **EVERYTHING** | **Hidden** | **UUID** | Maximum privacy, zero metadata |

### Authorized vs Unauthorized View

```
# What authorized users see:
my-secret-project/
  src/api/payments.py
  src/core/algorithm.py
  .env
  README.md

# What everyone else sees (Dark Mode):
07bf37a1-ce68-4bd1-8e71-7767f7b0d07a/
  encrypted.gpg
  README.md ("This repository is encrypted")
```

```
════════════════════════════════════════════════════════════════════════════════
  DARK MODE HIDES:

  [*] Real project name (replaced with random UUID)
  [*] All source code and file structure
  [*] Git history, commits, branch names
  [*] Contributors and timestamps
  [*] GitHub insights show NOTHING useful
════════════════════════════════════════════════════════════════════════════════
```

---

## [::: WHY ENCRYPT YOUR REPOS :::]

![Threats](https://img.shields.io/badge/THREAT%20MODEL-COMPREHENSIVE-00D9FF?style=for-the-badge)

| Threat | What Happens | gitcloakd Fix |
|--------|--------------|---------------|
| GitHub gets breached | Your code is leaked | They get encrypted blobs |
| Employee goes rogue | Copies private repos | Can't decrypt without your key |
| Laptop stolen | Attacker clones your repos | Local storage is GPG encrypted |
| Subpoena/legal request | GitHub hands over data | They hand over encrypted data |
| Nosy coworker/investor | Snoops your private repos | Sees nothing useful |
| You leave a company | They still have repo access | Revoke their key, re-encrypt |

**You control the keys. Not GitHub. Not your employer. You.**

---

## [::: INSTALLATION :::]

![Install](https://img.shields.io/badge/INSTALL-PIP-00D9FF?style=for-the-badge&logo=pypi)
![Setup Time](https://img.shields.io/badge/SETUP%20TIME-30%20SECONDS-FF10F0?style=for-the-badge)

```bash
pip install gitcloakd
```

### Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.9+ | Runtime |
| GPG | 2.x | Encryption |
| Git | 2.x | Version control |

```
════════════════════════════════════════════════════════════════════════════════
  [*] Works on Linux, macOS, Windows
  [*] No compilation required - pure Python
  [*] GPG must be installed and configured with at least one key
════════════════════════════════════════════════════════════════════════════════
```

---

## [::: QUICK START :::]

![Difficulty](https://img.shields.io/badge/DIFFICULTY-TRIVIAL-00D9FF?style=for-the-badge)

```bash
# Selective: encrypt specific files (.env, keys, etc.)
gitcloakd init --wizard
gitcloakd encrypt

# Full: encrypt entire codebase
gitcloakd init --full
gitcloakd encrypt --full

# Dark: encrypt everything including history and repo name
gitcloakd init --dark
gitcloakd encrypt --dark
```

### Test Before You Commit (Don't Nuke Your Repo)

```bash
gitcloakd test create --mode dark    # Create demo repo with fake secrets
gitcloakd test dry-run --mode full   # Preview changes (no modifications)
gitcloakd test backup                # Backup before encrypting
```

---

## [::: ENCRYPTION MODES :::]

### Mode 1: Selective (Default)

![Selective](https://img.shields.io/badge/MODE-SELECTIVE-blue?style=for-the-badge)

Encrypts only files matching patterns (`.env`, `*.key`, `*.pem`, etc.). Source code stays readable. Normal git workflow.

```bash
gitcloakd init --wizard
gitcloakd encrypt
```

```mermaid
graph LR
    A[main.py] --> B[main.py<br/>unchanged]
    C[.env<br/>API_KEY=secret] --> D[.env.gpg<br/>encrypted]

    style C fill:#fe4450,stroke:#fe4450,color:#fff
    style D fill:#72f1b8,stroke:#72f1b8,color:#1a1a2e
```

### Mode 2: Full Encryption

![Full](https://img.shields.io/badge/MODE-FULL-orange?style=for-the-badge)

Packs entire codebase into single encrypted blob. Git history preserved. Unauthorized users see only `encrypted.gpg`.

```bash
gitcloakd init --full
gitcloakd encrypt --full
```

**What unauthorized users see:**
```
myrepo/
  .gitcloakd/          # config
  encrypted.gpg        # your entire codebase
  README.md            # "this repo is encrypted"
```

### Mode 3: Dark Mode (Maximum Paranoia)

![Dark](https://img.shields.io/badge/MODE-DARK-black?style=for-the-badge)

Encrypts code, git history, commit messages, and replaces repo name with random UUID. Zero metadata leakage.

```bash
gitcloakd init --dark
gitcloakd encrypt --dark
```

**What's hidden in Dark Mode:**

| Item | Selective | Full | Dark |
|------|-----------|------|------|
| Source code | Visible | Hidden | Hidden |
| File structure | Visible | Hidden | Hidden |
| Git history | Visible | Visible | **Hidden** |
| Commit messages | Visible | Visible | **Hidden** |
| Branch names | Visible | Visible | **Hidden** |
| Contributors | Visible | Visible | **Hidden** |
| Project name | Visible | Visible | **Hidden (UUID)** |

```mermaid
graph TB
    subgraph Real[Real Repository]
        R1[my-secret-project]
        R2[Source Code]
        R3[100 commits, 5 branches]
        R4[Contributors List]
    end

    subgraph Visible[What Unauthorized Users See]
        V1[550e8400-...<br/>random UUID]
        V2[encrypted.gpg]
        V3[Single commit]
    end

    Real -->|GPG Encrypt| Visible

    style Real fill:#72f1b8,stroke:#72f1b8,color:#1a1a2e
    style Visible fill:#1a1a2e,stroke:#ff7edb,color:#ff7edb
```

```
════════════════════════════════════════════════════════════════════════════════
  DARK MODE LIMITATION:

  Single encrypted blob = no merge capability. Whoever pushes last wins.

  Best for:
  [*] Solo projects you want hidden
  [*] Archiving finished projects
  [*] Repos where one person pushes and others just pull/read

  For active team collaboration, use Selective Mode instead.
════════════════════════════════════════════════════════════════════════════════
```

---

## [::: LOCAL WORKSTATION PROTECTION :::]

![Local](https://img.shields.io/badge/LOCAL-ENCRYPTED-00D9FF?style=for-the-badge)

Laptop stolen? They could see what repos you manage, your command history, cached secrets. Unless you encrypt all that too.

```bash
gitcloakd secure init    # Set up encrypted local storage
gitcloakd unlock         # Decrypt to work
gitcloakd lock           # Re-encrypt when done
```

| Data | Without secure init | With secure init |
|------|---------------------|------------------|
| Repo list | Plaintext | GPG Encrypted |
| Command history | Plaintext | GPG Encrypted |
| Cached tokens | Plaintext | GPG Encrypted |

---

## [::: USER MANAGEMENT :::]

![Users](https://img.shields.io/badge/MULTI--USER-SUPPORTED-FF10F0?style=for-the-badge)

### Add Collaborators

```bash
# Import their GPG key
gpg --import colleague.pub

# Add to repository
gitcloakd add-user --email colleague@example.com --key-id THEIR_KEY_ID

# Re-encrypt to include new user
gitcloakd encrypt --dark
git add -A && git commit -m "Add collaborator" && git push
```

### Dark Mode Name Control

Control whether users see the real project name or only the UUID:

```bash
# User sees real name
gitcloakd dark add-user -e user@example.com -k KEY_ID --reveal-name

# User sees only UUID (maximum secrecy)
gitcloakd dark add-user -e user@example.com -k KEY_ID --hide-name
```

### Remove Access

```bash
gitcloakd remove-user colleague@example.com
gitcloakd encrypt --dark
git add -A && git commit -m "Revoke access" && git push
```

---

## [::: PYTHON API :::]

![API](https://img.shields.io/badge/API-PYTHON-3776AB?style=for-the-badge&logo=python)

```python
from gitcloakd import encrypt_files, decrypt_files, encrypt_matching

# Encrypt specific files
encrypt_files([".env", "config/secrets.yaml"])

# Encrypt all files matching patterns
encrypt_matching(["*.env", "*.key", "**/*.pem"])

# Decrypt
decrypt_files([".env.gpg"])
```

### Pre-Commit Hook

```python
#!/usr/bin/env python3
from gitcloakd import encrypt_staged
import subprocess, sys

result = encrypt_staged()
if result['encrypted']:
    for f in result['encrypted']:
        subprocess.run(["git", "add", f + ".gpg"])
if result['errors']:
    sys.exit(1)
```

---

## [::: COMMANDS REFERENCE :::]

![Commands](https://img.shields.io/badge/CLI-COMPREHENSIVE-00D9FF?style=for-the-badge)

| Command | Description |
|---------|-------------|
| `init` | Initialize encryption (`--wizard`, `--full`, `--dark`) |
| `encrypt` | Encrypt files (`--all`, `--full`, `--dark`) |
| `decrypt` | Decrypt files (`--all`, `--full`, `--dark`) |
| `status` | Show encryption status |
| `check` | Run security audit |
| `add-user` | Add collaborator |
| `remove-user` | Revoke access |
| `secure init` | Set up local protection |
| `lock` / `unlock` | Lock/unlock local storage |
| `test create` | Create demo repo |
| `test dry-run` | Preview changes |
| `test backup` | Backup before encryption |
| `clean paranoid` | Secure cleanup |

---

## [::: SECURITY MODEL :::]

![Security](https://img.shields.io/badge/SECURITY-COMPREHENSIVE-00D9FF?style=for-the-badge)

### What gitcloakd Protects

- Source code (Full/Dark modes)
- Sensitive files (all modes)
- Git history and commits (Dark mode)
- Project name (Dark mode)
- Local workstation data (with `secure init`)

### What gitcloakd Does NOT Protect

- Repository existence on GitHub (repo visible, contents encrypted)
- Network traffic (use HTTPS/SSH)
- Runtime secrets (use proper secret management)
- OS swap files or SSD wear leveling (use full-disk encryption)

### Threat Model

| Threat | Selective | Full | Dark |
|--------|-----------|------|------|
| Accidental secret commit | Yes | N/A | N/A |
| Unauthorized code access | No | Yes | Yes |
| Git history analysis | No | No | Yes |
| Project discovery | No | No | Yes |
| Server breach (GitHub) | Partial | Yes | Yes |
| Laptop theft | With secure init | With secure init | With secure init |

---

## [::: ALTERNATIVES :::]

![Comparison](https://img.shields.io/badge/VS-ALTERNATIVES-FF10F0?style=for-the-badge)

| Tool | Full Repo | Git History | Repo Name | Local Protection |
|------|-----------|-------------|-----------|------------------|
| **gitcloakd** | Yes | Hidden (Dark) | UUID (Dark) | Yes |
| git-crypt | No | Visible | Visible | No |
| git-secret | No | Visible | Visible | No |
| BlackBox | No | Visible | Visible | No |
| SOPS | No | Visible | Visible | No |

```
════════════════════════════════════════════════════════════════════════════════
  WHY GITCLOAKD:

  git-crypt, git-secret - they still leak:
  [*] Project name
  [*] File structure
  [*] Git history and commit messages
  [*] Contributors and timestamps

  gitcloakd Dark Mode? They see NOTHING. UUID-named repo. Single encrypted blob.
════════════════════════════════════════════════════════════════════════════════
```

---

## [::: DISCLAIMER :::]

```
════════════════════════════════════════════════════════════════════════════════

  USE AT YOUR OWN RISK.

  Lose your GPG key or passphrase? Your data is GONE.
  No recovery. No backdoor. No magic fix.

  Back up your keys or cry later.

════════════════════════════════════════════════════════════════════════════════
```

---

## [::: LICENSE :::]

MIT

---

## [::: CREDITS :::]

Developed by the [haKC.ai](https://github.com/haKC-ai) collective

Part of the SecKC (Kansas City Security) community

---

*stay encrypted*
