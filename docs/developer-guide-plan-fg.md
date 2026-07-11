# Guide développeur — Plan F/G

## Objectif
Fournir la base de travail pour maintenir les flux B2B et la qualité release.

## Commandes utiles
- audit package : `bash scripts/audit_package.sh --check`
- qualité ciblée : `bash scripts/run_plan_fg_quality.sh`
- preflight release : `bash scripts/preflight_go_v25.sh`

## Discipline de livraison
- ne pas committer d’artefacts build/runtime
- garder les documents de handover à jour
- ne pas transformer un gate manuel en succès automatique
- ajouter tests ciblés sur sécurité et régressions critiques

## Zones à surveiller
- `api-server/api/v1/b2b_portal.py`
- `api-server/services/b2b_portal_service.py`
- `autocommerce-app/src/pages/B2BPortal.jsx`
- `monitoring/`
- `scripts/preflight_go_v25.sh`
