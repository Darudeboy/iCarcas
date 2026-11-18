from __future__ import annotations

from ios_restore.domain.ports import AuthPort


class AuthService:
    def __init__(self, adapter: AuthPort) -> None:
        self._adapter = adapter

    def login_interactive(self) -> dict[str, str]:
        self._adapter.begin_interactive_login()
        return self._adapter.auth_info()

    def logout(self) -> None:
        self._adapter.revoke_session()
