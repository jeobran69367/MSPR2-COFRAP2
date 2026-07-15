import json
import os
from datetime import UTC, datetime

import bcrypt
import psycopg2
import pyotp
from cryptography.fernet import Fernet, InvalidToken

SIX_MONTHS_SECONDS = 6 * 30 * 24 * 3600


def read_secret(name: str) -> str:
    path = os.path.join("/var/openfaas/secrets", name)
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return os.environ.get(name.upper().replace("-", "_"), "")


def get_fernet() -> Fernet:
    key = read_secret("totp-encryption-key")
    if not key:
        raise RuntimeError("Secret 'totp-encryption-key' manquant.")
    return Fernet(key.encode())


def get_db_connection():
    return psycopg2.connect(
        host=read_secret("db-host"),
        port=int(read_secret("db-port") or 5432),
        dbname=read_secret("db-name"),
        user=read_secret("db-user"),
        password=read_secret("db-password"),
        connect_timeout=5,
    )


def handle(event, context):
    """
    Body attendu :
        { "username": "john.doe", "password": "...", "totp_code": "123456" }

    Réponses :
        200 { "authenticated": true,  "username": "..." }
        200 { "authenticated": false, "expired": true,  "username": "..." }
        401 { "error": "Identifiants invalides." }
        400 / 404 / 500
    """
    # 1. Parse input
    try:
        body = json.loads(event.body) if isinstance(event.body, (str, bytes)) else {}
    except (json.JSONDecodeError, TypeError):
        return {"statusCode": 400, "body": json.dumps({"error": "Corps JSON invalide."})}

    username  = (body.get("username")  or "").strip()
    password  = (body.get("password")  or "").strip()
    totp_code = (body.get("totp_code") or "").strip()

    if not all([username, password, totp_code]):
        return {"statusCode": 400, "body": json.dumps({"error": "Champs 'username', 'password' et 'totp_code' obligatoires."})}

    # 2. Clé AES
    try:
        fernet = get_fernet()
    except RuntimeError as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    # 3. Récupération utilisateur
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT password, mfa, gendate, expired FROM users WHERE username = %s",
            (username,)
        )
        row = cur.fetchone()
    except psycopg2.Error as e:
        return {"statusCode": 500, "body": json.dumps({"error": f"Erreur BDD : {e}"})}

    if not row:
        return {"statusCode": 404, "body": json.dumps({"error": "Utilisateur introuvable."})}

    hashed_pwd, encrypted_mfa, gendate, expired = row

    # 4. Vérification mot de passe (bcrypt)
    if not bcrypt.checkpw(password.encode(), hashed_pwd.encode()):
        return {"statusCode": 401, "body": json.dumps({"error": "Identifiants invalides."})}

    # 5. Vérification TOTP (AES déchiffrement + pyotp)
    try:
        totp_secret = fernet.decrypt(encrypted_mfa.encode()).decode()
    except (InvalidToken, Exception):
        return {"statusCode": 500, "body": json.dumps({"error": "Impossible de déchiffrer le secret 2FA."})}

    totp = pyotp.TOTP(totp_secret)
    if not totp.verify(totp_code, valid_window=1):
        return {"statusCode": 401, "body": json.dumps({"error": "Code 2FA invalide."})}

    # 6. Vérification expiration (> 6 mois)
    now_ts = int(datetime.now(UTC).timestamp())
    is_expired = expired or (now_ts - int(gendate)) > SIX_MONTHS_SECONDS

    if is_expired:
        try:
            cur.execute("UPDATE users SET expired = 1 WHERE username = %s", (username,))
            conn.commit()
        except psycopg2.Error:
            pass
        cur.close(); conn.close()
        return {
            "statusCode": 200,
            "body": json.dumps({
                "authenticated": False,
                "expired": True,
                "username": username,
                "message": "Identifiants expirés. Veuillez renouveler votre mot de passe et votre 2FA.",
            }),
        }

    cur.close(); conn.close()
    return {
        "statusCode": 200,
        "body": json.dumps({
            "authenticated": True,
            "expired": False,
            "username": username,
            "message": "Authentification réussie.",
        }),
    }
