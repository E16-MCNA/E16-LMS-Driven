# -*- coding: utf-8 -*-
from e16_app.urls import app_url_for, public_url


def test_app_url_for_prefers_configured_app_base_url(app):
    app.config["APP_BASE_URL"] = "https://app.e16.example/"
    with app.test_request_context("/", base_url="https://preview.vercel.app"):
        assert app_url_for("auth.login") == "https://app.e16.example/auth/login"
        assert (
            app_url_for("auth.reset_password", token="abc")
            == "https://app.e16.example/auth/reset-password/abc"
        )


def test_public_url_normalizes_domain_without_scheme(app):
    app.config["PUBLIC_SITE_URL"] = "www.e16.example/"
    with app.app_context():
        assert public_url("/") == "https://www.e16.example/"
        assert public_url("/courses/python") == "https://www.e16.example/courses/python"
