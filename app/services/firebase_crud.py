import os
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pdfkit
from google.cloud.firestore_v1.base_query import FieldFilter
from jinja2 import Environment, FileSystemLoader
from passlib.context import CryptContext

from app.core.firebase import get_db
from app.models.schemas import (
    EvaluationSchema,
    InteractionLogSchema,
    ReportSchema,
    SessionInputsPayload,
    SessionSchema,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_session() -> Optional[Tuple[str, str]]:
    db = get_db()
    code = secrets.token_hex(3).upper()
    session_ref = db.collection("sessions").document()
    session_data = {
        "code": code,
        "status": "ready",
        "created_at": datetime.now(timezone.utc),
    }
    session_ref.set(session_data)
    return session_ref.id, code


def get_session_id_by_code(code: str) -> Optional[str]:
    db = get_db()
    sessions_ref = db.collection("sessions")
    query = sessions_ref.where(filter=FieldFilter("code", "==", code)).limit(1)
    results = query.stream()
    for doc in results:
        return doc.id
    return None


def save_session_inputs(session_id: str, inputs: SessionInputsPayload) -> bool:
    db = get_db()
    session_ref = db.collection("sessions").document(session_id)
    hashed_password = get_password_hash(inputs.password)
    education_data = inputs.education.model_dump() if inputs.education else None
    update_data = {
        "name": inputs.name,
        "pw_hash": hashed_password,
        "email": inputs.email,
        "education": education_data,
        "career_summary": inputs.career_summary,
        "company_name": inputs.company_name,
        "job_role": inputs.job_role,
        "self_intro": inputs.self_intro,
        "status": "inputs_saved",
        "updated_at": datetime.now(timezone.utc),
    }
    update_data_cleaned = {k: v for k, v in update_data.items() if v is not None}
    try:
        session_ref.update(update_data_cleaned)
        return True
    except Exception:
        return False


def add_interaction(
    session_id: str, interaction_data: InteractionLogSchema
) -> Optional[str]:
    db = get_db()
    try:
        interaction_ref = (
            db.collection("sessions")
            .document(session_id)
            .collection("interactions")
            .document()
        )
        log_data = interaction_data.model_dump(exclude_unset=True, exclude={"id"})
        log_data["created_at"] = datetime.now(timezone.utc)
        interaction_ref.set(log_data)
        return interaction_ref.id
    except Exception:
        return None


def render_report_html(session_data, logs, summary):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("report.html")
    html = template.render(session=session_data, logs=logs, summary=summary)
    return html


def generate_pdf_from_html(
    html: str, out_path: str, wkhtmltopdf_path: Optional[str] = None
):
    config = None
    if wkhtmltopdf_path:
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    pdfkit.from_string(html, out_path, configuration=config)
    return out_path
