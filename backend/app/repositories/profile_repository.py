# backend/app/repositories/profile_repository.py
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.core.paths import DATA_DIR
from app.models.profile import ProfileMaster

_PROFILE_PATH = DATA_DIR / "profile_master.json"
_PARTIAL_PATH = DATA_DIR / "profile_partial.json"


class ProfileNotFoundError(Exception):
    pass


class ProfileRepository:
    def __init__(self, path: Path = _PROFILE_PATH, partial_path: Path = _PARTIAL_PATH) -> None:
        self._partial_path = partial_path
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, profile: ProfileMaster) -> None:
        self._path.write_text(
            profile.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )

    def load(self) -> ProfileMaster:
        if not self._path.exists():
            raise ProfileNotFoundError(
                f"No profile found at {self._path}. "
                "Upload a resume to create your profile."
            )
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return ProfileMaster.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Stored profile is corrupted: {exc}") from exc

    def exists(self) -> bool:
        return self._path.exists()

    def delete(self) -> None:
        if self._path.exists():
            self._path.unlink()

    def save_partial(self, profile: ProfileMaster) -> None:
        self._partial_path.parent.mkdir(parents=True, exist_ok=True)
        self._partial_path.write_text(
            profile.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )

    def load_partial(self) -> ProfileMaster:
        if not self._partial_path.exists():
            raise ProfileNotFoundError("No partial profile found. Run /ingest first.")
        try:
            data = json.loads(self._partial_path.read_text(encoding="utf-8"))
            return ProfileMaster.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Partial profile is corrupted: {exc}") from exc

    def partial_exists(self) -> bool:
        return self._partial_path.exists()

    def delete_partial(self) -> None:
        if self._partial_path.exists():
            self._partial_path.unlink()
