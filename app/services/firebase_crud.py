import os
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from google.cloud.firestore_v1.base_query import FieldFilter
from passlib.context import CryptContext

from app.core.firebase import get_db
from app.models.schemas import (
    EvaluationSchema,
    InteractionLogSchema,
    ReportSchema,
    SessionCreateSchema,
    SessionInterviewInfoPayload,
    SessionProfilePayload,
    SessionSchema,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_session_status(session_id: str) -> Optional[str]:
    db = get_db()
    session_ref = db.collection("sessions").document(session_id)
    session_data = session_ref.get().to_dict()
    return session_data.get("status")


def create_session(req: SessionCreateSchema) -> Optional[Tuple[str, str]]:
    db = get_db()
    code = secrets.token_hex(3).upper()
    session_ref = db.collection("sessions").document()
    hashed_password = get_password_hash(req.password)
    session_data = {
        "code": code,
        "status": "ready",
        "created_at": datetime.now(timezone.utc),
        "username": req.username,
        "pw_hash": hashed_password,
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


def save_session_profile(session_id: str, inputs: SessionProfilePayload) -> bool:
    db = get_db()
    session_ref = db.collection("sessions").document(session_id)
    update_data = {
        "age": inputs.age,
        "gender": inputs.gender,
        "email": inputs.email,
        "status": "profile_saved",
        "updated_at": datetime.now(timezone.utc),
    }
    update_data_cleaned = {k: v for k, v in update_data.items() if v is not None}
    try:
        session_ref.update(update_data_cleaned)
        return True
    except Exception:
        return False


def save_session_interview_info(
    session_id: str, inputs: SessionInterviewInfoPayload
) -> bool:
    db = get_db()
    session_ref = db.collection("sessions").document(session_id)
    update_data = {
        "company": inputs.company,
        "position": inputs.position,
        "self_intro": inputs.self_intro,
        "status": "interview_info_saved",
        "updated_at": datetime.now(timezone.utc),
    }
    update_data_cleaned = {k: v for k, v in update_data.items() if v is not None}
    try:
        session_ref.update(update_data_cleaned)
        return True
    except Exception:
        return False


def save_chat_end(session_id: str) -> bool:
    db = get_db()
    session_ref = db.collection("sessions").document(session_id)
    update_data = {
        "status": "chat_end",
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


def get_all_questions_and_answers() -> Tuple[list, list]:
    """
    모든 세션의 모든 인터랙션(질문/응답)을 리스트로 반환합니다.
    반환 예시: [{ 'session_id': ..., 'turn': ..., 'question': ..., 'answer': ... }, ...]
    """
    db = get_db()
    result = []
    eval_result = []
    sessions = db.collection("sessions").stream()
    for session in sessions:
        session_id = session.id
        interactions_ref = (
            db.collection("sessions").document(session_id).collection("interactions")
        )
        interactions = interactions_ref.stream()
        for interaction in interactions:
            data = interaction.to_dict()
            result.append(
                {
                    "session_id": session_id,
                    "turn": data.get("turn"),
                    "question": data.get("question"),
                    "answer": data.get("answer"),
                }
            )
            eval_result.append(
                {
                    "session_id": session_id,
                    "turn": data.get("turn"),
                    "evaluation": data.get("evaluation"),
                }
            )
    return result, eval_result
