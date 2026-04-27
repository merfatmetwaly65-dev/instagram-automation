import httpx
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class InstagramClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _request(self, method: str, endpoint: str, retries: int = 3, **kwargs) -> dict:
        """Make a Graph API request with retry/backoff on rate limits."""
        url = f"{GRAPH_API_BASE}/{endpoint}"
        params = kwargs.pop("params", {})
        params["access_token"] = self.access_token

        for attempt in range(retries):
            try:
                resp = await self.client.request(method, url, params=params, **kwargs)
                data = resp.json()

                if resp.status_code == 200:
                    logger.info(f"API {method} /{endpoint} → 200 OK")
                    return data

                error = data.get("error", {})
                error_code = error.get("code")

                # Rate limit: code 4 or 32
                if error_code in (4, 32) and attempt < retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited. Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                    continue

                logger.error(f"API error: {data}")
                raise Exception(f"Instagram API error: {error.get('message', 'Unknown error')}")

            except httpx.RequestError as e:
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise Exception(f"Network error: {e}")

        raise Exception("Max retries exceeded")

    async def reply_to_comment(self, comment_id: str, message: str) -> dict:
        """Post a public reply to a comment."""
        logger.info(f"Replying to comment {comment_id}")
        result = await self._request(
            "POST",
            f"{comment_id}/replies",
            json={"message": message}
        )
        logger.info(f"Comment reply sent: {result}")
        return result

    async def send_dm(self, instagram_user_id: str, message: str, page_id: str) -> dict:
        """Send a private DM via the Instagram Messaging API."""
        logger.info(f"Sending DM to user {instagram_user_id}")
        result = await self._request(
            "POST",
            f"{page_id}/messages",
            json={
                "recipient": {"id": instagram_user_id},
                "message": {"text": message},
                "messaging_type": "RESPONSE"
            }
        )
        logger.info(f"DM sent: {result}")
        return result

    async def get_post_details(self, post_id: str) -> Optional[dict]:
        """Fetch post thumbnail URL and caption."""
        logger.info(f"Fetching post details for {post_id}")
        try:
            result = await self._request(
                "GET",
                post_id,
                params={"fields": "id,caption,media_url,thumbnail_url,timestamp,media_type"}
            )
            return {
                "id": result.get("id"),
                "caption": result.get("caption", "")[:200],
                "thumbnail": result.get("thumbnail_url") or result.get("media_url"),
                "media_type": result.get("media_type"),
                "timestamp": result.get("timestamp"),
            }
        except Exception as e:
            logger.error(f"Failed to fetch post details: {e}")
            return None

    async def verify_token(self, instagram_account_id: str) -> bool:
        """Check if the token is valid by fetching account info."""
        try:
            result = await self._request(
                "GET",
                instagram_account_id,
                params={"fields": "id,username"}
            )
            return "id" in result
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()
