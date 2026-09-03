# JIKKODESK-SUPPORT — Réplica Zendesk `silin` + Backup Absoluto

**Stack:** `FastAPI` + `PostgreSQL/SQLite` + `Redis` + `Vite 5.4 + React 18` (Jikkoops Soporte) + `Docker` + `Kubernetes`

Réplica funcional de Zendesk Support para `silin.zendesk.com` con backup absoluto `4805/4863` tickets (58 `deleted` excluidos), `17092` hilos, `30747` audits, `33962` ticket_events, `11206` adjuntos `12.33 GB`, `30` Help Center.

## Estructura
```
JIKKODESK-SUPPORT/
  api/                 # FastAPI — /api/v2/* compat Zendesk + cursor incremental
    app/main.py        # enrich_ticket (requester_name/email), comments/audits enriquecidos, PUT clasificación, GET /attachments
    app/models.py      # Ticket, User, Organization, Group, TicketField (113)
    app/schemas.py     # TicketOut con custom_fields_enriched
  web-jikko/           # Vite + Jikkoops Soporte — 10 dropdowns + No-Tarjeta + dependencias
    src/app.jsx        # Sidebar 260→56px, KPI Bar, tabla 14 cols, modal 92vh con hilo + auditoría + IA
    src/icons.jsx      # 40 iconos + pencil
    styles/tokens.css  # --accent #0A60C2, --bg #FAFAFA
  web/                 # Next.js alternativo (3000)
  scripts/etl_map_legacy.py  # Mapeo 41 huérfanos (gob-valle→g-valle, X→null)
  k8s/                 # deployment-api.yaml (HPA 3-20), deployment-web.yaml, postgres-redis.yaml
  docker-compose.yml   # postgres + redis + api (8000) + web (3000) + web-jikko (5173)
```

## Quick Start Local
```bash
# API + DB (SQLite fallback sin Docker)
cd api && py -u -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# o Docker
docker-compose up --build

# Seed con backup absoluto (si tienes backups/.../json)
py scripts/etl_map_legacy.py  # mapea 778 custom_fields + actualiza zendesk_clone.db

# Web Jikko
cd web-jikko && npm install && npm run dev -- --host 0.0.0.0 --port 5173
# Abrir http://localhost:5173/ (KPI + tabla 4863 + modal 211 con 27 hilos) y http://localhost:8000/docs
```

## Backup Absoluto
- `zendesk-backup-silin/backups/2026-09-02_FULL_.../json/tickets.json` 86 MB `4863`, `users 1209`, `organizations 61`, `groups 5`, `ticket_fields 113`
- `json/comments/ 4805` + `audits/ 4805` + `attachments/ 11206` + `ticket_events.json` `help_center_articles.json`
- Scripts `backup_zendesk.py` (incremental cursor) + `backup_absolute.py` (hilos + audits + adjuntos, reanudable)

## API Endpoints (compat Zendesk)
- `GET /api/v2/tickets.json` + `GET /api/v2/tickets/{id}.json` (enrich_ticket)
- `GET /api/v2/tickets/{id}/comments.json` / `audits.json` (enrich author_name)
- `PUT /api/v2/tickets/{id}.json` (subject,status,priority,group_id,tags,custom_fields)
- `GET /api/v2/ticket_fields.json` (10 dropdowns: Tipo-Informe 41302..., Entidad 11622..., Tributo 35139..., Portal SILIN 12491..., TipoTicket 11588..., Tipo Solicitud 11588..., Otras 38276..., Nivel 30920..., Impacto 11749..., Urgencia→Prioridad)
- `GET /attachments/{ticket_id}/{filename}` (sirve 12.33 GB local)
- `GET /api/v2/incremental/tickets/cursor.json?cursor=`

## Clasificación (10 dropdowns + No-Tarjeta)
Poblados de `GET /ticket_fields.json` `custom_field_options` (no hardcode), `No-Tarjeta` texto. Dependencias `Entidad→Tributo→Portal→TipoTicket→Tipo Solicitud→Otras` filtradas por `history co-ocurrencia` (ej `g-valle→tescc 880`). `lápiz` en header clasificación `PUT` conserva valor.

## Deploy
```bash
docker-compose.prod.yml  # VPS
kubectl apply -f k8s/    # EKS/GKE (RDS + ElastiCache + S3)
```

## Licencia
MIT © 2026 Jikkosoft — ver `LICENSE`
