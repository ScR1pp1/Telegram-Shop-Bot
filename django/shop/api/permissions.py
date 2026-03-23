from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsTelegramClient(BasePermission):
    def has_permission(self, request, view) -> bool:
        return bool(request.user and getattr(request.user, "telegram_id", None))

