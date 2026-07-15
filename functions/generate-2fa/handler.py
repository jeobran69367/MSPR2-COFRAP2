import base64
import io
import json
import os

import psycopg2
import pyotp
import qrcode
from cryptography.fernet import Fernet

ISSUER = "COFRAP"


# ── Helpers ───────────────────────────────────────────────────

def read_secret(name: str) -> str:
    """Lit un secret OpenFaaS (fichier) avec fallback variable d'env."""
    path = os.path.join("/var/openfaas/secrets", name)
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return os.environ.get(name.upper().replace("-", "_"), "")


def get_fernet() -> Fernet:
    """Retourne une instance Fernet à partir de la clé secrète AES."""
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


def generate_totp_secret() -> str:
    """Génère un secret TOTP base32 compatible Google Authenticator."""
    return pyotp.random_base32()


def encrypt_secret(secret: str, fernet: Fernet) -> str:
    """Chiffre le secret TOTP en AES (Fernet) — stockable en BDD."""
    return fernet.encrypt(secret.encode()).decode()


def secret_to_qr_base64(username: str, secret: str) -> str:
    """Génère le QR code otpauth:// en base64 PNG."""
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=ISSUER)
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── Handler OpenFaaS ──────────────────────────────────────────

def handle(event, context):
    """
    Body attendu  : { "username": "john.doe" }
    Réponse 200   : { "username", "qr_code" (base64 PNG), "message" }
    """
    # 1. Parse input
    try:
        body = json.loads(event.body) if isinstance(event.body, (str, bytes)) else {}
    except (json.JSONDecodeError, TypeError):
        return {"statusCode": 400, "body": json.dumps({"error": "Corps JSON invalide."})}

    username = (body.get("username") or "").strip()
    if not username:
        return {"statusCode": 400, "body": json.dumps({"error": "Le champ 'username' est obligatoire."})}

    # 2. Clé AES
    try:
        fernet = get_fernet()
    except RuntimeError as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    # 3. Vérification existence utilisateur
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if not cur.fetchone():
            cur.close(); conn.close()
            return {"statusCode": 404, "body": json.dumps({"error": f"Utilisateur '{username}' introuvable. Créez d'abord un mot de passe."})}
    except psycopg2.Error as e:
        return {"statusCode": 500, "body": json.dumps({"error": f"Erreur BDD : {e}"})}

    # 4. Génération + chiffrement AES du secret TOTP
    secret = generate_totp_secret()
    encrypted = encrypt_secret(secret, fernet)

    # 5. QR code (secret en clair — affiché une seule fois)
    qr_b64 = secret_to_qr_base64(username, secret)

    # 6. Stockage BDD (secret chiffré)
    try:
        cur.execute("UPDATE users SET mfa = %s WHERE username = %s", (encrypted, username))
        conn.commit()
        cur.close(); conn.close()
    except psycopg2.Error as e:
        return {"statusCode": 500, "body": json.dumps({"error": f"Erreur mise à jour BDD : {e}"})}

    # 7. Réponse — le secret en clair n'est JAMAIS retourné
    return {
        "statusCode": 200,
        "body": json.dumps({
            "username": username,
            "qr_code": qr_b64,
            "message": "Secret 2FA généré et stocké avec succès.",
        }),
    }
