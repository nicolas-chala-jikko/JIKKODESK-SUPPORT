from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class TicketOut(BaseModel):
    id: int
    subject: Optional[str]
    status: str
    priority: Optional[str] = None
    type: Optional[str] = None
    requester_id: Optional[int] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    submitter_id: Optional[int] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    organization_id: Optional[int] = None
    tags: List[str] = []
    custom_fields: List[Any] = []
    custom_fields_enriched: List[Any] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class UserOut(BaseModel):
    id: int
    name: Optional[str]
    email: Optional[str]
    role: Optional[str]
    organization_id: Optional[int] = None
    class Config:
        from_attributes = True

class PaginatedTickets(BaseModel):
    tickets: List[TicketOut]
    count: int
    next_page: Optional[str] = None
    previous_page: Optional[str] = None

class CursorTickets(BaseModel):
    tickets: List[TicketOut]
    after_cursor: Optional[str] = None
    after_url: Optional[str] = None
    before_cursor: Optional[str] = None
    end_of_stream: bool

class TicketCreate(BaseModel):
    subject: str
    description: Optional[str] = None
    status: str = "new"
    priority: Optional[str] = "normal"
    type: Optional[str] = None
    requester_id: Optional[int] = None
    assignee_id: Optional[int] = None
    group_id: Optional[int] = None
    tags: List[str] = []
