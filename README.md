# MSPR – Projet Serverless COFRAP

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
[![CD](https://github.com/OWNER/REPO/actions/workflows/cd.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/cd.yml)

> Remplacer `OWNER/REPO` ci-dessus par le chemin réel du dépôt GitHub une fois poussé.

PoC de renforcement de l'authentification (mot de passe fort auto-généré +
2FA TOTP obligatoire, renouvellement automatique tous les 6 mois) pour la
COFRAP, sous forme de 3 fonctions serverless OpenFaaS + un frontend FastAPI.

## Sommaire

- [Architecture](#architecture)
- [Installation locale](#installation-locale)
- [Tests](#tests)
- [Pipeline CI/CD](#pipeline-cicd)
- [Structure du dépôt](#structure-du-dépôt)

## Architecture

```
Navigateur ─▶ Frontend FastAPI ─▶ Gateway OpenFaaS ─▶ Fonctions Python ─▶ PostgreSQL
                (port 30080)        (port 31112)      generate-password
                                                       generate-2fa
                                                       authenticate
```

Le frontend ne parle jamais directement à la base de données : toute la
logique sensible (génération, hachage, chiffrement, vérification TOTP) vit
dans les fonctions serverless, isolées derrière la gateway OpenFaaS.

## Installation locale

```bash
# 1. Outils (Mac) puis cluster + plateforme
bash scripts/01_install_tools.sh
bash scripts/02_create_cluster.sh
bash scripts/03_install_openfaas.sh
bash scripts/04_install_postgresql.sh
bash scripts/06_generate_totp_key.sh
bash scripts/07_deploy_functions.sh
bash scripts/05_verify.sh

# 2. Frontend (en local, pointant vers la gateway du cluster)
cd frontend
pip install -r requirements.txt
export OPENFAAS_URL=http://localhost:31112
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
# Dépendances de test + dépendances applicatives
pip install -r requirements-dev.txt
pip install -r functions/generate-password/requirements.txt
pip install -r functions/generate-2fa/requirements.txt
pip install -r functions/authenticate/requirements.txt
pip install -r frontend/requirements.txt

# Suite complète + couverture (seuil : 80 %, configuré dans pyproject.toml)
pytest --cov --cov-report=term-missing

# Lint
ruff check functions frontend/app frontend/tests

# Sécurité (SAST)
bandit -r functions frontend/app --exclude "*/test_*.py"
```

Les tests unitaires sont colocalisés avec le code qu'ils testent
(`functions/<fonction>/test_*.py`, `frontend/tests/`), sur le modèle des
handlers OpenFaaS qui doivent rester déployables tels quels (pas de
package Python autour du `handler.py`).

## Pipeline CI/CD

Deux workflows GitHub Actions, strictement séparés :

### `ci.yml` — sur chaque push / pull request

1. **lint** — `ruff check` sur les 3 fonctions et le frontend.
2. **test** — matrice par composant (`generate-password`, `generate-2fa`,
   `authenticate`, `frontend`), tests unitaires + couverture par composant.
3. **coverage-gate** — couverture combinée sur l'ensemble du dépôt,
   **le build échoue si la couverture totale descend sous 80 %**
   (`--cov-fail-under=80`). Rapport HTML + XML archivé en artefact et
   résumé publié dans le job summary GitHub.
4. **security** — analyse statique Bandit ; le job échoue sur toute
   vulnérabilité de sévérité *medium* ou *high* (rapport JSON complet
   archivé même en cas de succès).
5. **ci-success** — statut agrégé unique, à utiliser comme *required
   check* dans la protection de branche `main`.

### `cd.yml` — uniquement après un CI vert (`workflow_run`), sur `main`,
`develop`, ou un tag `vX.Y.Z`

1. **build** — une image Docker par composant (3 fonctions via `faas-cli
   build` + frontend via `frontend/Dockerfile`), construite **une seule
   fois** puis exportée en artefact (les jobs suivants la réutilisent sans
   jamais la reconstruire).
2. **scan-images** — scan de vulnérabilités Trivy sur chaque image ;
   échoue sur toute faille CRITICAL/HIGH corrigeable.
3. **e2e-deploy** — **déploiement réel** sur un cluster Kubernetes
   **Kind éphémère** créé dans le runner : namespaces, OpenFaaS (Helm),
   PostgreSQL, secrets, déploiement des 3 fonctions et du frontend, puis
   **tests fonctionnels de bout en bout** sur les vraies routes HTTP
   (création de compte → génération 2FA → authentification, y compris le
   rejet contrôlé d'un mauvais mot de passe). Le cluster est détruit à la
   fin du job, qu'il ait réussi ou non.
4. **push-images** — publication des images vers Docker Hub (tag `latest`
   + tag court du commit), uniquement une fois le scan **et** le e2e
   validés, jamais sur une pull request. Protégé par l'environnement
   GitHub `staging`.
5. **deploy-production** — déploiement sur l'infrastructure réelle COFRAP,
   déclenché uniquement sur un tag `vX.Y.Z`, exécuté sur un **self-hosted
   runner** enregistré sur l'infrastructure cible (un runner hébergé par
   GitHub ne peut pas atteindre un cluster interne), et protégé par
   l'environnement GitHub `production` qui exige une **approbation
   manuelle** avant exécution.

### Secrets / environnements GitHub à configurer

| Nom | Où | Usage |
| --- | --- | --- |
| `DOCKERHUB_USERNAME` | Repository secret | Publication des images |
| `DOCKERHUB_TOKEN` | Repository secret | Publication des images (access token, pas le mot de passe du compte) |
| `PROD_OPENFAAS_GATEWAY` | Environment secret (`production`) | URL de la gateway OpenFaaS réelle |
| Environnement `staging` | Settings → Environments | Sans reviewers, juste une trace d'audit |
| Environnement `production` | Settings → Environments | Reviewers obligatoires (approbation manuelle) |
| Runner self-hosted `[self-hosted, cofrap]` | Settings → Actions → Runners | Enregistré sur l'hôte ayant accès au cluster COFRAP réel |

## Structure du dépôt

```
functions/
  generate-password/   handler.py + test_generate_password_handler.py
  generate-2fa/        handler.py + test_generate_2fa_handler.py
  authenticate/         handler.py + test_authenticate_handler.py
frontend/
  app/                 FastAPI (5 routes) + templates Jinja2
  tests/               tests du frontend (TestClient, appels OpenFaaS mockés)
  Dockerfile
k8s/
  kind-config.yaml
  postgresql/statefulset.yaml
  frontend/deployment.yaml
scripts/               01 à 07, installation manuelle séquencée
stack.yml              déclaration OpenFaaS des 3 fonctions
pyproject.toml         config pytest / coverage / ruff
requirements-dev.txt   dépendances de test/lint/sécurité
.github/workflows/     ci.yml + cd.yml
```
