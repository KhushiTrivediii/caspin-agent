import logging
import httpx
import uuid
import json
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from backend.database import list_webhook_subscriptions, log_webhook_delivery

logger = logging.getLogger("webhook_dispatcher")

class WebhookDispatcher:
    """
    Asynchronously dispatches webhook events to registered HTTP targets with retry logic.
    """
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=5.0)

    async def dispatch(self, event_type: str, payload: Dict[str, Any]):
        """
        Scan registered subscriptions and dispatch the payload if the event matches.
        """
        try:
            subscriptions = await list_webhook_subscriptions()
        except Exception as e:
            logger.error(f"Failed to fetch webhook subscriptions from DB: {e}")
            return

        active_subs = [s for s in subscriptions if s.get("is_active")]
        if not active_subs:
            return

        tasks = []
        for sub in active_subs:
            event_types = sub.get("event_types") or []
            if event_type in event_types or "*" in event_types:
                tasks.append(self._dispatch_to_subscriber(sub, event_type, payload))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _dispatch_to_subscriber(self, sub: Dict[str, Any], event_type: str, payload: Dict[str, Any]):
        sub_id = sub["id"]
        url = sub["url"]
        secret = sub.get("secret")

        headers = {
            "Content-Type": "application/json",
            "X-Caspin-Event": event_type,
            "X-Caspin-Subscription-ID": sub_id,
        }
        if secret:
            # Add simple authentication header
            headers["X-Caspin-Signature"] = secret

        from fastapi.encoders import jsonable_encoder
        webhook_payload = {
            "event_id": f"EVT-{uuid.uuid4().hex[:12].upper()}",
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": jsonable_encoder(payload)
        }

        max_attempts = 3
        attempt = 1
        success = False
        status_code = None
        response_body = None

        while attempt <= max_attempts:
            try:
                response = await self.client.post(url, json=webhook_payload, headers=headers)
                status_code = response.status_code
                response_body = response.text[:1000] # Cap logged response length

                if 200 <= status_code < 300:
                    success = True
                    break
                else:
                    logger.warning(f"Webhook subscription {sub_id} returned status {status_code} on attempt {attempt}")
            except Exception as e:
                response_body = str(e)
                logger.warning(f"Error dispatching webhook to {url} on attempt {attempt}: {e}")

            # Backoff before retrying
            await asyncio.sleep(attempt * 0.5)
            attempt += 1

        # Log delivery outcome in the DB
        log_id = f"WLOG-{uuid.uuid4().hex[:10].upper()}"
        try:
            await log_webhook_delivery(
                log_id=log_id,
                subscription_id=sub_id,
                event_type=event_type,
                url=url,
                status_code=status_code,
                attempt=min(attempt, max_attempts),
                success=success,
                response_body=response_body,
            )
        except Exception as e:
            logger.error(f"Failed to log webhook delivery to DB: {e}")

# Global singleton dispatcher
webhook_dispatcher = WebhookDispatcher()
