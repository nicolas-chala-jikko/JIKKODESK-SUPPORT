from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    role = Column(String(50)) # admin, agent, end-user
    organization_id = Column(Integer, nullable=True)
    locale = Column(String(10), default="es")
    verified = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    external_id = Column(String(255), nullable=True)
    tags = Column(JSON, default=list)
    raw = Column(JSON, nullable=True)

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    raw = Column(JSON)

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    created_at = Column(DateTime(timezone=True))
    raw = Column(JSON)

class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    subdomain = Column(String(255))
    raw = Column(JSON)

class TicketField(Base):
    __tablename__ = "ticket_fields"
    id = Column(Integer, primary_key=True)
    type = Column(String(50))
    title = Column(String(255))
    raw = Column(JSON)

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True)
    subject = Column(String(500))
    raw_subject = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), index=True) # new, open, pending, solved, closed, deleted
    priority = Column(String(50), nullable=True)
    type = Column(String(50), nullable=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    submitter_id = Column(Integer, nullable=True)
    assignee_id = Column(Integer, nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    organization_id = Column(Integer, nullable=True)
    brand_id = Column(Integer, nullable=True)
    tags = Column(JSON, default=list)
    custom_fields = Column(JSON, default=list)
    via = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), index=True)
    updated_at = Column(DateTime(timezone=True), index=True)
    generated_timestamp = Column(Integer, nullable=True)
    raw = Column(JSON, nullable=True)

Index("ix_tickets_status_priority", Ticket.status, Ticket.priority)
Index("ix_tickets_requester", Ticket.requester_id)

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), index=True)
    author_id = Column(Integer)
    body = Column(Text)
    html_body = Column(Text, nullable=True)
    public = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True))
    attachments = Column(JSON, default=list)
    raw = Column(JSON)

class Trigger(Base):
    __tablename__ = "triggers"
    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    active = Column(Boolean, default=True)
    conditions = Column(JSON) # {all: [], any: []}
    actions = Column(JSON)
    raw = Column(JSON)

class Automation(Base):
    __tablename__ = "automations"
    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    active = Column(Boolean, default=True)
    conditions = Column(JSON)
    actions = Column(JSON)
    raw = Column(JSON)

class Macro(Base):
    __tablename__ = "macros"
    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    active = Column(Boolean, default=True)
    actions = Column(JSON)
    raw = Column(JSON)

class View(Base):
    __tablename__ = "views"
    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    active = Column(Boolean, default=True)
    conditions = Column(JSON)
    raw = Column(JSON)
