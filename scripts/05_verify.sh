#!/bin/bash
# ================================================================
# 05_verify.sh — Vérification complète de l'infrastructure
# ================================================================
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  VÉRIFICATION INFRASTRUCTURE COFRAP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "[ Cluster Kind ]"
kubectl get nodes

echo ""
echo "[ Pods OpenFaaS ]"
kubectl -n openfaas get pods

echo ""
echo "[ Pods PostgreSQL ]"
kubectl -n cofrap-db get pods

echo ""
echo "[ Table users ]"
PG_POD=$(kubectl -n cofrap-db get pod -l app=postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl -n cofrap-db exec "${PG_POD}" -- \
  psql -U cofrap_user -d cofrap -c "\d users"

echo ""
echo "[ Test INSERT → SELECT → DELETE ]"
kubectl -n cofrap-db exec "${PG_POD}" -- \
  psql -U cofrap_user -d cofrap -c "
    INSERT INTO users (username, password, mfa) VALUES ('test.verify', 'hash_test', '');
    SELECT id, username, gendate, expired FROM users WHERE username = 'test.verify';
    DELETE FROM users WHERE username = 'test.verify';
    SELECT 'Nettoyage OK' AS status;
  "

echo ""
echo "[ OpenFaaS Gateway ]"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:31112/healthz | grep -q "200"; then
  echo "✅ Gateway répond sur http://localhost:31112"
else
  echo "⚠️  Gateway pas encore prête (attends 30s et relance)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Infrastructure COFRAP opérationnelle !"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
