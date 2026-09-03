from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# SQLite fallback para dev sin postgres (permite correr sin docker)
# fallback sqlite si postgres no disponible - usa ruta absoluta para compat seed+api
import pathlib
_default_sqlite = f"sqlite:///{(pathlib.Path(__file__).parent.parent.parent / 'zendesk_clone.db').as_posix()}"
# si DATABASE_URL contiene postgres pero no hay postgres corriendo, el seed ya usó sqlite absoluto via env var
if "sqlite" in settings.DATABASE_URL:
    DATABASE_URL = settings.DATABASE_URL
elif "postgres" in settings.DATABASE_URL:
    # intentar postgres, pero si falla al conectar, fallback se maneja en runtime via sqlite file existente
    # para demo local sin docker, forzar sqlite si el archivo ya existe
    if pathlib.Path("C:/Users/Nicolas Chala/Product Owner - Soporte/zendesk-clone/zendesk_clone.db").exists():
        DATABASE_URL = "sqlite:///C:/Users/Nicolas Chala/Product Owner - Soporte/zendesk-clone/zendesk_clone.db"
    else:
        DATABASE_URL = settings.DATABASE_URL
else:
    DATABASE_URL = _default_sqlite

# handle sqlite vs postgres connect_args
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
