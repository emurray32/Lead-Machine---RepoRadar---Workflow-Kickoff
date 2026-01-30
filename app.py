"""
Lead Machine - Apollo Prospector
Flask application for processing RepoRadar webhooks and managing lead approval workflow.
"""
import logging
import hashlib
import hmac
import time
import uuid
from flask import Flask, request, jsonify

from config import config
from schema import RepoRadarPayload, ApprovalRequest
from storage import init_db, save_approval_request, get_approval_request, update_approval_status
from apollo_client import apollo_client
from slack_bot import slack_bot
from email_gen import generate_personalized_email, format_i18n_signals

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def verify_slack_signature(request) -> bool:
    """Verify that the request came from Slack."""
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Check timestamp to prevent replay attacks
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{request.get_data(as_text=True)}"
    expected_signature = "v0=" + hmac.new(
        config.SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "apollo-prospector"})


@app.route("/webhook/reporadar", methods=["POST"])
def handle_reporadar_webhook():
    """
    Handle incoming webhooks from RepoRadar.

    Expected payload:
    {
        "company": "Shopify",
        "domain": "shopify.com",
        "signal_type": "NEW_LANG_FILE",
        "signal_summary": "Added French and German locale files",
        "languages": ["fr", "de"],
        "author": "developer-username",
        "url": "https://github.com/Shopify/repo/commit/abc123",
        "metadata": {}
    }
    """
    try:
        # Parse and validate payload
        data = request.get_json()
        logger.info(f"Received webhook: {data}")

        payload = RepoRadarPayload(**data)

        # Step 1: Search for contacts at the company
        contacts = apollo_client.search_people(payload.domain)

        if not contacts:
            logger.warning(f"No contacts found for domain: {payload.domain}")
            return jsonify({
                "status": "skipped",
                "reason": "no_contacts_found",
                "domain": payload.domain
            }), 200

        # Step 2: Pick the best contact (first one for now, could add scoring)
        contact = contacts[0]

        if not contact.email:
            logger.warning(f"Best contact has no email: {contact.display_name}")
            return jsonify({
                "status": "skipped",
                "reason": "no_email",
                "contact": contact.display_name
            }), 200

        # Step 3: Generate personalized email
        subject, body = generate_personalized_email(payload, contact)

        # Step 4: Create approval request
        approval_request = ApprovalRequest(
            id=str(uuid.uuid4()),
            company=payload.company,
            domain=payload.domain,
            signal_summary=payload.signal_summary,
            contact_id=contact.id,
            contact_name=contact.display_name,
            contact_title=contact.title,
            contact_email=contact.email,
            personalized_subject=subject,
            personalized_email=body,
            i18n_signals=format_i18n_signals(payload)
        )

        # Step 5: Save to database
        save_approval_request(approval_request)

        # Step 6: Post to Slack for approval
        slack_ts = slack_bot.post_approval_card(approval_request)
        update_approval_status(approval_request.id, "pending", slack_ts)

        return jsonify({
            "status": "pending_approval",
            "request_id": approval_request.id,
            "company": payload.company,
            "contact": contact.display_name
        }), 200

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return jsonify({"error": "Invalid payload", "details": str(e)}), 400
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/slack/interactions", methods=["POST"])
def handle_slack_interactions():
    """Handle Slack button interactions."""

    # Verify Slack signature
    if not verify_slack_signature(request):
        logger.warning("Invalid Slack signature")
        return jsonify({"error": "Invalid signature"}), 401

    try:
        # Slack sends payload as form-encoded JSON string
        import json
        payload = json.loads(request.form.get("payload", "{}"))

        action = payload.get("actions", [{}])[0]
        action_id = action.get("action_id")
        request_id = action.get("value")
        channel = payload.get("channel", {}).get("id")
        message_ts = payload.get("message", {}).get("ts")

        logger.info(f"Slack interaction: {action_id} for request {request_id}")

        # Get the approval request
        approval_request = get_approval_request(request_id)
        if not approval_request:
            return jsonify({"error": "Request not found"}), 404

        if action_id == "approve_lead":
            return handle_approve(approval_request, channel, message_ts)
        elif action_id == "skip_lead":
            return handle_skip(approval_request, channel, message_ts)
        elif action_id == "edit_lead":
            return handle_edit(approval_request)
        elif action_id == "regenerate_lead":
            return handle_regenerate(approval_request, channel, message_ts)
        else:
            return jsonify({"error": "Unknown action"}), 400

    except Exception as e:
        logger.error(f"Error handling Slack interaction: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


def handle_approve(request: ApprovalRequest, channel: str, message_ts: str):
    """Handle lead approval - create contact and add to sequence."""
    try:
        # Create contact in Apollo with custom fields
        name_parts = request.contact_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        custom_fields = {
            "personalized_subject": request.personalized_subject,
            "personalized_email_1": request.personalized_email,
            "i18n_signals": request.i18n_signals
        }

        # Create the contact
        contact_response = apollo_client.create_contact(
            email=request.contact_email,
            first_name=first_name,
            last_name=last_name,
            organization_name=request.company,
            title=request.contact_title,
            custom_fields=custom_fields
        )

        new_contact_id = contact_response.get("contact", {}).get("id")

        # Add to sequence
        if new_contact_id:
            apollo_client.add_to_sequence(new_contact_id)

        # Update status
        update_approval_status(request.id, "approved")

        # Update Slack card
        slack_bot.update_card_approved(channel, message_ts, request)

        return jsonify({"status": "approved"}), 200

    except Exception as e:
        logger.error(f"Error approving lead: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def handle_skip(request: ApprovalRequest, channel: str, message_ts: str):
    """Handle lead skip."""
    update_approval_status(request.id, "skipped")
    slack_bot.update_card_rejected(channel, message_ts, request)
    return jsonify({"status": "skipped"}), 200


def handle_edit(request: ApprovalRequest):
    """Handle edit request - opens modal (placeholder)."""
    # TODO: Implement modal for editing email
    return jsonify({"status": "edit_not_implemented"}), 501


def handle_regenerate(request: ApprovalRequest, channel: str, message_ts: str):
    """Handle regenerate request - regenerate email with AI."""
    # TODO: Implement regeneration
    return jsonify({"status": "regenerate_not_implemented"}), 501


if __name__ == "__main__":
    # Initialize database on startup
    init_db()

    # Validate configuration
    missing = config.validate()
    if missing:
        logger.warning(f"Missing configuration: {', '.join(missing)}")

    # Run the app
    app.run(host="0.0.0.0", port=5000, debug=True)
