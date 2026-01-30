"""
Slack Bot integration for approval workflow.
Posts approval cards and handles button interactions.
"""
import logging
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import config
from schema import ApprovalRequest

logger = logging.getLogger(__name__)


class SlackBot:
    """Slack bot for posting approval cards and handling interactions."""

    def __init__(self):
        self.client = WebClient(token=config.SLACK_BOT_TOKEN)
        self.channel_id = config.SLACK_CHANNEL_ID

    def post_approval_card(self, request: ApprovalRequest) -> str:
        """
        Post an approval card to Slack.

        Args:
            request: ApprovalRequest with all the details

        Returns:
            Slack message timestamp (ts) for updating later
        """
        blocks = self._build_approval_blocks(request)

        try:
            response = self.client.chat_postMessage(
                channel=self.channel_id,
                blocks=blocks,
                text=f"New lead approval request: {request.company}"  # Fallback text
            )
            return response["ts"]
        except SlackApiError as e:
            logger.error(f"Failed to post Slack message: {e}")
            raise

    def update_card_approved(self, channel: str, ts: str, request: ApprovalRequest):
        """Update card to show approved status."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *APPROVED* - {request.company}\n"
                           f"Contact: {request.contact_name} ({request.contact_email})\n"
                           f"_Added to sequence_"
                }
            }
        ]

        self._update_message(channel, ts, blocks)

    def update_card_rejected(self, channel: str, ts: str, request: ApprovalRequest):
        """Update card to show rejected status."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"❌ *SKIPPED* - {request.company}\n"
                           f"Contact: {request.contact_name}"
                }
            }
        ]

        self._update_message(channel, ts, blocks)

    def _update_message(self, channel: str, ts: str, blocks: list):
        """Update a Slack message."""
        try:
            self.client.chat_update(
                channel=channel,
                ts=ts,
                blocks=blocks,
                text="Updated"
            )
        except SlackApiError as e:
            logger.error(f"Failed to update Slack message: {e}")

    def _build_approval_blocks(self, request: ApprovalRequest) -> list:
        """Build Slack Block Kit blocks for approval card."""
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🎯 New Lead: {request.company}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Domain:*\n{request.domain}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Contact:*\n{request.contact_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Title:*\n{request.contact_title or 'N/A'}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Email:*\n{request.contact_email or 'N/A'}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*i18n Signal:*\n{request.signal_summary}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📧 Email Preview*\n*Subject:* {request.personalized_subject}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{request.personalized_email[:500]}{'...' if len(request.personalized_email) > 500 else ''}```"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Approve",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "approve_lead",
                        "value": request.id
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✏️ Edit",
                            "emoji": True
                        },
                        "action_id": "edit_lead",
                        "value": request.id
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🔄 Regenerate",
                            "emoji": True
                        },
                        "action_id": "regenerate_lead",
                        "value": request.id
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "⏭️ Skip",
                            "emoji": True
                        },
                        "style": "danger",
                        "action_id": "skip_lead",
                        "value": request.id
                    }
                ]
            }
        ]


# Singleton instance
slack_bot = SlackBot()
