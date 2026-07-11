# Architecture — Plan F/G

## Vue d’ensemble
AutoCommerce V25 assemble :
- un backend FastAPI multi-tenant
- un frontend React/Vite
- une couche de sécurité middleware
- un portail B2B métier
- des workers asynchrones Celery
- une stack d’observabilité Prometheus/Grafana/Alertmanager

## Composants principaux
### Backend
- API REST FastAPI
- SQLAlchemy + Alembic
- Redis pour queue/rate limiting/cache
- services métier B2B, paiements, conversations, AI

### Frontend
- SPA React avec pages dashboard, commandes, promotions, B2B, storefront, settings

### Overlay entreprise
- PgBouncer
- replicas API/Celery
- Redis Sentinel
- migration job dédié

## Décisions de structure visibles dans le code
- middlewares de sécurité empilés avec ordre explicite
- `/metrics` protégé par token interne
- migrations retirées du boot applicatif en mode entreprise
- preflight séparé du run-time
