"""services/upload_security.py — Validation et stockage sécurisé des fichiers."""
from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)

from config import settings

MAX_UPLOAD_SIZE = 10 * 1024 * 1024

ALLOWED_MIME_TYPES: dict[str, set[str]] = {
    "image/*": {"image/jpeg", "image/png", "image/webp", "image/gif"},
    "application/pdf": {"application/pdf"},
}


class UploadRejected(Exception):
    """Levée si le fichier uploadé est rejeté pour raison de sécurité."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _normalize_allowed_types(allowed_types: Iterable[str]) -> set[str]:
    normalized: set[str] = set()
    for item in allowed_types:
        if item in ALLOWED_MIME_TYPES:
            normalized.update(ALLOWED_MIME_TYPES[item])
        else:
            normalized.add(item)
    return normalized


def _detect_mime_type(file_bytes: bytes) -> str:
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if file_bytes.startswith(b"\x89PNG"):
        return "image/png"
    if len(file_bytes) >= 12 and file_bytes[8:12] == b"WEBP":
        return "image/webp"
    if file_bytes.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if file_bytes.startswith(b"%PDF"):
        return "application/pdf"
    raise UploadRejected("Invalid file signature")


def validate_upload(
    file_bytes: bytes,
    filename: str,
    allowed_types: list[str] = None,
) -> str:
    """Valide la taille et les magic bytes, puis retourne le vrai MIME détecté."""
    if allowed_types is None:
        allowed_types = ["image/jpeg", "image/png", "image/webp", "application/pdf"]
    if not file_bytes:
        raise UploadRejected("Empty file")
    if len(file_bytes) >= MAX_UPLOAD_SIZE:
        raise UploadRejected("File exceeds 10MB limit")

    detected_mime = _detect_mime_type(file_bytes)
    allowed = _normalize_allowed_types(allowed_types)
    if detected_mime not in allowed:
        raise UploadRejected(
            f"MIME type {detected_mime} not allowed for {filename}"
        )
    return detected_mime


async def validate_and_store(
    file_bytes: bytes,
    filename: str,
    store_id: int,
    mime_type: str | None = None,
) -> dict:
    """Valide le fichier puis le stocke sur S3 si configuré, sinon en local sous /tmp/uploads."""
    detected_mime = validate_upload(file_bytes, filename)
    safe_name = os.path.basename(filename) or "upload.bin"
    object_name = f"{uuid.uuid4().hex}_{safe_name}"

    bucket = (getattr(settings, "S3_BUCKET", "") or "").strip()
    s3_endpoint = (getattr(settings, "S3_ENDPOINT", "") or "").strip()
    access_key = (getattr(settings, "S3_ACCESS_KEY", "") or "").strip()
    secret_key = (getattr(settings, "S3_SECRET_KEY", "") or "").strip()

    if bucket:
        try:
            import boto3

            client_kwargs = {
                "region_name": getattr(settings, "S3_REGION", "us-east-1"),
                "aws_access_key_id": access_key or None,
                "aws_secret_access_key": secret_key or None,
            }
            if s3_endpoint:
                client_kwargs["endpoint_url"] = s3_endpoint

            s3_client = boto3.client("s3", **client_kwargs)
            key = f"uploads/{store_id}/{object_name}"
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=file_bytes,
                ContentType=detected_mime,
            )

            public_url = (getattr(settings, "S3_PUBLIC_URL", "") or "").strip()
            if public_url:
                url = f"{public_url.rstrip('/')}/{key}"
            elif s3_endpoint:
                url = f"{s3_endpoint.rstrip('/')}/{bucket}/{key}"
            else:
                url = None

            return {
                "url": url,
                "stored": True,
                "filename": safe_name,
                "size": len(file_bytes),
                "mime_type": detected_mime,
            }
        except Exception as _exc:
            logger.warning("operation failed: %s", _exc)
            # En dev/CI, boto3 ou le backend S3 peut être absent : fallback local.
            pass

    target_dir = Path("/tmp/uploads") / str(store_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / object_name
    target_path.write_bytes(file_bytes)

    return {
        "url": str(target_path),
        "stored": True,
        "filename": safe_name,
        "size": len(file_bytes),
        "mime_type": detected_mime,
    }
