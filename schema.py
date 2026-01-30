"""
Pydantic models for payload validation.
Strictly validates incoming webhooks from RepoRadar.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from enum import Enum


class SignalType(str, Enum):
    """Types of i18n signals detected by RepoRadar."""
    NEW_LANG_FILE = "NEW_LANG_FILE"
    OPEN_PR = "OPEN_PR"
    I18N_DEPENDENCY = "I18N_DEPENDENCY"
    LOCALE_DIRECTORY = "LOCALE_DIRECTORY"
    TRANSLATION_CONFIG = "TRANSLATION_CONFIG"


class RepoRadarPayload(BaseModel):
    """
    Webhook payload from RepoRadar.

    Required fields: company, domain, signal_type, signal_summary
    Optional fields: languages, author, url, metadata
    """
    company: str = Field(..., min_length=1, description="Company name")
    domain: str = Field(..., min_length=1, description="Company domain (e.g., shopify.com)")
    signal_type: SignalType = Field(..., description="Type of i18n signal detected")
    signal_summary: str = Field(..., min_length=1, description="Human-readable summary of the signal")

    # Optional fields
    languages: Optional[list[str]] = Field(default=None, description="Language codes detected")
    author: Optional[str] = Field(default=None, description="GitHub username of commit author")
    url: Optional[HttpUrl] = Field(default=None, description="URL to the commit/PR")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional context")

    class Config:
        use_enum_values = True


class ApolloContact(BaseModel):
    """Contact returned from Apollo People Search."""
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    organization_name: Optional[str] = None

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or "Unknown"


class ApprovalRequest(BaseModel):
    """Stored approval request awaiting BDR action."""
    id: str
    company: str
    domain: str
    signal_summary: str
    contact_id: str
    contact_name: str
    contact_title: Optional[str]
    contact_email: Optional[str]
    personalized_subject: str
    personalized_email: str
    i18n_signals: str
    slack_message_ts: Optional[str] = None
    status: str = "pending"  # pending, approved, rejected, skipped
    created_at: Optional[str] = None
