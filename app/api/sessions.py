from app.services import firebase_crud, llm_service, rag
from app.models.schemas import (
    EvaluationSchema,
    InteractionLogSchema,
    ReportResponse,
    SessionCreateResponse,
    SessionCreateSchema,
    SessionInterviewInfoPayload,
    SessionJoinResponse,
    SessionProfilePayload,
)
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
import io
import speech_recognition as sr
from pydub import AudioSegment
import os
import re
import uuid
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


TEMP_RAG_DB = {
    "company_overview": "회사 개요",
    "job_posting": "채용 공고",
    "tech_stack": "기술스택",
    "hiring_values": "가치관",
    "sample_interview_questions": "샘플 질문",
}


router = APIRouter()


class SessionJoinRequest(BaseModel):
    username: str
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
    persona_name: str
    department: str


class GenerateQuestionsRequest(BaseModel):
    num_questions: int = 5


class GenerateQuestionsResponse(BaseModel):
    questions: list


class GenerateReportResponse(BaseModel):
    url: str
    report_type: str
    summary: str


@router.get("/")
def root():
    return {"message": "AI Interview API 서버입니다."}


@router.post("/sessions", response_model=SessionCreateResponse)
def create_session(req: SessionCreateSchema):
    missing = []
    if not req.username:
        missing.append("username")
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
    return SessionCreateResponse(
        code=code, session_id=session_id, created_at=datetime.now()
    )


@router.post("/sessions/{code}", response_model=SessionJoinResponse)
def join_session(code: str, req: SessionJoinRequest):

    missing = []
    if not req.username:
        missing.append("username")
    if not req.password:
        missing.append("password")
    if missing:
        raise HTTPException(
            status_code=400, detail=f"필수 입력 누락: {', '.join(missing)}"
        )
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
    if not firebase_crud.verify_password(req.password, data.get("pw_hash", "")):
        raise HTTPException(status_code=401, detail="비밀번호가 일치하지 않습니다.")

    return SessionJoinResponse(session_id=session_id, created_at=datetime.now())


@router.post("/sessions/{code}/persona", response_model=PersonaResponse)
def persona_api(code: str):

    session_id = firebase_crud.get_session_id_by_code(code)
    db = firebase_crud.get_db()
    doc = db.collection("sessions").document(session_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="세션이 존재하지 않습니다.")
    data = doc.to_dict()
    company = data.get("company")
    position = data.get("position")
    rag_info_ref = db.collection("jobs").document(f"({company}, {position})")
    rag_info = rag_info_ref.get()
    if rag_info.exists:
        rag_info = rag_info.to_dict()
    else:
        rag_info = TEMP_RAG_DB
    persona_dict = llm_service.generate_persona(rag_info, company, position)
    persona = persona_dict.get("persona", "") if isinstance(
        persona_dict, dict) else ""
    # Firestore에 persona 저장
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")

    db.collection("sessions").document(session_id).update(
        {
            "persona": persona,
            "persona_name": persona_dict.get("persona_name", ""),
            "department": persona_dict.get("department", ""),
        }
    )
    return PersonaResponse(
        persona_name=persona_dict.get("persona_name", ""),
        department=persona_dict.get("department", ""),
    )


# 저장된 persona 가져오기
@router.get("/sessions/{code}/persona", response_model=PersonaResponse)
def get_persona(code: str):
    session_id = firebase_crud.get_session_id_by_code(code)
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")

    db = firebase_crud.get_db()
    doc = db.collection("sessions").document(session_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="세션이 존재하지 않습니다.")

    data = doc.to_dict()
    persona_name = data.get("persona_name", "")
    department = data.get("department", "")
    return PersonaResponse(
        persona_name=persona_name,
        department=department,
    )


@router.post("/sessions/{code}/questions", response_model=GenerateQuestionsResponse)
def questions_api(code: str, req: GenerateQuestionsRequest):
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
    user_info = {
        "company": data.get("company", ""),
        "position": data.get("position", ""),
        "name": data.get("name", ""),
        "age": data.get("age", ""),
        "gender": data.get("gender", ""),
        "self_intro": data.get("self_intro", ""),
    }

    company = data.get("company")
    position = data.get("position")
    rag_info_ref = db.collection("jobs").document(f"({company}, {position})")
    rag_info = rag_info_ref.get()
    if rag_info.exists:
        rag_info = rag_info.to_dict()
    else:
        rag_info = TEMP_RAG_DB

    keywords = rag.get_top_keywords_by_category(user_info)
    questions = llm_service.generate_questions(
        persona, keywords, user_info, rag_info, req.num_questions
    )
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


@router.post("/sessions/{code}/profile")
def save_profile(code: str, payload: SessionProfilePayload):
    # 필수 입력 검증
    missing = []
    if not payload.name:
        missing.append("name")
    if not payload.age:
        missing.append("age")
    if not payload.gender:
        missing.append("gender")
    if not payload.email:
        missing.append("email")
    if missing:
        raise HTTPException(
            status_code=400, detail=f"필수 입력 누락: {', '.join(missing)}"
        )
    session_id = firebase_crud.get_session_id_by_code(code)
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    ok = firebase_crud.save_session_profile(session_id, payload)
    if not ok:
        raise HTTPException(status_code=500, detail="입력 저장 실패")
    return {"message": "Profile created successfully"}


