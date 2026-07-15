"""Tests unitaires pour la fonction serverless generate-2fa."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).with_name("handler.py")
SPEC = importlib.util.spec_from_file_location("generate_2fa_handler", MODULE_PATH)
handler = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(handler)


def make_event(body):
    return SimpleNamespace(body=body)


def test_handle_rejects_invalid_json():
    response = handler.handle(make_event("not-json"), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"error": "Corps JSON invalide."}


def test_handle_rejects_missing_username():
    response = handler.handle(make_event(json.dumps({"username": "  "})), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"error": "Le champ 'username' est obligatoire."}


def test_handle_returns_404_when_user_is_missing(monkeypatch):
    class FakeCursor:
        def execute(self, *args, **kwargs):
            pass

        def fetchone(self):
            return None

        def close(self):
            pass

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(handler, "get_fernet", lambda: object())
    monkeypatch.setattr(handler, "get_db_connection", lambda: FakeConnection())

    response = handler.handle(make_event(json.dumps({"username": "john.doe"})), None)

    assert response["statusCode"] == 404
    assert json.loads(response["body"]) == {
        "error": "Utilisateur 'john.doe' introuvable. Créez d'abord un mot de passe."
    }


def test_handle_generates_and_stores_secret(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.calls = []

        def execute(self, query, params=None):
            self.calls.append((query, params))

        def fetchone(self):
            return (1,)

        def close(self):
            self.calls.append(("close", None))

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.committed = False
            self.closed = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed = True

        def close(self):
            self.closed = True

    connection = FakeConnection()

    monkeypatch.setattr(handler, "get_fernet", lambda: object())
    monkeypatch.setattr(handler, "get_db_connection", lambda: connection)
    monkeypatch.setattr(handler, "generate_totp_secret", lambda: "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr(handler, "encrypt_secret", lambda secret, fernet: "encrypted-secret")
    monkeypatch.setattr(handler, "secret_to_qr_base64", lambda username, secret: "qr-code")

    response = handler.handle(make_event(json.dumps({"username": "john.doe"})), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "username": "john.doe",
        "qr_code": "qr-code",
        "message": "Secret 2FA généré et stocké avec succès.",
    }
    assert connection.committed is True
    assert connection.closed is True


def test_handle_returns_500_when_secret_key_is_missing(monkeypatch):
    def raise_runtime_error():
        raise RuntimeError("Secret 'totp-encryption-key' manquant.")

    monkeypatch.setattr(handler, "get_fernet", raise_runtime_error)

    response = handler.handle(make_event(json.dumps({"username": "john.doe"})), None)

    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == {"error": "Secret 'totp-encryption-key' manquant."}


def test_read_secret_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("TOTP_ENCRYPTION_KEY", "some-env-value")

    assert handler.read_secret("totp-encryption-key") == "some-env-value"


def test_get_fernet_builds_a_working_fernet(monkeypatch):
    key = handler.Fernet.generate_key().decode()
    monkeypatch.setenv("TOTP_ENCRYPTION_KEY", key)

    fernet = handler.get_fernet()
    token = fernet.encrypt(b"my-secret")

    assert fernet.decrypt(token) == b"my-secret"


def test_get_db_connection_passes_secrets_to_psycopg2(monkeypatch):
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

    assert handler.get_db_connection() == "connection"
    assert captured["host"] == "db.local"
    assert captured["dbname"] == "cofrap"


def test_generate_totp_secret_returns_base32_string():
    secret = handler.generate_totp_secret()

    assert isinstance(secret, str)
    assert len(secret) >= 16


def test_encrypt_secret_roundtrip():
    fernet = handler.Fernet(handler.Fernet.generate_key())

    encrypted = handler.encrypt_secret("JBSWY3DPEHPK3PXP", fernet)

    assert fernet.decrypt(encrypted.encode()).decode() == "JBSWY3DPEHPK3PXP"


def test_secret_to_qr_base64_returns_valid_png():
    qr_b64 = handler.secret_to_qr_base64("john.doe", "JBSWY3DPEHPK3PXP")
    raw = handler.base64.b64decode(qr_b64)

    assert raw.startswith(b"\x89PNG")


def test_handle_returns_500_on_db_error_during_lookup(monkeypatch):
    class FakeDbError(Exception):
        pass

    def raise_db_error():
        raise FakeDbError("connexion refusée")

    monkeypatch.setattr(handler.psycopg2, "Error", FakeDbError)
    monkeypatch.setattr(handler, "get_fernet", lambda: object())
    monkeypatch.setattr(handler, "get_db_connection", raise_db_error)

    response = handler.handle(make_event(json.dumps({"username": "john.doe"})), None)

    assert response["statusCode"] == 500
