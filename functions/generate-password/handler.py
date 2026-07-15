import base64
import io
import json
import os
import secrets
import string
from datetime import UTC, datetime

import bcrypt
import psycopg2
import qrcode

# ── Constantes ────────────────────────────────────────────────
PASSWORD_LENGTH = 24
CHARSET = string.ascii_uppercase + string.ascii_lowercase + string.digits + "!@#$%^&*()-_=+"


def generate_secure_password() -> str:
    """Génère un mot de passe de 24 chars garantissant au moins 1 char de chaque classe."""
    while True:
        pwd = "".join(secrets.choice(CHARSET) for _ in range(PASSWORD_LENGTH))
        # Garantit la complexité minimale exigée par le sujet
        if (
            any(c in string.ascii_uppercase for c in pwd)
            and any(c in string.ascii_lowercase for c in pwd)
            and any(c in string.digits for c in pwd)
            and any(c in "!@#$%^&*()-_=+" for c in pwd)
        ):
            return pwd


def password_to_qr_base64(password: str) -> str:
    """Encode le mot de passe en QR code PNG, retourne en base64."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=2,
    )
    qr.add_data(password)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def get_db_connection():
    """Connexion PostgreSQL depuis les secrets OpenFaaS montés en fichiers."""
    secret_path = "/var/openfaas/secrets"

    def read_secret(name: str) -> str:
        path = os.path.join(secret_path, name)
        if os.path.exists(path):
            with open(path) as f:
                return f.read().strip()
        # Fallback variables d'environnement (dev local)
        return os.environ.get(name.upper().replace("-", "_"), "")

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
    Point d'entrée OpenFaaS.

    Body attendu (JSON) :
        { "username": "john.doe" }

    Réponse (JSON) :
        {
            "username": "john.doe",
            "qr_code": "<base64 PNG>",
            "message": "Mot de passe généré et stocké."
        }
    """
    # ── 1. Parse de l'input ───────────────────────────────────
    try:
        body = json.loads(event.body) if isinstance(event.body, (str, bytes)) else {}
    except (json.JSONDecodeError, TypeError):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Corps JSON invalide."}),
        }

    username = (body.get("username") or "").strip()
    if not username:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Le champ 'username' est obligatoire."}),
        }

    # ── 2. Génération du mot de passe ─────────────────────────
    password = generate_secure_password()

    # ── 3. Hachage bcrypt ─────────────────────────────────────
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # ── 4. QR code (mot de passe en clair — usage unique) ─────
    qr_b64 = password_to_qr_base64(password)

    # ── 5. Stockage BDD ───────────────────────────────────────
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        now_ts = int(datetime.now(UTC).timestamp())

        # Upsert : si l'utilisateur existe déjà, on renouvelle son mot de passe
        cur.execute(
            """
            INSERT INTO users (username, password, mfa, gendate, expired)
            VALUES (%s, %s, '', %s, 0)
            ON CONFLICT (username)
            DO UPDATE SET password = EXCLUDED.password,
                          gendate  = EXCLUDED.gendate,
                          expired  = 0
            """,
            (username, hashed, now_ts),
        )
        conn.commit()
        cur.close()
        conn.close()
    except psycopg2.Error as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Erreur base de données : {str(e)}"}),
        }

    # ── 6. Réponse ────────────────────────────────────────────
    return {
        "statusCode": 200,
        "body": json.dumps({
            "username": username,
            "qr_code": qr_b64,
            "message": "Mot de passe généré et stocké avec succès.",
        }),
    }
