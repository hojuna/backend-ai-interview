import os
import re
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from app.models.schemas import (
    EvaluationSchema,
    InteractionLogSchema,
    QuestionSchema,
    ReportResponse,
    SessionCreateResponse,
    SessionCreateSchema,
    SessionInputsPayload,
    SessionInterviewInfoPayload,
    SessionProfilePayload,
    SessionSchema,
)
from app.services import firebase_crud, llm_service
from app.services.rag_temp_db import search_rag

router = APIRouter()


class SessionJoinRequest(BaseModel):
    name: str
    password: str


class JobUrlRequest(BaseModel):
    url: str


class JobUrlParseResponse(BaseModel):
    company_name: str
    job_role: str


class PersonaRequest(BaseModel):
    company_name: str
    job_role: str


class PersonaResponse(BaseModel):
    persona: str


class GenerateQuestionsRequest(BaseModel):
    num_questions: int = 5


class GenerateQuestionsResponse(BaseModel):
    questions: list


class GenerateReportResponse(BaseModel):
    url: str
    report_type: str
    summary: str


@router.post("/sessions", response_model=SessionCreateResponse)
def create_session(req: SessionCreateSchema):
    missing = []
    if not req.id:
        missing.append("id")
    if not req.password:
        missing.append("password")
    if missing:
        raise HTTPException(
            status_code=422, detail=f"필수 입력 누락: {', '.join(missing)}"
        )
    result = firebase_crud.create_session(req)
    if not result:
        raise HTTPException(status_code=500, detail="세션 생성 실패")
    session_id, code = result
    return SessionCreateResponse(code=code, session_id=session_id)


@router.post("/sessions/{code}/join", response_model=SessionSchema)
def join_session(code: str, req: SessionJoinRequest):
    session_id = firebase_crud.get_session_id_by_code(code)
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    # Firestore에서 세션 정보 조회
    db = firebase_crud.get_db()
    doc = db.collection("sessions").document(session_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="세션이 존재하지 않습니다.")
    data = doc.to_dict()
    # 이름, 비밀번호 검증
    if data.get("name") != req.name:
        raise HTTPException(status_code=401, detail="이름이 일치하지 않습니다.")
    if not firebase_crud.verify_password(req.password, data.get("pw_hash", "")):
        raise HTTPException(status_code=401, detail="비밀번호가 일치하지 않습니다.")
    # Pydantic 모델로 변환
    return SessionSchema(**data, id=session_id)


@router.post("/sessions/{code}/persona", response_model=PersonaResponse)
def persona_api(code: str, req: PersonaRequest):

    session_id = firebase_crud.get_session_id_by_code(code)

    # TODO: 사용자의 입력 정보를 통해서 rag_info 생성 로직 구현해야함
    rag_info = search_rag(req.company_name, req.job_role)
    if not rag_info:
        raise HTTPException(
            status_code=404, detail="RAG DB에서 회사/직군 정보를 찾을 수 없습니다."
        )
    persona_dict = llm_service.generate_persona(rag_info)
    persona = persona_dict.get("persona", "") if isinstance(persona_dict, dict) else ""
    # Firestore에 persona 저장

    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    db = firebase_crud.get_db()
    db.collection("sessions").document(session_id).update({"persona": persona})
    return PersonaResponse(persona=persona)


@router.post(
    "/sessions/{code}/generate_questions", response_model=GenerateQuestionsResponse
)
def generate_questions_api(code: str, req: GenerateQuestionsRequest):
    session_id = firebase_crud.get_session_id_by_code(code)
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    db = firebase_crud.get_db()
    doc = db.collection("sessions").document(session_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="세션이 존재하지 않습니다.")
    data = doc.to_dict()
    persona = data.get("persona")
    if not persona:
        raise HTTPException(
            status_code=400,
            detail="세션에 페르소나가 없습니다. 먼저 페르소나를 생성하세요.",
        )
    questions = llm_service.generate_questions(persona, req.num_questions)
    print(questions)
    if not isinstance(questions, list) or len(questions) == 0:
        raise HTTPException(
            status_code=500, detail="질문 생성에 실패했습니다. LLM 응답을 확인하세요."
        )
    # 각 질문에 id, type, difficulty(예약) 추가
    questions_with_meta = []
    for q in questions:
        questions_with_meta.append(
            {
                "id": str(uuid.uuid4()),
                "text": q.get("question", ""),
                "type": "basic",
                "difficulty": None,  # 난이도 필드 예약
            }
        )
    db.collection("sessions").document(session_id).update(
        {"questions": questions_with_meta}
    )
    return GenerateQuestionsResponse(questions=questions_with_meta)


