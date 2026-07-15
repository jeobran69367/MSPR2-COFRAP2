"""Tests unitaires pour la fonction serverless authenticate."""
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).with_name("handler.py")
SPEC = importlib.util.spec_from_file_location("authenticate_handler", MODULE_PATH)
handler = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(handler)


def make_event(body):
    return SimpleNamespace(body=body)


def test_handle_rejects_invalid_json():
    response = handler.handle(make_event("not-json"), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"error": "Corps JSON invalide."}


def test_handle_rejects_missing_fields():
    response = handler.handle(make_event(json.dumps({"username": "john.doe"})), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {
        "error": "Champs 'username', 'password' et 'totp_code' obligatoires."
    }


def test_handle_returns_404_when_user_is_missing(monkeypatch):
    class FakeCursor:
        def execute(self, *args, **kwargs):
            pass

        def fetchone(self):
            return None

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(handler, "get_fernet", lambda: object())
    monkeypatch.setattr(handler, "get_db_connection", lambda: FakeConnection())

    response = handler.handle(
        make_event(json.dumps({"username": "john.doe", "password": "pw", "totp_code": "123456"})),
        None,
    )

    assert response["statusCode"] == 404
    assert json.loads(response["body"]) == {"error": "Utilisateur introuvable."}


def test_handle_rejects_invalid_password(monkeypatch):
    class FakeCursor:
        def execute(self, *args, **kwargs):
            pass

        def fetchone(self):
            return ("hashed", "encrypted", int(datetime.now(UTC).timestamp()), 0)

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    class FakeFernet:
        def decrypt(self, value):
            return b"secret"

    monkeypatch.setattr(handler, "get_fernet", lambda: FakeFernet())
    monkeypatch.setattr(handler, "get_db_connection", lambda: FakeConnection())
    monkeypatch.setattr(handler.bcrypt, "checkpw", lambda password, hashed: False)

    response = handler.handle(
        make_event(json.dumps({"username": "john.doe", "password": "wrong", "totp_code": "123456"})),
        None,
    )

    assert response["statusCode"] == 401
    assert json.loads(response["body"]) == {"error": "Identifiants invalides."}


def test_handle_rejects_invalid_totp_code(monkeypatch):
    class FakeCursor:
        def execute(self, *args, **kwargs):
            pass

        def fetchone(self):
            return ("hashed", "encrypted", int(datetime.now(UTC).timestamp()), 0)

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    class FakeFernet:
        def decrypt(self, value):
            return b"secret"

    class FakeTotp:
        def __init__(self, secret):
            self.secret = secret

        def verify(self, code, valid_window=1):
            return False

    monkeypatch.setattr(handler, "get_fernet", lambda: FakeFernet())
    monkeypatch.setattr(handler, "get_db_connection", lambda: FakeConnection())
    monkeypatch.setattr(handler.bcrypt, "checkpw", lambda password, hashed: True)
    monkeypatch.setattr(handler.pyotp, "TOTP", lambda secret: FakeTotp(secret))

    response = handler.handle(
        make_event(json.dumps({"username": "john.doe", "password": "pw", "totp_code": "000000"})),
        None,
    )

    assert response["statusCode"] == 401
    assert json.loads(response["body"]) == {"error": "Code 2FA invalide."}


def test_handle_returns_authenticated_user(monkeypatch):
    now_ts = int(datetime.now(UTC).timestamp())

    class FakeCursor:
        def __init__(self):
            self.executed = []

        def execute(self, query, params=None):
            self.executed.append((query, params))

        def fetchone(self):
            return ("hashed", "encrypted", now_ts, 0)

        def close(self):
            self.executed.append(("close", None))

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

    class FakeFernet:
        def decrypt(self, value):
            return b"secret"

    class FakeTotp:
        def __init__(self, secret):
            self.secret = secret

        def verify(self, code, valid_window=1):
            return True

    connection = FakeConnection()

    monkeypatch.setattr(handler, "get_fernet", lambda: FakeFernet())
    monkeypatch.setattr(handler, "get_db_connection", lambda: connection)
    monkeypatch.setattr(handler.bcrypt, "checkpw", lambda password, hashed: True)
    monkeypatch.setattr(handler.pyotp, "TOTP", lambda secret: FakeTotp(secret))

    response = handler.handle(
        make_event(json.dumps({"username": "john.doe", "password": "pw", "totp_code": "123456"})),
        None,
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "authenticated": True,
        "expired": False,
        "username": "john.doe",
        "message": "Authentification réussie.",
    }
    assert connection.committed is False
    assert connection.closed is True


def test_handle_marks_expired_accounts(monkeypatch):
    expired_ts = int(datetime.now(UTC).timestamp()) - handler.SIX_MONTHS_SECONDS - 10

    class FakeCursor:
        def __init__(self):
            self.executed = []

        def execute(self, query, params=None):
            self.executed.append((query, params))

        def fetchone(self):
            return ("hashed", "encrypted", expired_ts, 0)

        def close(self):
            self.executed.append(("close", None))

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

    class FakeFernet:
        def decrypt(self, value):
            return b"secret"

    class FakeTotp:
        def __init__(self, secret):
            self.secret = secret

        def verify(self, code, valid_window=1):
            return True

    connection = FakeConnection()

    monkeypatch.setattr(handler, "get_fernet", lambda: FakeFernet())
    monkeypatch.setattr(handler, "get_db_connection", lambda: connection)
    monkeypatch.setattr(handler.bcrypt, "checkpw", lambda password, hashed: True)
    monkeypatch.setattr(handler.pyotp, "TOTP", lambda secret: FakeTotp(secret))

    response = handler.handle(
        make_event(json.dumps({"username": "john.doe", "password": "pw", "totp_code": "123456"})),
        None,
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "authenticated": False,
        "expired": True,
        "username": "john.doe",
        "message": "Identifiants expirés. Veuillez renouveler votre mot de passe et votre 2FA.",
    }
    assert connection.committed is True
    assert connection.closed is True


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


def test_handle_returns_500_when_totp_decryption_fails(monkeypatch):
    class FakeCursor:
        def execute(self, *args, **kwargs):
            pass

        def fetchone(self):
            return ("hashed", "not-a-valid-token", int(datetime.now(UTC).timestamp()), 0)

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    class FakeFernet:
        def decrypt(self, value):
            raise handler.InvalidToken("bad token")

    monkeypatch.setattr(handler, "get_fernet", lambda: FakeFernet())
    monkeypatch.setattr(handler, "get_db_connection", lambda: FakeConnection())
    monkeypatch.setattr(handler.bcrypt, "checkpw", lambda password, hashed: True)

    response = handler.handle(
        make_event(json.dumps({"username": "john.doe", "password": "pw", "totp_code": "123456"})),
        None,
    )

    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == {"error": "Impossible de déchiffrer le secret 2FA."}


def test_handle_returns_500_on_db_error_during_lookup(monkeypatch):
    class FakeDbError(Exception):
        pass

    def raise_db_error():
        raise FakeDbError("connexion refusée")

    monkeypatch.setattr(handler.psycopg2, "Error", FakeDbError)
    monkeypatch.setattr(handler, "get_fernet", lambda: object())
    monkeypatch.setattr(handler, "get_db_connection", raise_db_error)

    response = handler.handle(
        make_event(json.dumps({"username": "john.doe", "password": "pw", "totp_code": "123456"})),
        None,
    )

    assert response["statusCode"] == 500


def test_handle_returns_500_when_secret_key_is_missing(monkeypatch):
    def raise_runtime_error():
        raise RuntimeError("Secret 'totp-encryption-key' manquant.")

    monkeypatch.setattr(handler, "get_fernet", raise_runtime_error)

    response = handler.handle(
        make_event(json.dumps({"username": "john.doe", "password": "pw", "totp_code": "123456"})),
        None,
    )

    assert response["statusCode"] == 500
