"""
Configuration management for Apollo Prospector.
Loads environment variables with sensible defaults.
"""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration from environment variables."""

    # Apollo API
    APOLLO_API_KEY: str = os.getenv("APOLLO_API_KEY", "")
    APOLLO_SEQUENCE_ID: str = os.getenv("APOLLO_SEQUENCE_ID", "")

    # Slack
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_SIGNING_SECRET: str = os.getenv("SLACK_SIGNING_SECRET", "")
    SLACK_CHANNEL_ID: str = os.getenv("SLACK_CHANNEL_ID", "")

    # AI Provider (anthropic or gemini)
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "anthropic")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Caching
    CACHE_EXPIRY_DAYS: int = int(os.getenv("CACHE_EXPIRY_DAYS", "7"))

    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "prospector.db")

    # Webhook security (optional shared secret with RepoRadar)
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")

    def validate(self) -> list[str]:
        """Validate required configuration. Returns list of missing fields."""
        missing = []

        if not self.APOLLO_API_KEY:
            missing.append("APOLLO_API_KEY")
        if not self.APOLLO_SEQUENCE_ID:
            missing.append("APOLLO_SEQUENCE_ID")
        if not self.SLACK_BOT_TOKEN:
            missing.append("SLACK_BOT_TOKEN")
        if not self.SLACK_SIGNING_SECRET:
            missing.append("SLACK_SIGNING_SECRET")
        if not self.SLACK_CHANNEL_ID:
            missing.append("SLACK_CHANNEL_ID")

        if self.AI_PROVIDER == "anthropic" and not self.ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY")
        elif self.AI_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")

        return missing


config = Config()
