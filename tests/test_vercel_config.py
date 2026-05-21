# -*- coding: utf-8 -*-
import importlib


def test_vercel_engine_options_are_psycopg2_safe(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.com/db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    import e16_app.config as config_module

    try:
        config_module = importlib.reload(config_module)
        options = config_module.ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS

        assert options["poolclass"].__name__ == "NullPool"
        assert "prepare_threshold" not in options.get("connect_args", {})
    finally:
        monkeypatch.delenv("VERCEL", raising=False)
        monkeypatch.setenv("APP_ENV", "testing")
        importlib.reload(config_module)
