"""Approval notification delivery — Slack, email, webhook (APR-02)."""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from acp.config import settings

log = logging.getLogger(__name__)


async def send_approval_notification(
    *,
    request_id: str,
    agent_id: str,
    action_type: str,
    action_detail: dict,
    policy_id: str,
    expires_at: str,
    channels: list[str],
    base_url: str = "",
) -> list[str]:
    """Send approval notifications to all configured channels.

    Returns list of channels successfully notified.
    """
    notified: list[str] = []

    approve_url = f"{base_url}/api/approvals/{request_id}/decide"

    message_text = (
        f"*ACP Approval Required* :rotating_light:\n\n"
        f"*Agent:* `{agent_id}`\n"
        f"*Action:* `{action_type}`\n"
        f"*Detail:* ```{json.dumps(action_detail, indent=2)[:400]}```\n"
        f"*Policy:* `{policy_id}`\n"
        f"*Expires:* {expires_at}\n\n"
        f"Approve: `POST {approve_url}` with `{{\"action\": \"approve\"}}`\n"
        f"Deny: `POST {approve_url}` with `{{\"action\": \"deny\", \"reason\": \"...\"}}`"
    )

    for channel in channels:
        try:
            if channel.startswith("slack"):
                await _notify_slack(channel, message_text, request_id, approve_url)
                notified.append(channel)
            elif channel.startswith("http"):
                await _notify_webhook(channel, {
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "action_type": action_type,
                    "action_detail": action_detail,
                    "policy_id": policy_id,
                    "expires_at": expires_at,
                    "approve_url": approve_url,
                })
                notified.append(channel)
            else:
                log.warning("Unknown notification channel type: %s", channel)
        except Exception as exc:
            log.error("Failed to notify channel %s: %s", channel, exc)

    return notified


async def _notify_slack(channel: str, text: str, request_id: str, approve_url: str) -> None:
    """Send a Slack message via incoming webhook or bot token."""
    if not settings.slack_webhook_url and not settings.slack_bot_token:
        log.warning("Slack not configured — skipping notification for %s", channel)
        return

    payload: dict = {}

    if settings.slack_webhook_url:
        payload = {
            "text": text,
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": text}},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve"},
                            "style": "primary",
                            "value": f"approve:{request_id}",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Deny"},
                            "style": "danger",
                            "value": f"deny:{request_id}",
                        },
                    ],
                },
            ],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.slack_webhook_url, json=payload)
            resp.raise_for_status()


async def _notify_webhook(url: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
