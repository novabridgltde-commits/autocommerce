# Guide administrateur — monitoring

## Composants fournis
- `monitoring/prometheus.yml`
- `monitoring/alert_rules.yml`
- `monitoring/b2b_alert_rules.yml`
- `monitoring/alertmanager.yml`
- `monitoring/grafana_dashboard.json`
- `monitoring/grafana_b2b_portal_dashboard.json`
- `monitoring/redis-sentinel.conf`

## Points clés
- `/metrics` backend doit être protégé par `X-Internal-Token`.
- Le token doit être injecté dans Prometheus avant démarrage.
- Alertmanager est livré comme template et doit être rendu avec les bons secrets SMTP / PagerDuty / Slack.

## Vérifications minimales
- 403 sur `/metrics` sans token
- 200 sur `/metrics` avec token valide
- scrape Prometheus OK
- dashboards Grafana importés
- alertes warning/critical configurées

## Dashboards attendus
- dashboard général AutoCommerce
- dashboard B2B portal

## Exploitation
- surveiller latence API, erreurs 5xx, backlog queues, incidents OpenAI/paiement, métriques B2B
- conserver une procédure de rotation des secrets et de test d’alerte périodique
