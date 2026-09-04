import imaplib, email, ssl, time, re
from email.header import decode_header
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Ticket, User, Organization
from .config import settings
import pathlib, json

def decode_str(s):
    if not s:
        return ""
    parts=decode_header(s)
    out=""
    for part, enc in parts:
        if isinstance(part, bytes):
            out+=part.decode(enc or "utf-8", errors="ignore")
        else:
            out+=part
    return out

def get_or_create_user(email_addr: str, name: str, db: Session):
    if not email_addr:
        return None
    email_addr=email_addr.lower().strip()
    u=db.query(User).filter(User.email==email_addr).first()
    if u:
        return u
    # crear end-user
    domain=email_addr.split("@")[-1]
    org=db.query(Organization).filter(Organization.name.ilike(f"%{domain}%")).first()
    org_id=org.id if org else None
    new_user=User(
        name=name or email_addr.split("@")[0],
        email=email_addr,
        role="end-user",
        organization_id=org_id,
        locale="es",
        verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        tags=[],
        raw={"email": email_addr, "name": name}
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    print(f"[EMAIL-INGEST] Created user {email_addr} id {new_user.id}")
    return new_user

def ingest_one_email(msg, db: Session):
    subject=decode_str(msg.get("Subject","(sin asunto)"))
    from_header=decode_str(msg.get("From",""))
    # parse From: "Name <email>" or "email"
    m=re.search(r'<([^>]+)>', from_header)
    if m:
        email_addr=m.group(1)
        name=from_header.split("<")[0].strip().strip('"')
    else:
        email_addr=from_header.strip()
        name=email_addr.split("@")[0] if "@" in email_addr else "Cliente"
    date_str=msg.get("Date")
    # body
    body=""
    html_body=""
    attachments=[]
    if msg.is_multipart():
        for part in msg.walk():
            ctype=part.get_content_type()
            disp=str(part.get("Content-Disposition",""))
            if "attachment" in disp:
                fname=part.get_filename()
                if fname:
                    fname=decode_str(fname)
                    payload=part.get_payload(decode=True)
                    if payload:
                        # guardar temporal y crear attachment entry para ticket
                        attachments.append({"file_name": fname, "content_type": ctype, "size": len(payload), "payload": payload})
            elif ctype=="text/plain" and not body:
                payload=part.get_payload(decode=True)
                if payload:
                    charset=part.get_content_charset() or "utf-8"
                    body=payload.decode(charset, errors="ignore")
            elif ctype=="text/html" and not html_body:
                payload=part.get_payload(decode=True)
                if payload:
                    charset=part.get_content_charset() or "utf-8"
                    html_body=payload.decode(charset, errors="ignore")
    else:
        payload=msg.get_payload(decode=True)
        if payload:
            charset=msg.get_content_charset() or "utf-8"
            body=payload.decode(charset, errors="ignore")
            if msg.get_content_type()=="text/html":
                html_body=body
                body=""
    # crear ticket: subject como nombre del ticket, editable luego
    user=get_or_create_user(email_addr, name, db)
    requester_id=user.id if user else None
    # si subject vacío, usar body preview
    if not subject or subject=="(sin asunto)":
        subject=(body[:80] or "Ticket via Email").strip()
    ticket=Ticket(
        subject=subject[:500],
        description=body[:2000] if body else html_body[:2000],
        status="new",
        priority="normal",
        type="incident",
        requester_id=requester_id,
        submitter_id=requester_id,
        group_id=None,
        tags=["email_ingest"],
        custom_fields=[],
        via={"channel": "email", "source": {"from": {"address": email_addr, "name": name}, "to": {"address": settings.EMAIL_FROM}}},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        raw={"subject": subject, "from": from_header, "via": "email", "description": body or html_body}
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    # crear comment inicial con body + attachments
    # guardar attachments físicos en backup attachments/{ticket_id}/
    backup_base=pathlib.Path(__file__).parent.parent.parent.parent / "zendesk-backup-silin" / "backups"
    # buscar ultimo FULL para guardar attachments
    import json as js
    candidates=sorted(backup_base.glob("*_FULL_*")) if backup_base.exists() else []
    if candidates and attachments:
        att_dir=candidates[-1] / "attachments" / str(ticket.id)
        att_dir.mkdir(parents=True, exist_ok=True)
        for idx, att in enumerate(attachments):
            # sanitizar y asignar id
            import re as _re
            fname=_re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', att["file_name"])
            att_id = int(time.time()*1000) + idx
            att["id"] = att_id
            dest=att_dir / f"{att_id}_{fname}"
            dest.write_bytes(att["payload"])
            att["content_url"]=f"/attachments/{ticket.id}/{dest.name}"
            del att["payload"]
    # crear comments.json entry
    if candidates:
        c_path=candidates[-1] / "json" / "comments" / f"{ticket.id}.json"
        c_path.parent.mkdir(parents=True, exist_ok=True)
        comment={
            "id": int(time.time()*1000) % 2147483647,
            "type": "Comment",
            "author_id": requester_id,
            "body": body or html_body,
            "html_body": html_body or f"<p>{body}</p>",
            "public": True,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "attachments": [{k:v for k,v in att.items() if k!="payload"} for att in attachments],
            "via": {"channel": "email"}
        }
        c_path.write_text(js.dumps({"comments": [comment], "count": 1, "ticket_id": ticket.id}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[EMAIL-INGEST] Created ticket {ticket.id} subject={subject!r} from={email_addr} attachments={len(attachments)}")
    return ticket

def poll_once():
    if not settings.EMAIL_IMAP_PASS:
        print("[EMAIL-INGEST] No EMAIL_IMAP_PASS, skip")
        return 0
    # intentar IMAP con hosts fallback
    hosts=[settings.EMAIL_IMAP_HOST, "imap.gmail.com", "outlook.office365.com", "mail.jikkosoft.com"]
    # deduplicar
    hosts=list(dict.fromkeys(hosts))
    last_err=None
    for host in hosts:
        try:
            print(f"[EMAIL-INGEST] Trying IMAP {host}:{settings.EMAIL_IMAP_PORT} user {settings.EMAIL_IMAP_USER}")
            # Python 3.14 Gmail cert fix: usar unverified si falla verify
            try:
                context=ssl.create_default_context()
            except:
                context=ssl._create_unverified_context()
            # fallback unverified para Gmail Basic Constraints
            try:
                M=imaplib.IMAP4_SSL(host, settings.EMAIL_IMAP_PORT, ssl_context=context, timeout=20)
            except ssl.SSLError:
                M=imaplib.IMAP4_SSL(host, settings.EMAIL_IMAP_PORT, ssl_context=ssl._create_unverified_context(), timeout=20)
            M.login(settings.EMAIL_IMAP_USER, settings.EMAIL_IMAP_PASS)
            M.select(settings.EMAIL_IMAP_FOLDER)
            typ, data=M.search(None, 'UNSEEN')
            if typ!="OK":
                print(f"SEARCH failed {typ} {data}")
                M.logout()
                continue
            ids=data[0].split()
            print(f"Found {len(ids)} unseen")
            if not ids:
                M.logout()
                return 0
            db=SessionLocal()
            try:
                count=0
                for num in ids:
                    typ, msg_data=M.fetch(num, '(RFC822)')
                    if typ!="OK": continue
                    raw=msg_data[0][1]
                    msg=email.message_from_bytes(raw)
                    ingest_one_email(msg, db)
                    M.store(num, '+FLAGS', '\\Seen')
                    count+=1
                    if count>=10: break # procesar max 10 por poll
                print(f"Ingested {count}")
                return count
            finally:
                db.close()
                try: M.logout()
                except: pass
        except Exception as e:
            last_err=e
            print(f"IMAP {host} failed: {e}")
            continue
    print(f"All IMAP hosts failed last_err={last_err}")
    return 0

def mock_ingest(from_email: str, subject: str, body: str, to_email: str = None):
    """Para validación interna sin IMAP real: simula email entrante"""
    import email.message
    msg=email.message.EmailMessage()
    msg["From"]=from_email
    msg["To"]=to_email or settings.EMAIL_FROM
    msg["Subject"]=subject
    msg.set_content(body)
    db=SessionLocal()
    try:
        t=ingest_one_email(msg, db)
        return t.id
    finally:
        db.close()

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="poll once")
    parser.add_argument("--loop", action="store_true", help="poll loop every EMAIL_POLL_INTERVAL")
    parser.add_argument("--mock", nargs=3, metavar=("FROM","SUBJECT","BODY"), help="mock ingest")
    args=parser.parse_args()
    if args.mock:
        print(mock_ingest(args.mock[0], args.mock[1], args.mock[2]))
    elif args.once:
        poll_once()
    elif args.loop:
        while True:
            poll_once()
            time.sleep(settings.EMAIL_POLL_INTERVAL)
    else:
        poll_once()
