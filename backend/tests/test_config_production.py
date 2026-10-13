import os
import pytest
from backend.app import create_app

def test_production_missing_database_url(monkeypatch):
    # Set production env without DATABASE_URL
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    # Expect RuntimeError on app creation
    with pytest.raises(RuntimeError) as exc:
        create_app()
    assert 'DATABASE_URL must be set' in str(exc.value)

def test_production_with_database_url(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost/db')
    # Should create app without error
    app = create_app()
    assert app is not None

def test_development_fallback(monkeypatch):
    monkeypatch.delenv('APP_ENV', raising=False)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    # Should fallback to sqlite and not raise
    app = create_app()
    assert app.config['SQLALCHEMY_DATABASE_URI'].endswith('test.db')
