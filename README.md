# AutoCommerce V25

Plateforme SaaS d’omnicanal commerce orientée retail/aftermarket avec backend FastAPI, frontend React/Vite, portail B2B, observabilité Prometheus/Grafana et overlay HA pour déploiement entreprise.

## Contenu du package
- `api-server/` : API FastAPI, modèles, migrations Alembic, services métier, tests backend.
- `autocommerce-app/` : frontend React/Vite.
- `e2e/` : tests Playwright critiques.
- `monitoring/` : Prometheus, Alertmanager, dashboards Grafana, Sentinel Redis.
- `scripts/` : génération de secrets, audit de package, preflight de release.
- `docs/` : dossier de handover, stratégie de déploiement, guide B2B, monitoring et go/no-go.

## Démarrage rapide local
1. Générer un fichier d’environnement à partir des scripts fournis.
2. Compléter les secrets obligatoires dans `api-server/.env`.
3. Lancer l’environnement dev/all-in-one :
   - `docker-compose up -d`
4. Exécuter les migrations et le seed initial si nécessaire :
   - `docker-compose exec api python3 -m alembic upgrade heads`
   - `docker-compose exec api python3 seed_production.py`

## Déploiement entreprise
- Voir `docs/deployment-strategy.md`.
- L’overlay HA est fourni via `docker-compose.ha.yml`.
- La validation release passe par `scripts/preflight_go_v25.sh`.
- Le round-trip final reste un gate manuel et ne doit pas être contourné.

## Qualité et sécurité
- Audit de package : `bash scripts/audit_package.sh --check`
- Suite ciblée Plan F/G : `bash scripts/run_plan_fg_quality.sh`
- Tests sécurité backend : inclus dans le preflight release.
- Observabilité : voir `docs/admin-guide-monitoring.md`

## Documents de handover essentiels
- `ONBOARDING.md`
- `CHANGES_HARDENING.md`
- `AUTOCOMMERCE_E_README.md`
- `docs/go-nogo-v25.md`
- `docs/go-nogo-v25-final.md`

## Statut attendu du package
Ce package est conçu pour être **propre, auditable et diffusable**. Un package final ne doit contenir ni `dist/`, ni `.coverage`, ni `.tsbuildinfo`, ni dossiers `__pycache__/`.
