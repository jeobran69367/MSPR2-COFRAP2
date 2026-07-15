#!/bin/bash
# ================================================================
# 01_install_tools.sh — Installation des outils sur Mac
# Prérequis : Docker Desktop installé et démarré
# ================================================================
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 1 — Vérification Docker Desktop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ! docker info > /dev/null 2>&1; then
  echo "❌ Docker Desktop n'est pas démarré !"
  echo "   → Ouvre Docker Desktop depuis tes Applications et attends qu'il soit prêt"
  echo "   → Relance ce script quand la baleine Docker est verte dans la barre du haut"
  exit 1
fi
echo "✅ Docker est démarré"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 2 — Vérification Homebrew"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ! command -v brew &>/dev/null; then
  echo "❌ Homebrew non installé !"
  echo "   → Installe-le avec cette commande :"
  echo '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi
echo "✅ Homebrew disponible : $(brew --version | head -1)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 3 — Installation Kind"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v kind &>/dev/null; then
  echo "✅ Kind déjà installé : $(kind --version)"
else
  brew install kind
  echo "✅ Kind installé : $(kind --version)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 4 — Installation kubectl"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v kubectl &>/dev/null; then
  echo "✅ kubectl déjà installé : $(kubectl version --client --short 2>/dev/null)"
else
  brew install kubectl
  echo "✅ kubectl installé"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 5 — Installation Helm"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v helm &>/dev/null; then
  echo "✅ Helm déjà installé : $(helm version --short)"
else
  brew install helm
  echo "✅ Helm installé : $(helm version --short)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ÉTAPE 6 — Installation faas-cli"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v faas-cli &>/dev/null; then
  echo "✅ faas-cli déjà installé : $(faas-cli version --short-version 2>/dev/null)"
else
  brew install faas-cli
  echo "✅ faas-cli installé"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Tous les outils sont installés !"
echo "   Lance maintenant : bash scripts/02_create_cluster.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
