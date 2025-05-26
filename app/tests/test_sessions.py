import re

from fastapi.testclient import TestClient

from app.main import app


def test_create_session():
    client = TestClient(app)
    response = client.post("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "code" in data
    assert "session_id" in data


# /sessions/{code}/inputs 테스트는 실제 세션 생성 후에만 가능
# 아래는 예시 코드


def test_save_profile_and_interview_info():
    client = TestClient(app)
    # 세션 생성
    res = client.post("/sessions")
    code = res.json()["code"]
    # 프로필 저장 (education 포함)
    profile_payload = {
        "name": "홍길동",
        "age": 25,
        "gender": "남성",
        "organization": "테스트대학교",
        "position": "학생",
        "education": {"school": "서울대", "major": "컴퓨터공학", "gradYear": 2024},
    }
    res_profile = client.post(f"/sessions/{code}/profile", json=profile_payload)
    assert res_profile.status_code == 200
    assert res_profile.json()["success"] == True
    # 프로필 저장 (education 없이)
    profile_payload_no_edu = {
        "name": "홍길동",
        "age": 25,
        "gender": "남성",
        "organization": "테스트대학교",
        "position": "학생",
    }
    res_profile2 = client.post(f"/sessions/{code}/profile", json=profile_payload_no_edu)
    assert res_profile2.status_code == 200
    assert res_profile2.json()["success"] == True
    # 면접 정보 저장
    interview_payload = {
        "company_name": "테스트회사",
        "job_role": "백엔드",
        "self_intro": "열심히 하겠습니다.",
    }
    res_interview = client.post(
        f"/sessions/{code}/interview_info", json=interview_payload
    )
    assert res_interview.status_code == 200
    assert res_interview.json()["success"] == True


def test_save_profile_missing_required():
    client = TestClient(app)
    res = client.post("/sessions")
    code = res.json()["code"]
    # age, gender 누락
    profile_payload = {
        "name": "홍길동",
        "organization": "테스트대학교",
        "position": "학생",
    }
    res_profile = client.post(f"/sessions/{code}/profile", json=profile_payload)
    assert res_profile.status_code == 422
    assert "필수 입력 누락" in res_profile.json()["detail"]
    # education 필수값 누락 (school 없음)
    profile_payload_edu_missing = {
        "name": "홍길동",
        "age": 25,
        "gender": "남성",
        "organization": "테스트대학교",
        "position": "학생",
        "education": {"major": "컴퓨터공학", "gradYear": 2024},
    }
    res_profile2 = client.post(
        f"/sessions/{code}/profile", json=profile_payload_edu_missing
    )
    assert res_profile2.status_code == 422
    assert "education.school" in res_profile2.json()["detail"]
    # education 필수값 누락 (major 없음)
    profile_payload_edu_missing2 = {
        "name": "홍길동",
        "age": 25,
        "gender": "남성",
        "organization": "테스트대학교",
        "position": "학생",
        "education": {"school": "서울대", "gradYear": 2024},
    }
    res_profile3 = client.post(
        f"/sessions/{code}/profile", json=profile_payload_edu_missing2
    )
    assert res_profile3.status_code == 422
    assert "education.major" in res_profile3.json()["detail"]
    # education 필수값 누락 (gradYear 없음)
    profile_payload_edu_missing3 = {
        "name": "홍길동",
        "age": 25,
        "gender": "남성",
        "organization": "테스트대학교",
        "position": "학생",
        "education": {"school": "서울대", "major": "컴퓨터공학"},
    }
    res_profile4 = client.post(
        f"/sessions/{code}/profile", json=profile_payload_edu_missing3
    )
    assert res_profile4.status_code == 422
    assert "education.gradYear" in res_profile4.json()["detail"]


def test_save_interview_info_missing_required():
    client = TestClient(app)
    res = client.post("/sessions")
    code = res.json()["code"]
    # company_name, job_role 누락
    interview_payload = {
        "company_name": "",
        "job_role": "",
        "self_intro": "열심히 하겠습니다.",
    }
    res_interview = client.post(
        f"/sessions/{code}/interview_info", json=interview_payload
    )
    assert res_interview.status_code == 422
    assert "필수 입력 누락" in res_interview.json()["detail"]


# def test_parse_job_url_success():
#     client = TestClient(app)
#     res = client.post("/sessions")
#     code = res.json()["code"]
#     url = "https://jobs.example.com/naver/backend-engineer"
#     res2 = client.post(f"/sessions/{code}/parse_job_url", json={"url": url})
#     assert res2.status_code == 200
#     data = res2.json()
#     assert data["company_name"] == "Naver"
#     assert data["job_role"] == "Backend engineer"


# def test_parse_job_url_fail():
#     client = TestClient(app)
#     res = client.post("/sessions")
#     code = res.json()["code"]
#     url = "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=12345"
#     res2 = client.post(f"/sessions/{code}/parse_job_url", json={"url": url})
#     assert res2.status_code == 422
#     assert "수동 입력" in res2.json()["detail"]


def test_generate_persona_success():
    client = TestClient(app)
    res = client.post("/sessions")
    code = res.json()["code"]
    payload = {"company_name": "Naver", "job_role": "Backend engineer"}
    res2 = client.post(f"/sessions/{code}/generate_persona", json=payload)
    assert res2.status_code == 200
    data = res2.json()
    assert "persona" in data
    assert len(data["persona"]) > 0


def test_generate_persona_fail():
    client = TestClient(app)
    res = client.post("/sessions")
    code = res.json()["code"]
    payload = {"company_name": "UnknownCorp", "job_role": "UnknownRole"}
    res2 = client.post(f"/sessions/{code}/generate_persona", json=payload)
    assert res2.status_code == 404
    assert "RAG DB" in res2.json()["detail"]


def test_generate_questions_success():
    client = TestClient(app)
    res = client.post("/sessions")
    code = res.json()["code"]
    # 페르소나 생성
    payload = {"company_name": "Naver", "job_role": "Backend engineer"}
    client.post(f"/sessions/{code}/generate_persona", json=payload)
    # 질문 생성
    res2 = client.post(
        f"/sessions/{code}/generate_questions", json={"num_questions": 3}
    )
    assert res2.status_code == 200
    data = res2.json()

    print(data)
    assert "questions" in data
    assert len(data["questions"]) == 3
    for q in data["questions"]:
        assert "id" in q and "text" in q and "type" in q and "difficulty" in q


def test_generate_questions_fail_no_persona():
    client = TestClient(app)
    res = client.post("/sessions")
    code = res.json()["code"]
    # 질문 생성 (페르소나 없이)
    res2 = client.post(
        f"/sessions/{code}/generate_questions", json={"num_questions": 2}
    )
    assert res2.status_code == 400
    assert "페르소나" in res2.json()["detail"]


def test_chat_websocket_success():
    client = TestClient(app)
    # 세션 생성 및 준비
    res = client.post("/sessions")
    code = res.json()["code"]
    # 페르소나 생성
    payload = {"company_name": "Naver", "job_role": "Backend engineer"}
    client.post(f"/sessions/{code}/generate_persona", json=payload)
    # 질문 생성
    res_q = client.post(
        f"/sessions/{code}/generate_questions", json={"num_questions": 2}
    )
    assert res_q.status_code == 200
    assert len(res_q.json()["questions"]) == 2
    # WebSocket 연결
    with client.websocket_connect(f"/sessions/{code}/chat") as ws:
        for i in range(6):
            msg = ws.receive_json()
            assert "question" in msg
            ws.send_text(f"테스트 답변 {i+1}")
        end_msg = ws.receive_json()
        print("WebSocket 마지막 메시지:", end_msg)
        assert end_msg["event"] == "면접 종료"
        assert "소진" in end_msg["message"]


def test_chat_websocket_no_questions():
    client = TestClient(app)
    res = client.post("/sessions")
    code = res.json()["code"]
    # WebSocket 연결 (질문 미생성)
    with client.websocket_connect(f"/sessions/{code}/chat") as ws:
        msg = ws.receive_json()
        assert "error" in msg
        assert "질문이 없습니다" in msg["error"]


def test_generate_and_get_report():
    client = TestClient(app)
    # 세션 준비
    res = client.post("/sessions")
    code = res.json()["code"]
    # 페르소나/질문 생성
    payload = {"company_name": "Naver", "job_role": "Backend engineer"}
    client.post(f"/sessions/{code}/generate_persona", json=payload)
    client.post(f"/sessions/{code}/generate_questions", json={"num_questions": 2})
    # Q&A 진행
    with client.websocket_connect(f"/sessions/{code}/chat") as ws:
        for i in range(2):
            msg = ws.receive_json()
            ws.send_text(f"테스트 답변 {i+1}")
        ws.receive_json()  # 종료 메시지
    # 리포트 생성
    res2 = client.post(f"/sessions/{code}/generate_report")
    assert res2.status_code == 200
    data = res2.json()
    assert "url" in data and "summary" in data and data["report_type"] == "pdf"
    # 리포트 열람
    res3 = client.get(f"/sessions/{code}/report")
    assert res3.status_code == 200
    data2 = res3.json()
    assert "url" in data2 and data2["report_type"] == "pdf"


def test_get_report_not_generated():
    client = TestClient(app)
    res = client.post("/sessions")
    code = res.json()["code"]
    res2 = client.get(f"/sessions/{code}/report")
    assert res2.status_code == 404
    assert "리포트" in res2.json()["detail"]


# def test_chat_websocket_followup():
#     client = TestClient(app)
#     # 세션 생성 및 준비
#     res = client.post("/sessions")
#     code = res.json()["code"]
#     # 페르소나 생성
#     payload = {"company_name": "Naver", "job_role": "Backend engineer"}
#     client.post(f"/sessions/{code}/generate_persona", json=payload)
#     # 질문 생성 (1개만 생성)
#     client.post(f"/sessions/{code}/generate_questions", json={"num_questions": 1})
#     # WebSocket 연결
#     with client.websocket_connect(f"/sessions/{code}/chat") as ws:
#         msg = ws.receive_json()
#         assert "question" in msg
#         ws.send_text("모르겠습니다")  # 일부러 점수 낮게 유도
#         followup_count = 0
#         while True:
#             followup_msg = ws.receive_json()
#             if followup_msg.get("event") == "면접 종료":
#                 assert "소진" in followup_msg["message"]
#                 break
#             assert "question" in followup_msg
#             assert followup_msg.get("followup") is True
#             followup_count += 1
#             ws.send_text("이것도 잘 모르겠습니다")
#             if followup_count >= 2:
#                 # 2회 이상 꼬리질문이 오면 안 됨
#                 end_msg = ws.receive_json()
#                 assert end_msg["event"] == "면접 종료"
#                 assert "소진" in end_msg["message"]
#                 break
#         assert 0 <= followup_count <= 2
