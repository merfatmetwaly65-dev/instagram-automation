from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(Text, nullable=False)
    page_id = Column(String(64), nullable=False)
    instagram_account_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, default="Untitled Campaign")
    post_id = Column(String(64), nullable=False)
    post_caption = Column(Text, nullable=True)
    post_thumbnail = Column(Text, nullable=True)
    keywords = Column(Text, nullable=False)          # comma-separated
    comment_reply = Column(Text, nullable=False)
    dm_message = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    @property
    def keyword_list(self):
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]


class ProcessedComment(Base):
    __tablename__ = "processed_comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String(64), unique=True, nullable=False, index=True)
    campaign_id = Column(Integer, nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
