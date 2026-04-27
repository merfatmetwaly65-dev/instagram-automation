from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Config, Campaign, ProcessedComment
from instagram import InstagramClient
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ConfigIn(BaseModel):
    access_token: str
    page_id: str
    instagram_account_id: str


class CampaignIn(BaseModel):
    name: str
    post_id: str
    keywords: str
    comment_reply: str
    dm_message: str
    is_active: bool = True


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    keywords: Optional[str] = None
    comment_reply: Optional[str] = None
    dm_message: Optional[str] = None
    is_active: Optional[bool] = None


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    config = db.query(Config).order_by(Config.id.desc()).first()
    if not config:
        return {"configured": False}
    return {
        "configured": True,
        "page_id": config.page_id,
        "instagram_account_id": config.instagram_account_id,
        "token_preview": config.access_token[:12] + "..." if config.access_token else None,
    }


@router.post("/config")
async def save_config(data: ConfigIn, db: Session = Depends(get_db)):
    # Verify token works
    client = InstagramClient(data.access_token)
    valid = await client.verify_token(data.instagram_account_id)
    await client.close()

    if not valid:
        raise HTTPException(status_code=400, detail="Invalid access token or Instagram account ID")

    config = db.query(Config).order_by(Config.id.desc()).first()
    if config:
        config.access_token = data.access_token
        config.page_id = data.page_id
        config.instagram_account_id = data.instagram_account_id
    else:
        config = Config(
            access_token=data.access_token,
            page_id=data.page_id,
            instagram_account_id=data.instagram_account_id,
        )
        db.add(config)

    db.commit()
    return {"success": True, "message": "Credentials saved and verified."}


# ── Campaigns ─────────────────────────────────────────────────────────────────

def campaign_to_dict(c: Campaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "post_id": c.post_id,
        "post_caption": c.post_caption,
        "post_thumbnail": c.post_thumbnail,
        "keywords": c.keywords,
        "comment_reply": c.comment_reply,
        "dm_message": c.dm_message,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.id.desc()).all()
    return [campaign_to_dict(c) for c in campaigns]


@router.post("/campaigns")
async def create_campaign(data: CampaignIn, db: Session = Depends(get_db)):
    config = db.query(Config).order_by(Config.id.desc()).first()

    post_caption = None
    post_thumbnail = None

    if config:
        client = InstagramClient(config.access_token)
        details = await client.get_post_details(data.post_id)
        await client.close()
        if details:
            post_caption = details.get("caption")
            post_thumbnail = details.get("thumbnail")

    campaign = Campaign(
        name=data.name,
        post_id=data.post_id,
        post_caption=post_caption,
        post_thumbnail=post_thumbnail,
        keywords=data.keywords,
        comment_reply=data.comment_reply,
        dm_message=data.dm_message,
        is_active=data.is_active,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign_to_dict(campaign)


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, data: CampaignUpdate, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)
    return campaign_to_dict(campaign)


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"success": True}


@router.post("/campaigns/{campaign_id}/toggle")
def toggle_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.is_active = not campaign.is_active
    db.commit()
    return {"is_active": campaign.is_active}


# ── Post preview ──────────────────────────────────────────────────────────────

@router.get("/post-preview/{post_id}")
async def get_post_preview(post_id: str, db: Session = Depends(get_db)):
    config = db.query(Config).order_by(Config.id.desc()).first()
    if not config:
        raise HTTPException(status_code=400, detail="No Instagram credentials configured")

    client = InstagramClient(config.access_token)
    details = await client.get_post_details(post_id)
    await client.close()

    if not details:
        raise HTTPException(status_code=404, detail="Post not found or inaccessible")

    return details


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_campaigns = db.query(Campaign).count()
    active_campaigns = db.query(Campaign).filter(Campaign.is_active == True).count()  # noqa: E712
    total_processed = db.query(ProcessedComment).count()
    return {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_processed": total_processed,
    }
