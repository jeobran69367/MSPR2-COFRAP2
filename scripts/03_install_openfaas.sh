#!/bin/bash
# ================================================================
# 03_install_openfaas.sh — Déploiement OpenFaaS via Helm sur Kind
# Prérequis : script 02 exécuté
# ================================================================
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 1 — Création des namespaces"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl apply -f https://raw.githubusercontent.com/openfaas/faas-netes/master/namespaces.yml
echo "✅ Namespaces openfaas et openfaas-fn créés"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 2 — Ajout repo Helm OpenFaaS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
helm repo add openfaas https://openfaas.github.io/faas-netes/
helm repo update
echo "✅ Repo Helm ajouté"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 3 — Génération mot de passe admin"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
OPENFAAS_PASSWORD=$(head -c 16 /dev/urandom | base64 | tr -d '=/+' | head -c 20)
kubectl -n openfaas create secret generic basic-auth \
  --from-literal=basic-auth-user=admin \
  --from-literal=basic-auth-password="${OPENFAAS_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "✅ Secret créé"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 4 — Déploiement OpenFaaS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
helm upgrade --install openfaas openfaas/openfaas \
  --namespace openfaas \
  --set functionNamespace=openfaas-fn \
  --set generateBasicAuth=false \
  --set basic_auth=true \
  --set serviceType=NodePort \
  --set faasnetes.imagePullPolicy=IfNotPresent \
  --wait --timeout 5m
echo "✅ OpenFaaS déployé"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 5 — Connexion faas-cli"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
OPENFAAS_URL="http://localhost:31112"
echo "${OPENFAAS_PASSWORD}" | faas-cli login \
  --gateway "${OPENFAAS_URL}" \
  --password-stdin
echo "✅ Connecté à OpenFaaS"

# Sauvegarder dans .env
cat > .env <<EOF
OPENFAAS_URL=${OPENFAAS_URL}
OPENFAAS_PASSWORD=${OPENFAAS_PASSWORD}
DOCKER_USER=
EOF

echo ""
kubectl -n openfaas get pods

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ OpenFaaS prêt !"
echo "   URL     : ${OPENFAAS_URL}"
echo "   Login   : admin"
echo "   Password: ${OPENFAAS_PASSWORD}"
echo ""
echo "   ⚠️  Édite .env et remplis DOCKER_USER=ton_compte_dockerhub"
echo "   Lance ensuite : bash scripts/04_install_postgresql.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
