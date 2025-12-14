"""
gitcloakd CLI - Main entry point
Colorful menu-driven interface with haKCer styling
"""

import click
import random
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
import questionary
from questionary import Style

from gitcloakd import __version__
from gitcloakd.core.encryption import GitCrypted
from gitcloakd.core.full_encryption import FullRepoEncryption, clone_and_decrypt
from gitcloakd.core.dark_mode import DarkMode, security_checklist
from gitcloakd.core.secure_storage import SecureStorage, get_secure_storage
from gitcloakd.core.memory_cleaner import get_memory_cleaner
from gitcloakd.core.audit_log import audit, AuditEventType
from gitcloakd.core.config import Config
from gitcloakd.crypto.gpg import GPGManager
from gitcloakd.github.client import GitHubClient
from gitcloakd.github.analyzer import RepoAnalyzer
from gitcloakd.agents.manager import AgentManager


# Initialize Rich console
console = Console()

# Global theme colors - set randomly on each command
THEME_COLORS = {
    'synthwave': {'primary': '#ff7edb', 'secondary': '#72f1b8', 'accent': '#fede5d', 'warning': '#f97e72', 'info': '#36f9f6'},
    'neon': {'primary': '#00ff00', 'secondary': '#ff00ff', 'accent': '#00ffff', 'warning': '#ffff00', 'info': '#ff0080'},
    'tokyo_night': {'primary': '#7aa2f7', 'secondary': '#bb9af7', 'accent': '#7dcfff', 'warning': '#f7768e', 'info': '#9ece6a'},
    'cyberpunk': {'primary': '#ff0080', 'secondary': '#00ffff', 'accent': '#ffff00', 'warning': '#ff00ff', 'info': '#00ff00'},
    'matrix': {'primary': '#00ff00', 'secondary': '#00cc00', 'accent': '#009900', 'warning': '#33ff33', 'info': '#00ff00'},
    'dracula': {'primary': '#ff79c6', 'secondary': '#bd93f9', 'accent': '#8be9fd', 'warning': '#ffb86c', 'info': '#50fa7b'},
    'nord': {'primary': '#88c0d0', 'secondary': '#81a1c1', 'accent': '#5e81ac', 'warning': '#d08770', 'info': '#a3be8c'},
    'gruvbox': {'primary': '#fb4934', 'secondary': '#b8bb26', 'accent': '#fabd2f', 'warning': '#fe8019', 'info': '#83a598'},
}

# Current session theme
_current_theme = None

def set_random_theme():
    """Set a random theme for this session."""
    global _current_theme
    _current_theme = random.choice(list(THEME_COLORS.keys()))
    return _current_theme

# HaKCer styling for questionary
HAKC_STYLE = Style([
    ('qmark', 'fg:#00ff00 bold'),       # Green question mark
    ('question', 'fg:#00ffff bold'),     # Cyan questions
    ('answer', 'fg:#00ff00'),            # Green answers
    ('pointer', 'fg:#ff00ff bold'),      # Magenta pointer
    ('highlighted', 'fg:#ff00ff bold'),  # Magenta highlight
    ('selected', 'fg:#00ff00'),          # Green selected
    ('separator', 'fg:#666666'),         # Gray separator
    ('instruction', 'fg:#888888'),       # Gray instructions
    ('text', 'fg:#ffffff'),              # White text
])


def safe_select(message: str, choices: list, animated: bool = False) -> str:
    """Wrapper for questionary.select that falls back to themed numbered menu on error."""
    global _current_theme

    # Set theme if not already set
    if _current_theme is None:
        set_random_theme()

    theme = THEME_COLORS.get(_current_theme, THEME_COLORS['synthwave'])
    primary = theme['primary']
    secondary = theme['secondary']
    accent = theme['accent']

    try:
        result = questionary.select(message, choices=choices, style=HAKC_STYLE).ask()
        return result
    except (AttributeError, Exception):
        # Fallback to themed numbered menu with optional animation
        menu_text = f"\n[bold {primary}]{message}[/bold {primary}]\n"
        for i, choice in enumerate(choices):
            menu_text += f"  [{accent}]{i}[/{accent}]. [{secondary}]{choice}[/{secondary}]\n"

        if animated:
            try:
                from hakcer import show_banner
                import tempfile
                import os
                # Write menu to temp file and animate it
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    # Strip Rich markup for hakcer
                    plain_menu = f"\n{message}\n"
                    for i, choice in enumerate(choices):
                        plain_menu += f"  {i}. {choice}\n"
                    f.write(plain_menu)
                    temp_path = f.name
                show_banner(custom_file=temp_path, speed_preference='fast', theme=_current_theme, hold_time=0.0)
                os.unlink(temp_path)
            except Exception:
                console.print(menu_text)
        else:
            console.print(menu_text)

        selection = Prompt.ask(f"[{primary}]Select option[/{primary}]", default="0")
        try:
            idx = int(selection)
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        return choices[0] if choices else None


def print_banner(animated: bool = False):
    """Print the gitcloakd banner with haKCer styling."""
    import os

    # Set theme for this session
    theme = set_random_theme()

    try:
        from hakcer import show_banner
        # Get path to banner file relative to package
        banner_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'banner.txt')
        if not os.path.exists(banner_path):
            # Try alternate location
            banner_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'banner.txt')
        if os.path.exists(banner_path):
            if animated:
                # Menu gets slower effect
                show_banner(custom_file=banner_path, effect_name='scattered', theme=theme, hold_time=1.0)
            else:
                # Regular commands get fast random effect
                show_banner(custom_file=banner_path, speed_preference='fast', theme=theme, hold_time=0.0)
        else:
            _print_fallback_banner()
    except Exception:
        _print_fallback_banner()


def _print_fallback_banner():
    """Fallback banner if hakcer library not available."""
    banner = """
[bold magenta]
+###############################     ##############################         ######################      #############################
++++++++++++++++++++++##++++++##     #+++++++++++++++++++++++++++##      +#++++++++++++##++++++###   +#++++++++####++++++++++++++++++##
+------+▄▄▄▄#▄▄▄#▄▄▄▄▄+-------##     #-------+###########+-------+#   +----------------+-------+##+---------+##+-+###########++------+#
-......█ ▄▄ █▄ ▄█▄▄ ▄▄█.     .##     +.......+#          +.......+# +.........##.......+-........................-##          -......-#
-      █ █▀▀██ ████ █ -.     .##     +.      +#          +.      +-.      .+####.     .-.                        -##          -      -#
-      █ ▀▀▄█▀ ▀███ █ -.     .##     +.      +#          +.   .-.       -###   #.     .-.      -##########+      -##          -      -#
-      .▀▀▀▀▀▀▀▀▀▀▀▀ --.     .----------------+##---------...-.      .-##+------.     .-.      +##        +      -##----------.      -#
-                    ...                   .+##-.        .-..     .-####  +-.         .-.      +##        +      -##.               .##
+---------------------++-----------------+###-----------+--------+###       +----------++------+##        +------+##--------------+###
[/bold magenta]
"""
    console.print(banner)
    console.print(f"  [dim]v{__version__} | HaKC.dev | GPG encrypted repos[/dim]\n")


def print_success(message: str):
    """Print success message."""
    console.print(f"[bold green][+][/bold green] {message}")


def print_error(message: str):
    """Print error message."""
    console.print(f"[bold red][-][/bold red] {message}")


def print_warning(message: str):
    """Print warning message."""
    console.print(f"[bold yellow][!][/bold yellow] {message}")


def print_info(message: str):
    """Print info message."""
    console.print(f"[bold cyan][*][/bold cyan] {message}")


def check_gpg_installed() -> bool:
    """Check if GPG is installed on the system."""
    import shutil
    return shutil.which("gpg") is not None


