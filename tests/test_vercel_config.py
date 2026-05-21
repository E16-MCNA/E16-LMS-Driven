# -*- coding: utf-8 -*-
import importlib
import sqlite3


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


def test_vercel_startup_self_heals_legacy_schema(monkeypatch, tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE users (
            id VARCHAR(36) PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            phone VARCHAR(20),
            is_active BOOLEAN NOT NULL DEFAULT 1,
            role VARCHAR(20) NOT NULL,
            created_at DATETIME NOT NULL,
            last_login DATETIME,
            login_count INTEGER NOT NULL DEFAULT 0,
            reset_token VARCHAR(100) UNIQUE,
            reset_token_expiry DATETIME
        );

        CREATE TABLE courses (
            id VARCHAR(36) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            short_description VARCHAR(500) NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            cover_image_url VARCHAR(500) NOT NULL DEFAULT '',
            total_lessons INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            is_deleted BOOLEAN NOT NULL DEFAULT 0,
            category_id VARCHAR(36),
            teacher_id VARCHAR(36) NOT NULL,
            rejection_note TEXT,
            submitted_at DATETIME,
            published_at DATETIME,
            created_at DATETIME NOT NULL
        );
        """
    )
    conn.close()

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    import e16_app.config as config_module

    try:
        importlib.reload(config_module)
        from e16_app import create_app
        from e16_app.extensions import db
        from sqlalchemy import inspect

        app = create_app()
        with app.app_context():
            inspector = inspect(db.engine)
            user_columns = {col["name"] for col in inspector.get_columns("users")}
            course_columns = {col["name"] for col in inspector.get_columns("courses")}

        assert {"must_change_password", "created_by", "temp_password_hash"} <= user_columns
        assert {"price", "tags", "level", "reviewed_by", "starts_at", "max_students"} <= course_columns
    finally:
        monkeypatch.delenv("VERCEL", raising=False)
        monkeypatch.setenv("APP_ENV", "testing")
        importlib.reload(config_module)
