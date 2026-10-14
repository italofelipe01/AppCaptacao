from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pyodbc
from werkzeug.security import check_password_hash

from app_core import app as legacy_app


class DesktopAppError(Exception):
    pass


class DesktopPermissionError(DesktopAppError):
    pass


@dataclass
class DesktopBackend:
    current_user: dict[str, Any] | None = None
    execution_credentials: dict[str, str] = field(
        default_factory=lambda: {
            "email": "",
            "senha": "",
            "sharepoint_link": "",
        }
    )

    def _apply_session_state(self) -> None:
        legacy_app.session.clear()
        if not self.current_user:
            return

        legacy_app.session["user_id"] = self.current_user["id"]
        legacy_app.session["user_login"] = self.current_user["login"]
        legacy_app.session["user_email"] = self.current_user["email"]
        legacy_app.session["user_area"] = self.current_user["area"]
        legacy_app.session["user_access_id"] = self.current_user["access_id"]
        legacy_app.set_execution_preferences_for_current_session(
            self.execution_credentials.get("email", ""),
            self.execution_credentials.get("sharepoint_link", ""),
        )