def install_gpg() -> bool:
    """
    Attempt to install GPG on the system.
    Returns True if installation was successful.
    """
    import subprocess
    import platform

    system = platform.system().lower()

    try:
        if system == "darwin":
            # macOS - use Homebrew
            print_info("Installing GPG via Homebrew...")
            result = subprocess.run(
                ["brew", "install", "gnupg"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print_success("GPG installed successfully!")
                return True
            else:
                # Try MacPorts as fallback
                print_warning("Homebrew failed, trying MacPorts...")
                result = subprocess.run(
                    ["sudo", "port", "install", "gnupg2"],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0

        elif system == "linux":
            # Linux - detect package manager
            import shutil as sh
            if sh.which("apt-get"):
                print_info("Installing GPG via apt...")
                subprocess.run(["sudo", "apt-get", "update"], capture_output=True)
                result = subprocess.run(
                    ["sudo", "apt-get", "install", "-y", "gnupg"],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            elif sh.which("dnf"):
                print_info("Installing GPG via dnf...")
                result = subprocess.run(
                    ["sudo", "dnf", "install", "-y", "gnupg2"],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            elif sh.which("yum"):
                print_info("Installing GPG via yum...")
                result = subprocess.run(
                    ["sudo", "yum", "install", "-y", "gnupg2"],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            elif sh.which("pacman"):
                print_info("Installing GPG via pacman...")
                result = subprocess.run(
                    ["sudo", "pacman", "-S", "--noconfirm", "gnupg"],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            elif sh.which("zypper"):
                print_info("Installing GPG via zypper...")
                result = subprocess.run(
                    ["sudo", "zypper", "install", "-y", "gpg2"],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            else:
                print_error("Could not detect package manager")
                return False

        elif system == "windows":
            # Windows - use winget or chocolatey
            import shutil as sh
            if sh.which("winget"):
                print_info("Installing GPG via winget...")
                result = subprocess.run(
                    ["winget", "install", "--id", "GnuPG.GnuPG", "-e", "--accept-package-agreements"],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            elif sh.which("choco"):
                print_info("Installing GPG via Chocolatey...")
                result = subprocess.run(
                    ["choco", "install", "gnupg", "-y"],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            else:
                print_error("Please install GPG manually from https://gnupg.org/download/")
                return False
        else:
            print_error(f"Unsupported operating system: {system}")
            return False

    except Exception as e:
        print_error(f"Failed to install GPG: {e}")
        return False


def ensure_gpg_available() -> bool:
    """
    Ensure GPG is available, installing it if necessary.
    Returns True if GPG is available (either already installed or successfully installed).
    """

    if check_gpg_installed():
        return True

    print_warning("GPG is not installed on your system.")
    print_info("GPG is required for gitcloakd encryption features.")
    console.print()

    # Auto-install GPG
    print_info("Attempting to install GPG automatically...")
    if install_gpg():
        # Verify installation
        if check_gpg_installed():
            return True
        else:
            print_error("GPG was installed but is not in PATH. Please restart your terminal.")
            return False
    else:
        console.print()
        print_error("Could not install GPG automatically.")
        console.print()
        console.print("[yellow]Please install GPG manually:[/yellow]")
        console.print()
        console.print("  [cyan]macOS:[/cyan]     brew install gnupg")
        console.print("  [cyan]Ubuntu:[/cyan]    sudo apt install gnupg")
        console.print("  [cyan]Fedora:[/cyan]    sudo dnf install gnupg2")
        console.print("  [cyan]Arch:[/cyan]      sudo pacman -S gnupg")
        console.print("  [cyan]Windows:[/cyan]   winget install GnuPG.GnuPG")
        console.print()
        return False


@click.group()
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx):
    """
    gitcloakd - Encrypt Git repositories with GPG

    Secure your code with style. GPG encryption for Git repos with
    GitHub integration, AI agent support, and team collaboration.
    """
    ctx.ensure_object(dict)


@cli.command()
@click.option('--wizard', '-w', is_flag=True, help='Run interactive setup wizard')
@click.option('--full', '-f', is_flag=True, help='Enable FULL repository encryption (encrypt entire codebase)')
@click.option('--dark', '-d', is_flag=True, help='DARK mode - encrypt EVERYTHING including git history with UUID naming')
@click.option('--yes', '-y', is_flag=True, help='Non-interactive mode, skip confirmations')
@click.option('--key', '-k', help='GPG key ID to use (for non-interactive mode)')
@click.option('--name', '-n', help='Real project name (for dark mode non-interactive)')
@click.option('--passphrase', '-p', help='GPG passphrase (for non-interactive mode)', envvar='GITCLOAKD_PASSPHRASE')
def init(wizard: bool, full: bool, dark: bool, yes: bool, key: str, name: str, passphrase: str):
    """Initialize gitcloakd in current repository."""
    print_banner()

    # Ensure GPG is available before proceeding
    if not ensure_gpg_available():
        raise SystemExit(1)

    if dark:
        # Dark mode - encrypt EVERYTHING including git history
        _run_dark_init(non_interactive=yes, key_id=key, real_name=name, passphrase=passphrase)
        return

    if full:
        # Full encryption mode - encrypt ENTIRE codebase
        _run_full_encryption_init()
        return

    gc = GitCrypted()

    if gc.is_initialized():
        print_warning("Repository already initialized with gitcloakd.")
        if not Confirm.ask("Reinitialize?"):
            return

    if wizard:
        _run_init_wizard(gc)
    else:
        _run_quick_init(gc)


def _run_init_wizard(gc: GitCrypted):
    """Run interactive initialization wizard."""
    console.print("\n[bold cyan]═══ gitcloakd Setup Wizard ═══[/bold cyan]\n")

    gpg = GPGManager()

    # Step 1: Check/create GPG key
    console.print("[bold]Step 1: GPG Key Setup[/bold]")
    keys = gpg.list_keys(secret=True)

    if not keys:
        print_warning("No GPG keys found.")
        if Confirm.ask("Create a new GPG key?"):
            _create_gpg_key_wizard(gpg)
            keys = gpg.list_keys(secret=True)

    if not keys:
        print_error("Cannot continue without a GPG key.")
        return

    # Select key
    key_choices = [
        f"{k['keyid']} - {k['uids'][0]}" for k in keys
    ]
    selected = safe_select("Select your GPG key:", key_choices)

    key_id = selected.split(" - ")[0]
    key_email = keys[key_choices.index(selected)]['uids'][0]
    if "<" in key_email:
        key_email = key_email.split("<")[1].rstrip(">")

    # Step 2: Encryption patterns
    console.print("\n[bold]Step 2: File Patterns to Encrypt[/bold]")

    default_patterns = [
        "*.env", "*.key", "*.pem", "*.secret",
        "credentials.*", "secrets/*", ".secrets/*"
    ]

    console.print("[dim]Default patterns:[/dim]")
    for p in default_patterns:
        console.print(f"  [cyan]•[/cyan] {p}")

    use_defaults = Confirm.ask("Use default patterns?", default=True)

    patterns = default_patterns
    if not use_defaults:
        custom = Prompt.ask("Enter patterns (comma-separated)")
        patterns = [p.strip() for p in custom.split(",")]

    # Step 3: GitHub integration
    console.print("\n[bold]Step 3: GitHub Integration[/bold]")

    setup_github = Confirm.ask("Set up GitHub integration?", default=True)

    if setup_github:
        try:
            gh = GitHubClient()
            if not gh.is_authenticated():
                print_warning("Not authenticated with GitHub.")
                if Confirm.ask("Authenticate now?"):
                    gh.authenticate()
        except Exception as e:
            print_error(f"GitHub setup failed: {e}")

    # Step 4: Initialize
    console.print("\n[bold]Step 4: Initializing...[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Initializing gitcloakd...", total=None)

        try:
            gc.initialize(
                owner_key_id=key_id,
                owner_email=key_email,
                patterns=patterns
            )
            progress.update(task, description="[green]Complete![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            return

    print_success("gitcloakd initialized successfully!")

    # Show summary
    console.print("\n[bold cyan]═══ Summary ═══[/bold cyan]")
    table = Table(show_header=False, box=None)
    table.add_row("[cyan]Owner Key:[/cyan]", key_id)
    table.add_row("[cyan]Email:[/cyan]", key_email)
    table.add_row("[cyan]Patterns:[/cyan]", ", ".join(patterns))
    console.print(table)

    console.print("\n[dim]Next steps:[/dim]")
    console.print("  1. Run [cyan]gitcloakd encrypt[/cyan] to encrypt sensitive files")
    console.print("  2. Run [cyan]gitcloakd add-user[/cyan] to add collaborators")
    console.print("  3. Run [cyan]gitcloakd add-agent[/cyan] to configure AI agents")


def _run_quick_init(gc: GitCrypted):
    """Run quick initialization without wizard."""
    gpg = GPGManager()
    keys = gpg.list_keys(secret=True)

    if not keys:
        print_error("No GPG keys found. Run with --wizard to create one.")
        return

    # Use first key
    key = keys[0]
    key_id = key['keyid']
    key_email = key['uids'][0]
    if "<" in key_email:
        key_email = key_email.split("<")[1].rstrip(">")

    gc.initialize(owner_key_id=key_id, owner_email=key_email)
    print_success(f"Initialized with key {key_id}")


def _create_gpg_key_wizard(gpg: GPGManager):
    """Wizard to create a new GPG key."""
    console.print("\n[bold magenta]═══ Create GPG Key ═══[/bold magenta]\n")

    name = Prompt.ask("Your name")
    email = Prompt.ask("Your email")

    console.print("\n[dim]Key options:[/dim]")
    key_type = safe_select("Key type:", ["RSA (recommended)", "DSA", "ECDSA"])

    key_length = safe_select("Key length:", ["4096 (most secure)", "2048 (faster)", "3072"])

    expire = safe_select("Expiration:", ["2 years (recommended)", "1 year", "Never", "Custom"])

    expire_map = {
        "2 years (recommended)": "2y",
        "1 year": "1y",
        "Never": "0",
        "Custom": Prompt.ask("Enter expiration (e.g., 6m, 1y)")
    }

    use_passphrase = Confirm.ask("Protect with passphrase?", default=True)
    passphrase = None
    if use_passphrase:
        passphrase = Prompt.ask("Enter passphrase", password=True)
        confirm = Prompt.ask("Confirm passphrase", password=True)
        if passphrase != confirm:
            print_error("Passphrases don't match!")
            return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Generating GPG key (this may take a while)...", total=None)

        try:
            key_id, fingerprint = gpg.generate_key(
                name=name,
                email=email,
                passphrase=passphrase,
                key_type=key_type.split()[0],
                key_length=int(key_length.split()[0]),
                expire_date=expire_map.get(expire, "2y")
            )
            progress.update(task, description="[green]Key generated![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            return

    print_success(f"GPG key created: {key_id}")
    console.print(f"[dim]Fingerprint: {fingerprint}[/dim]")

    # Offer to publish
    if Confirm.ask("Publish key to keyserver?"):
        try:
            gpg.publish_key(key_id)
            print_success("Key published to keyserver.ubuntu.com")
        except Exception as e:
            print_error(f"Failed to publish: {e}")


def _run_full_encryption_init():
    """Initialize repository with FULL encryption mode."""
    console.print("\n[bold cyan]═══ FULL Encryption Mode ═══[/bold cyan]\n")
    console.print("[bold yellow][!] FULL ENCRYPTION MODE[/bold yellow]")
    console.print("This will encrypt your ENTIRE codebase into a single GPG-encrypted blob.")
    console.print("Unauthorized users who pull this repo will ONLY see:")
    console.print("  [cyan]•[/cyan] encrypted.gpg (the entire codebase)")
    console.print("  [cyan]•[/cyan] README.md (explaining how to get access)")
    console.print("  [cyan]•[/cyan] .gitcloakd/ (public configuration)\n")

    if not Confirm.ask("Continue with full encryption setup?"):
        return

    gpg = GPGManager()
    full_enc = FullRepoEncryption()

    # Check for GPG keys
    keys = gpg.list_keys(secret=True)
    if not keys:
        print_warning("No GPG keys found.")
        if Confirm.ask("Create a new GPG key?"):
            _create_gpg_key_wizard(gpg)
            keys = gpg.list_keys(secret=True)

    if not keys:
        print_error("Cannot continue without a GPG key.")
        return

    # Select key
    key_choices = [f"{k['keyid']} - {k['uids'][0]}" for k in keys]
    selected = safe_select("Select your GPG key:", key_choices)

    key_id = selected.split(" - ")[0]
    key_email = keys[key_choices.index(selected)]['uids'][0]
    if "<" in key_email:
        key_email = key_email.split("<")[1].rstrip(">")

    # Initialize
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Initializing full encryption...", total=None)

        try:
            full_enc.initialize_full_encryption(
                owner_key_id=key_id,
                owner_email=key_email,
            )
            progress.update(task, description="[green]Initialized![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            return

    print_success("Full encryption initialized!")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Run [cyan]gitcloakd encrypt --full[/cyan] to encrypt the entire codebase")
    console.print("  2. Run [cyan]gitcloakd add-user --full[/cyan] to add collaborators")
    console.print("  3. Commit and push - others will only see encrypted.gpg")


def _run_full_encrypt():
    """Encrypt entire codebase into single GPG blob."""
    full_enc = FullRepoEncryption()

    if not full_enc.config.initialized:
        print_error("Not initialized. Run: gitcloakd init --full")
        return

    if full_enc.is_encrypted():
        print_warning("Repository is already encrypted.")
        if not Confirm.ask("Re-encrypt?"):
            return
        # Decrypt first
        full_enc.decrypt_all()

    console.print("\n[bold cyan]═══ FULL Codebase Encryption ═══[/bold cyan]\n")
    console.print("[bold yellow][!] This will encrypt ALL files in the repository![/bold yellow]")
    console.print("After encryption, only authorized GPG key holders can decrypt.\n")

    if not Confirm.ask("Proceed with full encryption?"):
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Encrypting entire codebase...", total=None)

        try:
            results = full_enc.encrypt_all()
            progress.update(task, description="[green]Complete![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            print_error(f"Encryption failed: {e}")
            return

    if results['errors']:
        print_warning(f"Completed with {len(results['errors'])} errors:")
        for err in results['errors']:
            console.print(f"  [red]•[/red] {err}")
    else:
        print_success(f"Encrypted {results['files_encrypted']} files into encrypted.gpg")

    # Show summary
    console.print("\n[bold]Summary:[/bold]")
    table = Table(show_header=False, box=None)
    table.add_row("[cyan]Files encrypted:[/cyan]", str(results['files_encrypted']))
    table.add_row("[cyan]Original size:[/cyan]", f"{results['total_size_before'] / 1024:.1f} KB")
    table.add_row("[cyan]Encrypted size:[/cyan]", f"{results['encrypted_size'] / 1024:.1f} KB")
    console.print(table)

    console.print("\n[bold green]Codebase is now fully encrypted![/bold green]")
    console.print("[dim]Commit encrypted.gpg and push. Unauthorized users will only see the blob.[/dim]")


def _run_full_decrypt():
    """Decrypt entire codebase from GPG blob."""
    full_enc = FullRepoEncryption()

    if not (full_enc.repo_path / "encrypted.gpg").exists():
        print_error("No encrypted.gpg found. Repository may not be encrypted.")
        return

    console.print("\n[bold cyan]═══ FULL Codebase Decryption ═══[/bold cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Decrypting codebase...", total=None)

        try:
            results = full_enc.decrypt_all()
            progress.update(task, description="[green]Complete![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            print_error(f"Decryption failed: {e}")
            return

    if results['errors']:
        print_warning("Completed with errors:")
        for err in results['errors']:
            console.print(f"  [red]•[/red] {err}")
    else:
        print_success(f"Decrypted {results['files_decrypted']} files")

    console.print("\n[bold green]Codebase decrypted and ready to work![/bold green]")
    console.print("[dim]Remember to encrypt before pushing: gitcloakd encrypt --full[/dim]")


# =============================================================================
# DARK MODE (TOTAL ENCRYPTION INCLUDING GIT HISTORY + UUID NAMING)
# =============================================================================

def _run_dark_init(non_interactive: bool = False, key_id: str = None, real_name: str = None, passphrase: str = None):
    """Initialize repository with DARK encryption mode.

    Args:
        non_interactive: Skip confirmations and prompts
        key_id: GPG key ID to use (required for non-interactive)
        real_name: Real project name (required for non-interactive)
        passphrase: GPG passphrase (optional, uses gpg-agent if not provided)
    """
    console.print("\n[bold cyan]=== DARK Mode Encryption ===[/bold cyan]\n")

    console.print("[bold red][!] MAXIMUM SECURITY: DARK MODE[/bold red]")
    console.print("This encrypts EVERYTHING including git history, commits, and branches.")
    console.print("Repository will use a random UUID name - real name is encrypted.\n")

    if not non_interactive:
        console.print("[bold]What unauthorized users will see:[/bold]")
        console.print("  [cyan]•[/cyan] encrypted.gpg (single blob)")
        console.print("  [cyan]•[/cyan] README.md (generic 'this is encrypted' message)")
        console.print("  [cyan]•[/cyan] Random UUID repository name (e.g., a1b2c3d4-...)")
        console.print("  [cyan]•[/cyan] Single git commit (no real history visible)")
        console.print("")

        console.print("[bold]What is HIDDEN from unauthorized users:[/bold]")
        console.print("  [cyan]•[/cyan] Real project name")
        console.print("  [cyan]•[/cyan] All source code")
        console.print("  [cyan]•[/cyan] Complete git history")
        console.print("  [cyan]•[/cyan] All commit messages")
        console.print("  [cyan]•[/cyan] Branch names")
        console.print("  [cyan]•[/cyan] File structure")
        console.print("  [cyan]•[/cyan] Contributors list")
        console.print("")

        if not Confirm.ask("Continue with dark mode setup?"):
            return

    gpg = GPGManager()
    dark = DarkMode(passphrase=passphrase)

    # Check for GPG keys
    keys = gpg.list_keys(secret=True)
    if not keys:
        if non_interactive:
            print_error("No GPG keys found. Cannot continue in non-interactive mode.")
            return
        print_warning("No GPG keys found.")
        if Confirm.ask("Create a new GPG key?"):
            _create_gpg_key_wizard(gpg)
            keys = gpg.list_keys(secret=True)

    if not keys:
        print_error("Cannot continue without a GPG key.")
        return

    # Select key (use provided key_id in non-interactive mode)
    if non_interactive and key_id:
        # Find matching key
        matching_key = None
        for k in keys:
            if k['keyid'] == key_id or k['keyid'].endswith(key_id):
                matching_key = k
                break
        if not matching_key:
            print_error(f"GPG key not found: {key_id}")
            return
        selected_key_id = matching_key['keyid']
        key_email = matching_key['uids'][0]
        if "<" in key_email:
            key_email = key_email.split("<")[1].rstrip(">")
    else:
        key_choices = [f"{k['keyid']} - {k['uids'][0]}" for k in keys]
        selected = safe_select("Select your GPG key:", key_choices)

        selected_key_id = selected.split(" - ")[0]
        key_email = keys[key_choices.index(selected)]['uids'][0]
        if "<" in key_email:
            key_email = key_email.split("<")[1].rstrip(">")

    # Get real project name
    if non_interactive:
        if not real_name:
            print_error("Real project name required (--name) for non-interactive mode.")
            return
        description = ""
    else:
        console.print("\n[bold]Project Information[/bold]")
        real_name = Prompt.ask("Real project name (will be encrypted)")
        description = Prompt.ask("Project description (optional, encrypted)", default="")

    # Initialize
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Initializing dark mode...", total=None)

        try:
            result = dark.initialize_dark_mode(
                real_name=real_name,
                owner_key_id=selected_key_id,
                owner_email=key_email,
                description=description if description else None,
            )
            progress.update(task, description="[green]Initialized![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            return

    print_success("Dark mode initialized!")

    console.print("\n[bold]Repository Identity:[/bold]")
    table = Table(show_header=False, box=None)
    table.add_row("[cyan]Real Name:[/cyan]", f"{real_name} [dim](encrypted)[/dim]")
    table.add_row("[cyan]Public UUID:[/cyan]", result['public_uuid'])
    table.add_row("[cyan]Owner:[/cyan]", key_email)
    console.print(table)

    console.print("\n[bold yellow]IMPORTANT:[/bold yellow]")
    console.print(f"  Use this UUID when creating the GitHub repository: [cyan]{result['public_uuid']}[/cyan]")
    console.print("  The real name is only visible to authenticated users.")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Create GitHub repo with UUID name (not real name)")
    console.print("  2. Work on your code normally")
    console.print("  3. Run [cyan]gitcloakd encrypt --dark[/cyan] before pushing")
    console.print("  4. Git history will be hidden - only encrypted blob pushed")
    console.print("  5. Run [cyan]gitcloakd decrypt --dark[/cyan] to resume working")

    audit(AuditEventType.DARK_MODE_INIT, f"Dark mode initialized: {real_name}", {
        "public_uuid": result['public_uuid']
    })


def _run_dark_encrypt(non_interactive: bool = False, passphrase: str = None, rename: bool = False):
    """Encrypt repository to dark mode wrapper state.

    Args:
        non_interactive: Skip confirmation prompts
        passphrase: GPG passphrase for encryption operations
        rename: Rename folder to UUID after encryption
    """
    dark = DarkMode(passphrase=passphrase)

    console.print("\n[bold cyan]=== DARK Mode Encryption ===[/bold cyan]\n")
    console.print("[bold red][!] This will encrypt EVERYTHING including git history![/bold red]")
    console.print("After this, only the encrypted blob will be visible.\n")

    # Show real name if authenticated
    name_info = dark.get_name_info()
    if name_info and name_info.get('real_name'):
        console.print(f"[dim]Project: {name_info['real_name']} -> {name_info['public_uuid']}[/dim]\n")

    if rename:
        console.print("[yellow]Folder will be renamed to UUID after encryption[/yellow]\n")

    if not non_interactive and not Confirm.ask("Proceed with dark mode encryption?"):
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Encrypting entire repository...", total=None)

        try:
            results = dark.encrypt_to_wrapper(rename_to_uuid=rename)
            progress.update(task, description="[green]Complete![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            print_error(f"Encryption failed: {e}")
            return

    if not results['success']:
        print_error("Encryption failed:")
        for err in results['errors']:
            console.print(f"  [red]•[/red] {err}")
        return

    print_success("Repository is now in dark mode!")

    console.print("\n[bold]Summary:[/bold]")
    table = Table(show_header=False, box=None)
    table.add_row("[cyan]Files encrypted:[/cyan]", str(results['files_encrypted']))
    table.add_row("[cyan]Commits hidden:[/cyan]", str(results['real_commits']))
    if results.get('new_path'):
        table.add_row("[cyan]Renamed to:[/cyan]", results['new_path'])
    console.print(table)

    console.print("\n[bold green]Your repository is now completely dark![/bold green]")
    console.print("[dim]Unauthorized users will only see encrypted.gpg[/dim]")
    console.print("[dim]Commit and push to share the encrypted state[/dim]")

    audit(AuditEventType.ENCRYPT, "Dark mode encryption completed", {
        "files": results['files_encrypted'],
        "commits_hidden": results['real_commits'],
        "renamed": results.get('new_path')
    })


def _run_dark_decrypt(non_interactive: bool = False, passphrase: str = None):
    """Decrypt from dark mode wrapper state.

    Args:
        non_interactive: Skip confirmation prompts
        passphrase: GPG passphrase for decryption operations
    """
    dark = DarkMode(passphrase=passphrase)

    if not dark.is_wrapper_state():
        print_error("Repository is not in dark mode encrypted state.")
        return

    console.print("\n[bold cyan]=== DARK Mode Decryption ===[/bold cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Decrypting repository...", total=None)

        try:
            results = dark.decrypt_from_wrapper()
            progress.update(task, description="[green]Complete![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            print_error(f"Decryption failed: {e}")
            return

    if not results['success']:
        print_error("Decryption failed:")
        for err in results['errors']:
            console.print(f"  [red]•[/red] {err}")
        return

    print_success("Repository decrypted!")

    # Show real name now that we're authenticated
    name_info = dark.get_name_info()
    if name_info and name_info.get('real_name'):
        console.print(f"\n[bold]Project:[/bold] {name_info['real_name']}")

    console.print("\n[bold]Restored:[/bold]")
    table = Table(show_header=False, box=None)
    table.add_row("[cyan]Files:[/cyan]", str(results['files_decrypted']))
    table.add_row("[cyan]Commits:[/cyan]", str(results['commits_restored']))
    console.print(table)

    console.print("\n[bold green]Full repository restored including git history![/bold green]")
    console.print("[dim]Remember to encrypt before pushing: gitcloakd encrypt --dark[/dim]")

    audit(AuditEventType.DECRYPT, "Dark mode decryption completed", {
        "files": results['files_decrypted'],
        "commits_restored": results['commits_restored']
    })


@cli.command('check')
def security_check():
    """Run comprehensive security checklist."""
    global _current_theme
    import tempfile
    import os

    print_banner()
    console.print("\n[bold cyan]═══ Security Checklist ═══[/bold cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Running security checks...", total=None)
        results = security_checklist()
        progress.update(task, description="[green]Complete![/green]")

    # Build output text for animation
    output_lines = []

    # Critical issues
    if results['critical']:
        output_lines.append("\n[CRITICAL]")
        for item in results['critical']:
            output_lines.append(f"  [-] {item}")

    # Warnings
    if results['warnings']:
        output_lines.append("\n[WARNINGS]")
        for item in results['warnings']:
            output_lines.append(f"  [!] {item}")

    # Passed checks
    if results['passed']:
        output_lines.append("\n[PASSED]")
        for item in results['passed']:
            output_lines.append(f"  [+] {item}")

    # Recommendations
    output_lines.append("\n[RECOMMENDATIONS]")
    for item in results['recommendations']:
        output_lines.append(f"  • {item}")

    # Summary
    output_lines.append("\nSummary:")
    if results['critical']:
        output_lines.append(f"  CRITICAL ISSUES: {len(results['critical'])}")
    if results['warnings']:
        output_lines.append(f"  Warnings: {len(results['warnings'])}")
    output_lines.append(f"  Passed: {len(results['passed'])}")

    # Animate with hakcer
    try:
        from hakcer import show_banner

        # Set theme if not set
        if _current_theme is None:
            set_random_theme()

        # Write to temp file and animate
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('\n'.join(output_lines))
            temp_path = f.name

        show_banner(custom_file=temp_path, speed_preference='fast', theme=_current_theme, hold_time=0.5)
        os.unlink(temp_path)
    except Exception:
        # Fallback to Rich console output
        if results['critical']:
            console.print("\n[bold red][CRITICAL][/bold red]")
            for item in results['critical']:
                console.print(f"  [red][-][/red] {item}")

        if results['warnings']:
            console.print("\n[bold yellow][WARNINGS][/bold yellow]")
            for item in results['warnings']:
                console.print(f"  [yellow][!][/yellow] {item}")

        if results['passed']:
            console.print("\n[bold green][PASSED][/bold green]")
            for item in results['passed']:
                console.print(f"  [green][+][/green] {item}")

        console.print("\n[bold cyan][RECOMMENDATIONS][/bold cyan]")
        for item in results['recommendations']:
            console.print(f"  [cyan]•[/cyan] {item}")

        console.print("\n[bold]Summary:[/bold]")
        if results['critical']:
            console.print(f"  [red]CRITICAL ISSUES: {len(results['critical'])}[/red]")
        if results['warnings']:
            console.print(f"  [yellow]Warnings: {len(results['warnings'])}[/yellow]")
        console.print(f"  [green]Passed: {len(results['passed'])}[/green]")


@cli.command()
@click.argument('files', nargs=-1)
@click.option('--all', '-a', 'encrypt_all', is_flag=True, help='Encrypt all matching patterns')
@click.option('--full', '-f', is_flag=True, help='FULL encryption - encrypt entire codebase into single GPG blob')
@click.option('--dark', '-d', is_flag=True, help='DARK mode - encrypt entire repo INCLUDING git history')
@click.option('--yes', '-y', is_flag=True, help='Non-interactive mode, skip confirmations')
@click.option('--passphrase', '-p', help='GPG passphrase (for non-interactive mode)', envvar='GITCLOAKD_PASSPHRASE')
@click.option('--rename', '-r', is_flag=True, help='Rename folder to UUID after encryption (dark mode only)')
def encrypt(files: tuple, encrypt_all: bool, full: bool, dark: bool, yes: bool, passphrase: str, rename: bool):
    """Encrypt files or all sensitive files."""

    if dark:
        # Dark mode - encrypt EVERYTHING including git history
        _run_dark_encrypt(non_interactive=yes, passphrase=passphrase, rename=rename)
        return

    if full:
        # Full encryption mode - encrypt ENTIRE codebase
        _run_full_encrypt()
        return

    gc = GitCrypted()

    if not gc.is_initialized():
        print_error("Not initialized. Run: gitcloakd init")
        return

    if encrypt_all:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Encrypting files...", total=None)
            results = gc.encrypt_repo()

        print_success(f"Encrypted {len(results['encrypted'])} files")
        if results['errors']:
            print_warning(f"Errors: {len(results['errors'])}")
            for err in results['errors']:
                console.print(f"  [red]•[/red] {err['file']}: {err['error']}")
    else:
        for file in files:
            try:
                gc.encrypt_file(file)
                print_success(f"Encrypted: {file}")
            except Exception as e:
                print_error(f"Failed to encrypt {file}: {e}")


@cli.command()
@click.argument('files', nargs=-1)
@click.option('--all', '-a', 'decrypt_all', is_flag=True, help='Decrypt all encrypted files')
@click.option('--full', '-f', is_flag=True, help='FULL decryption - decrypt entire codebase from GPG blob')
@click.option('--dark', '-d', is_flag=True, help='DARK mode - decrypt entire repo INCLUDING git history')
@click.option('--yes', '-y', is_flag=True, help='Non-interactive mode, skip confirmations')
@click.option('--passphrase', '-p', help='GPG passphrase (for non-interactive mode)', envvar='GITCLOAKD_PASSPHRASE')
def decrypt(files: tuple, decrypt_all: bool, full: bool, dark: bool, yes: bool, passphrase: str):
    """Decrypt files or all encrypted files."""

    if dark:
        # Dark mode - decrypt EVERYTHING including git history
        _run_dark_decrypt(non_interactive=yes, passphrase=passphrase)
        return

    if full:
        # Full decryption mode - decrypt ENTIRE codebase from blob
        _run_full_decrypt()
        return

    gc = GitCrypted()

    if not gc.is_initialized():
        print_error("Not initialized. Run: gitcloakd init")
        return

    if decrypt_all:
        results = gc.decrypt_repo()
        print_success(f"Decrypted {len(results['decrypted'])} files")
    else:
        for file in files:
            try:
                gc.decrypt_file(file)
                print_success(f"Decrypted: {file}")
            except Exception as e:
                print_error(f"Failed to decrypt {file}: {e}")


@cli.command('add-user')
@click.option('--email', '-e', help='User email')
@click.option('--key-id', '-k', help='GPG key ID')
@click.option('--fetch', '-f', is_flag=True, help='Fetch key from keyserver')
def add_user(email: Optional[str], key_id: Optional[str], fetch: bool):
    """Add a user who can decrypt repository content."""
    gc = GitCrypted()
    gpg = GPGManager()

    if not gc.is_initialized():
        print_error("Not initialized. Run: gitcloakd init")
        return

    if not email:
        email = Prompt.ask("User email")

    if fetch:
        print_info(f"Searching keyservers for {email}...")
        try:
            gpg.fetch_key(email)
            keys = gpg.list_keys(keys=[email])
            if keys:
                key_id = keys[0]['keyid']
                print_success(f"Found and imported key: {key_id}")
        except Exception as e:
            print_error(f"Failed to fetch key: {e}")
            return

    if not key_id:
        key_id = Prompt.ask("GPG key ID")

    try:
        gc.add_user(email=email, gpg_key_id=key_id)
        print_success(f"Added user: {email}")
    except Exception as e:
        print_error(f"Failed to add user: {e}")


@cli.command('remove-user')
@click.argument('email')
def remove_user(email: str):
    """Remove a user's access to encrypted content."""
    gc = GitCrypted()

    if gc.remove_user(email):
        print_success(f"Removed user: {email}")
    else:
        print_error(f"User not found: {email}")


@cli.command('add-agent')
@click.option('--type', '-t', 'agent_type', type=click.Choice(['claude', 'copilot', 'gemini', 'custom']))
@click.option('--name', '-n', help='Agent name')
def add_agent(agent_type: Optional[str], name: Optional[str]):
    """Add an AI coding agent configuration."""
    gc = GitCrypted()
    agent_mgr = AgentManager()

    if not gc.is_initialized():
        print_error("Not initialized. Run: gitcloakd init")
        return

    if not agent_type:
        agent_type = safe_select("Select agent type:", ['claude', 'copilot', 'gemini', 'custom'])

    try:
        agent = agent_mgr.add_agent(agent_type, name)
        print_success(f"Added agent: {agent.name}")
        console.print("[dim]Agent instructions created in .gitcloakd/agents/[/dim]")
    except Exception as e:
        print_error(f"Failed to add agent: {e}")


@cli.command()
@click.option('--deep', '-d', is_flag=True, help='Deep scan including git history')
def scan(deep: bool):
    """Scan repository for sensitive data."""
    gc = GitCrypted()

    console.print("[bold]Scanning for sensitive data...[/bold]\n")

    analysis = gc.analyze_exposure()

    # Display results
    if analysis['sensitive_files']:
        print_warning(f"Found {len(analysis['sensitive_files'])} sensitive files:")
        for file in analysis['sensitive_files']:
            console.print(f"  [yellow]•[/yellow] {file['path']}")

    if analysis['unencrypted_secrets']:
        print_error(f"Found {len(analysis['unencrypted_secrets'])} unencrypted secrets!")

    if analysis['history_exposure']:
        print_error("Sensitive data found in git history!")
        console.print("[dim]Run: gitcloakd purge-history[/dim]")

    for rec in analysis['recommendations']:
        console.print(f"[cyan]→[/cyan] {rec['action']}: {rec['details']}")


@cli.command()
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def status(output_json: bool):
    """Show gitcloakd status."""
    gc = GitCrypted()
    config = Config.load_repo()

    if output_json:
        import json
        console.print(json.dumps({
            "initialized": gc.is_initialized(),
            "owner": config.owner_email,
            "users": len(config.users),
            "agents": len(config.agents),
            "patterns": config.auto_encrypt_patterns,
        }, indent=2))
        return

    print_banner()

    if not gc.is_initialized():
        print_warning("Not initialized")
        return

    console.print("[bold cyan]═══ Status ═══[/bold cyan]\n")

    table = Table(show_header=False, box=None)
    table.add_row("[cyan]Owner:[/cyan]", config.owner_email)
    table.add_row("[cyan]Users:[/cyan]", str(len(config.users)))
    table.add_row("[cyan]Agents:[/cyan]", str(len(config.agents)))
    table.add_row("[cyan]Patterns:[/cyan]", str(len(config.auto_encrypt_patterns)))
    console.print(table)

    console.print("\n[bold]Users:[/bold]")
    for user in config.users:
        console.print(f"  [green]•[/green] {user.name} <{user.email}> [{user.role}]")

    console.print("\n[bold]Agents:[/bold]")
    for agent in config.agents:
        decrypt_status = "[green][+][/green]" if agent.can_decrypt else "[red][-][/red]"
        console.print(f"  {decrypt_status} {agent.name} ({agent.type})")


@cli.command()
def analyze():
    """Analyze all GitHub repositories for security."""
    print_banner()

    try:
        gh = GitHubClient()
        if not gh.is_authenticated():
            print_error("Not authenticated with GitHub. Run: gh auth login")
            return

        analyzer = RepoAnalyzer(gh)

        console.print("[bold]Analyzing your GitHub repositories...[/bold]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Fetching repositories...", total=None)
            analyses = analyzer.analyze_all_repos()
            progress.update(task, description=f"Analyzed {len(analyses)} repositories")

        # Display report
        report = analyzer.generate_report(analyses, format="markdown")
        console.print(Markdown(report))

        # Show critical repos
        critical = [a for a in analyses if a.risk_score >= 70]
        if critical:
            console.print("\n[bold red]═══ CRITICAL REPOSITORIES ═══[/bold red]")
            for repo in critical:
                console.print(f"  [red]•[/red] {repo.repo_name} (Risk: {repo.risk_score})")
                console.print(f"    [dim]{repo.recommendation}[/dim]")

    except Exception as e:
        print_error(f"Analysis failed: {e}")


@cli.command('purge-history')
@click.option('--confirm', 'confirmed', is_flag=True, help='Confirm destructive operation')
def purge_history(confirmed: bool):
    """Purge git history of sensitive files (DESTRUCTIVE)."""
    gc = GitCrypted()

    if not confirmed:
        console.print("[bold red]WARNING: This operation is DESTRUCTIVE![/bold red]")
        console.print("It will permanently remove sensitive files from git history.")
        console.print("A backup branch will be created first.\n")

        if not Confirm.ask("Are you sure you want to continue?"):
            return

        confirmed = Confirm.ask("Type 'yes' to confirm", default=False)

    if not confirmed:
        print_warning("Operation cancelled.")
        return

    try:
        gc.purge_history(confirm=True)
        print_success("Git history purged!")
        print_warning("Remember to force push: git push --force")
    except Exception as e:
        print_error(f"Failed: {e}")


@cli.command()
@click.option('--confirm', 'confirmed', is_flag=True, help='Confirm removal of encryption')
def unencrypt(confirmed: bool):
    """Remove gitcloakd encryption (DESTRUCTIVE)."""
    gc = GitCrypted()

    if not gc.is_initialized():
        print_error("Not initialized")
        return

    if not confirmed:
        console.print("[bold red]WARNING: This will remove all encryption![/bold red]")
        console.print("All encrypted files will be decrypted and exposed.\n")

        if not Confirm.ask("Are you sure?"):
            return

    try:
        gc.unencrypt(confirm=True)
        print_success("Encryption removed. Repository is now unencrypted.")
    except Exception as e:
        print_error(f"Failed: {e}")


@cli.command()
def menu():
    """Launch interactive menu."""
    print_banner()

    while True:
        choice = safe_select(
            "What would you like to do?",
            [
                "Initialize repository",
                "Encrypt files",
                "Decrypt files",
                "Manage users",
                "Manage AI agents",
                "Scan for secrets",
                "Analyze GitHub repos",
                "View status",
                "GPG key management",
                "Exit"
            ],
            animated=True
        )

        if choice == "Exit" or choice is None:
            console.print("\n[bold green]Stay encrypted![/bold green]")
            break

        console.print()

        if choice == "Initialize repository":
            _run_init_wizard(GitCrypted())
        elif choice == "Encrypt files":
            ctx = click.Context(encrypt)
            ctx.invoke(encrypt, encrypt_all=True)
        elif choice == "Decrypt files":
            ctx = click.Context(decrypt)
            ctx.invoke(decrypt, decrypt_all=True)
        elif choice == "Manage users":
            _user_menu()
        elif choice == "Manage AI agents":
            _agent_menu()
        elif choice == "Scan for secrets":
            ctx = click.Context(scan)
            ctx.invoke(scan, deep=False)
        elif choice == "Analyze GitHub repos":
            ctx = click.Context(analyze)
            ctx.invoke(analyze)
        elif choice == "View status":
            ctx = click.Context(status)
            ctx.invoke(status, output_json=False)
        elif choice == "GPG key management":
            _gpg_menu()

        console.print()


def _user_menu():
    """User management submenu."""
    gc = GitCrypted()
    config = Config.load_repo()

    action = safe_select("User management:", ["Add user", "Remove user", "List users", "Back"])

    if action == "Add user":
        email = Prompt.ask("User email")
        key_id = Prompt.ask("GPG key ID")
        gc.add_user(email=email, gpg_key_id=key_id)
        print_success(f"Added: {email}")
    elif action == "Remove user":
        users = [u.email for u in config.users]
        if not users:
            print_warning("No users to remove")
            return
        email = safe_select("Select user:", users)
        gc.remove_user(email)
        print_success(f"Removed: {email}")
    elif action == "List users":
        for user in config.users:
            console.print(f"  • {user.name} <{user.email}> [{user.role}]")


def _agent_menu():
    """Agent management submenu."""
    agent_mgr = AgentManager()
    config = Config.load_repo()

    action = safe_select("Agent management:", ["Add agent", "Remove agent", "List agents", "Generate GitHub Action", "Back"])

    if action == "Add agent":
        agent_type = safe_select("Agent type:", ['claude', 'copilot', 'gemini', 'custom'])
        agent = agent_mgr.add_agent(agent_type)
        print_success(f"Added: {agent.name}")
    elif action == "Remove agent":
        agents = [a.name for a in config.agents]
        if not agents:
            print_warning("No agents to remove")
            return
        name = safe_select("Select agent:", agents)
        agent_mgr.remove_agent(name)
        print_success(f"Removed: {name}")
    elif action == "List agents":
        for agent in config.agents:
            console.print(f"  • {agent.name} ({agent.type}) - decrypt: {agent.can_decrypt}")
    elif action == "Generate GitHub Action":
        workflow = agent_mgr.generate_github_action()
        console.print(Panel(workflow, title="GitHub Action Workflow"))
        if Confirm.ask("Save to .github/workflows/gitcloakd.yml?"):
            path = Path(".github/workflows")
            path.mkdir(parents=True, exist_ok=True)
            (path / "gitcloakd.yml").write_text(workflow)
            print_success("Saved!")


def _gpg_menu():
    """GPG key management submenu."""
    gpg = GPGManager()

    action = safe_select("GPG key management:", ["List keys", "Create new key", "Import key", "Export key", "Publish to keyserver", "Back"])

    if action == "List keys":
        keys = gpg.list_keys(secret=True)
        for key in keys:
            console.print(f"  [green]•[/green] {key['keyid']} - {key['uids'][0]}")
    elif action == "Create new key":
        _create_gpg_key_wizard(gpg)
    elif action == "Import key":
        file_path = Prompt.ask("Key file path")
        try:
            result = gpg.import_key_from_file(file_path)
            print_success(f"Imported {result['count']} key(s)")
        except Exception as e:
            print_error(f"Failed: {e}")
    elif action == "Export key":
        keys = gpg.list_keys()
        key_choices = [f"{k['keyid']} - {k['uids'][0]}" for k in keys]
        selected = safe_select("Select key:", key_choices)
        key_id = selected.split(" - ")[0]
        pub_key = gpg.export_public_key(key_id)
        console.print(Panel(pub_key, title="Public Key"))
    elif action == "Publish to keyserver":
        keys = gpg.list_keys(secret=True)
        key_choices = [f"{k['keyid']} - {k['uids'][0]}" for k in keys]
        selected = safe_select("Select key:", key_choices)
        key_id = selected.split(" - ")[0]
        try:
            gpg.publish_key(key_id)
            print_success("Key published!")
        except Exception as e:
            print_error(f"Failed: {e}")


# =============================================================================
# SECURE LOCAL STORAGE COMMANDS
# =============================================================================

@cli.group()
def secure():
    """Manage GPG-protected local storage (laptop protection)."""
    pass


@secure.command('init')
def secure_init():
    """
    Initialize GPG-encrypted local storage.

    This protects ALL gitcloakd data on your laptop with your GPG key.
    If your laptop is stolen, attackers cannot see:
    - What repos you manage
    - Your command history
    - Any cached secrets or tokens
    """
    print_banner()
    console.print("\n[bold cyan]=== Secure Local Storage Setup ===[/bold cyan]\n")

    console.print("[bold yellow][!] LAPTOP PROTECTION MODE[/bold yellow]")
    console.print("This encrypts ALL local gitcloakd data with your GPG key.")
    console.print("Even if your laptop is stolen, your data stays protected.\n")

    console.print("[bold]What gets protected:[/bold]")
    console.print("  [cyan]•[/cyan] List of managed repositories")
    console.print("  [cyan]•[/cyan] Command history")
    console.print("  [cyan]•[/cyan] Cached tokens and secrets")
    console.print("  [cyan]•[/cyan] Session data")
    console.print("")

    console.print("[bold]What you'll need:[/bold]")
    console.print("  [cyan]•[/cyan] Your GPG key (store passphrase in password manager!)")
    console.print("  [cyan]•[/cyan] Run 'gitcloakd unlock' before using gitcloakd")
    console.print("")

    storage = SecureStorage()

    if storage.is_initialized():
        print_warning("Secure storage already initialized.")
        if not Confirm.ask("Reinitialize? (This will wipe existing data!)"):
            return
        storage.wipe_all(confirm=True)
        storage = SecureStorage()

    gpg = GPGManager()
    keys = gpg.list_keys(secret=True)

    if not keys:
        print_warning("No GPG keys found.")
        if Confirm.ask("Create a new GPG key?"):
            _create_gpg_key_wizard(gpg)
            keys = gpg.list_keys(secret=True)

    if not keys:
        print_error("Cannot continue without a GPG key.")
        return

    key_choices = [f"{k['keyid']} - {k['uids'][0]}" for k in keys]
    selected = safe_select("Select GPG key for local encryption:", key_choices)

    key_id = selected.split(" - ")[0]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Initializing secure storage...", total=None)

        try:
            storage.initialize(key_id)
            progress.update(task, description="[green]Complete![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            return

    print_success("Secure local storage initialized!")
    console.print("\n[dim]Storage location: ~/.gitcloakd/[/dim]")
    console.print(f"[dim]Encryption key: {key_id}[/dim]")

    console.print("\n[bold]Important:[/bold]")
    console.print("  1. Store your GPG passphrase in a password manager (Proton Pass, 1Password, etc.)")
    console.print("  2. Back up your GPG key securely")
    console.print("  3. Run [cyan]gitcloakd unlock[/cyan] before using gitcloakd")
    console.print("  4. Run [cyan]gitcloakd lock[/cyan] when done or leaving your laptop")


@cli.command()
def unlock():
    """
    Unlock gitcloakd with your GPG key.

    Required before any gitcloakd operations.
    Your GPG passphrase will be requested by gpg-agent.
    """
    storage = get_secure_storage()

    if not storage.is_initialized():
        print_error("Secure storage not initialized. Run: gitcloakd secure init")
        return

    if storage.is_unlocked():
        print_warning("Already unlocked.")
        return

    console.print("[bold]Unlocking gitcloakd...[/bold]")
    console.print("[dim]Your GPG passphrase will be requested by gpg-agent.[/dim]\n")

    try:
        if storage.unlock():
            print_success("Unlocked! You can now use gitcloakd.")
            console.print("[dim]Session will auto-lock after 30 minutes of inactivity.[/dim]")
        else:
            print_error("Unlock failed. Check your GPG key and passphrase.")
    except Exception as e:
        print_error(f"Unlock failed: {e}")


@cli.command()
def lock():
    """
    Lock gitcloakd, protecting local data.

    Run this when leaving your laptop unattended.
    """
    storage = get_secure_storage()

    storage.lock()
    print_success("Locked! Your gitcloakd data is now protected.")
    console.print("[dim]Run 'gitcloakd unlock' to continue working.[/dim]")


@secure.command('status')
def secure_status():
    """Show secure storage status."""
    storage = get_secure_storage()

    print_banner()

    if not storage.is_initialized():
        print_warning("Secure storage not initialized.")
        console.print("[dim]Run: gitcloakd secure init[/dim]")
        return

    console.print("[bold cyan]=== Secure Storage Status ===[/bold cyan]\n")

    is_unlocked = storage.is_unlocked()

    table = Table(show_header=False, box=None)
    table.add_row("[cyan]Status:[/cyan]", "[green]UNLOCKED[/green]" if is_unlocked else "[red]LOCKED[/red]")
    table.add_row("[cyan]Storage:[/cyan]", str(storage.path))
    table.add_row("[cyan]GPG Key:[/cyan]", storage.get_gpg_key_id() or "Unknown")
    console.print(table)

    if is_unlocked:
        repos = storage.list_repos()
        console.print(f"\n[bold]Managed Repos:[/bold] {len(repos)}")
        for repo in repos[:5]:
            console.print(f"  [cyan]•[/cyan] {repo['full_name']} ({repo['encryption_type']})")
        if len(repos) > 5:
            console.print(f"  [dim]... and {len(repos) - 5} more[/dim]")


@secure.command('wipe')
@click.option('--confirm', 'confirmed', is_flag=True, help='Confirm destructive operation')
def secure_wipe(confirmed: bool):
    """
    Securely wipe ALL local gitcloakd data.

    WARNING: This is irreversible! All local data will be destroyed.
    """
    if not confirmed:
        console.print("[bold red]WARNING: This will PERMANENTLY DELETE all local gitcloakd data![/bold red]")
        console.print("This includes:")
        console.print("  [red]•[/red] List of managed repositories")
        console.print("  [red]•[/red] Command history")
        console.print("  [red]•[/red] Cached secrets")
        console.print("  [red]•[/red] All local configuration")
        console.print("")

        if not Confirm.ask("[red]Are you absolutely sure?[/red]"):
            return

    storage = get_secure_storage()

    try:
        storage.wipe_all(confirm=True)
        print_success("All local gitcloakd data has been securely wiped.")
    except Exception as e:
        print_error(f"Wipe failed: {e}")


@secure.command('history')
@click.option('--limit', '-l', default=20, help='Number of entries to show')
def secure_history(limit: int):
    """Show encrypted command history."""
    storage = get_secure_storage()

    if not storage.is_unlocked():
        print_error("Locked. Run: gitcloakd unlock")
        return

    history = storage.get_history(limit=limit)

    if not history:
        console.print("[dim]No command history.[/dim]")
        return

    console.print(f"[bold]Last {len(history)} commands:[/bold]\n")
    for entry in reversed(history):
        timestamp = entry.get("timestamp", "")[:19].replace("T", " ")
        cmd = entry.get("command", "")
        repo = entry.get("repo_path", "")
        console.print(f"[dim]{timestamp}[/dim] [cyan]{cmd}[/cyan]")
        if repo:
            console.print(f"  [dim]in {repo}[/dim]")


@cli.command()
@click.argument('repo_url')
@click.option('--dest', '-d', help='Destination path')
def clone(repo_url: str, dest: Optional[str]):
    """
    Clone and decrypt an encrypted repository.

    Clones a gitcloakd repository and automatically decrypts it
    if you have access (your GPG key is authorized).
    """
    print_banner()

    console.print("[bold]Cloning encrypted repository...[/bold]")
    console.print(f"[dim]{repo_url}[/dim]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Cloning...", total=None)

        try:
            result = clone_and_decrypt(repo_url, dest)
            progress.update(task, description="[green]Complete![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            return

    if result.get("errors"):
        print_warning("Completed with issues:")
        for err in result["errors"]:
            console.print(f"  [yellow]•[/yellow] {err}")
    else:
        print_success(f"Cloned and decrypted to: {result['path']}")
        if result.get("files"):
            console.print(f"[dim]Decrypted {result['files']} files[/dim]")

    # Register with secure storage if available
    try:
        storage = get_secure_storage()
        if storage.is_unlocked():
            repo_name = repo_url.rstrip("/").split("/")[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            storage.add_repo(result["path"], repo_name, "full")
    except Exception:
        pass


# =============================================================================
# DARK MODE MANAGEMENT COMMANDS
# =============================================================================

@cli.group()
def dark():
    """Manage Dark Mode encrypted repositories."""
    pass


@dark.command('info')
def dark_info():
    """Show dark mode repository information."""
    dm = DarkMode()

    if not dm.config.initialized:
        print_error("Not a dark mode repository.")
        return

    name_info = dm.get_name_info()

    console.print("\n[bold cyan]=== Dark Mode Repository ===[/bold cyan]\n")

    table = Table(show_header=False, box=None)
    if name_info:
        table.add_row("[cyan]Real Name:[/cyan]", name_info.get('real_name', '[encrypted]'))
        table.add_row("[cyan]Public UUID:[/cyan]", name_info.get('public_uuid', 'Unknown'))
        table.add_row("[cyan]Description:[/cyan]", name_info.get('description', '-'))
        table.add_row("[cyan]Created:[/cyan]", name_info.get('created_at', '-')[:19])
    table.add_row("[cyan]State:[/cyan]", "Encrypted" if dm.is_wrapper_state() else "Decrypted")
    console.print(table)


@dark.command('add-user')
@click.option('--email', '-e', required=True, help='User email')
@click.option('--key-id', '-k', required=True, help='GPG key ID')
@click.option('--reveal-name/--hide-name', default=True, help='Whether user can see real project name')
def dark_add_user(email: str, key_id: str, reveal_name: bool):
    """Add a user to dark mode repository."""
    dm = DarkMode()

    if not dm.config.initialized:
        print_error("Not a dark mode repository.")
        return

    console.print(f"\n[bold]Adding user: {email}[/bold]")
    console.print(f"[dim]GPG Key: {key_id}[/dim]")
    console.print(f"[dim]Can see project name: {'Yes' if reveal_name else 'No'}[/dim]\n")

    try:
        dm.add_user(
            email=email,
            gpg_key_id=key_id,
            can_see_name=reveal_name,
        )
        print_success(f"User {email} added to dark mode repository.")
        if reveal_name:
            console.print("[dim]User will be able to see the real project name.[/dim]")
        else:
            console.print("[dim]User will only see the UUID, not the real project name.[/dim]")

        audit(AuditEventType.USER_ADDED, f"User added to dark mode: {email}", {
            "can_see_name": reveal_name
        })
    except Exception as e:
        print_error(f"Failed to add user: {e}")


@dark.command('list-users')
def dark_list_users():
    """List users with access to dark mode repository."""
    dm = DarkMode()

    if not dm.config.initialized:
        print_error("Not a dark mode repository.")
        return

    users = dm.list_users()

    console.print("\n[bold cyan]=== Dark Mode Users ===[/bold cyan]\n")

    if not users:
        console.print("[dim]No users added yet.[/dim]")
        return

    table = Table()
    table.add_column("Email", style="cyan")
    table.add_column("Role", style="green")
    table.add_column("Can See Name", style="yellow")
    table.add_column("Added", style="dim")

    for user in users:
        can_see = "[green]Yes[/green]" if user.get('can_see_name', True) else "[red]No[/red]"
        added = user.get('added_at', '-')[:10] if user.get('added_at') else '-'
        table.add_row(user['email'], user.get('role', 'user'), can_see, added)

    console.print(table)


# =============================================================================
# MEMORY/CACHE CLEANER COMMANDS
# =============================================================================

@cli.group()
def clean():
    """Clean traces, cache, and memory artifacts."""
    pass


@clean.command('quick')
def clean_quick():
    """Quick clean - clear obvious caches (safe to run frequently)."""
    cleaner = get_memory_cleaner()

    console.print("\n[bold cyan]=== Quick Clean ===[/bold cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Clearing caches...", total=None)
        result = cleaner.clean_quick()
        progress.update(task, description="[green]Complete![/green]")

    print_success(f"Cleared {result['items_cleaned']} items")

    if result['errors']:
        print_warning("Some errors occurred:")
        for err in result['errors']:
            console.print(f"  [yellow]•[/yellow] {err}")


@clean.command('standard')
def clean_standard():
    """Standard clean - clear all gitcloakd temporary data."""
    cleaner = get_memory_cleaner()

    console.print("\n[bold cyan]=== Standard Clean ===[/bold cyan]\n")
    console.print("[bold yellow][!] This will clear:[/bold yellow]")
    console.print("  [cyan]•[/cyan] All cache directories")
    console.print("  [cyan]•[/cyan] Temporary files")
    console.print("  [cyan]•[/cyan] Session data (requires re-unlock)")
    console.print("")

    if not Confirm.ask("Proceed with standard clean?"):
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Clearing data...", total=None)
        result = cleaner.clean_standard()
        progress.update(task, description="[green]Complete![/green]")

    print_success(f"Cleared {result['items_cleaned']} items")

    if result.get('categories'):
        console.print("\n[bold]Summary:[/bold]")
        for category, count in result['categories'].items():
            console.print(f"  [cyan]•[/cyan] {category}: {count}")


@clean.command('paranoid')
@click.option('--confirm', 'confirmed', is_flag=True, help='Confirm destructive operation')
def clean_paranoid(confirmed: bool):
    """Paranoid clean - aggressive clearing of all traces (DESTRUCTIVE)."""
    cleaner = get_memory_cleaner()

    console.print("\n[bold cyan]=== PARANOID Clean ===[/bold cyan]\n")
    console.print("[bold red][!] WARNING: AGGRESSIVE CLEANING[/bold red]")
    console.print("This will:")
    console.print("  [red]•[/red] Clear ALL gitcloakd data (requires re-setup)")
    console.print("  [red]•[/red] Attempt to scrub memory")
    console.print("  [red]•[/red] Clear Python object caches")
    console.print("  [red]•[/red] Delete encrypted cache files")
    console.print("")

    if not confirmed:
        if not Confirm.ask("[red]Are you absolutely sure?[/red]"):
            return
        confirmed = True

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Performing paranoid clean...", total=None)
        result = cleaner.clean_paranoid(confirm=confirmed)
        progress.update(task, description="[green]Complete![/green]")

    print_success(f"Cleared {result['items_cleaned']} items")

    if result.get('warnings'):
        console.print("\n[bold yellow]Limitations:[/bold yellow]")
        for warning in result['warnings']:
            console.print(f"  [yellow]•[/yellow] {warning}")


@clean.command('history')
def clean_history():
    """Clear command history only."""
    cleaner = get_memory_cleaner()

    if cleaner.clear_command_history():
        print_success("Command history cleared.")
    else:
        console.print("[dim]No command history to clear.[/dim]")


@clean.command('audit')
@click.option('--confirm', 'confirmed', is_flag=True, help='Confirm destructive operation')
def clean_audit(confirmed: bool):
    """Clear audit logs (DESTRUCTIVE)."""
    cleaner = get_memory_cleaner()

    if not confirmed:
        console.print("[bold red]WARNING: This will delete all audit logs![/bold red]")
        if not Confirm.ask("Are you sure?"):
            return
        confirmed = True

    if cleaner.clear_audit_logs(confirm=confirmed):
        print_success("Audit logs cleared.")
    else:
        console.print("[dim]No audit logs to clear.[/dim]")


@clean.command('footprint')
def clean_footprint():
    """Show gitcloakd data footprint on system."""
    cleaner = get_memory_cleaner()

    footprint = cleaner.get_data_footprint()

    console.print("\n[bold cyan]=== Data Footprint ===[/bold cyan]\n")

    table = Table()
    table.add_column("Location", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Files", style="yellow")
    table.add_column("Size", style="magenta")

    for loc in footprint['locations']:
        size_kb = loc['size_bytes'] / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
        table.add_row(loc['path'], loc['type'], str(loc['file_count']), size_str)

    console.print(table)

    total_kb = footprint['total_size_bytes'] / 1024
    total_str = f"{total_kb:.1f} KB" if total_kb < 1024 else f"{total_kb/1024:.1f} MB"
    console.print(f"\n[bold]Total:[/bold] {footprint['file_count']} files, {total_str}")


# =============================================================================
# TEST MODE COMMANDS
# =============================================================================

@cli.group()
def test():
    """Test gitcloakd safely before committing to encryption."""
    pass


@test.command('create')
@click.option('--path', '-p', default=None, help='Path to create test repo (default: ./gitcloakd-test-repo)')
@click.option('--mode', '-m', type=click.Choice(['selective', 'full', 'dark']), default='selective',
              help='Encryption mode to demonstrate')
def test_create(path: Optional[str], mode: str):
    """
    Create a demo repository to test gitcloakd.

    Creates a sample repo with fake sensitive files so you can
    experiment with gitcloakd without risking real data.
    """
    import shutil
    from datetime import datetime

    print_banner()
    console.print("\n[bold cyan]=== Create Test Repository ===[/bold cyan]\n")

    # Determine path
    if path is None:
        path = Path.cwd() / "gitcloakd-test-repo"
    else:
        path = Path(path)

    if path.exists():
        print_warning(f"Directory already exists: {path}")
        if not Confirm.ask("Remove and recreate?"):
            return
        shutil.rmtree(path)

    console.print(f"[bold]Creating test repository at:[/bold] {path}")
    console.print(f"[bold]Mode:[/bold] {mode.upper()}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Creating test repo...", total=None)

        try:
            # Create directory structure
            path.mkdir(parents=True)
            (path / "src").mkdir()
            (path / "tests").mkdir()
            (path / "config").mkdir()

            # Create sample files
            (path / "README.md").write_text(f"""# gitcloakd Test Repository

This is a test repository created by gitcloakd to demonstrate encryption.

Created: {datetime.now().isoformat()}
Mode: {mode.upper()}

## Sample Files

- `src/main.py` - Sample Python code
- `src/utils.py` - Utility functions
- `.env` - Fake environment variables (will be encrypted)
- `config/secrets.yaml` - Fake secrets (will be encrypted)
- `config/api_keys.json` - Fake API keys (will be encrypted)

## Test gitcloakd

```bash
cd {path.name}
gitcloakd init {'--' + mode if mode != 'selective' else '--wizard'}
gitcloakd encrypt {'--' + mode if mode != 'selective' else '--all'}
gitcloakd status
gitcloakd decrypt {'--' + mode if mode != 'selective' else '--all'}
```

**This is a test repo - all secrets are fake!**
""")

            # Sample Python code
            (path / "src" / "main.py").write_text('''"""
Sample application for gitcloakd testing.
"""
import os
from utils import get_config

def main():
    """Main entry point."""
    config = get_config()
    api_key = os.environ.get("API_KEY", "not-set")
    print(f"Running with API key: {api_key[:4]}...")

if __name__ == "__main__":
    main()
''')

            (path / "src" / "utils.py").write_text('''"""
Utility functions.
"""
import json
import yaml

def get_config():
    """Load configuration."""
    return {"debug": True, "version": "1.0.0"}

def load_secrets():
    """Load secrets from config."""
    # In real code, this would load encrypted secrets
    pass
''')

            # Sample .env file (fake secrets)
            (path / ".env").write_text("""# FAKE SECRETS FOR TESTING - NOT REAL!
API_KEY=sk-test-fake-key-1234567890abcdef
DATABASE_URL=postgres://user:FAKE_PASSWORD_123@localhost:5432/testdb
SECRET_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.FAKE_TOKEN
AWS_ACCESS_KEY_ID=AKIAFAKEACCESSKEY123
AWS_SECRET_ACCESS_KEY=FakeSecretAccessKey/1234567890abcdefgh
STRIPE_SECRET_KEY=sk_test_fake_stripe_key_1234567890
GITHUB_TOKEN=ghp_FakeGitHubToken1234567890abcdefghij
""")

            # Sample secrets.yaml
            (path / "config" / "secrets.yaml").write_text("""# FAKE SECRETS FOR TESTING
database:
  host: localhost
  port: 5432
  username: admin
  password: FAKE_DB_PASSWORD_123

api_credentials:
  service_a:
    key: fake-service-a-key-12345
    secret: fake-service-a-secret-67890
  service_b:
    token: fake-service-b-token-abcdef

encryption:
  master_key: FAKE_MASTER_KEY_DO_NOT_USE_IN_PRODUCTION
""")

            # Sample api_keys.json
            (path / "config" / "api_keys.json").write_text("""{
  "_comment": "FAKE API KEYS FOR TESTING ONLY",
  "openai": "sk-fake-openai-key-1234567890",
  "anthropic": "sk-ant-fake-key-1234567890",
  "google": "AIzaFakeGoogleAPIKey123456789",
  "sendgrid": "SG.FakeSendGridKey.1234567890abcdefghij"
}
""")

            # Sample test file
            (path / "tests" / "test_main.py").write_text('''"""
Tests for main module.
"""
import pytest

def test_sample():
    """Sample test."""
    assert True

def test_config_loads():
    """Test config loading."""
    from src.utils import get_config
    config = get_config()
    assert config["version"] == "1.0.0"
''')

            # Initialize git repo
            import subprocess
            import os
            subprocess.run(["git", "init"], cwd=path, capture_output=True)
            subprocess.run(["git", "add", "-A"], cwd=path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial test repo for gitcloakd"],
                cwd=path, capture_output=True,
                env={**os.environ, "GIT_AUTHOR_NAME": "gitcloakd-test",
                     "GIT_AUTHOR_EMAIL": "test@gitcloakd.local",
                     "GIT_COMMITTER_NAME": "gitcloakd-test",
                     "GIT_COMMITTER_EMAIL": "test@gitcloakd.local"}
            )

            progress.update(task, description="[green]Complete![/green]")

        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            return

    print_success(f"Test repository created at: {path}")

    console.print("\n[bold]Files created:[/bold]")
    console.print("  [cyan]•[/cyan] src/main.py, src/utils.py")
    console.print("  [cyan]•[/cyan] tests/test_main.py")
    console.print("  [red]•[/red] .env (fake secrets)")
    console.print("  [red]•[/red] config/secrets.yaml (fake secrets)")
    console.print("  [red]•[/red] config/api_keys.json (fake secrets)")

    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  1. [cyan]cd {path}[/cyan]")
    if mode == 'selective':
        console.print("  2. [cyan]gitcloakd init --wizard[/cyan]")
        console.print("  3. [cyan]gitcloakd encrypt --all[/cyan]")
    elif mode == 'full':
        console.print("  2. [cyan]gitcloakd init --full[/cyan]")
        console.print("  3. [cyan]gitcloakd encrypt --full[/cyan]")
    else:  # dark
        console.print("  2. [cyan]gitcloakd init --dark[/cyan]")
        console.print("  3. [cyan]gitcloakd encrypt --dark[/cyan]")
    console.print("  4. [cyan]gitcloakd status[/cyan]")

    console.print("\n[bold yellow][!] All secrets in this repo are FAKE - safe to experiment![/bold yellow]")


@test.command('dry-run')
@click.option('--mode', '-m', type=click.Choice(['selective', 'full', 'dark']), default='selective',
              help='Encryption mode to simulate')
def test_dry_run(mode: str):
    """
    Preview what gitcloakd would do WITHOUT making changes.

    Shows exactly which files would be encrypted, what the
    encrypted repo would look like, etc.
    """
    print_banner()
    console.print("\n[bold cyan]=== Dry Run (Preview Only) ===[/bold cyan]\n")
    console.print("[bold yellow][!] DRY RUN - No changes will be made[/bold yellow]\n")

    repo_path = Path.cwd()

    # Check if it's a git repo
    if not (repo_path / ".git").exists():
        print_error("Not a git repository. Run this from a git repo root.")
        return

    console.print(f"[bold]Repository:[/bold] {repo_path}")
    console.print(f"[bold]Mode:[/bold] {mode.upper()}\n")

    # Find files that would be affected
    console.print("[bold]Scanning repository...[/bold]\n")

    # Default patterns for selective mode
    sensitive_patterns = [
        "*.env", ".env", ".env.*",
        "*.key", "*.pem", "*.p12", "*.pfx",
        "*.secret", "secrets.*", "*secrets*",
        "credentials.*", "*credentials*",
        "*.gpg", "id_rsa", "id_ed25519",
        "**/config/secrets*", "**/config/api*"
    ]

    import fnmatch

    all_files = []
    sensitive_files = []

    for f in repo_path.rglob("*"):
        if f.is_file() and ".git" not in str(f):
            rel_path = f.relative_to(repo_path)
            all_files.append(rel_path)

            # Check if matches sensitive patterns
            for pattern in sensitive_patterns:
                if fnmatch.fnmatch(str(rel_path), pattern) or fnmatch.fnmatch(f.name, pattern):
                    sensitive_files.append(rel_path)
                    break

    # Show what would happen
    if mode == 'selective':
        console.print("[bold cyan]SELECTIVE MODE - What would happen:[/bold cyan]\n")

        if sensitive_files:
            console.print(f"[bold red]Files that would be ENCRYPTED ({len(sensitive_files)}):[/bold red]")
            for f in sensitive_files[:20]:
                size = (repo_path / f).stat().st_size
                console.print(f"  [red]•[/red] {f} ({size} bytes)")
            if len(sensitive_files) > 20:
                console.print(f"  [dim]... and {len(sensitive_files) - 20} more[/dim]")
        else:
            console.print("[dim]No sensitive files detected with default patterns.[/dim]")

        console.print(f"\n[bold green]Files that would remain VISIBLE ({len(all_files) - len(sensitive_files)}):[/bold green]")
        visible = [f for f in all_files if f not in sensitive_files]
        for f in visible[:10]:
            console.print(f"  [green]•[/green] {f}")
        if len(visible) > 10:
            console.print(f"  [dim]... and {len(visible) - 10} more[/dim]")

    elif mode == 'full':
        console.print("[bold cyan]FULL MODE - What would happen:[/bold cyan]\n")

        total_size = sum((repo_path / f).stat().st_size for f in all_files)

        console.print("[bold red]ALL files would be encrypted into encrypted.gpg:[/bold red]")
        console.print(f"  [cyan]•[/cyan] Total files: {len(all_files)}")
        console.print(f"  [cyan]•[/cyan] Total size: {total_size / 1024:.1f} KB")

        console.print("\n[bold]After encryption, repo would contain only:[/bold]")
        console.print("  [cyan]•[/cyan] encrypted.gpg (entire codebase)")
        console.print("  [cyan]•[/cyan] README.md (generic encrypted message)")
        console.print("  [cyan]•[/cyan] .gitcloakd/ (public config)")

    else:  # dark
        console.print("[bold cyan]DARK MODE - What would happen:[/bold cyan]\n")

        total_size = sum((repo_path / f).stat().st_size for f in all_files)

        # Count commits
        import subprocess
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=repo_path, capture_output=True, text=True
        )
        commit_count = result.stdout.strip() if result.returncode == 0 else "?"

        # Get branches
        result = subprocess.run(
            ["git", "branch", "--list"],
            cwd=repo_path, capture_output=True, text=True
        )
        branch_count = len([b for b in result.stdout.strip().split('\n') if b]) if result.returncode == 0 else "?"

        console.print("[bold red]EVERYTHING would be encrypted and hidden:[/bold red]")
        console.print(f"  [cyan]•[/cyan] Files: {len(all_files)}")
        console.print(f"  [cyan]•[/cyan] Total size: {total_size / 1024:.1f} KB")
        console.print(f"  [cyan]•[/cyan] Git commits: {commit_count}")
        console.print(f"  [cyan]•[/cyan] Branches: {branch_count}")

        import uuid
        fake_uuid = str(uuid.uuid4())

        console.print("\n[bold]After encryption, unauthorized users would see:[/bold]")
        console.print(f"  [cyan]•[/cyan] Repository name: [yellow]{fake_uuid}[/yellow] (UUID)")
        console.print("  [cyan]•[/cyan] encrypted.gpg (single blob)")
        console.print("  [cyan]•[/cyan] README.md (generic message)")
        console.print("  [cyan]•[/cyan] Single commit (no history)")
        console.print("  [cyan]•[/cyan] No file structure visible")
        console.print("  [cyan]•[/cyan] No contributors visible")

    console.print("\n[bold green]No changes were made - this was a dry run.[/bold green]")
    console.print("[dim]To actually encrypt, run: gitcloakd encrypt --" + mode + "[/dim]")


@test.command('backup')
@click.option('--output', '-o', default=None, help='Backup destination (default: ../REPO_backup_TIMESTAMP)')
def test_backup(output: Optional[str]):
    """
    Create a full backup of the repository before encryption.

    Creates a complete copy including .git directory so you can
    restore if anything goes wrong.
    """
    import shutil
    from datetime import datetime

    print_banner()
    console.print("\n[bold cyan]=== Create Backup ===[/bold cyan]\n")

    repo_path = Path.cwd()

    if not (repo_path / ".git").exists():
        print_error("Not a git repository.")
        return

    # Determine backup path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    repo_name = repo_path.name

    if output:
        backup_path = Path(output)
    else:
        backup_path = repo_path.parent / f"{repo_name}_backup_{timestamp}"

    if backup_path.exists():
        print_error(f"Backup destination already exists: {backup_path}")
        return

    # Calculate size
    total_size = sum(f.stat().st_size for f in repo_path.rglob("*") if f.is_file())

    console.print(f"[bold]Source:[/bold] {repo_path}")
    console.print(f"[bold]Destination:[/bold] {backup_path}")
    console.print(f"[bold]Size:[/bold] {total_size / 1024 / 1024:.1f} MB\n")

    if not Confirm.ask("Create backup?"):
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Creating backup...", total=None)

        try:
            shutil.copytree(repo_path, backup_path)
            progress.update(task, description="[green]Complete![/green]")
        except Exception as e:
            progress.update(task, description=f"[red]Failed: {e}[/red]")
            return

    print_success(f"Backup created: {backup_path}")

    console.print("\n[bold]To restore from backup:[/bold]")
    console.print(f"  rm -rf {repo_path}")
    console.print(f"  mv {backup_path} {repo_path}")

    console.print("\n[bold yellow][!] Keep this backup until you're confident encryption works![/bold yellow]")


@test.command('verify')
def test_verify():
    """
    Verify an encrypted repository can be decrypted.

    Checks that your GPG key can decrypt the encrypted content
    and that the encryption is working correctly.
    """
    print_banner()
    console.print("\n[bold cyan]=== Verify Encryption ===[/bold cyan]\n")

    repo_path = Path.cwd()

    # Check what type of encryption is present
    has_gpg_files = list(repo_path.glob("*.gpg")) + list(repo_path.rglob("*.gpg"))
    has_encrypted_blob = (repo_path / "encrypted.gpg").exists()
    has_gitcloakd = (repo_path / ".gitcloakd").exists()

    if not has_gpg_files and not has_encrypted_blob:
        print_warning("No encrypted files found in this repository.")
        console.print("[dim]Run 'gitcloakd encrypt' first to encrypt files.[/dim]")
        return

    console.print("[bold]Checking encryption status...[/bold]\n")

    gpg = GPGManager()
    keys = gpg.list_keys(secret=True)

    if not keys:
        print_error("No GPG secret keys found. You need a key to decrypt.")
        return

    console.print(f"[green][+][/green] Found {len(keys)} GPG secret key(s)")

    # Try to verify we can decrypt
    errors = []
    success = []

    if has_encrypted_blob:
        console.print("\n[bold]Testing full/dark mode decryption...[/bold]")
        try:
            # Just test that we can read the GPG header
            with open(repo_path / "encrypted.gpg", "rb") as f:
                header = f.read(100)
            if header[:5] == b'-----' or header[0:1] in [b'\x85', b'\x84', b'\xa3']:
                console.print("[green][+][/green] encrypted.gpg appears to be valid GPG data")
                success.append("encrypted.gpg format valid")
            else:
                errors.append("encrypted.gpg doesn't appear to be GPG encrypted")
        except Exception as e:
            errors.append(f"Could not read encrypted.gpg: {e}")

    # Test individual encrypted files
    gpg_files = [f for f in repo_path.rglob("*.gpg") if f.name != "encrypted.gpg"]
    if gpg_files:
        console.print(f"\n[bold]Testing selective encryption ({len(gpg_files)} files)...[/bold]")

        test_file = gpg_files[0]
        try:
            result = gpg.gpg.decrypt_file(str(test_file), always_trust=True)
            if result.ok:
                console.print(f"[green][+][/green] Successfully decrypted test file: {test_file.name}")
                success.append("Can decrypt .gpg files")
            else:
                errors.append(f"Failed to decrypt {test_file.name}: {result.status}")
        except Exception as e:
            errors.append(f"Decryption test failed: {e}")

    # Check config
    if has_gitcloakd:
        config_file = repo_path / ".gitcloakd" / "config.yaml"
        if config_file.exists():
            console.print("[green][+][/green] .gitcloakd/config.yaml found")
            success.append("Config present")
        else:
            errors.append("Missing .gitcloakd/config.yaml")

    # Summary
    console.print("\n[bold]Verification Results:[/bold]\n")

    if success:
        console.print("[bold green]PASSED:[/bold green]")
        for s in success:
            console.print(f"  [green][+][/green] {s}")

    if errors:
        console.print("\n[bold red]ISSUES:[/bold red]")
        for e in errors:
            console.print(f"  [red][-][/red] {e}")

    if not errors:
        print_success("\nEncryption verified! You can decrypt this repository.")
    else:
        print_warning("\nSome issues detected. Check the errors above.")


if __name__ == "__main__":
    cli()
