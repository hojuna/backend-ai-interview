import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_service import answer_question_with_llm

logging.basicConfig(
    filename="test.log",  # 저장할 파일명
    level=logging.INFO,  # 저장할 로그 레벨
    format="%(asctime)s %(levelname)s %(message)s",
)


# def test_final_eval_analysis():
#     """
#     최종 평가 분석 API와 분석 메소드가 제대로 동작하는지 통합적으로 검증한다.
#     """
#     client = TestClient(app)
#     # 1. 세션 생성
#     res = client.post(
#         "/sessions", json={"username": "evaltestuser", "password": "testpw"}
#     )
#     assert res.status_code == 200
#     code = res.json()["code"]
#     # 2. 프로필 저장
#     profile_payload = {
#         "name": "홍길동",
#         "age": 25,
#         "gender": "남성",
#         "email": "test@example.com",
#     }
#     res_profile = client.post(f"/sessions/{code}/profile", json=profile_payload)
#     assert res_profile.status_code == 200
#     # 3. 면접 정보 저장
#     interview_payload = {
#         "company": "Naver",
#         "position": "Backend engineer",
#         "self_intro": "열심히 하겠습니다.",
#     }
#     res_interview = client.post(
#         f"/sessions/{code}/interview_info", json=interview_payload
#     )
#     assert res_interview.status_code == 200
#     # 4. 페르소나 생성
#     persona_payload = {"company_name": "Naver", "job_role": "Backend engineer"}
#     res_persona = client.post(f"/sessions/{code}/persona", json=persona_payload)
#     assert res_persona.status_code == 200
#     # 5. 질문 생성
#     res_questions = client.post(
#         f"/sessions/{code}/questions", json={"num_questions": 2}
#     )
#     assert res_questions.status_code == 200
#     questions = res_questions.json()["questions"]
#     assert len(questions) == 2
#     # 6. Q&A 진행 (WebSocket)
#     with client.websocket_connect(f"/sessions/{code}/chat") as ws:
#         for i in range(4):
#             msg = ws.receive_json()
#             if msg.get("event") == "면접 종료":
#                 break
#             assert "question" in msg
#             ws.send_text(answer_question_with_llm(msg["question"]))
#         # 종료 메시지
#         if msg.get("event") == "면접 종료":
#             end_msg = msg
#         else:
#             end_msg = ws.receive_json()
#             assert end_msg["event"] == "면접 종료"

#         assert end_msg["event"] == "면접 종료"
#     # 7. 최종 평가 분석 호출
#     res_eval = client.post(f"/sessions/{code}/final_eval")
#     assert res_eval.status_code == 200
#     data = res_eval.json()

#     # 필수 키 존재 및 타입 체크
#     assert "total_score" in data and isinstance(data["total_score"], (int, float))
#     assert "question_count" in data and isinstance(data["question_count"], int)
#     assert "category_scores" in data and isinstance(data["category_scores"], dict)
#     assert "category_feedbacks" in data and isinstance(data["category_feedbacks"], dict)
#     assert "questions" in data and isinstance(data["questions"], list)
#     assert "final_feedback" in data and isinstance(data["final_feedback"], str)
#     # 카테고리별 점수 6개
#     assert len(data["category_scores"]) == 6
#     # 질문별 상세 분석
#     for q in data["questions"]:
#         assert "question" in q and "answer" in q and "scores" in q and "feedback" in q
#         assert isinstance(q["scores"], list) and len(q["scores"]) == 6
#     # 최종 피드백 길이 체크
#     assert len(data["final_feedback"]) > 0
#     log = logging.getLogger(__name__)
#     log.info(data)


# def test_various_question_counts():
#     """
#     질문 개수 다양화(1, 3, 5개) 시나리오
#     """
#     client = TestClient(app)
#     for n in [1, 3, 5]:
#         res = client.post("/sessions", json={"username": f"user{n}", "password": "pw"})
#         code = res.json()["code"]
#         profile_payload = {
#             "name": "테스터",
#             "age": 22,
#             "gender": "여성",
#             "email": "test@ex.com",
#         }
#         client.post(f"/sessions/{code}/profile", json=profile_payload)
#         interview_payload = {
#             "company": "Kakao",
#             "position": "Frontend engineer",
#             "self_intro": "열정적입니다.",
#         }
#         client.post(f"/sessions/{code}/interview_info", json=interview_payload)
#         persona_payload = {"company_name": "Kakao", "job_role": "Frontend engineer"}
#         client.post(f"/sessions/{code}/persona", json=persona_payload)
#         res_questions = client.post(
#             f"/sessions/{code}/questions", json={"num_questions": n}
#         )
#         questions = res_questions.json()["questions"]
#         assert len(questions) == n
#         with client.websocket_connect(f"/sessions/{code}/chat") as ws:
#             for i in range(n):
#                 msg = ws.receive_json()
#                 if msg.get("event") == "면접 종료":
#                     break
#                 ws.send_text(answer_question_with_llm(msg["question"]))
#             end_msg = ws.receive_json()
#             assert end_msg["event"] == "면접 종료"
#         res_eval = client.post(f"/sessions/{code}/final_eval")
#         assert res_eval.status_code == 200
#         data = res_eval.json()
#         assert data["question_count"] == n


def test_eval_missing_fields():
    """
    LLM이 점수/피드백 누락 등 비정상 응답을 반환해도 시스템이 견고하게 동작하는지(수동으로 mock)
    """
    from unittest.mock import patch

    client = TestClient(app)
    res = client.post("/sessions", json={"username": "missingeval", "password": "pw"})
    code = res.json()["code"]
    profile_payload = {
        "name": "누락테스터",
        "age": 28,
        "gender": "여성",
        "email": "miss@ex.com",
    }
    client.post(f"/sessions/{code}/profile", json=profile_payload)
    interview_payload = {
        "company": "Kakao",
        "position": "Frontend engineer",
        "self_intro": "성장하고 싶습니다.",
    }
    client.post(f"/sessions/{code}/interview_info", json=interview_payload)
    persona_payload = {"company_name": "Kakao", "job_role": "Frontend engineer"}
    client.post(f"/sessions/{code}/persona", json=persona_payload)
    res_questions = client.post(
        f"/sessions/{code}/questions", json={"num_questions": 1}
    )
    questions = res_questions.json()["questions"]
    # patch evaluate_answer to return abnormal result
    with patch("app.services.llm_service.evaluate_answer", return_value={}):
        with client.websocket_connect(f"/sessions/{code}/chat") as ws:
            msg = ws.receive_json()
            ws.send_text("테스트 답변")
            end_msg = ws.receive_json()
            assert end_msg["event"] == "면접 종료"
    res_eval = client.post(f"/sessions/{code}/final_eval")
    assert res_eval.status_code == 200
    data = res_eval.json()
    # 점수/피드백 누락에도 시스템이 crash되지 않아야 함
    assert "total_score" in data
    assert "questions" in data