@router.post("/sessions/{code}/interview_info")
def save_interview_info(code: str, payload: SessionInterviewInfoPayload):
    session_id = firebase_crud.get_session_id_by_code(code)

    missing = []
    if not payload.company:
        missing.append("company")
    if not payload.position:
        missing.append("position")
    if not payload.self_intro:
        missing.append("self_intro")
    if missing:
        raise HTTPException(
            status_code=400, detail=f"필수 입력 누락: {', '.join(missing)}"
        )
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    ok = firebase_crud.save_session_interview_info(session_id, payload)
    if not ok:
        raise HTTPException(status_code=500, detail="입력 저장 실패")
    return {"message": "Interview info saved successfully"}


@router.websocket("/sessions/{code}/ws/chat")
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
            evaluation = llm_service.evaluate_answer(
                questions[turn]["text"], answer)
            print(evaluation)
            # dict가 아니면 빈 dict로 처리
            if not isinstance(evaluation, dict):
                evaluation = {}
            # categories에서 점수/피드백 추출
            categories = evaluation.get("categories", [])
            scores = [cat.get("score", 0) for cat in categories]
            feedbacks = [cat.get("feedback", "") for cat in categories]
            # InteractionLog 기록 (평가 결과는 클라에 전송X)
            evaluations = (
                [EvaluationSchema(categories=categories)] if categories else []
            )
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
            if scores and len(scores) > 0:
                try:
                    avg_score = sum(float(s) for s in scores) / len(scores)
                except Exception:
                    avg_score = None
            need_followup = False
            if avg_score is not None and avg_score < 3:
                need_followup = True
            # 꼬리질문 최대 2회
            q_and_a_history = [
                {"question": questions[turn]["text"], "answer": answer}]
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
                followup_eval = llm_service.evaluate_answer(
                    followup_q, followup_answer)
                if not isinstance(followup_eval, dict):
                    followup_eval = {}
                followup_categories = followup_eval.get("categories", [])
                followup_scores = [cat.get("score", 0)
                                   for cat in followup_categories]
                followup_evaluations = (
                    [EvaluationSchema(categories=followup_categories)]
                    if followup_categories
                    else []
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
                if followup_scores and len(followup_scores) > 0:
                    try:
                        avg_score = sum(float(s) for s in followup_scores) / len(
                            followup_scores
                        )
                    except Exception:
                        avg_score = None
                if avg_score is not None and avg_score < 3:
                    need_followup = True
            turn += 1
        firebase_crud.save_chat_end(session_id)
        await websocket.send_json(
            {"event": "면접 종료", "message": "모든 질문이 소진되었습니다."}
        )
        await websocket.close()
    except WebSocketDisconnect:
        pass


@router.post("/sessions/{code}/chat/end")
def end_session(code: str):
    session_id = firebase_crud.get_session_id_by_code(code)
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    status = firebase_crud.get_session_status(session_id)
    if status != "chat_end":
        raise HTTPException(status_code=500, detail="면접 종료 전 채팅을 종료해주세요.")

    # eval 추가
    return {
        "message": "Interview session ended successfully",
        "final_evaluation": "in-progress",
    }


@router.post("/sessions/{code}/final_eval")
def final_eval_session(code: str):
    session_id = firebase_crud.get_session_id_by_code(code)
    if not session_id:
        raise HTTPException(status_code=404, detail="세션 코드가 유효하지 않습니다.")
    status = firebase_crud.get_session_status(session_id)
    if status != "chat_end":
        raise HTTPException(status_code=500, detail="면접이 아직 종료되지 않았습니다.")

    # 해당 세션의 인터랙션만 추출
    db = firebase_crud.get_db()
    interactions_ref = (
        db.collection("sessions").document(
            session_id).collection("interactions")
    )
    interactions = list(interactions_ref.stream())
    logs = [x.to_dict() for x in interactions]
    result = llm_service.final_eval(logs)

    db.collection("sessions").document(
        session_id).update({"final_eval": result})
    return result


@router.websocket("/sessions/{code}/ws/stt")
async def sst_ws(websocket: WebSocket, code: str):
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
        await websocket.send_json({"error": "세션에 질문이 없습니다. 먼저 질문을 생성하세요."})
        await websocket.close(code=4003)
        return

    client = genai.Client()
    SAMPLE_RATE = 24000
    CHANNELS = 1

    async def stream_tts(text: str, voice_name: str = "Sadaltager"):
        await websocket.send_json({
            "event": "question_audio_start",
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "format": "pcm_s16le"
        })
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name,
                            )
                        )
                    ),
                ),
            )
            # 전체 오디오 바이트를 한 번에 전송
            sent_any = False
            candidates = getattr(response, "candidates", [])
            if candidates:
                content = getattr(candidates[0], "content", None)
                if content:
                    for part in getattr(content, "parts", []):
                        inline = getattr(part, "inline_data", None)
                        if inline and getattr(inline, "data", None):
                            await websocket.send_bytes(inline.data)
                            sent_any = True
            if not sent_any:
                await websocket.send_json({"error": "TTS 응답이 비어있습니다."})
        except Exception:
            await websocket.send_json({"error": "TTS 생성에 실패했습니다."})
        finally:
            await websocket.send_json({"event": "question_audio_end"})

    def transcribe_mp3(mp3_bytes: bytes) -> str:
        """
        MP3 바이트를 WAV(PCM, mono, 16kHz)로 변환 후 Google Web Speech API(ko-KR)로 전사.
        """
        try:
            audio_seg = AudioSegment.from_file(
                io.BytesIO(mp3_bytes), format="mp3")
            audio_seg = audio_seg.set_channels(
                1).set_frame_rate(16000).set_sample_width(2)
            wav_buf = io.BytesIO()
            audio_seg.export(wav_buf, format="wav")
            wav_buf.seek(0)

            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_buf) as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language='ko-KR')
            print("stt_text", text)
            return text.strip()
        except sr.UnknownValueError:
            print("stt_unknown_error")
            return ""
        except Exception as e:
            print("stt_error", e)
            return ""

    turn = 0
    try:
        while turn < len(questions):
            question_text = questions[turn]["text"]
            await stream_tts(question_text)

            recv = await websocket.receive()

            mp3_bytes = None
            if recv.get("type") == "websocket.disconnect":
                break
            if "bytes" in recv and recv["bytes"] is not None:
                mp3_bytes = recv["bytes"]
            elif "text" in recv and recv["text"]:
                # 텍스트 제어 메시지는 무시
                pass

            if not mp3_bytes:
                await websocket.send_json({"error": "오디오 응답이 필요합니다."})
                await websocket.close(code=4004)
                return

            answer_text = transcribe_mp3(mp3_bytes)
            evaluation = llm_service.evaluate_answer(
                question_text, answer_text)
            if not isinstance(evaluation, dict):
                evaluation = {}

            categories = evaluation.get("categories", [])
            scores = [cat.get("score", 0) for cat in categories]
            evaluations = (
                [EvaluationSchema(categories=categories)] if categories else []
            )
            log = InteractionLogSchema(
                turn=turn + 1,
                question=question_text,
                answer=answer_text,
                evaluation=evaluations,
            )
            firebase_crud.add_interaction(session_id, log)

            followup_count = 0
            avg_score = None
            if scores and len(scores) > 0:
                try:
                    avg_score = sum(float(s) for s in scores) / len(scores)
                except Exception:
                    avg_score = None
            need_followup = False
            if avg_score is not None and avg_score < 3:
                need_followup = True
            q_and_a_history = [
                {"question": question_text, "answer": answer_text}]

            while need_followup and followup_count < 2:
                followup_result = llm_service.insufficient_judgment(
                    data.get("persona", ""), q_and_a_history
                )
                if not (isinstance(followup_result, dict) and followup_result.get("followup")):
                    break
                followup_q = followup_result.get("question", "")
                await stream_tts(followup_q)

                recv_fu = await websocket.receive()
                fu_mp3 = None
                if recv_fu.get("type") == "websocket.disconnect":
                    need_followup = False
                    break
                if "bytes" in recv_fu and recv_fu["bytes"] is not None:
                    fu_mp3 = recv_fu["bytes"]
                if not fu_mp3:
                    need_followup = False
                    break

                followup_answer = transcribe_mp3(fu_mp3)
                followup_eval = llm_service.evaluate_answer(
                    followup_q, followup_answer)
                if not isinstance(followup_eval, dict):
                    followup_eval = {}
                followup_categories = followup_eval.get("categories", [])
                followup_scores = [cat.get("score", 0)
                                   for cat in followup_categories]
                followup_evaluations = (
                    [EvaluationSchema(categories=followup_categories)]
                    if followup_categories
                    else []
                )
                log = InteractionLogSchema(
                    turn=turn + 1,
                    question=followup_q,
                    answer=followup_answer,
                    evaluation=followup_evaluations,
                )
                firebase_crud.add_interaction(session_id, log)
                followup_count += 1
                q_and_a_history.append(
                    {"question": followup_q, "answer": followup_answer})

                need_followup = False
                avg_score = None
                if followup_scores and len(followup_scores) > 0:
                    try:
                        avg_score = sum(
                            float(s) for s in followup_scores) / len(followup_scores)
                    except Exception:
                        avg_score = None
                if avg_score is not None and avg_score < 3:
                    need_followup = True

            turn += 1

        firebase_crud.save_chat_end(session_id)
        await websocket.send_json({"event": "면접 종료", "message": "모든 질문이 소진되었습니다."})
        await websocket.close()
    except WebSocketDisconnect:
        pass
