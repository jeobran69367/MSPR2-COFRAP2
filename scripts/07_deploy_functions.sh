#!/bin/bash
# ================================================================
# 07_deploy_functions.sh — Build + push + deploy des 3 fonctions
# Prérequis : .env rempli (DOCKER_USER), script 06 exécuté
# ================================================================
set -euo pipefail

source "$(dirname "$0")/../.env"

if [[ -z "${DOCKER_USER:-}" ]]; then
  echo "❌ DOCKER_USER non défini dans .env"
  exit 1
fi

export TAG="${TAG:-latest}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 1 — Login DockerHub"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker login

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 2 — Pull template python3-http"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
faas-cli template store pull python3-http

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 3 — Build images Docker"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DOCKER_USER="${DOCKER_USER}" faas-cli build -f stack.yml
echo "✅ Images buildées"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 4 — Push DockerHub"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DOCKER_USER="${DOCKER_USER}" faas-cli push -f stack.yml
echo "✅ Images pushées"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 5 — Déploiement sur OpenFaaS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DOCKER_USER="${DOCKER_USER}" faas-cli deploy -f stack.yml
echo "✅ Fonctions déployées"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 6 — Vérification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
faas-cli list --gateway http://localhost:31112

echo ""
echo "✅ Déploiement terminé !"
echo "   Test rapide :"
echo "   curl -s -X POST http://localhost:31112/function/generate-password \\"
echo "        -H 'Content-Type: application/json' \\"
echo "        -d '{\"username\": \"test.user\"}' | jq ."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"