"""
AI-powered email generation for personalized outreach.
Supports both Anthropic Claude and Google Gemini.
"""
import logging
from typing import Tuple

from config import config
from schema import RepoRadarPayload, ApolloContact

logger = logging.getLogger(__name__)


def generate_personalized_email(
    payload: RepoRadarPayload,
    contact: ApolloContact
) -> Tuple[str, str]:
    """
    Generate a personalized cold email based on i18n signals.

    Args:
        payload: RepoRadar webhook payload with signal info
        contact: Apollo contact to personalize for

    Returns:
        Tuple of (subject, body)
    """
    if config.AI_PROVIDER == "anthropic":
        return _generate_with_anthropic(payload, contact)
    elif config.AI_PROVIDER == "gemini":
        return _generate_with_gemini(payload, contact)
    else:
        raise ValueError(f"Unknown AI provider: {config.AI_PROVIDER}")


def _build_prompt(payload: RepoRadarPayload, contact: ApolloContact) -> str:
    """Build the prompt for email generation."""
    return f"""You are a sales development representative for a localization/internationalization platform.

Generate a personalized cold email based on the following i18n signal detected at the prospect's company:

COMPANY: {payload.company}
DOMAIN: {payload.domain}
SIGNAL TYPE: {payload.signal_type}
SIGNAL SUMMARY: {payload.signal_summary}
LANGUAGES DETECTED: {', '.join(payload.languages) if payload.languages else 'Not specified'}
{f'COMMIT/PR URL: {payload.url}' if payload.url else ''}

CONTACT INFO:
- Name: {contact.display_name}
- Title: {contact.title or 'Unknown'}
- Company: {contact.organization_name or payload.company}

REQUIREMENTS:
1. Subject line must be compelling and under 50 characters
2. Use Apollo.io dynamic variables: {{{{first_name}}}} for greeting, {{{{company}}}} in body, {{{{sender_first_name}}}} for signature
3. NEVER use {{{{first_name}}}} in the subject line (triggers spam filters)
4. Reference the specific i18n activity you detected
5. Keep the email under 150 words
6. End with a soft CTA (question, not a demand)
7. Be conversational, not salesy
8. Don't mention that you "detected" or "noticed" their activity - instead, frame it as industry awareness

OUTPUT FORMAT:
SUBJECT: [your subject line here]
BODY:
[your email body here]"""


def _generate_with_anthropic(
    payload: RepoRadarPayload,
    contact: ApolloContact
) -> Tuple[str, str]:
    """Generate email using Anthropic Claude."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    prompt = _build_prompt(payload, contact)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text
    return _parse_email_response(response_text)


def _generate_with_gemini(
    payload: RepoRadarPayload,
    contact: ApolloContact
) -> Tuple[str, str]:
    """Generate email using Google Gemini."""
    import google.generativeai as genai

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = _build_prompt(payload, contact)

    response = model.generate_content(prompt)
    return _parse_email_response(response.text)


def _parse_email_response(response: str) -> Tuple[str, str]:
    """Parse the AI response to extract subject and body."""
    lines = response.strip().split('\n')

    subject = ""
    body_lines = []
    in_body = False

    for line in lines:
        if line.startswith("SUBJECT:"):
            subject = line.replace("SUBJECT:", "").strip()
        elif line.startswith("BODY:"):
            in_body = True
        elif in_body:
            body_lines.append(line)

    body = '\n'.join(body_lines).strip()

    if not subject or not body:
        logger.warning("Failed to parse AI response, using fallback")
        # Fallback parsing - try to extract from raw response
        if not subject and lines:
            subject = lines[0][:50]
        if not body:
            body = response

    return subject, body


def format_i18n_signals(payload: RepoRadarPayload) -> str:
    """Format i18n signals for storage in Apollo custom field."""
    parts = [
        f"Signal: {payload.signal_type}",
        f"Summary: {payload.signal_summary}",
    ]

    if payload.languages:
        parts.append(f"Languages: {', '.join(payload.languages)}")

    if payload.url:
        parts.append(f"URL: {payload.url}")

    if payload.author:
        parts.append(f"Author: {payload.author}")

    return " | ".join(parts)
