# API B2B Portal

## Portée fonctionnelle
Le portail B2B couvre :
- comptes entreprises
- utilisateurs de comptes
- règles de tarification négociée
- simulation de prix
- commandes B2B
- approbation de commandes
- facturation groupée
- snapshot dashboard

## Endpoints principaux
- `GET /api/v1/b2b/accounts`
- `POST /api/v1/b2b/accounts`
- `GET /api/v1/b2b/accounts/{company_account_id}/users`
- `POST /api/v1/b2b/accounts/{company_account_id}/users`
- `GET /api/v1/b2b/accounts/{company_account_id}/pricing`
- `POST /api/v1/b2b/accounts/{company_account_id}/pricing`
- `POST /api/v1/b2b/pricing/quote`
- `GET /api/v1/b2b/orders`
- `POST /api/v1/b2b/orders`
- `POST /api/v1/b2b/orders/{order_id}/approve`
- `GET /api/v1/b2b/invoices`
- `POST /api/v1/b2b/invoices/grouped`
- `GET /api/v1/b2b/dashboard`

## Contrôles d’accès
- `viewer` : lecture
- `manager` : création comptes, users, pricing, commandes
- `admin` : approbation et facturation groupée
- feature flag requis : `b2b_portal`

## Flux nominal
1. créer un compte entreprise
2. ajouter une règle tarifaire
3. simuler un devis
4. créer une commande
5. approuver la commande
6. générer la facture groupée
