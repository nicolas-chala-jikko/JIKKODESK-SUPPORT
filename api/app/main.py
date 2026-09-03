import base64, json, time
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
import pathlib, re

from .database import Base, engine, get_db
from .models import Ticket, User, Organization, Group, Brand, TicketField, Trigger, Automation, Macro, View
from .schemas import TicketOut, UserOut, CursorTickets, TicketCreate

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Jikkodesk Support - Silin", version="1.0.0", description="Réplica escalable Jikkodesk Support - compat /api/v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "subdomain": "silin", "version": "1.0.0"}

@app.get("/api/v2/users/me.json")
def me(db: Session = Depends(get_db)):
    # stub: devuelve admin silin (sin auth real en MVP - añadir JWT en prod)
    user = db.query(User).first()
    if not user:
        return {"user": {"id": 12148510564365, "email": "nicolas.chala@jikkosoft.com", "name": "Nicolas Chala Amaya", "role": "admin"}}
    return {"user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}}

FIELD_MAP = {
    "Tipo-Informe": 41302403884557,
    "Entidad": 11622270573837,
    "Tributo": 35139407697805,
    "Portal SILIN": 12491763418637,
    "TipoTicket Entidad SILIN": 11588515928205,
    "Tipo Solicitud Entidad SILIN": 11588303168525,
    "Otras Solicitudes": 38276732136461,
    "Nivel de Atención": 30920328139405,
    "Impacto": 11749979171469,
    "Urgencia": 11393617430669,  # Prioridad sistema como Urgencia
    "No-Tarjeta": 30598614640397,
}

def enrich_ticket(ticket, db):
    """Resuelve nombres a partir de IDs para display idéntico Zendesk + custom_fields 10 dropdowns"""
    data = TicketOut.model_validate(ticket).model_dump()
    if ticket.requester_id:
        u = db.query(User).filter(User.id==ticket.requester_id).first()
        if u:
            data["requester_name"] = u.name
            data["requester_email"] = u.email
    if ticket.assignee_id:
        a = db.query(User).filter(User.id==ticket.assignee_id).first()
        if a:
            data["assignee_name"] = a.name
    if ticket.group_id:
        g = db.query(Group).filter(Group.id==ticket.group_id).first()
        if g:
            data["group_name"] = g.name
    if not data.get("requester_name") and ticket.raw and isinstance(ticket.raw, dict):
        data["requester_name"] = ticket.raw.get("via",{}).get("source",{}).get("from",{}).get("name")
    # enriquecer custom_fields con value_name y title para los 10 dropdowns
    enriched_cfs=[]
    for cf in (ticket.custom_fields or []):
        fid=cf.get("id")
        val=cf.get("value")
        # buscar field
        field=db.query(TicketField).filter(TicketField.id==fid).first()
        title=field.title if field else f"field_{fid}"
        # buscar option name
        value_name=val
        if field and field.raw and field.raw.get("custom_field_options"):
            for opt in field.raw.get("custom_field_options"):
                if opt.get("value")==val:
                    value_name=opt.get("name")
                    break
        elif field and field.raw and field.raw.get("system_field_options"):
            for opt in field.raw.get("system_field_options"):
                if opt.get("value")==val:
                    value_name=opt.get("name")
                    break
        enriched_cfs.append({"id": fid, "title": title, "value": val, "value_name": value_name})
    data["custom_fields_enriched"]=enriched_cfs
    # también mantener custom_fields original para compat
    return data

# --- Tickets CRUD ---
@app.get("/api/v2/tickets.json")
def list_tickets(page: int = 1, per_page: int = 25, status: Optional[str] = None, priority: Optional[str] = None, sort_by: str = "created_at", sort_order: str = "desc", db: Session = Depends(get_db)):
    q = db.query(Ticket)
    if status:
        q = q.filter(Ticket.status == status)
    if priority:
        q = q.filter(Ticket.priority == priority)
    total = q.count()
    order_col = getattr(Ticket, sort_by, Ticket.created_at)
    q = q.order_by(desc(order_col) if sort_order=="desc" else asc(order_col))
    tickets = q.offset((page-1)*per_page).limit(per_page).all()
    enriched = [enrich_ticket(t, db) for t in tickets]
    return {"tickets": enriched, "count": total, "next_page": f"/api/v2/tickets.json?page={page+1}" if page*per_page < total else None}

@app.get("/api/v2/tickets/{ticket_id}.json")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id==ticket_id).first()
    if not t:
        raise HTTPException(404, "ticket not found")
    return {"ticket": enrich_ticket(t, db), "raw": t.raw}

