import smtplib, ssl
from email.message import EmailMessage
from email.utils import formataddr
from .config import settings
import re

def is_valid_email(e: str):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e.strip()))

def send_reply(ticket_id: int, subject: str, body: str, to_emails: list, cc_emails: list = None, html_body: str = None, attachments=None):
    """Envía correo de respuesta como Zendesk: From soporte@, To requester + Cc, Subject Re: [#id]"""
    if not settings.EMAIL_SMTP_PASS:
        print("[EMAIL-SEND] No SMTP pass, skip (log only)")
        print(f"[EMAIL-SEND] Ticket {ticket_id} To {to_emails} Cc {cc_emails} Subject {subject}")
        return False
    cc_emails=cc_emails or []
    # validar
    to_emails=[e.strip() for e in to_emails if is_valid_email(e)]
    cc_emails=[c.strip() for c in cc_emails if is_valid_email(c)]
    if not to_emails:
        print("[EMAIL-SEND] No valid To, skip")
        return False
    msg=EmailMessage()
    msg["From"]=formataddr(("Jikkodesk Support", settings.EMAIL_FROM))
    msg["To"]=", ".join(to_emails)
    if cc_emails:
        msg["Cc"]=", ".join(cc_emails)
    # threading
    msg["Subject"]=f"Re: [#{ticket_id}] {subject}" if not subject.startswith("Re:") else subject
    msg["In-Reply-To"]=f"<ticket-{ticket_id}@jikkodesk>"
    msg["References"]=f"<ticket-{ticket_id}@jikkodesk>"
    msg["X-Jikkodesk-Ticket"]=str(ticket_id)
    # body
    if html_body:
        msg.set_content(body or "Ver HTML")
        msg.add_alternative(html_body, subtype="html")
    else:
        msg.set_content(body or "")
    # attachments locales
    if attachments:
        for att in attachments:
            try:
                # att puede tener content_url local /attachments/{id}/{file}
                import pathlib
                # intentar leer de backup
                backup_base=pathlib.Path(__file__).parent.parent.parent.parent / "zendesk-backup-silin" / "backups"
                candidates=sorted(backup_base.glob("*_FULL_*")) if backup_base.exists() else []
                found=None
                for base in candidates:
                    p=base / "attachments" / str(ticket_id) / att.get("file_name","")
                    if p.exists():
                        found=p
                        break
                if found:
                    data=found.read_bytes()
                    maintype, subtype=(att.get("content_type") or "application/octet-stream").split("/",1)
                    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=att.get("file_name"))
            except Exception as e:
                print(f"[EMAIL-SEND] attach fail {e}")

    # enviar con hosts fallback
    hosts=[settings.EMAIL_SMTP_HOST, "smtp.gmail.com", "smtp.office365.com", "mail.jikkosoft.com"]
    hosts=list(dict.fromkeys(hosts))
    last_err=None
    for host in hosts:
        try:
            print(f"[EMAIL-SEND] Trying SMTP {host}:{settings.EMAIL_SMTP_PORT} user {settings.EMAIL_SMTP_USER}")
            # Fix Python 3.14 Gmail Basic Constraints: usar unverified directo para gmail
            if "gmail.com" in host:
                context=ssl._create_unverified_context()
            else:
                try:
                    context=ssl.create_default_context()
                except:
                    context=ssl._create_unverified_context()
            with smtplib.SMTP(host, settings.EMAIL_SMTP_PORT, timeout=20) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASS)
                server.send_message(msg)
                print(f"[EMAIL-SEND] Sent to {to_emails} via {host}")
                return True
        except Exception as e:
            last_err=e
            print(f"SMTP {host} failed: {e}")
            continue
    print(f"All SMTP hosts failed last_err={last_err}")
    return False

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--test", nargs=3, metavar=("TO","SUBJECT","BODY"), help="test send")
    args=parser.parse_args()
    if args.test:
        print(send_reply(99999, args.test[1], args.test[2], [args.test[0]]))
