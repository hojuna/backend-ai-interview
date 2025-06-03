from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class SessionCreateSchema(BaseModel):
    username: str
    password: str


class EducationSchema(BaseModel):
    school: str
    major: str
    gradYear: Optional[int] = None


class QuestionSchema(BaseModel):
    id: str
    text: str
    type: str


class CategoryScoreFeedback(BaseModel):
    name: str
    score: float
    feedback: str


class EvaluationSchema(BaseModel):
    categories: List[CategoryScoreFeedback]


class InteractionLogSchema(BaseModel):
    id: Optional[str] = None
    turn: int
    question: str
    answer: Optional[str] = None
    evaluation: Optional[List[EvaluationSchema]] = None
    created_at: Optional[datetime] = None


class ReportSchema(BaseModel):
    id: Optional[str] = None
    url: str
    report_type: str
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SessionSchema(BaseModel):
    id: Optional[str] = None
    code: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    education: Optional[EducationSchema] = None
    career_summary: Optional[str] = None
    company_name: Optional[str] = None
    job_role: Optional[str] = None
    self_intro: Optional[str] = None
    persona: Optional[Dict[str, Any]] = None
    questions: Optional[List[QuestionSchema]] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    interactions: Optional[List[InteractionLogSchema]] = None
    report: Optional[ReportSchema] = None


class SessionCreateResponse(BaseModel):
    session_id: str
    code: str
    created_at: datetime


class SessionJoinResponse(BaseModel):
    session_id: str
    created_at: datetime


class SessionProfilePayload(BaseModel):
    name: str
    age: int
    education: Optional[EducationSchema] = None
    gender: str
    email: EmailStr


class SessionInterviewInfoPayload(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    self_intro: Optional[str] = None


class ReportResponse(ReportSchema):
    pass
