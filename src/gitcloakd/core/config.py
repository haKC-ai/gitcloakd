"""
gitcloakd Configuration Management
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class UserConfig:
    """User/collaborator configuration."""
    name: str
    email: str
    gpg_key_id: str
    role: str = "collaborator"  # owner, admin, collaborator, readonly
    added_date: str = ""
    can_decrypt: bool = True
    notifications: bool = True


@dataclass
class AgentConfig:
    """AI agent configuration."""
    name: str
    type: str  # claude, gemini, copilot, custom
    gpg_key_id: Optional[str] = None
    can_decrypt: bool = False
    can_commit: bool = True
    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=list)
    instructions_file: str = ".gitcloakd/agent-instructions.md"


@dataclass
class AlertConfig:
    """Alert configuration."""
    enabled: bool = True
    on_commit: bool = True
    on_key_change: bool = True
    on_decrypt: bool = True
    on_new_user: bool = True
    webhook_url: Optional[str] = None
    email_notifications: bool = False
    slack_webhook: Optional[str] = None
    discord_webhook: Optional[str] = None


@dataclass
class Config:
    """Main gitcloakd configuration."""
    version: str = "1.0"
    initialized: bool = False
    repo_path: str = ""
    owner_key_id: str = ""
    owner_email: str = ""

    # Encryption settings
    encryption_algorithm: str = "AES256"
    key_server: str = "keyserver.ubuntu.com"
    auto_encrypt_patterns: List[str] = field(default_factory=lambda: [
        "*.env", "*.key", "*.pem", "*.secret", "credentials.*",
        "secrets/*", ".secrets/*", "config/secrets/*"
    ])

    # Users and agents
    users: List[UserConfig] = field(default_factory=list)
    agents: List[AgentConfig] = field(default_factory=list)

    # Alerts
    alerts: AlertConfig = field(default_factory=AlertConfig)

    # Metadata
    created_date: str = ""
    last_modified: str = ""

    @classmethod
    def get_config_dir(cls) -> Path:
        """Get the global config directory."""
        config_dir = Path.home() / ".config" / "gitcloakd"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @classmethod
    def get_repo_config_dir(cls, repo_path: Optional[str] = None) -> Path:
        """Get the repo-specific config directory."""
        if repo_path:
            path = Path(repo_path) / ".gitcloakd"
        else:
            path = Path.cwd() / ".gitcloakd"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def load_global(cls) -> "Config":
        """Load global configuration."""
        config_file = cls.get_config_dir() / "config.yaml"
        if config_file.exists():
            with open(config_file) as f:
                data = yaml.safe_load(f) or {}
            return cls._from_dict(data)
        return cls()

    @classmethod
    def load_repo(cls, repo_path: Optional[str] = None) -> "Config":
        """Load repository-specific configuration."""
        config_file = cls.get_repo_config_dir(repo_path) / "config.yaml"
        if config_file.exists():
            with open(config_file) as f:
                data = yaml.safe_load(f) or {}
            return cls._from_dict(data)
        return cls()

    def save_global(self) -> None:
        """Save global configuration."""
        config_file = self.get_config_dir() / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(self._to_dict(), f, default_flow_style=False)

    def save_repo(self, repo_path: Optional[str] = None) -> None:
        """Save repository-specific configuration."""
        config_file = self.get_repo_config_dir(repo_path) / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(self._to_dict(), f, default_flow_style=False)

    def _to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        data = asdict(self)
        # Convert nested dataclasses
        data["users"] = [asdict(u) if isinstance(u, UserConfig) else u for u in self.users]
        data["agents"] = [asdict(a) if isinstance(a, AgentConfig) else a for a in self.agents]
        data["alerts"] = asdict(self.alerts) if isinstance(self.alerts, AlertConfig) else self.alerts
        return data

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        # Convert nested dicts to dataclasses
        if "users" in data:
            data["users"] = [
                UserConfig(**u) if isinstance(u, dict) else u
                for u in data.get("users", [])
            ]
        if "agents" in data:
            data["agents"] = [
                AgentConfig(**a) if isinstance(a, dict) else a
                for a in data.get("agents", [])
            ]
        if "alerts" in data and isinstance(data["alerts"], dict):
            data["alerts"] = AlertConfig(**data["alerts"])

        # Handle missing fields gracefully
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered_data)

    def add_user(self, user: UserConfig) -> None:
        """Add a user to the configuration."""
        # Check if user already exists
        for i, existing in enumerate(self.users):
            if existing.email == user.email:
                self.users[i] = user
                return
        self.users.append(user)

    def remove_user(self, email: str) -> bool:
        """Remove a user by email."""
        for i, user in enumerate(self.users):
            if user.email == email:
                self.users.pop(i)
                return True
        return False

    def add_agent(self, agent: AgentConfig) -> None:
        """Add an AI agent to the configuration."""
        for i, existing in enumerate(self.agents):
            if existing.name == agent.name:
                self.agents[i] = agent
                return
        self.agents.append(agent)

    def remove_agent(self, name: str) -> bool:
        """Remove an agent by name."""
        for i, agent in enumerate(self.agents):
            if agent.name == name:
                self.agents.pop(i)
                return True
        return False
