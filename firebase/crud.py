from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1 import ArrayUnion, Increment # Firestore 특정 연산자
import secrets
from passlib.context import CryptContext
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any

from . import schemas # 현재 디렉토리의 schemas.py
from .firebase_connector import get_firestore_client # firebase_connector.py에서 클라이언트 가져오기

# --- Firestore 클라이언트 가져오기 ---
def get_db():
    return get_firestore_client()

# --- 비밀번호 해싱 ---
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# --- Helper Functions ---
def _update_session_status(session_id: str, status: str, db=None) -> bool:
    if db is None:
        db = get_db()
    session_ref = db.collection('sessions').document(session_id)
    try:
        session_ref.update({
            "status": status,
            "updated_at": datetime.now(timezone.utc)
        })
        print(f"세션 {session_id} 상태 변경: {status}")
        return True
    except Exception as e:
        print(f"세션 {session_id} 상태 변경 실패: {e}")
        return False

def get_session_doc(session_id: str, db=None) -> Optional[Dict[str, Any]]:
    if db is None:
        db = get_db()
    doc_ref = db.collection('sessions').document(session_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

# --- 세션 생성 및 초기 설정 관련 CRUD ---

def create_session() -> Optional[Tuple[str, str]]:
    db = get_db()
    code = secrets.token_hex(3).upper()
    # TODO: 코드 중복 방지 로직 (매우 낮은 확률)

    session_ref = db.collection('sessions').document()
    session_data = schemas.SessionFirestoreSchema(
        code=code,
        status="ready",
        created_at=datetime.now(timezone.utc)
    )
    session_ref.set(session_data.model_dump(exclude_none=True))
    print(f"세션 생성 완료: ID={session_ref.id}, Code={code}")
    return session_ref.id, code

def get_session_id_by_code(code: str) -> Optional[str]:
    db = get_db()
    sessions_ref = db.collection('sessions')
    query = sessions_ref.where(filter=FieldFilter("code", "==", code)).limit(1)
    results = list(query.stream())
    if results:
        return results[0].id
    return None

def join_session_with_credentials(session_id: str, payload: schemas.SessionJoinPayload) -> bool:
    db = get_db()
    session_ref = db.collection('sessions').document(session_id)
    hashed_password = get_password_hash(payload.password)
    try:
        session_ref.update({
            "name": payload.name,
            "pw_hash": hashed_password
        })
        return _update_session_status(session_id, "joined", db=db)
    except Exception as e:
        print(f"세션 참가 정보(이름/비밀번호) 저장 실패 (ID: {session_id}): {e}")
        return False

def update_session_profile(session_id: str, payload: schemas.ProfilePayload) -> bool:
    db = get_db()
    session_ref = db.collection('sessions').document(session_id)
    try:
        update_data = {
            "email": payload.email,
            "education": payload.education.model_dump(exclude_none=True)
        }
        if payload.career_summary is not None:
            update_data["career_summary"] = payload.career_summary
        session_ref.update(update_data)
        return _update_session_status(session_id, "profiled", db=db)
    except Exception as e:
        print(f"세션 프로필 정보 저장 실패 (ID: {session_id}): {e}")
        return False

def update_session_interview_info(session_id: str, payload: schemas.InterviewInfoPayload) -> bool:
    db = get_db()
    session_ref = db.collection('sessions').document(session_id)
    try:
        update_data = {
            "company_name": payload.company_name,
            "job_role": payload.job_role,
        }
        if payload.self_intro is not None:
            update_data["self_intro"] = payload.self_intro
        session_ref.update(update_data)
        return _update_session_status(session_id, "info_submitted", db=db)
    except Exception as e:
        print(f"세션 면접 정보 저장 실패 (ID: {session_id}): {e}")
        return False

def generate_and_save_persona(session_id: str) -> Optional[schemas.PersonaResponse]:
    db = get_db()
    session_ref = db.collection('sessions').document(session_id)
    session_data = get_session_doc(session_id, db)
    if not session_data: return None

    # TODO: AI 페르소나 생성 로직 호출 (session_data 활용)
    persona_text_example = f"'{session_data.get('job_role', '직무')}' 역할에 대한 면접관입니다."
    persona_details_example = {"company_focus": session_data.get('company_name'), "interviewer_style": "analytical"}

    try:
        update_data = {
            "persona_text": persona_text_example,
            "persona_config": persona_details_example
        }
        session_ref.update(update_data)
        _update_session_status(session_id, "persona_generated", db=db)
        return schemas.PersonaResponse(
            persona_text=persona_text_example,
            persona_details=persona_details_example
        )
    except Exception as e:
        print(f"페르소나 저장 실패 (ID: {session_id}): {e}")
        return None

def generate_and_save_questions(session_id: str, request_payload: Optional[schemas.QuestionGenerationRequest] = None) -> Optional[List[schemas.QuestionSchema]]:
    db = get_db()
    session_ref = db.collection('sessions').document(session_id)
    session_data = get_session_doc(session_id, db)
    if not session_data: return None

    # TODO: AI 질문 생성 로직 (session_data, request_payload.context 등 활용)
    # request_payload의 current_turn, last_interaction_id 등을 활용하여 꼬리질문 분기
    current_turn_for_question = request_payload.current_turn if request_payload else (len(session_data.get("questions_generated", [])) + 1)

    questions_example_data = [
        {"id": f"q_s{session_id}_t{current_turn_for_question}", "text": f"{current_turn_for_question}번째 생성된 질문입니다.", "type": "general", "turn": current_turn_for_question},
    ]
    if request_payload and request_payload.last_interaction_id:
        questions_example_data[0]["text"] = f"{current_turn_for_question}번째 꼬리 질문입니다 (이전 답변 ID: {request_payload.last_interaction_id})."
        questions_example_data[0]["type"] = "follow-up"

    questions_to_save_pydantic = [schemas.QuestionSchema(**q) for q in questions_example_data]
    questions_to_save_dict = [q.model_dump(exclude_none=True) for q in questions_to_save_pydantic]

    try:
        # 기존 질문에 추가하려면 ArrayUnion, 덮어쓰려면 그냥 set
        session_ref.update({"questions_generated": ArrayUnion(questions_to_save_dict)})
        _update_session_status(session_id, "questions_generated", db=db) # or 'interviewing'
        return questions_to_save_pydantic
    except Exception as e:
        print(f"질문 저장 실패 (ID: {session_id}): {e}")
        return None

def get_chat_history(session_id: str) -> Optional[List[schemas.InteractionLogSchema]]:
    db = get_db()
    interactions_ref = db.collection('sessions').document(session_id).collection('interactions').order_by("turn")
    logs = []
    try:
        for doc in interactions_ref.stream():
            log_data = doc.to_dict()
            log_data["id"] = doc.id
            logs.append(schemas.InteractionLogSchema(**log_data))
        return logs
    except Exception as e:
        print(f"채팅 내역 조회 실패 (ID: {session_id}): {e}")
        return None

def save_chat_answer(session_id: str, payload: schemas.AnswerPayload) -> Optional[schemas.InteractionLogSchema]:
    db = get_db()
    interaction_ref = db.collection('sessions').document(session_id).collection('interactions').document()

    # Fetch question_text if needed (optional for logging)
    question_text_val = None
    session_doc_data = get_session_doc(session_id, db=db)
    if session_doc_data and "questions_generated" in session_doc_data:
        for q_data in session_doc_data["questions_generated"]:
            q_schema = schemas.QuestionSchema(**q_data) # dict를 Pydantic 모델로 변환
            if q_schema.id == payload.question_id:
                question_text_val = q_schema.text
                break

    log_data_model = schemas.InteractionLogSchema(
        id=interaction_ref.id,
        turn=payload.turn,
        question_id=payload.question_id,
        question_text=question_text_val,
        answer_text=payload.answer_text,
        interaction_time=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )
    try:
        interaction_ref.set(log_data_model.model_dump(exclude_none=True))
        _update_session_status(session_id, "interviewing", db=db)
        return log_data_model
    except Exception as e:
        print(f"답변 저장 실패 (ID: {session_id}, Turn: {payload.turn}): {e}")
        return None

def evaluate_chat_answer(session_id: str, interaction_id: str) -> Optional[schemas.EvaluationSchema]:
    db = get_db()
    interaction_ref = db.collection('sessions').document(session_id).collection('interactions').document(interaction_id)
    interaction_doc = interaction_ref.get()
    if not interaction_doc.exists:
        print(f"평가할 인터랙션 로그 없음 (InteractionID: {interaction_id})")
        return None

    # TODO: AI 답변 평가 로직 호출 (interaction_doc.to_dict().get('answer_text') 활용)
    evaluation_example_data = schemas.EvaluationSchema(
        score={"technical_depth": 4, "communication": 5, "problem_solving": 3},
        feedback="답변 내용이 명확하며, 문제 해결에 대한 접근 방식이 논리적입니다. 다만, XYZ 부분에 대한 기술적 깊이가 조금 더 보강되면 좋겠습니다."
    )
    try:
        interaction_ref.update({
            "evaluation": evaluation_example_data.model_dump(exclude_none=True)
        })
        # _update_session_status(session_id, "evaluating", db=db) # 세션 상태는 면접 전체가 평가중일때 변경
        return evaluation_example_data
    except Exception as e:
        print(f"답변 평가 저장 실패 (InteractionID: {interaction_id}): {e}")
        return None

def judge_follow_up_question(session_id: str, interaction_id: str) -> Optional[schemas.FollowUpDecisionResponse]:
    db = get_db() # session_id는 로깅이나 컨텍스트용
    interaction_ref = db.collection('sessions').document(session_id).collection('interactions').document(interaction_id)
    interaction_doc = interaction_ref.get()
    if not interaction_doc.exists:
        print(f"꼬리질문 판단 대상 인터랙션 로그 없음 (InteractionID: {interaction_id})")
        return None
    # TODO: AI 꼬리질문 판단 로직 (interaction_doc.to_dict().get('answer_text') 활용)
    should_follow_up_example = True # 예시
    reason_example = "답변 내용 중 언급된 'ABC 기술'에 대해 더 자세히 알고 싶습니다."
    next_question_type_example = "technical_deep_dive"

    return schemas.FollowUpDecisionResponse(
        should_generate_follow_up=should_follow_up_example,
        reason=reason_example,
        next_question_type=next_question_type_example
    )

def end_interview(session_id: str) -> bool:
    return _update_session_status(session_id, "report_generating")

def initiate_report_generation(session_id: str) -> Optional[schemas.ReportSchema]:
    db = get_db()
    # 세션 당 하나의 리포트만 생성한다고 가정하고 reportId를 'summary' 등으로 고정하거나, 여러개면 자동 ID
    report_doc_id = "main_report" # 예시로 고정 ID 사용
    report_ref = db.collection('sessions').document(session_id).collection('report').document(report_doc_id)

    # TODO: 실제 리포트 생성 비동기 작업 트리거
    report_data = schemas.ReportSchema(
        id=report_ref.id,
        session_id=session_id,
        report_type="pdf", # 또는 html
        status="pending_generation",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timezone.timedelta(days=1) # 예시: 24시간 후 만료
    )
    try:
        report_ref.set(report_data.model_dump(exclude_none=True))
        # _update_session_status(session_id, "report_generating") # end_interview에서 처리
        return report_data
    except Exception as e:
        print(f"리포트 생성 시작 실패 (ID: {session_id}): {e}")
        return None

def get_report(session_id: str, report_id: Optional[str] = None) -> Optional[schemas.ReportSchema]:
    db = get_db()
    report_collection_ref = db.collection('sessions').document(session_id).collection('report')
    doc_to_get = None
    try:
        if report_id:
            doc_to_get_ref = report_collection_ref.document(report_id)
        else: # report_id 없으면 'main_report' (예시) 조회
            doc_to_get_ref = report_collection_ref.document("main_report")

        doc = doc_to_get_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            data["session_id"] = session_id
            return schemas.ReportSchema(**data)
        print(f"리포트 없음: SessionID={session_id}, ReportID={report_id if report_id else 'main_report'}")
        return None
    except Exception as e:
        print(f"리포트 조회 실패 (SessionID: {session_id}, ReportID: {report_id}): {e}")
        return None

def get_report_download_details(session_id: str, report_id: Optional[str] = None) -> Optional[schemas.ReportDownloadLinkResponse]:
    report_info = get_report(session_id, report_id)
    if report_info and report_info.status == "completed" and report_info.url:
        # TODO: report_info.url이 GCS URL이라면, 여기서 서명된 URL 생성 로직 필요
        # from google.cloud import storage
        # storage_client = storage.Client()
        # bucket = storage_client.bucket(bucket_name)
        # blob = bucket.blob(blob_name) # report_info.url 에서 파싱
        # signed_url = blob.generate_signed_url(version="v4", expiration=datetime.timedelta(minutes=15), method="GET")
        signed_url = report_info.url # 임시로 DB에 저장된 URL 사용 (실제로는 서명 필요)

        return schemas.ReportDownloadLinkResponse(
            download_url=signed_url,
            file_name=f"interview_report_{session_id}_{report_info.id or ''}.{report_info.report_type}",
            content_type=f"application/{report_info.report_type}" if report_info.report_type == "pdf" else "text/html"
        )
    elif report_info and report_info.status != "completed":
        print(f"리포트 다운로드 불가 - 아직 생성 중이거나 실패: {report_info.status}")
    elif not report_info:
        print(f"리포트 다운로드 불가 - 리포트 정보 없음")
    return None