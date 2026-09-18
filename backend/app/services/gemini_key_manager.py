"""Gemini API Key and Configuration Manager.

Manages primary and backup Gemini API keys, key modes (auto, primary, backup),
failover orchestration, and model configuration while strictly guarding against
key leakage in logs, representations, and exceptions.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
VALID_KEY_MODES = {"auto", "primary", "backup"}


class GeminiKeyManager:
    """Manages Gemini API primary and backup keys with safe masking and mode selection."""

    def __init__(
        self,
        primary_key: Optional[str] = None,
        backup_key: Optional[str] = None,
        mode: Optional[str] = None,
        model: Optional[str] = None,
        env_path: Optional[Path | str] = None,
    ) -> None:
        """Initialize the key manager.

        Loads from backend/.env if keys are not explicitly provided.
        """
        self._env_loaded = False
        self._load_environment(env_path)

        # Explicit overrides take precedence, then environment variables
        loaded_primary = primary_key or os.getenv("GEMINI_API_KEY_PRIMARY") or os.getenv("GEMINI_API_KEY")
        loaded_backup = backup_key or os.getenv("GEMINI_API_KEY_BACKUP")
        loaded_mode = mode or os.getenv("GEMINI_KEY_MODE", "auto")
        loaded_model = model or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

        self._primary_key = loaded_primary.strip() if loaded_primary and loaded_primary.strip() else None
        self._backup_key = loaded_backup.strip() if loaded_backup and loaded_backup.strip() else None

        # Mode normalization: auto, primary, or backup
        normalized_mode = loaded_mode.lower().strip() if loaded_mode else "auto"
        if normalized_mode not in VALID_KEY_MODES:
            logger.warning(
                "Invalid GEMINI_KEY_MODE '%s'. Defaulting to 'auto'.",
                normalized_mode,
            )
            normalized_mode = "auto"
        self._mode = normalized_mode

        self._model = loaded_model.strip() if loaded_model and loaded_model.strip() else DEFAULT_GEMINI_MODEL

    def _load_environment(self, env_path: Optional[Path | str] = None) -> None:
        """Load variables from .env file using python-dotenv safely."""
        try:
            from dotenv import load_dotenv

            if env_path is not None:
                target_path = Path(env_path)
            else:
                # backend/.env is located 2 levels up from backend/app/services/
                target_path = Path(__file__).resolve().parents[2] / ".env"

            if target_path.exists():
                load_dotenv(dotenv_path=target_path, override=False)
                self._env_loaded = True
        except ImportError:
            logger.warning("python-dotenv is not installed; using existing environment variables.")
        except Exception as error:
            logger.warning("Could not load .env file: %s", type(error).__name__)

    @property
    def mode(self) -> str:
        """Return the current key mode: 'auto', 'primary', or 'backup'."""
        return self._mode

    @property
    def model(self) -> str:
        """Return the configured Gemini model name."""
        return self._model

    @property
    def has_primary(self) -> bool:
        """Return whether a primary key is configured."""
        return bool(self._primary_key)

    @property
    def has_backup(self) -> bool:
        """Return whether a backup key is configured."""
        return bool(self._backup_key)

    @property
    def is_configured(self) -> bool:
        """Return whether at least one usable key is configured for the current mode."""
        if self._mode == "primary":
            return self.has_primary
        if self._mode == "backup":
            return self.has_backup
        # auto mode
        return self.has_primary or self.has_backup

    def get_key_candidates(self) -> List[Tuple[str, str]]:
        """Return ordered list of (key_label, api_key) based on the active mode.

        - 'auto': returns [('primary', key), ('backup', key)] (omitting missing keys)
        - 'primary': returns [('primary', key)] if present
        - 'backup': returns [('backup', key)] if present
        """
        candidates: List[Tuple[str, str]] = []

        if self._mode == "primary":
            if self._primary_key:
                candidates.append(("primary", self._primary_key))
        elif self._mode == "backup":
            if self._backup_key:
                candidates.append(("backup", self._backup_key))
        else:  # auto mode
            if self._primary_key:
                candidates.append(("primary", self._primary_key))
            if self._backup_key:
                candidates.append(("backup", self._backup_key))

        return candidates

    @staticmethod
    def mask_key(key: Optional[str]) -> str:
        """Safely mask an API key for diagnostic reporting without exposing credentials."""
        if not key:
            return "[NOT SET]"
        if len(key) <= 8:
            return "[CONFIGURED]"
        return f"{key[:4]}...{key[-4:]}"

    def get_status_summary(self) -> dict:
        """Return safe, non-sensitive operational status metadata."""
        return {
            "mode": self._mode,
            "model": self._model,
            "primary_configured": self.has_primary,
            "primary_masked": self.mask_key(self._primary_key),
            "backup_configured": self.has_backup,
            "backup_masked": self.mask_key(self._backup_key),
            "is_configured": self.is_configured,
        }

    def __repr__(self) -> str:
        """Ensure secret keys are never exposed via representation or debugging logs."""
        return (
            f"<GeminiKeyManager mode={self._mode!r} model={self._model!r} "
            f"primary_configured={self.has_primary} backup_configured={self.has_backup}>"
        )

    def __str__(self) -> str:
        """Safe human-readable string without credentials."""
        return self.__repr__()