# @router.post("/sessions/{code}/parse_job_url", response_model=JobUrlParseResponse)
# def parse_job_url(code: str, req: JobUrlRequest):
#     # 예시: URL에서 회사명/직군 추출 (실제 구현은 크롤링/정규식 등 활용)
#     # 예: https://jobs.example.com/naver/backend-engineer
#     m = re.search(r"jobs\\.\w+\\.com/(\w+)/(\w+)", req.url)
#     if m:
#         company = m.group(1).capitalize()
#         role = m.group(2).replace("-", " ").capitalize()
#         return JobUrlParseResponse(company_name=company, job_role=role)
#     raise HTTPException(
#         status_code=422,
#         detail="URL에서 회사/직군 정보를 추출할 수 없습니다. 수동 입력을 이용해 주세요.",
#     )


@router.post("/sessions/{code}/profile")
def save_profile(code: str, payload: SessionProfilePayload):
    # 필수 입력 검증
    missing = []

    if not payload.age:
        missing.append("age")
    if not payload.gender:
        missing.append("gender")
    if payload.education:
        if not payload.education.school:
            missing.append("education.school")
        if not payload.education.major:
            missing.append("education.major")
        if not payload.education.gradYear:
            missing.append("education.gradYear")
    if not payload.organization:
        missing.append("organization")
    if not payload.position:
        missing.append("position")
    if missing:
        raise HTTPException(
            status_code=422, detail=f"필수 입력 누락: {', '.join(missing)}"
        )

    session_id = firebase_crud.get_session_id_by_code(code)
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    ok = firebase_crud.save_session_profile(session_id, payload)
    if not ok:
        raise HTTPException(status_code=500, detail="입력 저장 실패")
    return {"success": True}


@router.post("/sessions/{code}/interview_info")
def save_interview_info(code: str, payload: SessionInterviewInfoPayload):
    session_id = firebase_crud.get_session_id_by_code(code)

    missing = []
    if not payload.company_name:
        missing.append("company_name")
    if not payload.job_role:
        missing.append("job_role")
    if not payload.self_intro:
        missing.append("self_intro")
    if missing:
        raise HTTPException(
            status_code=422, detail=f"필수 입력 누락: {', '.join(missing)}"
        )
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    ok = firebase_crud.save_session_interview_info(session_id, payload)
    if not ok:
        raise HTTPException(status_code=500, detail="입력 저장 실패")
    return {"success": True}


