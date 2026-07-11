"""utils/whatsapp_client.py — WhatsApp Business API client wrapper."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """Thin wrapper around the WhatsApp Business API.

    Sends text/media messages via the Meta Graph API.
    """

    GRAPH_API_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, phone_number_id: str, access_token: str) -> None:
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    # ── Factory ────────────────────────────────────────────────────────────────
    @classmethod
    def from_settings(cls) -> WhatsAppClient:
        from config import settings
        return cls(
            phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID,
            access_token=settings.WHATSAPP_ACCESS_TOKEN,
        )

    @classmethod
    def from_store(cls, store: Any) -> WhatsAppClient:
        """Build a client from a Store ORM object (per-tenant BYOK)."""
        from config import settings
        token = getattr(store, "whatsapp_access_token", None) or settings.WHATSAPP_ACCESS_TOKEN
        phone_id = getattr(store, "whatsapp_phone_number_id", None) or settings.WHATSAPP_PHONE_NUMBER_ID
        return cls(phone_number_id=phone_id, access_token=token)

    # ── Message sending ────────────────────────────────────────────────────────
    async def send_text(self, to: str, body: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        }
        return await self._post(payload)

    async def send_template(self, to: str, template_name: str, language_code: str = "fr",
                            components: list | None = None) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components or [],
            },
        }
        return await self._post(payload)

    async def send_interactive_list(self, to: str, body_text: str,
                                    button_text: str, sections: list) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body_text},
                "action": {"button": button_text, "sections": sections},
            },
        }
        return await self._post(payload)

    async def send_interactive_buttons(self, to: str, body_text: str,
                                       buttons: list[dict]) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": buttons},
            },
        }
        return await self._post(payload)

    async def mark_as_read(self, message_id: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        return await self._post(payload)

    async def _post(self, payload: dict) -> dict:
        url = f"{self.GRAPH_API_URL}/{self.phone_number_id}/messages"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=self._headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "WhatsApp API error %s: %s — payload: %s",
                exc.response.status_code,
                exc.response.text,
                payload,
            )
            raise
        except Exception as exc:
            logger.error("WhatsApp API request failed: %s", exc)
            raise
