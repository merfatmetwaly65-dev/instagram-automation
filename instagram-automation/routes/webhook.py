import hashlib
import hmac
import json
import logging
import os
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Config, Campaign, ProcessedComment
from instagram import InstagramClient

logger = logging.getLogger(__name__)
router = APIRouter()

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "")
APP_SECRET = os.getenv("APP_SECRET", "")


def verify_signature(payload: bytes, signature_header: str) -> bool:
    if not APP_SECRET or not signature_header:
        logger.warning("No app secret or signature header — skipping validation")
        return True  # In dev, allow through; in prod APP_SECRET must be set
    if not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        APP_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.get("/webhook/instagram")
async def verify_webhook(request: Request):
    """Handle the Facebook webhook verification challenge."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(content=challenge)

    logger.warning(f"Webhook verification failed. mode={mode} token={token}")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/instagram")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive and process Instagram webhook events."""
    raw_body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(raw_body, sig):
        logger.error("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info(f"Webhook received: {json.dumps(payload, indent=2)}")

    # Process comment events
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            value = change.get("value", {})
            await handle_comment_event(value, db)

    return {"status": "ok"}


async def handle_comment_event(value: dict, db: Session):
    comment_id = value.get("id")
    comment_text = value.get("text", "")
    media_id = value.get("media", {}).get("id") or value.get("media_id")
    commenter_id = value.get("from", {}).get("id")

    if not comment_id or not media_id:
        logger.warning("Missing comment_id or media_id in event")
        return

    # Deduplication check
    existing = db.query(ProcessedComment).filter(
        ProcessedComment.comment_id == comment_id
    ).first()
    if existing:
        logger.info(f"Comment {comment_id} already processed — skipping")
        return

    # Find matching active campaign
    campaigns = db.query(Campaign).filter(
        Campaign.post_id == media_id,
        Campaign.is_active == True  # noqa: E712
    ).all()

    matched_campaign = None
    for campaign in campaigns:
        for keyword in campaign.keyword_list:
            if keyword in comment_text.lower():
                matched_campaign = campaign
                break
        if matched_campaign:
            break

    if not matched_campaign:
        logger.info(f"No matching campaign for comment on post {media_id}")
        return

    # Load config
    config = db.query(Config).order_by(Config.id.desc()).first()
    if not config:
        logger.error("No Instagram config found in database")
        return

    client = InstagramClient(config.access_token)

    try:
        # Reply to comment
        if matched_campaign.comment_reply:
            await client.reply_to_comment(comment_id, matched_campaign.comment_reply)

        # Send DM
        if commenter_id and matched_campaign.dm_message:
            await client.send_dm(commenter_id, matched_campaign.dm_message, config.page_id)

        # Mark as processed
        processed = ProcessedComment(
            comment_id=comment_id,
            campaign_id=matched_campaign.id
        )
        db.add(processed)
        db.commit()
        logger.info(f"Comment {comment_id} processed for campaign {matched_campaign.id}")

    except Exception as e:
        logger.error(f"Error processing comment {comment_id}: {e}")
        db.rollback()
    finally:
        await client.close()
