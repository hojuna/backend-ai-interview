from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class SessionCreateSchema(BaseModel):
    id: str
    password: str


class EducationSchema(BaseModel):
    school: str
    major: str
    gradYear: Optional[int] = None


class QuestionSchema(BaseModel):
    id: str
    text: str
    type: str


class EvaluationSchema(BaseModel):
    score: Optional[List[Any]] = None
    feedback: Optional[str] = None


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
    code: str
    session_id: str


class SessionInputsPayload(BaseModel):
    name: str
    password: str
    email: Optional[EmailStr] = None
    education: EducationSchema
    career_summary: Optional[str] = None
    company_name: str
    job_role: str
    self_intro: Optional[str] = None


class SessionProfilePayload(BaseModel):
    name: str
    age: int
    education: Optional[EducationSchema] = None
    gender: str
    organization: str
    position: str


class SessionInterviewInfoPayload(BaseModel):
    company_name: str
    job_role: str
    self_intro: str


class ReportResponse(ReportSchema):
    pass
