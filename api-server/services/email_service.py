"""services/email_service.py — Async email delivery service.

Sends transactional emails (password reset, invoice, subscription reminders).
Uses SMTP when configured; logs a warning and no-ops when SMTP is not configured.
"""
from __future__ import annotations

import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when an email cannot be delivered."""


def _get_smtp_config() -> dict[str, Any] | None:
    host = os.getenv("SMTP_HOST")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.getenv("SMTP_PORT", "587")),
        "username": os.getenv("SMTP_USERNAME", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_addr": os.getenv("SMTP_FROM", os.getenv("SMTP_USERNAME", "noreply@autocommerce.ai")),
        "use_tls": os.getenv("SMTP_USE_TLS", "1") not in ("0", "false", "False"),
    }


async def _send_email(to: str, subject: str, html_body: str) -> None:
    """Low-level email sender. No-ops gracefully when SMTP not configured."""
    cfg = _get_smtp_config()
    if not cfg:
        logger.warning(
            "email_service: SMTP_HOST not configured — email NOT sent to=%s subject=%s",
            to, subject,
        )
        return

    import smtplib
    import ssl

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as smtp:
            if cfg["use_tls"]:
                smtp.starttls(context=context)
            if cfg["username"]:
                smtp.login(cfg["username"], cfg["password"])
            smtp.sendmail(cfg["from_addr"], to, msg.as_string())
        logger.info("email_service: sent to=%s subject=%s", to, subject)
    except Exception as exc:
        logger.error("email_service: delivery failed to=%s error=%s", to, exc)
        raise EmailDeliveryError(str(exc)) from exc


async def send_password_reset_email(to_email: str, reset_token: str, store_name: str = "AutoCommerce") -> None:
    """Send a password-reset link to the user."""
    frontend_url = os.getenv("FRONTEND_URL", "")
    reset_url = f"{frontend_url}/reset-password?token={reset_token}"
    subject = f"[{store_name}] Réinitialisation de votre mot de passe"
    html = f"""
    <p>Bonjour,</p>
    <p>Cliquez sur le lien ci-dessous pour réinitialiser votre mot de passe (valable 1 heure) :</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.</p>
    <p>— L'équipe {store_name}</p>
    """
    await _send_email(to_email, subject, html)


async def send_invoice_email(to_email: str, invoice_url: str, order_ref: str, store_name: str = "AutoCommerce") -> None:
    """Send an invoice/payment confirmation email."""
    subject = f"[{store_name}] Votre facture #{order_ref}"
    html = f"""
    <p>Bonjour,</p>
    <p>Merci pour votre commande #{order_ref}.</p>
    <p>Votre facture est disponible ici : <a href="{invoice_url}">{invoice_url}</a></p>
    <p>— L'équipe {store_name}</p>
    """
    await _send_email(to_email, subject, html)


async def send_subscription_reminder_email(to_email: str, store_name: str, days_until_expiry: int) -> None:
    """Send a subscription expiry reminder email to a store admin."""
    subject = f"[AutoCommerce] Rappel — abonnement {store_name} expire dans {days_until_expiry} jours"
    html = f"""
    <p>Bonjour,</p>
    <p>L'abonnement de la boutique <strong>{store_name}</strong> expire dans <strong>{days_until_expiry} jour(s)</strong>.</p>
    <p>Veuillez renouveler votre abonnement pour continuer à bénéficier de nos services.</p>
    <p>— L'équipe AutoCommerce</p>
    """
    await _send_email(to_email, subject, html)
