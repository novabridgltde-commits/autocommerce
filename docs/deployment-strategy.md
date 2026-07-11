# Stratégie de déploiement AutoCommerce V25

## 1. Modes supportés
### Mode A — dev / all-in-one
- `docker-compose.yml`
- usage local ou démonstration technique
- frontend buildé puis servi par Nginx racine

### Mode B — overlay haute disponibilité
- `docker-compose.yml` + `docker-compose.ha.yml`
- ajoute PgBouncer, job `migrate`, replicas API/Celery et Redis Sentinel
- cible recommandée pour déploiement entreprise

## 2. Préparation
- générer les secrets
- compléter `api-server/.env`
- vérifier la base, Redis, DNS, certificats et connecteurs tiers
- définir le token interne pour `/metrics`

## 3. Déploiement recommandé
1. Audit du package : `bash scripts/audit_package.sh --check`
2. Vérification documentaire et technique : `bash scripts/preflight_go_v25.sh`
3. Déploiement des services de base
4. Application des migrations via le job dédié
5. Démarrage API/Celery/frontend/Nginx
6. Exécution des tests fonctionnels et sécurité
7. Validation monitoring et alerting
8. Round-trip manuel entreprise

## 4. Round-trip manuel entreprise (obligatoire)
Le package n’est pas autorisé à déclarer un GO automatique sans cette étape.

### Checklist minimale
- création/login d’un compte administrateur
- accès dashboard
- création/édition produit
- création commande
- flux B2B : compte entreprise → règle tarifaire → devis → commande → approbation → facture groupée
- vérification d’un webhook critique
- test d’accès `/metrics` : refus sans token, succès avec token
- confirmation de remontée Prometheus / dashboard / alertes
- vérification des logs et absence d’erreurs bloquantes

### Validation finale
Quand la checklist est terminée et approuvée, relancer :
- `ACK_MANUAL_ROUNDTRIP=1 bash scripts/preflight_go_v25.sh`
ou
- `bash scripts/preflight_go_v25.sh --ack-manual-roundtrip`

## 5. Wording comité / client
Avant signature finale :
- **Ready for enterprise release validation, pending final manual round-trip sign-off.**

Après exécution complète de la checklist et approbation formelle :
- **Enterprise release approved.**
