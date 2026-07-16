#!/bin/bash
# ================================================================
# 04_install_postgresql.sh — Déploiement PostgreSQL sur Kind
# Prérequis : script 03 exécuté
# ================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="${SCRIPT_DIR}/../k8s"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 1 — Déploiement PostgreSQL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl apply -f "${K8S_DIR}/postgresql/statefulset.yaml"
echo "✅ Manifests appliqués"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 2 — Attente démarrage pod"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl -n cofrap-db rollout status statefulset/postgresql --timeout=3m
echo "✅ PostgreSQL en ligne"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 3 — Vérification table users"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
PG_POD=$(kubectl -n cofrap-db get pod -l app=postgresql -o jsonpath='{.items[0].metadata.name}')
echo "Pod : $PG_POD"
sleep 3
kubectl -n cofrap-db exec "${PG_POD}" -- \
  psql -U cofrap_user -d cofrap -c "\d users"
echo "✅ Table users OK"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 4 — Création des secrets OpenFaaS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
# OpenFaaS résout chaque secret déclaré dans stack.yml en cherchant un
# objet Secret Kubernetes DONT LE NOM CORRESPOND EXACTEMENT au secret
# (ex: "db-host"), et le monte en fichier /var/openfaas/secrets/db-host.
# Il faut donc 5 secrets distincts, pas un seul secret combiné.
declare -A DB_SECRETS=(
  [db-host]="postgresql.cofrap-db.svc.cluster.local"
  [db-port]="5432"
  [db-name]="cofrap"
  [db-user]="cofrap_user"
  [db-password]="cofrap_secure_pass_2024"
)
for NAME in "${!DB_SECRETS[@]}"; do
  kubectl -n openfaas-fn create secret generic "${NAME}" \
    --from-literal="${NAME}=${DB_SECRETS[$NAME]}" \
    --dry-run=client -o yaml | kubectl apply -f -
done
echo "✅ Secrets db-host, db-port, db-name, db-user, db-password créés"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 5 — Exposition PostgreSQL en local"
echo "  (accès depuis ton Mac sur localhost:30432)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl -n cofrap-db expose statefulset postgresql \
  --name=postgresql-nodeport \
  --port=5432 \
  --target-port=5432 \
  --type=NodePort \
  --overrides='{"spec":{"ports":[{"port":5432,"targetPort":5432,"nodePort":30432}]}}' \
  --dry-run=client -o yaml | kubectl apply -f - 2>/dev/null || true
echo "✅ PostgreSQL accessible sur localhost:30432"

echo ""
kubectl -n cofrap-db get pods,svc

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Infrastructure complète et fonctionnelle !"
echo ""
echo "   OpenFaaS  → http://localhost:31112"
echo "   PostgreSQL → localhost:30432"
echo "   Base      : cofrap / cofrap_user"
echo ""
echo "   Commande de vérification globale :"
echo "   bash scripts/05_verify.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"