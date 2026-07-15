#!/bin/bash
# ================================================================
# 02_create_cluster.sh — Création du cluster Kubernetes avec Kind
# Prérequis : script 01 exécuté, Docker Desktop démarré
# ================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="${SCRIPT_DIR}/../k8s"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 1 — Vérification Docker"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ! docker info > /dev/null 2>&1; then
  echo "❌ Docker Desktop n'est pas démarré !"
  echo "   → Ouvre Docker Desktop et relance ce script"
  exit 1
fi
echo "✅ Docker est démarré"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 2 — Suppression cluster existant"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if kind get clusters 2>/dev/null | grep -q "^cofrap$"; then
  echo "Cluster 'cofrap' déjà existant, suppression..."
  kind delete cluster --name cofrap
fi
echo "✅ Prêt pour la création"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 3 — Création du cluster Kind"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kind create cluster --config "${K8S_DIR}/kind-config.yaml"
echo "✅ Cluster créé"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 4 — Configuration kubectl"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl cluster-info --context kind-cofrap
kubectl get nodes
echo "✅ kubectl configuré sur le cluster 'cofrap'"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Cluster Kubernetes prêt !"
echo "   Lance maintenant : bash scripts/03_install_openfaas.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
