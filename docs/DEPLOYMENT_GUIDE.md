# AutoCommerce V25 — Guide de déploiement production
## Du VPS vierge à l'app en ligne en 15 commandes

**Prérequis serveur :** Ubuntu 22.04+, 2 vCPU, 4 GB RAM, 40 GB SSD, Docker + Docker Compose v2 installés.

---

## Étape 1 — Préparer le serveur

```bash
# Installer Docker (si absent)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# Vérifier
docker --version && docker compose version
```

---

## Étape 2 — Déployer l'archive

```bash
# Uploader et extraire l'archive sur le serveur
unzip AUTOCOMMERCE-V25-RELEASE.zip -d /opt/autocommerce
cd /opt/autocommerce
```

---

## Étape 3 — Configurer les secrets

```bash
# Copier le template
cp .env.prod.example .env.prod

# Générer tous les secrets automatiquement
bash scripts/generate_secrets.sh > /tmp/secrets_generated.txt
cat /tmp/secrets_generated.txt   # copier les valeurs dans .env.prod

# OU éditer manuellement
nano .env.prod
# Remplacer TOUS les CHANGE_ME_ par des vraies valeurs
# Mettre SERVER_DOMAIN=https://votre-domaine.com
# Mettre CORS_ORIGINS=https://votre-domaine.com
```

---

## Étape 4 — Certificats TLS

```bash
# Option A — Let's Encrypt (recommandé)
sudo apt install certbot -y
sudo certbot certonly --standalone -d votre-domaine.com

# Copier dans le dossier attendu par nginx
mkdir -p /opt/autocommerce/certs
sudo cp /etc/letsencrypt/live/votre-domaine.com/fullchain.pem /opt/autocommerce/certs/
sudo cp /etc/letsencrypt/live/votre-domaine.com/privkey.pem /opt/autocommerce/certs/
sudo chown -R $USER:$USER /opt/autocommerce/certs/

# Option B — Sans TLS (HTTP seulement, non recommandé en prod)
# Commenter le port 443 dans docker-compose.prod.yml
```

---

## Étape 5 — Build et démarrage

```bash
cd /opt/autocommerce

# Build des images (5-10 min au premier lancement)
docker compose -f docker-compose.prod.yml --env-file .env.prod build

# Démarrer tous les services (postgres, redis, migrate, api, frontend, nginx)
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Suivre les logs au démarrage
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f --tail=50
```

---

## Étape 6 — Seed initial (UNE SEULE FOIS)

```bash
# Créer les utilisateurs admin/superadmin en base
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec api python3 seed_production.py

# Vérifier que le seed a bien fonctionné
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec api python3 -c "
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['DATABASE_URL'].replace('+asyncpg',''))
with e.connect() as c:
    r = c.execute(text('SELECT email, role FROM users LIMIT 5'))
    [print(row) for row in r]
"
```

---

## Étape 7 — Validation

```bash
# Test déploiement complet (depuis le serveur)
bash scripts/test_deployment.sh --url https://votre-domaine.com

# Preflight checklist
bash scripts/preflight_go_v25.sh --ack-manual-roundtrip
```

---

## Commandes de gestion courantes

```bash
# Voir le statut de tous les services
docker compose -f docker-compose.prod.yml --env-file .env.prod ps

# Logs d'un service spécifique
docker compose -f docker-compose.prod.yml --env-file .env.prod logs api -f
docker compose -f docker-compose.prod.yml --env-file .env.prod logs nginx -f

# Redémarrer un service
docker compose -f docker-compose.prod.yml --env-file .env.prod restart api

# Arrêt propre
docker compose -f docker-compose.prod.yml --env-file .env.prod down

# Mise à jour (nouvelle version)
docker compose -f docker-compose.prod.yml --env-file .env.prod down
unzip -o NOUVELLE_VERSION.zip -d /opt/autocommerce_new
rsync -av /opt/autocommerce_new/ /opt/autocommerce/ --exclude .env.prod
docker compose -f docker-compose.prod.yml --env-file .env.prod build
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

---

## Connexion initiale

| | |
|---|---|
| URL | https://votre-domaine.com |
| Email admin | admin@autocommerce.tn |
| Mot de passe | Valeur de `ADMIN_INITIAL_PASSWORD` dans `.env.prod` |

> **Important :** Changer le mot de passe admin dès la première connexion via Paramètres → Sécurité.

---

## Architecture des services

```
Internet
    │
    ▼
[Nginx :443]  ←── TLS, rate-limit, compression
    │
    ├── /api/*    ──► [API FastAPI :8000]  ←── [PostgreSQL :5432]
    │                                      ←── [Redis :6379]
    │
    └── /*        ──► [Frontend React/Nginx]
```

Réseau `backend` (interne, non exposé) : postgres + redis + api  
Réseau `frontend` (interne) : api + frontend + nginx
