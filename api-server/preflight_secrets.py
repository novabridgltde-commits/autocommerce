"""preflight_secrets.py — Vérification des secrets critiques au démarrage.

Vérifie que les 4 secrets sensibles sont :
  1. Présents (non vides)
  2. Ne commencent pas par "CHANGE_ME" / "changeme" (valeurs placeholder)
  3. Pour ENCRYPTION_KEY : sont une clé Fernet valide (validation déléguée à pydantic
     dans config.Settings.validate_fernet_key — ici on contrôle seulement le placeholder).

Comportement :
  • CLI       : `python preflight_secrets.py`
                Sortie 0 + "✅ All secrets configured" si OK, sinon RuntimeError + exit 1.
  • Lifespan  : appelé par `main.py:lifespan` AVANT toute autre initialisation
                (raise RuntimeError -> le serveur refuse de démarrer).

Aucune valeur de secret n'est jamais loguée ni affichée.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Variables à vérifier (cf. cahier des charges — section secrets critiques)
REQUIRED_SECRETS: tuple[str, ...] = (
    "JWT_SECRET_KEY",
    "ENCRYPTION_KEY",
    "CSRF_SECRET",
    "INTERNAL_HEALTH_TOKEN",
)

# Préfixes interdits (case-insensitive)
PLACEHOLDER_PREFIXES: tuple[str, ...] = ("change_me", "changeme")


def _is_placeholder(value: str) -> bool:
    """Retourne True si la valeur ressemble à un placeholder du .env.example."""
    lowered = value.strip().lower()
    return any(lowered.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def check_secrets() -> None:
    """Lève RuntimeError si l'un des secrets critiques est manquant ou placeholder.

    N'inclut JAMAIS la valeur du secret dans le message d'erreur — seulement son nom.
    """
    missing: list[str] = []
    placeholders: list[str] = []

    for name in REQUIRED_SECRETS:
        raw = os.environ.get(name, "")
        if not raw or not raw.strip():
            missing.append(name)
            continue
        if _is_placeholder(raw):
            placeholders.append(name)

    if missing or placeholders:
        parts: list[str] = ["Preflight secrets check FAILED."]
        if missing:
            parts.append(f"Missing or empty: {', '.join(missing)}.")
        if placeholders:
            parts.append(
                f"Still set to a CHANGE_ME placeholder: {', '.join(placeholders)}."
            )
        parts.append(
            "Generate fresh values with: bash scripts/generate_secrets.sh "
            "and paste them into autocommerce-api/.env"
        )
        raise RuntimeError(" ".join(parts))

    logger.info("preflight_secrets: %d critical secrets validated", len(REQUIRED_SECRETS))


def _load_env_file_if_present() -> None:
    """Pour l'usage CLI uniquement : charge un éventuel .env adjacent.

    Au démarrage de FastAPI, pydantic-settings (config.py) a déjà chargé le .env
    avant que lifespan ne s'exécute, donc os.environ est déjà peuplé. En CLI direct
    sans uvicorn, on charge le .env manuellement pour permettre le test de recette.
    """
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Ne pas écraser une variable déjà définie dans l'environnement
            os.environ.setdefault(key, value)
    except OSError as exc:
        # Pas de bare except — log explicite, on continue (le check fera échouer
        # proprement si une variable manque vraiment).
        logger.warning("preflight_secrets: cannot read .env file: %s", exc)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    _load_env_file_if_present()
    try:
        check_secrets()
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    print("✅ All secrets configured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
