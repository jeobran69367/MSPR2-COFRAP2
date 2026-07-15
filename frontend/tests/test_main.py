"""Tests unitaires du frontend FastAPI.

Les appels vers la gateway OpenFaaS (call_function) sont mockés :
ces tests valident le comportement des routes FastAPI de façon
isolée, indépendamment de toute infrastructure réelle.
"""
from app import main as main_module
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_index_returns_200():
    response = client.get("/")
    assert response.status_code == 200


def test_create_get_returns_200():
    response = client.get("/create")
    assert response.status_code == 200


def test_create_post_success_displays_qr_codes(monkeypatch):
    async def fake_call_function(name, payload):
        if name == "generate-password":
            return {"qr_code": "QR_PWD", "username": payload["username"]}
        if name == "generate-2fa":
            return {"qr_code": "QR_2FA", "username": payload["username"]}
        raise AssertionError(f"unexpected function call: {name}")

    monkeypatch.setattr(main_module, "call_function", fake_call_function)

    response = client.post("/create", data={"username": "john.doe"})

    assert response.status_code == 200
    assert "john.doe" in response.text
    assert "QR_PWD" in response.text
    assert "QR_2FA" in response.text


def test_create_post_password_error_is_shown(monkeypatch):
    async def fake_call_function(name, payload):
        return {"error": "Erreur base de données"}

    monkeypatch.setattr(main_module, "call_function", fake_call_function)

    response = client.post("/create", data={"username": "jane.doe"})

    assert response.status_code == 200
    assert "Erreur base de données" in response.text


def test_create_post_2fa_error_is_shown(monkeypatch):
    async def fake_call_function(name, payload):
        if name == "generate-password":
            return {"qr_code": "QR_PWD"}
        return {"error": "Secret manquant"}

    monkeypatch.setattr(main_module, "call_function", fake_call_function)

    response = client.post("/create", data={"username": "jane.doe"})

    assert response.status_code == 200
    assert "Secret manquant" in response.text


def test_login_get_returns_200():
    response = client.get("/login")
    assert response.status_code == 200


def test_login_post_redirects_when_expired(monkeypatch):
    async def fake_call_function(name, payload):
        return {"expired": True}

    monkeypatch.setattr(main_module, "call_function", fake_call_function)

    response = client.post(
        "/login",
        data={"username": "john.doe", "password": "pw", "totp_code": "123456"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/renew")


def test_login_post_success(monkeypatch):
    async def fake_call_function(name, payload):
        return {"authenticated": True, "expired": False}

    monkeypatch.setattr(main_module, "call_function", fake_call_function)

    response = client.post(
        "/login",
        data={"username": "john.doe", "password": "pw", "totp_code": "123456"},
    )

    assert response.status_code == 200
    assert "john.doe" in response.text


def test_login_post_invalid_credentials(monkeypatch):
    async def fake_call_function(name, payload):
        return {"authenticated": False, "expired": False, "error": "Identifiants invalides."}

    monkeypatch.setattr(main_module, "call_function", fake_call_function)

    response = client.post(
        "/login",
        data={"username": "john.doe", "password": "wrong", "totp_code": "123456"},
    )

    assert response.status_code == 200
    assert "Identifiants invalides." in response.text


def test_renew_get_returns_200():
    response = client.get("/renew", params={"username": "john.doe"})
    assert response.status_code == 200
    assert "john.doe" in response.text


def test_renew_post_success_displays_new_qr_codes(monkeypatch):
    async def fake_call_function(name, payload):
        if name == "generate-password":
            return {"qr_code": "QR_PWD_NEW"}
        return {"qr_code": "QR_2FA_NEW"}

    monkeypatch.setattr(main_module, "call_function", fake_call_function)

    response = client.post("/renew", data={"username": "john.doe"})

    assert response.status_code == 200
    assert "QR_PWD_NEW" in response.text
    assert "QR_2FA_NEW" in response.text


def test_renew_post_error_is_shown(monkeypatch):
    async def fake_call_function(name, payload):
        return {"error": "Erreur renouvellement mot de passe"}

    monkeypatch.setattr(main_module, "call_function", fake_call_function)

    response = client.post("/renew", data={"username": "john.doe"})

    assert response.status_code == 200
    assert "Erreur renouvellement mot de passe" in response.text
