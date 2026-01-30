# Lead Machine - Apollo Prospector

Automated lead qualification and outreach workflow that integrates RepoRadar i18n signals with Apollo.io sequences via Slack-based approval.

## Overview

This application:
1. Receives webhooks from RepoRadar when i18n activity is detected
2. Searches Apollo.io for relevant contacts at the company
3. Generates personalized outreach emails using AI (Claude or Gemini)
4. Posts approval cards to Slack for BDR review
5. On approval, creates contacts in Apollo and adds them to sequences

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Required variables:
- `APOLLO_API_KEY` - Your Apollo.io API key
- `APOLLO_SEQUENCE_ID` - The sequence ID to add approved contacts to
- `SLACK_BOT_TOKEN` - Slack bot OAuth token (xoxb-...)
- `SLACK_SIGNING_SECRET` - Slack app signing secret
- `SLACK_CHANNEL_ID` - Channel ID for approval messages
- `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` - AI provider API key

### 3. Slack App Setup

Create a Slack app with these permissions:
- `chat:write` - Post messages
- `chat:write.public` - Post to public channels

Enable Interactivity and set the Request URL to:
```
https://your-domain.com/slack/interactions
```

### 4. Run the Application

```bash
python app.py
```

The server starts on port 5000 by default.

## API Endpoints

### `POST /webhook/reporadar`
Receives webhooks from RepoRadar with i18n signal data.

**Payload:**
```json
{
  "company": "Shopify",
  "domain": "shopify.com",
  "signal_type": "NEW_LANG_FILE",
  "signal_summary": "Added French and German locale files",
  "languages": ["fr", "de"],
  "author": "developer-username",
  "url": "https://github.com/Shopify/repo/commit/abc123"
}
```

### `POST /slack/interactions`
Handles Slack button clicks and modal submissions.

### `GET /health`
Health check endpoint.

## Slack Workflow

When a webhook is received, the app posts an approval card with:
- Company and contact details
- i18n signal summary
- AI-generated email preview
- Action buttons: Approve, Edit, Regenerate, Skip

## Architecture

```
app.py           - Flask routes and request handling
config.py        - Environment variable configuration
schema.py        - Pydantic models for validation
storage.py       - SQLite database layer
apollo_client.py - Apollo.io API wrapper
slack_bot.py     - Slack integration
email_gen.py     - AI email generation
```

## License

MIT
