# -*- coding: utf-8 -*-
from urllib.parse import urljoin

from flask import current_app, url_for


def _normalize_origin(value: str | None) -> str | None:
    if not value:
        return None
    origin = value.strip().rstrip("/")
    if not origin:
        return None
    if not origin.startswith(("http://", "https://")):
        origin = f"https://{origin}"
    return origin


def app_origin() -> str | None:
    return _normalize_origin(
        current_app.config.get("APP_BASE_URL")
        or current_app.config.get("APP_URL")
    )


def public_origin() -> str | None:
    return _normalize_origin(current_app.config.get("PUBLIC_SITE_URL"))


def app_url_for(endpoint: str, **values) -> str:
    origin = app_origin()
    if not origin:
        return url_for(endpoint, _external=True, **values)
    path = url_for(endpoint, _external=False, **values)
    return urljoin(f"{origin}/", path.lstrip("/"))


def public_url(path: str = "/") -> str | None:
    origin = public_origin()
    if not origin:
        return None
    return urljoin(f"{origin}/", path.lstrip("/"))