def enrich_user(db: Session, user_id: Optional[int]):
    if not user_id:
        return None
    u = db.query(User).filter(User.id==user_id).first()
    if u:
        return {"id": u.id, "name": u.name, "email": u.email, "role": u.role or ""}
    return {"id": user_id, "name": f"#{user_id}", "email": "", "role": ""}

@app.get("/api/v2/tickets/{ticket_id}/comments.json")
def get_ticket_comments(ticket_id: int, db: Session = Depends(get_db)):
    import pathlib, json
    backup_base = pathlib.Path(__file__).parent.parent.parent.parent / "zendesk-backup-silin" / "backups"
    candidates = sorted(backup_base.glob("*_FULL_*")) if backup_base.exists() else []
    data = None
    if candidates:
        c_path = candidates[-1] / "json" / "comments" / f"{ticket_id}.json"
        if c_path.exists():
            data = json.loads(c_path.read_text(encoding="utf-8"))
    if not data:
        return {"comments": [], "count": 0, "ticket_id": ticket_id}
    # enriquecer author_id -> author_name/email
    for c in data.get("comments", []):
        author_id = c.get("author_id")
        info = enrich_user(db, author_id)
        if info:
            c["author_name"] = info["name"]
            c["author_email"] = info["email"]
            c["author_role"] = info.get("role","")
        # también via para mostrar canal
    return data

@app.get("/api/v2/tickets/{ticket_id}/audits.json")
def get_ticket_audits(ticket_id: int, db: Session = Depends(get_db)):
    import pathlib, json
    backup_base = pathlib.Path(__file__).parent.parent.parent.parent / "zendesk-backup-silin" / "backups"
    candidates = sorted(backup_base.glob("*_FULL_*")) if backup_base.exists() else []
    data = None
    if candidates:
        a_path = candidates[-1] / "json" / "audits" / f"{ticket_id}.json"
        if a_path.exists():
            data = json.loads(a_path.read_text(encoding="utf-8"))
    if not data:
        return {"audits": [], "count": 0}
    # enriquecer audits
    for a in data.get("audits", []):
        author_id = a.get("author_id")
        info = enrich_user(db, author_id)
        if info:
            a["author_name"] = info["name"]
            a["author_email"] = info["email"]
            a["author_role"] = info.get("role","")
        # enriquecer events donde field_name es ID
        for ev in a.get("events", []):
            fname = ev.get("field_name")
            # mapear IDs a nombres para trazabilidad legible
            if fname in ("assignee_id", "requester_id"):
                for key in ("value", "previous_value"):
                    val = ev.get(key)
                    if val and str(val).isdigit():
                        uinfo = enrich_user(db, int(val))
                        if uinfo:
                            ev[f"{key}_name"] = uinfo["name"]
            elif fname == "group_id":
                for key in ("value", "previous_value"):
                    val = ev.get(key)
                    if val and str(val).isdigit():
                        g = db.query(Group).filter(Group.id==int(val)).first()
                        if g:
                            ev[f"{key}_name"] = g.name
            elif fname == "organization_id":
                for key in ("value", "previous_value"):
                    val = ev.get(key)
                    if val and str(val).isdigit():
                        o = db.query(Organization).filter(Organization.id==int(val)).first()
                        if o:
                            ev[f"{key}_name"] = o.name
    return data

