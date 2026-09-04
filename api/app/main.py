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
from .config import settings
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

@app.post("/api/v2/tickets/{ticket_id}/comments.json")
def create_comment(ticket_id: int, payload: dict, db: Session = Depends(get_db)):
    # Payload: {"comment": {"body": "...", "public": true/false, "author_id": 123}} o {"body": "...", "public": true}
    import pathlib, json as js
    t = db.query(Ticket).filter(Ticket.id==ticket_id).first()
    if not t:
        raise HTTPException(404, "ticket not found")
    data = payload.get("comment", payload)
    body = data.get("body") or data.get("html_body") or ""
    if not body or not body.strip():
        raise HTTPException(400, "body requerido")
    public = data.get("public", True)
    # author: usa me (primer admin) si no se pasa
    author_id = data.get("author_id")
    if not author_id:
        me = db.query(User).filter(User.role=="admin").first() or db.query(User).first()
        author_id = me.id if me else 12148510564365
    new_comment = {
        "id": int(time.time()*1000) % 2147483647,
        "type": "Comment",
        "author_id": author_id,
        "body": body,
        "html_body": f"<p>{body}</p>",
        "plain_body": body,
        "public": public,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "attachments": data.get("attachments", []),
        "via": {"channel": "web", "source": {"from": {"id": author_id}}},
        "metadata": {"system": {"client": "Jikkodesk Support"}}
    }
    # guardar en backup json/comments/{id}.json (append)
    backup_base = pathlib.Path(__file__).parent.parent.parent.parent / "zendesk-backup-silin" / "backups"
    candidates = sorted(backup_base.glob("*_FULL_*")) if backup_base.exists() else []
    if candidates:
        c_path = candidates[-1] / "json" / "comments" / f"{ticket_id}.json"
        c_path.parent.mkdir(parents=True, exist_ok=True)
        if c_path.exists():
            try:
                existing = js.loads(c_path.read_text(encoding="utf-8"))
                comments = existing.get("comments", [])
                comments.append(new_comment)
                existing["comments"] = comments
                existing["count"] = len(comments)
                c_path.write_text(js.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            except:
                c_path.write_text(js.dumps({"comments": [new_comment], "count": 1, "ticket_id": ticket_id}, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            c_path.write_text(js.dumps({"comments": [new_comment], "count": 1, "ticket_id": ticket_id}, ensure_ascii=False, indent=2), encoding="utf-8")
    # actualizar ticket updated_at y raw
    t.updated_at = datetime.now(timezone.utc)
    if isinstance(t.raw, dict):
        t.raw["updated_at"] = t.updated_at.isoformat()
    db.commit()
    # enriquecer author
    info = enrich_user(db, author_id)
    if info:
        new_comment["author_name"] = info["name"]
        new_comment["author_email"] = info["email"]
        new_comment["author_role"] = info.get("role","")
    # si es público y tiene To/Cc, enviar email real vía SMTP en background (no bloquea respuesta, guarda en trazabilidad inmediato)
    if public:
        to_emails=data.get("to_emails") or []
        cc_emails=data.get("cc_emails") or []
        if not to_emails and t.requester_id:
            u=db.query(User).filter(User.id==t.requester_id).first()
            if u and u.email:
                to_emails=[u.email]
        if to_emails:
            # enviar en background thread para no bloquear POST (trazabilidad guarda inmediato, email llega async)
            import threading
            # capturar valores primitivos antes de cerrar sesión (evita DetachedInstanceError)
            subj_val = t.subject or f"Ticket #{ticket_id}"
            to_list = list(to_emails)
            cc_list = list(cc_emails)
            html_val = new_comment.get("html_body")
            def _send_bg(subj_p=subj_val, to_p=to_list, cc_p=cc_list, html_p=html_val):
                try:
                    from .email_send import send_reply
                    send_reply(ticket_id, subj_p, body, to_p, cc_p, html_body=html_p)
                except Exception as e:
                    print(f"[EMAIL-BG] send fail {e}")
            threading.Thread(target=_send_bg, daemon=True).start()
            print(f"[EMAIL-BG] encolado Ticket {ticket_id} to {to_list} cc {cc_list}")
        else:
            print(f"[EMAIL] Ticket {ticket_id} public comment to {data.get('to_emails')} cc {data.get('cc_emails')} body {body[:80]} (no To, solo historial)")
    return {"comment": new_comment, "audit": {"author_id": author_id}}

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
    # Sirve adjuntos locales del backup absoluto (12.3 GB) con sanitización, maneja undefined_ prefix de ingesta email
    # filename viene como {att_id}_{file_name_sanitizado} o solo file_name
    import mimetypes
    # sanitizar filename para Windows y quitar undefined_ prefix
    safe_name = filename
    if safe_name.startswith("undefined_"):
        safe_name = safe_name[len("undefined_"):]
    # también quitar prefijo att_id si es "undefined" o no numérico
    backup_base = pathlib.Path(__file__).parent.parent.parent.parent / "zendesk-backup-silin" / "backups"
    candidates = sorted(backup_base.glob("*_FULL_*")) if backup_base.exists() else []
    for base in candidates:
        att_dir = base / "attachments" / str(ticket_id)
        if not att_dir.exists():
            continue
        # 1. intentar exacto con safe_name
        p = att_dir / safe_name
        if p.exists():
            mt, _ = mimetypes.guess_type(str(p))
            return FileResponse(str(p), media_type=mt or "application/octet-stream", filename=safe_name)
        # 2. intentar con filename original exacto
        p2 = att_dir / filename
        if p2.exists():
            mt, _ = mimetypes.guess_type(str(p2))
            return FileResponse(str(p2), media_type=mt or "application/octet-stream", filename=filename)
        # 3. buscar por sufijo file_name sin id (para undefined_...)
        # extraer sufijo después de primer _
        suffix = safe_name
        # también probar sin sanitización: buscar cualquier archivo que termine con file_name original
        for f in att_dir.iterdir():
            if f.is_file() and (f.name == safe_name or f.name.endswith(safe_name) or safe_name in f.name or f.name.endswith(filename.split("_",1)[-1] if "_" in filename else filename)):
                mt, _ = mimetypes.guess_type(str(f))
                return FileResponse(str(f), media_type=mt or "application/octet-stream", filename=f.name)
        # 4. fallback por att_id prefix si existe y no es undefined
        if "_" in filename and not filename.startswith("undefined_"):
            prefix = filename.split("_")[0]
            if prefix.isdigit():
                for f in att_dir.glob(f"{prefix}_*"):
                    if f.name == filename or f.name.endswith(safe_name):
                        mt, _ = mimetypes.guess_type(str(f))
                        return FileResponse(str(f), media_type=mt or "application/octet-stream", filename=f.name)
    raise HTTPException(404, f"attachment {filename} not found for ticket {ticket_id} (tried {safe_name})")

@app.post("/api/v2/email/mock-ingest")
def email_mock_ingest(payload: dict, db: Session = Depends(get_db)):
    """Simula email entrante para validación interna 0 impacto (crea ticket 99999). No requiere IMAP real."""
    from .email_ingest import mock_ingest
    from_email=payload.get("from") or payload.get("from_email") or "test@jikkosoft.test"
    subject=payload.get("subject") or "(sin asunto)"
    body=payload.get("body") or payload.get("text") or ""
    to_email=payload.get("to") or settings.EMAIL_FROM
    tid=mock_ingest(from_email, subject, body, to_email)
    t=db.query(Ticket).filter(Ticket.id==tid).first()
    return {"ticket_id": tid, "ticket": enrich_ticket(t, db) if t else None}

@app.post("/api/v2/email/poll")
def email_poll(db: Session = Depends(get_db)):
    """Poll IMAP una vez (usa EMAIL_IMAP_* de .env). Seguro, solo UNSEEN."""
    from .email_ingest import poll_once
    count=poll_once()
    return {"ingested": count}

@app.get("/api/v2/email/oauth/login")
def email_oauth_login():
    """Redirige a Google OAuth para nicolas.chala@jikkosoft.com"""
    from urllib.parse import urlencode
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(400, "GOOGLE_CLIENT_ID no configurado en .env")
    params={
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://mail.google.com/",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true"
    }
    url="https://accounts.google.com/o/oauth2/v2/auth?"+urlencode(params)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url)

@app.get("/api/v2/email/oauth/callback")
def email_oauth_callback(code: str = Query(...), db: Session = Depends(get_db)):
    """Callback OAuth: intercambia code por tokens y guarda refresh_token en .env"""
    import requests, pathlib
    data={
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    r=requests.post("https://oauth2.googleapis.com/token", data=data, timeout=15)
    if r.status_code!=200:
        raise HTTPException(400, f"OAuth token error {r.status_code}: {r.text}")
    j=r.json()
    refresh=j.get("refresh_token")
    access=j.get("access_token")
    # guardar en .env
    env_path=pathlib.Path(__file__).parent.parent / ".env"
    try:
        content=env_path.read_text(encoding="utf-8")
        if "GOOGLE_REFRESH_TOKEN=" in content:
            content=re.sub(r"GOOGLE_REFRESH_TOKEN=.*", f"GOOGLE_REFRESH_TOKEN={refresh or ''}", content)
        else:
            content+=f"\nGOOGLE_REFRESH_TOKEN={refresh or ''}\n"
        if "GOOGLE_ACCESS_TOKEN=" in content:
            content=re.sub(r"GOOGLE_ACCESS_TOKEN=.*", f"GOOGLE_ACCESS_TOKEN={access or ''}", content)
        env_path.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"write .env fail {e}")
    return {"ok": True, "refresh_token": refresh[:20]+"..." if refresh else None, "access_token": access[:20]+"..." if access else None, "message": "Guarda refresh_token en .env, reinicia API para usar XOAUTH2"}

@app.get("/api/v2/email/test")
def email_test(db: Session = Depends(get_db)):
    """Test IMAP/SMTP sin enviar correo real, solo login. Usa XOAUTH2 si hay refresh_token, sino PASS. Fix Python 3.14 Gmail cert."""
    import imaplib, smtplib, ssl
    def get_ssl_context():
        try:
            return ssl.create_default_context()
        except:
            return ssl._create_unverified_context()
    imap_ok=False
    smtp_ok=False
    imap_err=None
    smtp_err=None
    # intentar OAuth si hay refresh_token
    if settings.GOOGLE_REFRESH_TOKEN:
        try:
            import requests
            data={"client_id": settings.GOOGLE_CLIENT_ID, "client_secret": settings.GOOGLE_CLIENT_SECRET, "refresh_token": settings.GOOGLE_REFRESH_TOKEN, "grant_type": "refresh_token"}
            r=requests.post("https://oauth2.googleapis.com/token", data=data, timeout=10)
            if r.status_code==200:
                access=r.json().get("access_token")
                import base64
                auth_str=f"user={settings.EMAIL_IMAP_USER}\x01auth=Bearer {access}\x01\x01"
                auth_b64=base64.b64encode(auth_str.encode()).decode()
                try:
                    ctx=get_ssl_context()
                    M=imaplib.IMAP4_SSL(settings.EMAIL_IMAP_HOST, settings.EMAIL_IMAP_PORT, ssl_context=ctx, timeout=10)
                except ssl.SSLError:
                    M=imaplib.IMAP4_SSL(settings.EMAIL_IMAP_HOST, settings.EMAIL_IMAP_PORT, ssl_context=ssl._create_unverified_context(), timeout=10)
                M.authenticate("XOAUTH2", lambda x: auth_b64)
                M.logout()
                imap_ok=True
            else:
                imap_err=f"refresh failed {r.text[:200]}"
        except Exception as e:
            imap_err=str(e)
    else:
        try:
            try:
                ctx=get_ssl_context()
                M=imaplib.IMAP4_SSL(settings.EMAIL_IMAP_HOST, settings.EMAIL_IMAP_PORT, ssl_context=ctx, timeout=10)
            except ssl.SSLError:
                M=imaplib.IMAP4_SSL(settings.EMAIL_IMAP_HOST, settings.EMAIL_IMAP_PORT, ssl_context=ssl._create_unverified_context(), timeout=10)
            M.login(settings.EMAIL_IMAP_USER, settings.EMAIL_IMAP_PASS)
            M.logout()
            imap_ok=True
        except Exception as e:
            imap_err=str(e)
    try:
        try:
            ctx=get_ssl_context()
        except:
            ctx=ssl._create_unverified_context()
        import smtplib
        with smtplib.SMTP(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT, timeout=10) as s:
            s.ehlo()
            try:
                s.starttls(context=ctx)
            except ssl.SSLError:
                s.starttls(context=ssl._create_unverified_context())
            if settings.GOOGLE_REFRESH_TOKEN:
                import base64, requests
                data={"client_id": settings.GOOGLE_CLIENT_ID, "client_secret": settings.GOOGLE_CLIENT_SECRET, "refresh_token": settings.GOOGLE_REFRESH_TOKEN, "grant_type": "refresh_token"}
                r=requests.post("https://oauth2.googleapis.com/token", data=data, timeout=10)
                access=r.json().get("access_token") if r.status_code==200 else None
                if access:
                    auth_str=f"user={settings.EMAIL_SMTP_USER}\x01auth=Bearer {access}\x01\x01"
                    auth_b64=base64.b64encode(auth_str.encode()).decode()
                    s.docmd("AUTH", "XOAUTH2 " + auth_b64)
                    smtp_ok=True
                else:
                    raise Exception(f"no access_token {r.text[:200]}")
            else:
                s.login(settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASS)
                smtp_ok=True
    except Exception as e:
        smtp_err=str(e)
    return {"imap_ok": imap_ok, "imap_err": imap_err, "smtp_ok": smtp_ok, "smtp_err": smtp_err, "imap_host": settings.EMAIL_IMAP_HOST, "smtp_host": settings.EMAIL_SMTP_HOST, "oauth": bool(settings.GOOGLE_REFRESH_TOKEN)}

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
