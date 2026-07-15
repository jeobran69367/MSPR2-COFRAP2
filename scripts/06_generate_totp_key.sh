#!/bin/bash
# ================================================================
# 06_generate_totp_key.sh — Génère la clé AES Fernet pour le TOTP
# Prérequis : script 04 exécuté (PostgreSQL + secrets db-* en place)
# ================================================================
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Génération clé AES Fernet (TOTP)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTP_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

kubectl -n openfaas-fn create secret generic totp-encryption-key \
  --from-literal=totp-encryption-key="${TOTP_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "✅ Secret 'totp-encryption-key' créé dans openfaas-fn"
echo ""
echo "  ⚠️  Sauvegarde cette clé en lieu sûr (hors Git) :"
echo "  ${TOTP_KEY}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
