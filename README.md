


<p align="center">
  <img src="img/gitcloakd.gif" alt="gitcloakd demo" width="640">
</p>

## `gitCloakd` **Hide ya repos. Hide ya code. They out here hacking everybody.**

[![Python](https://img.shields.io/badge/python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](https://opensource.org/licenses/MIT)
[![GPG](https://img.shields.io/badge/encryption-GPG-red?style=flat-square&logo=gnuprivacyguard&logoColor=white)](https://gnupg.org/)
[![GitHub](https://img.shields.io/badge/github-integration-181717?style=flat-square&logo=github&logoColor=white)](https://github.com)
[![Security](https://img.shields.io/badge/security-maximum-brightgreen?style=flat-square)](https://github.com/haKC-ai/gitcloakd)

## Python API

Use gitcloakd programmatically in your code, CI/CD pipelines, or git hooks:
```python
from gitcloakd import encrypt_files, encrypt_matching, decrypt_files

# Encrypt specific files
result = encrypt_files([".env", "config/secrets.yaml"])
print(f"Encrypted: {result['encrypted']}")

# Encrypt all files matching configured patterns
result = encrypt_matching()

# Or with custom patterns
result = encrypt_matching(["*.env", "*.key", "**/*.pem"])

# Decrypt files
result = decrypt_files([".env.gpg", "config/secrets.yaml.gpg"])
```
```
# What you see (authorized):
my-secret-startup-project/
  src/api/payments.py
  src/core/algorithm.py
  README.md (real documentation)

# What everyone else sees:
550e8400-e29b-41d4-a716-446655440000/
  encrypted.gpg
  README.md ("This repository is encrypted")
```
### Three encryption modes. 
- **Selective** for hiding secrets.
- **Full** for hiding your entire codebase.
- **Dark** for hiding *everything* - code, git history, commit messages, even the project name (swapped with a random UUID).
- Unlike git-crypt or git-secret, Dark Mode leaves zero traces. Your laptop gets stolen? They see nothing - local storage is GPG encrypted too.



## Why Encrypt Your Repos?

| Threat | What happens | gitcloakd fix |
|--------|--------------|---------------|
| GitHub gets breached | Your code is leaked | They get encrypted blobs |
| Employee goes rogue | Copies private repos | Can't decrypt without your key |
| Laptop stolen | Attacker clones your repos | Local storage is GPG encrypted |
| Subpoena/legal request | GitHub hands over data | They hand over encrypted data |
| Nosy coworker/investor | Snoops your private repos | Sees nothing useful |
| You leave a company | They still have repo access | Revoke their key, re-encrypt |

**You control the keys. Not GitHub. Not your employer. You.**

## Use Cases

| You want to... | Mode |
|----------------|------|
| Keep `.env` and API keys encrypted | Selective |
| Open source project with private secrets | Selective |
| Private codebase only your team can read | Full |
| GitHub breach won't leak your code | Full |
| Stealth project - hide everything including repo name | Dark |
| Side project your employer can't trace back to you | Dark |
| Laptop stolen - attacker sees nothing | Dark + `secure init` |

---


## Encryption Modes Comparison

| Mode | What's Encrypted | Git History | Repo Name | Unauthorized View |
|------|------------------|-------------|-----------|-------------------|
| ![Selective](https://img.shields.io/badge/-Selective-blue?style=flat-square) | Sensitive files only | Visible | Visible | Code + encrypted secrets |
| ![Full](https://img.shields.io/badge/-Full-orange?style=flat-square) | Entire codebase | Visible | Visible | encrypted.gpg blob |
| ![Dark](https://img.shields.io/badge/-Dark-black?style=flat-square) | **EVERYTHING** | **Hidden** | **UUID Only** | encrypted.gpg + README only |

```mermaid
flowchart LR
    subgraph Selective["SELECTIVE"]
        S1("code visible")
        S2("secrets.gpg")
        S3("history visible")
    end

    subgraph Full["FULL"]
        F1("encrypted.gpg")
        F2("history visible")
    end

    subgraph Dark["DARK"]
        D1("encrypted.gpg")
        D2("UUID name")
        D3("no history")
    end

    style Selective fill:#34294f,stroke:#ff7edb,color:#ff7edb
    style Full fill:#2b213a,stroke:#fede5d,color:#fede5d
    style Dark fill:#1a1a2e,stroke:#72f1b8,color:#72f1b8
```
![gitcloakd](img/gitcloakd_logo.png)

## Try It First (Test Mode)

New here? Don't nuke your repo on day one. Test it first:

```bash
# spin up a demo repo with fake secrets
gitcloakd test create --mode dark

# preview what would happen (no changes made)
cd your-repo
gitcloakd test dry-run --mode full

# backup before you encrypt (do this)
gitcloakd test backup

# verify encryption works
gitcloakd test verify
```

## Quick Start

```bash
pip install gitcloakd

# pick your poison
gitcloakd init --wizard           # selective (default)
gitcloakd init --full             # full encryption
gitcloakd init --dark             # max paranoia (Dark Mode)

# protect your local box too
gitcloakd secure init
gitcloakd unlock                   # before working
gitcloakd lock                     # when done
```

---

## Encrypt an Existing Repo

Already got a repo with secrets you need to hide? Here's what you do:

```bash
cd your-existing-repo

# backup first (seriously, do this)
gitcloakd test backup

# preview what will happen (no changes)
gitcloakd test dry-run --mode selective

# if that looks good, init and encrypt
gitcloakd init --wizard
gitcloakd encrypt --all

# commit the encrypted versions
git add -A && git commit -m "encrypt secrets"

# optional: nuke the plaintext secrets from git history
gitcloakd purge-history --confirm
git push --force
```

For dark mode on an existing repo (hides everything):
```bash
gitcloakd test backup
gitcloakd init --dark
# this creates a new UUID-named repo with your encrypted code
```

---

## Mode 1: Selective Encryption (Default)

Open source projects with some secrets, normal collaboration.

Encrypts only sensitive files (`.env`, `.key`, `.pem`, etc.) while keeping source code readable.

```bash
gitcloakd init --wizard
gitcloakd encrypt --all
```

```mermaid
flowchart LR
    subgraph Before["Your Repo"]
        CODE1("main.py")
        SECRET1(".env<br/>API_KEY=secret")
    end

    subgraph After["After Encryption"]
        CODE2("main.py<br/>unchanged")
        SECRET2(".env.gpg<br/>encrypted")
    end

    CODE1 --> CODE2
    SECRET1 -->|GPG| SECRET2

    style SECRET1 fill:#fe4450,stroke:#fe4450,color:#1a1a2e
    style SECRET2 fill:#72f1b8,stroke:#72f1b8,color:#1a1a2e

    linkStyle 1 stroke:#fe4450
```

---

## Mode 2: Full Encryption

Private codebases where you want to hide all code but keep git history.

Packs the **entire codebase** into a single GPG blob. Randos see `encrypted.gpg` and nothing else.

```bash
gitcloakd init --full
gitcloakd encrypt --full
```

### What randos see

```
myrepo/
  .gitcloakd/          # config
  encrypted.gpg         # your entire codebase
  README.md             # "this repo is encrypted"
```

### What you get

> [Watch the decrypt demo](img/gitcloaded_logo.mp4)

After `gitcloakd decrypt --full`:
```
myrepo/
  src/
  tests/
  .env
  README.md
  ... (everything decrypted)
```

```mermaid
sequenceDiagram
    participant Owner
    participant gitcloakd
    participant Repo
    participant Unauthorized

    Owner->>gitcloakd: encrypt --full
    gitcloakd->>Repo: Pack all files into tarball
    gitcloakd->>Repo: GPG encrypt -> encrypted.gpg
    gitcloakd->>Repo: Remove original files

    Unauthorized->>Repo: git clone
    Note over Unauthorized: Only sees encrypted.gpg
    Unauthorized--xgitcloakd: decrypt --full
    Note over Unauthorized: ACCESS DENIED - no GPG key

    Owner->>Repo: git clone
    Owner->>gitcloakd: decrypt --full
    gitcloakd->>Repo: Decrypt + extract all files
    Note over Owner: Full codebase restored!
```

---

## Mode 3: Dark Mode (Max Paranoia)

When you need to hide **everything** - git history, commit messages, branch names, file structure, even the real project name. Repo gets a random UUID. Nobody learns anything.

```bash
gitcloakd init --dark
# prompts for real project name (encrypted, never exposed)
# generates random UUID for public repo name

gitcloakd encrypt --dark
```

### What's Hidden in Dark Mode

| Item | Selective | Full | Dark |
|------|-----------|------|------|
| Real project name | Visible | Visible | **Hidden (UUID only)** |
| Source code | Visible | Hidden | Hidden |
| File structure | Visible | Hidden | Hidden |
| Git commits | Visible | Visible | **Hidden** |
| Commit messages | Visible | Visible | **Hidden** |
| Branch names | Visible | Visible | **Hidden** |
| Contributors | Visible | Visible | **Hidden** |
| Repository stats | Visible | Visible | **Hidden** |

### What randos see

```
550e8400-e29b-41d4-a716-446655440000/   # random UUID, not real name
  .git/                 # single commit
  .gitcloakd/
  encrypted.gpg         # everything inside (including real name)
  README.md             # "this is encrypted"
```

Git log shows: `"gitcloakd: encrypted repository state"`

No history. No code. No clues. Not even the project name.

```mermaid
flowchart TB
    subgraph Real["Real Repository"]
        direction TB
        R_NAME("my-secret-project<br/>real name")
        R_CODE("Source Code")
        R_GIT(".git/<br/>100 commits, 5 branches")
        R_AUTHORS("Contributors List")
    end

    subgraph Visible["What randos see"]
        direction TB
        V_UUID("550e8400-...<br/>random UUID")
        V_BLOB("encrypted.gpg")
        V_README("README.md<br/>This is encrypted")
        V_GIT("Single commit")
    end

    Real -->|"GPG Encrypt"| Visible

    style Real fill:#72f1b8,stroke:#72f1b8,color:#1a1a2e
    style Visible fill:#1a1a2e,stroke:#ff7edb,color:#ff7edb

    linkStyle 0 stroke:#72f1b8
```

### Adding Users with Name Control

Control whether users see the real project name or just the UUID:

```bash
# User can see real project name
gitcloakd dark add-user -e user@example.com -k KEY_ID --reveal-name

# User can only see UUID (maximum secrecy)
gitcloakd dark add-user -e user@example.com -k KEY_ID --hide-name

# List users and their access
gitcloakd dark list-users
```

---

## Local Workstation Protection

Laptop stolen? They could see what repos you manage, your command history, cached secrets. Unless you encrypt all that too.

```bash
gitcloakd secure init    # init encrypted local storage

gitcloakd unlock          # before working
gitcloakd lock            # when done

gitcloakd secure status   # check status
```

### What's Protected

| Data | Without secure init | With secure init |
|------|---------------------|------------------|
| List of repos | Plaintext | GPG Encrypted |
| Command history | Plaintext | GPG Encrypted |
| Cached tokens | Plaintext | GPG Encrypted |
| Session data | Plaintext | GPG Encrypted |

```mermaid
flowchart TB
    subgraph Unlocked["Unlocked - Working"]
        direction LR
        U_CMDS("gitcloakd commands")
        U_DATA("Decrypted data<br/>in memory")
    end

    subgraph Locked["Locked - Protected"]
        direction LR
        L_GPG("~/.gitcloakd/<br/>config.gpg<br/>repos.gpg<br/>history.gpg")
    end

    subgraph Thief["Stolen Laptop"]
        direction LR
        T_ACCESS("No GPG key<br/>No passphrase")
        T_RESULT("Cannot read<br/>ANYTHING")
    end

    Unlocked -->|"gitcloakd lock"| Locked
    Locked -->|"Laptop stolen"| Thief

    style Unlocked fill:#72f1b8,stroke:#72f1b8,color:#1a1a2e
    style Locked fill:#fede5d,stroke:#fede5d,color:#1a1a2e
    style Thief fill:#fe4450,stroke:#fe4450,color:#1a1a2e

    linkStyle 0 stroke:#72f1b8
    linkStyle 1 stroke:#fede5d
```

### Key Management

1. Store GPG passphrase in a password manager (Proton Pass, 1Password, Bitwarden)
2. Back up your GPG key (encrypted USB, paper backup)
3. Use gpg-agent for passphrase caching
4. Rotate keys periodically

---

## Security Checklist

Run the built-in security audit:

```bash
gitcloakd check
```

This checks:
- GPG key strength and expiration
- Local storage encryption
- File permissions
- Configuration issues

---

## Complete Workflow Example

### Setting Up Maximum Security with Dark Mode

```bash
# 1. Create GPG key if needed
gpg --full-generate-key

# 2. Initialize local protection
gitcloakd secure init
gitcloakd unlock

# 3. Initialize repository with dark mode
cd myproject
gitcloakd init --dark
# Enter real project name when prompted (will be encrypted)
# Note the UUID generated - use this for GitHub repo name!

# 4. Work on your code normally
# ... edit files, commit, etc ...

# 5. Before pushing - encrypt everything
gitcloakd encrypt --dark
git add -A
git commit -m "Updated encrypted state"
git push

# 6. Collaborator pulls and decrypts
git clone https://github.com/you/550e8400-e29b-...  # UUID repo name
cd 550e8400-e29b-...
gitcloakd decrypt --dark
# Now they have full repo with history and real name!
```

### Adding Team Members to Dark Mode

```bash
# Collaborator generates key and sends public key
gpg --armor --export colleague@example.com > colleague.pub

# You import and add them (with name visibility control)
gpg --import colleague.pub

# Option A: They can see real project name
gitcloakd dark add-user -e colleague@example.com -k THEIR_KEY_ID --reveal-name

# Option B: They only see UUID (maximum secrecy)
gitcloakd dark add-user -e colleague@example.com -k THEIR_KEY_ID --hide-name

# Re-encrypt to include new user
gitcloakd encrypt --dark
git add -A && git commit -m "Added team member" && git push
```

---

## All Commands

| Command | Description | Flags |
|---------|-------------|-------|
| `init` | Initialize repository | `--wizard`, `--full`, `--dark` |
| `encrypt` | Encrypt files | `--all`, `--full`, `--dark` |
| `decrypt` | Decrypt files | `--all`, `--full`, `--dark` |
| `add-user` | Add collaborator | `--email`, `--key-id`, `--fetch` |
| `remove-user` | Revoke access | `<email>` |
| `clone` | Clone + auto-decrypt | `<url>` |
| `scan` | Scan for secrets | `--deep` |
| `analyze` | Analyze GitHub repos | |
| `status` | Show encryption status | `--json` |
| `check` | Security checklist | |
| `lock` | Lock local storage | |
| `unlock` | Unlock local storage | |
| `secure init` | Set up local protection | |
| `secure status` | Local storage status | |
| `secure wipe` | Destroy local data | `--confirm` |
| `dark info` | Show dark mode repo info | |
| `dark add-user` | Add user to dark mode | `--reveal-name`, `--hide-name` |
| `dark list-users` | List dark mode users | |
| `clean quick` | Quick cache clean | |
| `clean standard` | Standard clean | |
| `clean paranoid` | Aggressive clean | `--confirm` |
| `clean footprint` | Show data footprint | |
| `test create` | Create demo test repo | `--path`, `--mode` |
| `test dry-run` | Preview encryption (no changes) | `--mode` |
| `test backup` | Backup repo before encryption | `--output` |
| `test verify` | Verify encryption works | |
| `menu` | Interactive menu | |

---

## Python API

Use gitcloakd programmatically in your code, CI/CD pipelines, or git hooks:

### Basic Usage

```python
from gitcloakd import encrypt_files, encrypt_matching, decrypt_files

# Encrypt specific files
result = encrypt_files([".env", "config/secrets.yaml"])
print(f"Encrypted: {result['encrypted']}")

# Encrypt all files matching configured patterns
result = encrypt_matching()

# Or with custom patterns
result = encrypt_matching(["*.env", "*.key", "**/*.pem"])

# Decrypt files
result = decrypt_files([".env.gpg", "config/secrets.yaml.gpg"])
```

### Pre-Commit Hook

Create `.git/hooks/pre-commit`:

```python
#!/usr/bin/env python3
from gitcloakd import encrypt_staged
import subprocess
import sys

result = encrypt_staged()

if result['encrypted']:
    print(f"Auto-encrypted {len(result['encrypted'])} files:")
    for f in result['encrypted']:
        print(f"  {f}")
        # Add encrypted version to staging
        subprocess.run(["git", "add", f + ".gpg"])

if result['errors']:
    print(f"Encryption errors: {result['errors']}")
    sys.exit(1)
```

### Available Functions

| Function | Description |
|----------|-------------|
| `encrypt_files(files)` | Encrypt specific files |
| `encrypt_matching(patterns)` | Encrypt files matching glob patterns |
| `encrypt_staged()` | Encrypt staged files (for pre-commit hooks) |
| `decrypt_files(files)` | Decrypt .gpg files |
| `is_initialized()` | Check if gitcloakd is set up |
| `get_encryption_patterns()` | Get configured patterns |
| `check_gpg()` | Check if GPG is installed |

### CI/CD Integration

```python
from gitcloakd import encrypt_matching, is_initialized

if is_initialized():
    result = encrypt_matching()
    if result['errors']:
        raise Exception(f"Encryption failed: {result['errors']}")
    print(f"Encrypted {len(result['encrypted'])} files")
```

---

## Architecture

```mermaid
graph TB
    subgraph CLI["CLI Commands"]
        INIT(init)
        ENC(encrypt/decrypt)
        SEC(secure)
        CLEAN(clean)
        DARK(dark)
        CHECK(check)
    end

    subgraph Core["Encryption Engines"]
        SELECTIVE(Selective Engine)
        FULL(Full Encryption)
        DARKMODE(Dark Mode)
        STORAGE(Secure Storage)
        AUDIT(Audit Log)
        CLEANER(Memory Cleaner)
    end

    subgraph Data["Protected Data"]
        REPO[(Repository)]
        LOCAL[(~/.gitcloakd)]
    end

    INIT --> SELECTIVE
    INIT --> FULL
    INIT --> DARKMODE

    ENC --> SELECTIVE
    ENC --> FULL
    ENC --> DARKMODE

    DARK --> DARKMODE
    SEC --> STORAGE
    CLEAN --> CLEANER
    CHECK --> STORAGE
    CHECK --> REPO

    SELECTIVE --> REPO
    FULL --> REPO
    DARKMODE --> REPO
    STORAGE --> LOCAL
    AUDIT --> LOCAL
    CLEANER --> LOCAL

    style CLI fill:#34294f,stroke:#ff7edb,color:#ff7edb
    style Core fill:#2b213a,stroke:#f97e72,color:#f97e72
    style Data fill:#1a1a2e,stroke:#72f1b8,color:#72f1b8
```

---

## Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.9+ | Runtime |
| GPG | 2.x | Encryption |
| Git | 2.x | Version control |
| GitHub CLI | Optional | GitHub integration |
| gitleaks | Optional | Secret scanning |

---

## Security Considerations

### What gitcloakd DOES protect:
- Source code (full/dark modes)
- Sensitive files (all modes)
- Git history and commits (dark mode)
- Real project name (dark mode with UUID naming)
- Local workstation data (secure storage)

### What gitcloakd DOES NOT protect:
- Repository existence on GitHub (repo is still visible, just encrypted)
- Network traffic (use HTTPS/SSH)
- Runtime secrets (use proper secret management)
- Backup copies you make manually
- OS swap files (use full-disk encryption)
- SSD wear leveling (use full-disk encryption)

### Threat Model

| Threat | Selective | Full | Dark |
|--------|-----------|------|------|
| Accidental secret commit | Protected | N/A | N/A |
| Unauthorized code access | No | Yes | Yes |
| Git history analysis | No | No | Yes |
| Project name discovery | No | No | Yes |
| Laptop theft | With secure init | With secure init | With secure init |
| Server breach (GitHub) | Partial | Yes | Yes |

---

## Alternatives & Why gitcloakd

There are several tools for encrypting Git repositories. Here's how they compare:

| Tool | Selective | Full Repo | Git History | Repo Name | Local Protection | Setup |
|------|-----------|-----------|-------------|-----------|------------------|-------|
| **gitcloakd** | [x] | [x] | [x] Hidden | [x] UUID | [x] GPG encrypted | `pip install` |
| git-crypt | [x] | [ ] | [ ] Visible | [ ] Visible | [ ] | Compile from source |
| git-secret | [x] | [ ] | [ ] Visible | [ ] Visible | [ ] | Manual setup |
| BlackBox | [x] | [ ] | [ ] Visible | [ ] Visible | [ ] | Shell scripts |
| SOPS | [x] | [ ] | [ ] Visible | [ ] Visible | [ ] | YAML only |
| Transcrypt | [x] | [ ] | [ ] Visible | [ ] Visible | [ ] | OpenSSL |

### Why gitcloakd

**[*] Dark Mode**

git-crypt, git-secret - they still leak:
- Project name
- File structure
- Git history and commit messages
- Contributors
- Timestamps

gitcloakd Dark Mode? They see **nothing**. UUID-named repo. Single encrypted blob.

**[~] UUID Naming**

Random UUID for repo name:

```
# What you see (authorized):
my-secret-startup-project/
  src/api/payments.py
  src/core/algorithm.py
  README.md (real documentation)

# What everyone else sees:
550e8400-e29b-41d4-a716-446655440000/
  encrypted.gpg
  README.md ("This repository is encrypted")
```

Zero metadata leakage. GitHub insights show nothing. UUID could be anything.

**[#] Local Protection**

Only tool that encrypts your local data. Laptop stolen?
- git-crypt: Attackers see repos, history, tokens
- gitcloakd: They see nothing

**[+] Install**

```bash
pip install gitcloakd
# vs git-crypt (compile from source) or git-secret (manual setup)
```

**[>] Three Modes**

1. **Selective** - encrypt specific files
2. **Full** - encrypt entire codebase
3. **Dark** - hide everything including history and name

**[@] AI Agent Support**

Built-in support for Claude, Copilot, Gemini with configurable access.

**[!] Audit Logging**

Slack/Discord alerts. Encrypted audit logs for compliance.

---

## Disclaimer

**USE AT YOUR OWN RISK.** Lose your GPG key or passphrase? Your data is GONE. No recovery. No backdoor. No magic fix. Back up your keys or cry later.

See [LICENSE](LICENSE) for full disclaimer.

## License

MIT

## Credits

[HaKC.dev](https://hakc.dev)

---

*stay encrypted*
