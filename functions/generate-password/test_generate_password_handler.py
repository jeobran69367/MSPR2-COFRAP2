"""Tests unitaires pour la fonction serverless generate-password.

Le handler est chargé dynamiquement via importlib pour rester
exécutable tel quel par OpenFaaS (pas de package Python autour du
handler), tout en étant testable par pytest depuis n'importe quel
répertoire (local ou CI).
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).with_name("handler.py")
SPEC = importlib.util.spec_from_file_location("generate_password_handler", MODULE_PATH)
handler = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(handler)


def make_event(body):
    return SimpleNamespace(body=body)


def test_generate_secure_password_has_expected_length_and_charset():
    pwd = handler.generate_secure_password()

    assert len(pwd) == handler.PASSWORD_LENGTH
    assert any(c.isupper() for c in pwd)
    assert any(c.islower() for c in pwd)
    assert any(c.isdigit() for c in pwd)
    assert any(c in "!@#$%^&*()-_=+" for c in pwd)


def test_handle_rejects_invalid_json():
    response = handler.handle(make_event("not-json"), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"error": "Corps JSON invalide."}


def test_handle_rejects_missing_username():
    response = handler.handle(make_event(json.dumps({"username": "   "})), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"error": "Le champ 'username' est obligatoire."}


def test_handle_stores_generated_password(monkeypatch):
    cursor = SimpleNamespace(
        execute=lambda *args, **kwargs: None,
        close=lambda: None,
    )
    connection = SimpleNamespace(
        cursor=lambda: cursor,
        commit=lambda: None,
        close=lambda: None,
    )

    monkeypatch.setattr(handler, "generate_secure_password", lambda: "Aa1!Aa1!Aa1!Aa1!Aa1!Aa1!")
    monkeypatch.setattr(handler.bcrypt, "hashpw", lambda password, salt: b"hashed-password")
    monkeypatch.setattr(handler.bcrypt, "gensalt", lambda: b"salt")
    monkeypatch.setattr(handler, "password_to_qr_base64", lambda password: "qr-code")
    monkeypatch.setattr(handler, "get_db_connection", lambda: connection)

    response = handler.handle(make_event(json.dumps({"username": "john.doe"})), None)

    assert response["statusCode"] == 200
    payload = json.loads(response["body"])
    assert payload == {
        "username": "john.doe",
        "qr_code": "qr-code",
        "message": "Mot de passe généré et stocké avec succès.",
    }


def test_password_to_qr_base64_returns_valid_png():
    qr_b64 = handler.password_to_qr_base64("Aa1!Aa1!Aa1!Aa1!Aa1!Aa1!")
    raw = handler.base64.b64decode(qr_b64)

    assert raw.startswith(b"\x89PNG")


def test_handle_returns_database_error(monkeypatch):
    class FakeDbError(Exception):
        pass

    monkeypatch.setattr(handler.psycopg2, "Error", FakeDbError)
    monkeypatch.setattr(handler, "generate_secure_password", lambda: "Aa1!Aa1!Aa1!Aa1!Aa1!Aa1!")
    monkeypatch.setattr(handler.bcrypt, "hashpw", lambda password, salt: b"hashed-password")
    monkeypatch.setattr(handler.bcrypt, "gensalt", lambda: b"salt")
    monkeypatch.setattr(handler, "password_to_qr_base64", lambda password: "qr-code")

    def raise_db_error():
        raise FakeDbError("boom")

    monkeypatch.setattr(handler, "get_db_connection", raise_db_error)

    response = handler.handle(make_event(json.dumps({"username": "john.doe"})), None)

    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == {"error": "Erreur base de données : boom"}


def test_get_db_connection_falls_back_to_env_vars(monkeypatch):
    # Aucun fichier de secret monté (cas des tests / environnement local
    # sans OpenFaaS) : get_db_connection doit retomber sur les variables
    # d'environnement DB_HOST, DB_PORT, etc.
    monkeypatch.setenv("DB_HOST", "db.local")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "cofrap")
    monkeypatch.setenv("DB_USER", "cofrap_user")
    monkeypatch.setenv("DB_PASSWORD", "secret")

    captured = {}

    def fake_connect(**kwargs):
        captured.update(kwargs)
        return "connection"

    monkeypatch.setattr(handler.psycopg2, "connect", fake_connect)

    result = handler.get_db_connection()

    assert result == "connection"
    assert captured["host"] == "db.local"
    assert captured["port"] == 5432
    assert captured["dbname"] == "cofrap"
    assert captured["user"] == "cofrap_user"
    assert captured["password"] == "secret"
