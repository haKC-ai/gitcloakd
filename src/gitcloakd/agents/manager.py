"""
gitcloakd AI Agent Manager
Manages AI coding agents access to encrypted repositories
"""

from pathlib import Path
from typing import Optional, List
from datetime import datetime

from gitcloakd.core.config import Config, AgentConfig


class AgentManager:
    """Manages AI coding agents for gitcloakd repositories."""

    # Predefined agent templates
    AGENT_TEMPLATES = {
        "claude": {
            "name": "claude-code",
            "type": "claude",
            "can_decrypt": False,
            "can_commit": True,
            "denied_paths": [
                ".gitcloakd/*",
                "*.key",
                "*.pem",
                ".env*",
                "secrets/*",
                "credentials.*"
            ],
            "instructions": """
# Claude Code Agent Instructions

You are working in a gitcloakd-protected repository.

## Security Rules
1. NEVER read or access files matching encrypted patterns
2. NEVER commit decrypted secrets or sensitive data
3. NEVER expose encryption keys or credentials
4. NEVER modify .gitcloakd/ configuration

## Encrypted Patterns
The following files are encrypted and off-limits:
{patterns}

## Workflow
- You can read and modify non-encrypted source code
- You can create new files (except in denied paths)
- You can run tests and builds
- Always check .gitcloakd/agent-instructions.md for updates
"""
        },
        "copilot": {
            "name": "github-copilot",
            "type": "copilot",
            "can_decrypt": False,
            "can_commit": False,
            "denied_paths": [
                ".gitcloakd/*",
                "*.key",
                "*.pem",
                ".env*"
            ],
            "instructions": """
# GitHub Copilot Agent Instructions

This repository uses gitcloakd encryption.

## Restrictions
- Do not suggest code that exposes secrets
- Do not autocomplete content from encrypted files
- Be aware of .gitcloakd/agent-instructions.md
"""
        },
        "gemini": {
            "name": "gemini-code",
            "type": "gemini",
            "can_decrypt": False,
            "can_commit": True,
            "denied_paths": [
                ".gitcloakd/*",
                "*.key",
                "*.pem",
                ".env*",
                "secrets/*"
            ],
            "instructions": """
# Gemini Code Agent Instructions

You are working in a gitcloakd-protected repository.

## Security Rules
1. NEVER access encrypted files
2. NEVER commit sensitive data
3. NEVER expose credentials

## See .gitcloakd/agent-instructions.md for full details
"""
        }
    }

    def __init__(self, repo_path: Optional[str] = None):
        """Initialize agent manager."""
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.config_dir = self.repo_path / ".gitcloakd"
        self.config = Config.load_repo(str(self.repo_path))

    def add_agent(
        self,
        agent_type: str,
        name: Optional[str] = None,
        can_decrypt: bool = False,
        gpg_key_id: Optional[str] = None,
        custom_instructions: Optional[str] = None
    ) -> AgentConfig:
        """
        Add an AI agent to the repository.

        Args:
            agent_type: Type of agent (claude, copilot, gemini, custom)
            name: Custom name for the agent
            can_decrypt: Whether agent can decrypt content
            gpg_key_id: GPG key ID if agent can decrypt
            custom_instructions: Custom instructions for the agent

        Returns:
            Created AgentConfig
        """
        # Get template if available
        template = self.AGENT_TEMPLATES.get(agent_type, {})

        agent = AgentConfig(
            name=name or template.get("name", f"{agent_type}-agent"),
            type=agent_type,
            can_decrypt=can_decrypt,
            gpg_key_id=gpg_key_id,
            can_commit=template.get("can_commit", True),
            denied_paths=template.get("denied_paths", [".gitcloakd/*"]),
        )

        # Add to config
        self.config.add_agent(agent)
        self.config.save_repo(str(self.repo_path))

        # Create agent-specific instructions file
        self._create_agent_instructions(agent, custom_instructions or template.get("instructions", ""))

        # Create .gitcloakd/agents/ directory for agent configs
        agents_dir = self.config_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Create agent config file
        agent_file = agents_dir / f"{agent.name}.yaml"
        self._write_agent_config(agent_file, agent)

        return agent

    def remove_agent(self, name: str) -> bool:
        """Remove an agent from the repository."""
        if not self.config.remove_agent(name):
            return False

        self.config.save_repo(str(self.repo_path))

        # Remove agent config file
        agent_file = self.config_dir / "agents" / f"{name}.yaml"
        if agent_file.exists():
            agent_file.unlink()

        # Update instructions
        self._update_main_instructions()

        return True

    def list_agents(self) -> List[AgentConfig]:
        """List all configured agents."""
        return self.config.agents

    def get_agent(self, name: str) -> Optional[AgentConfig]:
        """Get a specific agent configuration."""
        for agent in self.config.agents:
            if agent.name == name:
                return agent
        return None

    def grant_decrypt_access(self, agent_name: str, gpg_key_id: str) -> bool:
        """
        Grant an agent decrypt access.

        Args:
            agent_name: Name of the agent
            gpg_key_id: GPG key ID to grant access

        Returns:
            True if successful
        """
        for i, agent in enumerate(self.config.agents):
            if agent.name == agent_name:
                agent.can_decrypt = True
                agent.gpg_key_id = gpg_key_id
                self.config.agents[i] = agent
                self.config.save_repo(str(self.repo_path))
                return True
        return False

    def revoke_decrypt_access(self, agent_name: str) -> bool:
        """Revoke an agent's decrypt access."""
        for i, agent in enumerate(self.config.agents):
            if agent.name == agent_name:
                agent.can_decrypt = False
                agent.gpg_key_id = None
                self.config.agents[i] = agent
                self.config.save_repo(str(self.repo_path))
                return True
        return False

    def generate_github_action(self, agent_type: str = "generic") -> str:
        """
        Generate GitHub Action workflow for gitcloakd.

        Args:
            agent_type: Type of CI agent

        Returns:
            GitHub Action YAML content
        """
        workflow = """
name: gitcloakd Security Check

on:
  push:
    branches: [ main, master, develop ]
  pull_request:
    branches: [ main, master ]

jobs:
  security-check:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0  # Full history for scanning

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install gitcloakd
      run: pip install gitcloakd

    - name: Check for unencrypted secrets
      run: |
        gitcloakd scan --strict
        if [ $? -ne 0 ]; then
          echo "::error::Unencrypted secrets detected! Please encrypt sensitive files."
          exit 1
        fi

    - name: Verify encryption status
      run: |
        gitcloakd status --json > encryption-status.json
        cat encryption-status.json

    - name: Check for sensitive patterns
      run: |
        gitcloakd analyze --patterns-only
        if [ $? -ne 0 ]; then
          echo "::warning::Potential sensitive data patterns found."
        fi

  # Only run on PRs to check for accidental secret commits
  secret-scan:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'

    steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0

    - name: Install gitcloakd
      run: pip install gitcloakd

    - name: Scan PR diff for secrets
      run: |
        gitcloakd scan --diff origin/${{ github.base_ref }}..HEAD
"""
        return workflow.strip()

    def generate_pre_commit_hook(self) -> str:
        """Generate pre-commit hook for gitcloakd."""
        hook = """#!/bin/bash
# gitcloakd pre-commit hook
# Prevents committing unencrypted sensitive data

set -e

echo "[gitcloakd] Running pre-commit security check..."

# Check if gitcloakd is installed
if ! command -v gitcloakd &> /dev/null; then
    echo "[gitcloakd] Warning: gitcloakd not installed, skipping checks"
    exit 0
fi

# Get list of staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

if [ -z "$STAGED_FILES" ]; then
    exit 0
fi

# Check each staged file against sensitive patterns
SENSITIVE_PATTERNS=(
    "*.env"
    "*.key"
    "*.pem"
    "*.p12"
    "credentials.*"
    "secrets.*"
    "id_rsa*"
    "id_ed25519*"
)

FOUND_SENSITIVE=0

for file in $STAGED_FILES; do
    for pattern in "${SENSITIVE_PATTERNS[@]}"; do
        if [[ "$file" == $pattern ]]; then
            # Check if file is encrypted (ends with .gpg or is git-crypt encrypted)
            if [[ ! "$file" == *.gpg ]]; then
                echo "[gitcloakd] ERROR: Unencrypted sensitive file: $file"
                FOUND_SENSITIVE=1
            fi
        fi
    done
done

# Run gitcloakd scan on staged files
echo "$STAGED_FILES" | gitcloakd scan --stdin --strict
SCAN_RESULT=$?

if [ $SCAN_RESULT -ne 0 ] || [ $FOUND_SENSITIVE -ne 0 ]; then
    echo ""
    echo "[gitcloakd] =========================================="
    echo "[gitcloakd] COMMIT BLOCKED: Security issues detected!"
    echo "[gitcloakd] =========================================="
    echo ""
    echo "Options:"
    echo "  1. Encrypt sensitive files: gitcloakd encrypt <file>"
    echo "  2. Add to .gitignore if not needed in repo"
    echo "  3. Bypass (NOT RECOMMENDED): git commit --no-verify"
    echo ""
    exit 1
fi

echo "[gitcloakd] Security check passed!"
exit 0
"""
        return hook.strip()

    def _create_agent_instructions(self, agent: AgentConfig, template: str) -> None:
        """Create instructions file for an agent."""
        instructions_dir = self.config_dir / "agents"
        instructions_dir.mkdir(parents=True, exist_ok=True)

        instructions_file = instructions_dir / f"{agent.name}-instructions.md"

        # Format template with patterns
        patterns = "\n".join(f"- `{p}`" for p in self.config.auto_encrypt_patterns)
        content = template.format(patterns=patterns)

        instructions_file.write_text(content)

    def _update_main_instructions(self) -> None:
        """Update main agent instructions file."""
        instructions_file = self.config_dir / "agent-instructions.md"

        content = ["# gitcloakd Agent Instructions", ""]
        content.append("This repository uses gitcloakd for encryption.")
        content.append("")
        content.append("## Encrypted Patterns")
        for pattern in self.config.auto_encrypt_patterns:
            content.append(f"- `{pattern}`")
        content.append("")
        content.append("## Configured Agents")
        for agent in self.config.agents:
            content.append(f"### {agent.name} ({agent.type})")
            content.append(f"- Can decrypt: {agent.can_decrypt}")
            content.append(f"- Can commit: {agent.can_commit}")
            if agent.denied_paths:
                content.append(f"- Denied paths: {', '.join(agent.denied_paths)}")
            content.append("")

        instructions_file.write_text("\n".join(content))

    def _write_agent_config(self, path: Path, agent: AgentConfig) -> None:
        """Write agent configuration to file."""
        import yaml

        config = {
            "name": agent.name,
            "type": agent.type,
            "can_decrypt": agent.can_decrypt,
            "can_commit": agent.can_commit,
            "gpg_key_id": agent.gpg_key_id,
            "denied_paths": agent.denied_paths,
            "allowed_paths": agent.allowed_paths,
            "created": datetime.now().isoformat(),
        }

        with open(path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