@app.put("/api/v2/tickets/{ticket_id}.json")
def update_ticket(ticket_id: int, payload: dict, db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id==ticket_id).first()
    if not t:
        raise HTTPException(404, "ticket not found")
    data = payload.get("ticket", payload)
    # guardar previous para audit
    previous = {k: getattr(t, k) for k in ["subject","status","priority","type","group_id","assignee_id","tags"] if hasattr(t, k)}
    # actualizar campos de clasificación
    for field in ["subject","status","priority","type","group_id","assignee_id","tags","custom_fields"]:
        if field in data:
            setattr(t, field, data[field])
    t.updated_at = datetime.now(timezone.utc)
    # también actualizar raw para preservar
    if isinstance(t.raw, dict):
        t.raw.update(data)
    db.commit()
    db.refresh(t)
    # crear audit simple (no persiste en backup, solo DB)
    # para trazabilidad, el frontend mostrará el cambio inmediato
    return {"ticket": enrich_ticket(t, db), "audits": {"previous": previous, "updated": {k: data[k] for k in data if k in previous}}}

@app.post("/api/v2/tickets.json", status_code=201)
def create_ticket(payload: dict, db: Session = Depends(get_db)):
    data = payload.get("ticket", payload)
    ticket = Ticket(
        subject=data.get("subject","Sin asunto"),
        status=data.get("status","new"),
        priority=data.get("priority","normal"),
        type=data.get("type"),
        requester_id=data.get("requester_id"),
        assignee_id=data.get("assignee_id"),
        group_id=data.get("group_id"),
        tags=data.get("tags", []),
        custom_fields=data.get("custom_fields", []),
        description=data.get("comment",{}).get("body") if isinstance(data.get("comment"), dict) else data.get("description"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        raw=data
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    # TODO: disparar triggers cascade (stub)
    # trigger_engine.run(ticket, event="create")
    return {"ticket": TicketOut.model_validate(ticket).model_dump()}

@app.get("/api/v2/incremental/tickets/cursor.json")
def incremental_cursor(cursor: Optional[str] = Query(None), start_time: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """
    Replica Zendesk cursor-based incremental export.
    cursor = base64(<timestamp>|<id>) opaco. Para MVP decodificamos simple.
    """
    limit = 1000
    q = db.query(Ticket).order_by(asc(Ticket.id))
    # si cursor, decodificar id
    after_id = 0
    if cursor:
        try:
            decoded = base64.b64decode(cursor.encode()).decode()
            # formato: "<ts>|<id>" o solo id
            if "|" in decoded:
                after_id = int(decoded.split("|")[-1])
            else:
                after_id = int(decoded)
        except:
            after_id = 0
    elif start_time:
        # time-based fallback: filter por created_at
        dt = datetime.fromtimestamp(start_time, tz=timezone.utc)
        q = q.filter(Ticket.updated_at >= dt)
        after_id = 0
    else:
        after_id = 0

    if after_id:
        q = q.filter(Ticket.id > after_id)

    tickets = q.limit(limit+1).all()
    end_of_stream = len(tickets) <= limit
    tickets_page = tickets[:limit]
    next_cursor = None
    if tickets_page:
        last_id = tickets_page[-1].id
        last_ts = int(tickets_page[-1].updated_at.timestamp()) if tickets_page[-1].updated_at else int(time.time())
        next_cursor = base64.b64encode(f"{last_ts}|{last_id}".encode()).decode()
    after_url = f"http://localhost:8000/api/v2/incremental/tickets/cursor.json?cursor={next_cursor}" if next_cursor and not end_of_stream else None
    enriched_page = [enrich_ticket(t, db) for t in tickets_page]
    return {
        "tickets": enriched_page,
        "after_cursor": next_cursor,
        "after_url": after_url,
        "before_cursor": cursor,
        "end_of_stream": end_of_stream,
        "count": len(tickets_page)
    }

# --- Users / Orgs / Groups compat ---
@app.get("/api/v2/users.json")
def list_users(page_size: int = 100, page_after: Optional[str]=None, db: Session = Depends(get_db)):
    users = db.query(User).limit(page_size).all()
    return {"users": [UserOut.model_validate(u).model_dump() for u in users], "count": len(users)}

@app.get("/api/v2/organizations.json")
def list_orgs(db: Session = Depends(get_db)):
    orgs = db.query(Organization).all()
    return {"organizations": [{"id": o.id, "name": o.name, "raw": o.raw} for o in orgs], "count": len(orgs)}

@app.get("/api/v2/groups.json")
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(Group).all()
    return {"groups": [{"id": g.id, "name": g.name} for g in groups], "count": len(groups)}

@app.get("/api/v2/brands.json")
def list_brands(db: Session = Depends(get_db)):
    brands = db.query(Brand).all()
    return {"brands": [{"id": b.id, "name": b.name, "subdomain": b.subdomain} for b in brands]}

@app.get("/api/v2/ticket_fields.json")
def list_fields(db: Session = Depends(get_db)):
    fields = db.query(TicketField).all()
    return {"ticket_fields": [f.raw for f in fields]}

@app.get("/api/v2/triggers.json")
def list_triggers(db: Session = Depends(get_db)):
    triggers = db.query(Trigger).all()
    return {"triggers": [t.raw for t in triggers]}

@app.get("/api/v2/automations.json")
def list_automations(db: Session = Depends(get_db)):
    autos = db.query(Automation).all()
    return {"automations": [a.raw for a in autos]}

@app.get("/api/v2/macros.json")
def list_macros(db: Session = Depends(get_db)):
    macros = db.query(Macro).all()
    return {"macros": [m.raw for m in macros]}

@app.get("/api/v2/views.json")
def list_views(db: Session = Depends(get_db)):
    views = db.query(View).all()
    return {"views": [v.raw for v in views]}

@app.get("/attachments/{ticket_id}/{filename}")
def serve_attachment(ticket_id: int, filename: str):
    # Sirve adjuntos locales del backup absoluto (12.3 GB) con sanitización
    # filename viene como {att_id}_{file_name_sanitizado}
    backup_base = pathlib.Path(__file__).parent.parent.parent.parent / "zendesk-backup-silin" / "backups"
    candidates = sorted(backup_base.glob("*_FULL_*")) if backup_base.exists() else []
    # buscar archivo exacto o con prefijo att_id
    for base in candidates:
        # intentar directo
        p = base / "attachments" / str(ticket_id) / filename
        if p.exists():
            # guess content type por extensión
            import mimetypes
            mt, _ = mimetypes.guess_type(str(p))
            return FileResponse(str(p), media_type=mt or "application/octet-stream", filename=filename)
        # buscar por att_id prefix si sanitización difiere
        att_dir = base / "attachments" / str(ticket_id)
        if att_dir.exists():
            # si filename tiene att_id_ prefix, buscar que termine con sufijo
            for f in att_dir.glob(f"{filename.split('_')[0]}_*"):
                if f.name == filename or f.name.endswith(filename.split('_',1)[-1]):
                    import mimetypes
                    mt, _ = mimetypes.guess_type(str(f))
                    return FileResponse(str(f), media_type=mt or "application/octet-stream", filename=f.name)
    raise HTTPException(404, f"attachment {filename} not found for ticket {ticket_id}")

@app.get("/api/v2/search.json")
def search(query: str = Query(..., description="ej: status:open priority:high"), db: Session = Depends(get_db)):
    q = db.query(Ticket)
    # parser simple status: y priority:
    if "status:" in query:
        import re
        m = re.search(r"status:(\w+)", query)
        if m:
            q = q.filter(Ticket.status==m.group(1))
    if "priority:" in query:
        import re
        m = re.search(r"priority:(\w+)", query)
        if m:
            q = q.filter(Ticket.priority==m.group(1))
    results = q.limit(100).all()
    return {"results": [enrich_ticket(t, db) for t in results], "count": len(results)}