@router.websocket("/sessions/{code}/chat")
async def chat_ws(websocket: WebSocket, code: str):
    await websocket.accept()
    session_id = firebase_crud.get_session_id_by_code(code)
    if not session_id:
        await websocket.close(code=4001)
        return
    db = firebase_crud.get_db()
    doc = db.collection("sessions").document(session_id).get()
    if not doc.exists:
        await websocket.close(code=4002)
        return
    data = doc.to_dict()
    questions = data.get("questions", [])
    if not questions:
        await websocket.send_json(
            {"error": "세션에 질문이 없습니다. 먼저 질문을 생성하세요."}
        )
        await websocket.close(code=4003)
        return
    turn = 0
    try:
        while turn < len(questions):
            # 질문 전송
            await websocket.send_json({"question": questions[turn]["text"]})
            # 답변 수신
            answer = await websocket.receive_text()
            # 평가
            evaluation = llm_service.evaluate_answer(questions[turn]["text"], answer)
            # dict가 아니면 빈 dict로 처리
            if not isinstance(evaluation, dict):
                evaluation = {}
            # InteractionLog 기록 (평가 결과는 클라에 전송X)
            evaluations = [EvaluationSchema(**evaluation)] if evaluation else []
            log = InteractionLogSchema(
                turn=turn + 1,
                question=questions[turn]["text"],
                answer=answer,
                evaluation=evaluations,
            )
            firebase_crud.add_interaction(session_id, log)
            # 꼬리질문 판단
            followup_count = 0
            avg_score = None
            if evaluations and hasattr(evaluations[0], "score"):
                scores = evaluations[0].score
                if scores is not None and isinstance(scores, list) and len(scores) > 0:
                    try:
                        avg_score = sum(
                            float(s)
                            for s in scores
                            if isinstance(s, (int, float, str))
                            and str(s).replace(".", "", 1).isdigit()
                        ) / len(scores)
                    except Exception:
                        avg_score = None
            need_followup = False
            if avg_score is not None and avg_score < 3:
                need_followup = True
            # 꼬리질문 최대 2회
            q_and_a_history = [{"question": questions[turn]["text"], "answer": answer}]
            while need_followup and followup_count < 2:
                # insufficient_judgment를 활용해 꼬리질문 필요성 및 질문 생성
                followup_result = llm_service.insufficient_judgment(
                    data.get("persona", ""), q_and_a_history
                )
                if not (
                    isinstance(followup_result, dict)
                    and followup_result.get("followup")
                ):
                    break
                followup_q = followup_result.get("question", "")
                await websocket.send_json({"question": followup_q, "followup": True})
                followup_answer = await websocket.receive_text()
                followup_eval = llm_service.evaluate_answer(followup_q, followup_answer)
                if not isinstance(followup_eval, dict):
                    followup_eval = {}
                followup_evaluations = (
                    [EvaluationSchema(**followup_eval)] if followup_eval else []
                )
                log = InteractionLogSchema(
                    turn=turn + 1,
                    question=followup_q,
                    answer=followup_answer,
                    evaluation=followup_evaluations,
                )
                firebase_crud.add_interaction(session_id, log)
                followup_count += 1
                # q_and_a_history에 추가
                q_and_a_history.append(
                    {"question": followup_q, "answer": followup_answer}
                )
                # 추가 꼬리질문 필요 여부 재판단
                need_followup = False
                avg_score = None
                if followup_evaluations and hasattr(followup_evaluations[0], "score"):
                    scores = followup_evaluations[0].score
                    if (
                        scores is not None
                        and isinstance(scores, list)
                        and len(scores) > 0
                    ):
                        try:
                            avg_score = sum(
                                float(s)
                                for s in scores
                                if isinstance(s, (int, float, str))
                                and str(s).replace(".", "", 1).isdigit()
                            ) / len(scores)
                        except Exception:
                            avg_score = None
                if avg_score is not None and avg_score < 3:
                    need_followup = True
            turn += 1
        await websocket.send_json(
            {"event": "면접 종료", "message": "모든 질문이 소진되었습니다."}
        )
        await websocket.close()
    except WebSocketDisconnect:
        pass


@router.post("/sessions/{code}/generate_report", response_model=GenerateReportResponse)
def generate_report_api(code: str):
    session_id = firebase_crud.get_session_id_by_code(code)
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    db = firebase_crud.get_db()
    session_doc = db.collection("sessions").document(session_id).get()
    if not session_doc.exists:
        raise HTTPException(status_code=404, detail="세션이 존재하지 않습니다.")
    session_data = session_doc.to_dict()
    # InteractionLog 취합
    interactions = list(
        db.collection("sessions")
        .document(session_id)
        .collection("interactions")
        .stream()
    )
    logs = [x.to_dict() for x in interactions]
    # LLM으로 요약/분석(임시)
    summary_prompt = f"""
    아래는 신입 개발자 모의면접 세션의 질문/답변/평가 기록입니다. 전체 면접을 요약하고, 강점/개선점/최종 총평을 10줄 이내로 정리해줘.
    {logs}
    """
    summary = llm_service.ask_llm(summary_prompt)
    # HTML/PDF 생성
    html = firebase_crud.render_report_html(session_data, logs, summary)
    reports_dir = os.path.join(os.getcwd(), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    pdf_path = os.path.join(reports_dir, f"report_{session_id}.pdf")
    # wkhtmltopdf 경로가 필요하면 환경변수나 기본값 사용
    wkhtmltopdf_path = os.environ.get("WKHTMLTOPDF_PATH") or "wkhtmltopdf"
    firebase_crud.generate_pdf_from_html(html, pdf_path, wkhtmltopdf_path)
    # 파일 URL (로컬 경로 예시)
    report_url = f"/reports/report_{session_id}.pdf"
    db.collection("sessions").document(session_id).update(
        {"report": {"url": report_url, "report_type": "pdf", "summary": summary}}
    )
    return GenerateReportResponse(url=report_url, report_type="pdf", summary=summary)


@router.get("/sessions/{code}/report", response_model=ReportResponse)
def get_report(code: str):
    session_id = firebase_crud.get_session_id_by_code(code)
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    db = firebase_crud.get_db()
    doc = db.collection("sessions").document(session_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="세션이 존재하지 않습니다.")
    data = doc.to_dict()
    report = data.get("report")
    if not report:
        raise HTTPException(
            status_code=404, detail="리포트가 아직 생성되지 않았습니다."
        )
    return ReportResponse(**report)
