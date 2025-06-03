import ast
import json
import os

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore

load_dotenv()

cred = credentials.Certificate(os.getenv("FIREBASE_KEY_PATH"))
firebase_admin.initialize_app(cred)
db = firestore.client()

# with open("data/collected_jobs_llm_analyzed.json", "r", encoding="utf-8") as f:
#     data = json.load(f)

# for tuple_key, value in data.items():
#     company, position = ast.literal_eval(tuple_key)
#     value["company"] = company
#     value["position"] = position
#     db.collection("jobs").document(tuple_key).set(value)

# 테스트: 특정 키로 정상 조회되는지 확인
test_key = "('Naver', 'AI Engineer')"
doc_ref = db.collection("jobs").document(test_key)
doc = doc_ref.get()
if doc.exists:
    data = doc.to_dict()
    print("조회 성공:", data["company"], data["position"])
    # 주요 필드 예시 출력
    print("job_posting:", data.get("job_posting", "")[:100], "...")
    print("hiring_values:", data.get("hiring_values", "")[:100], "...")
    print("tech_stack:", data.get("tech_stack", "")[:100], "...")
    print(
        "sample_interview_questions:",
        data.get("sample_interview_questions", "")[:100],
        "...",
    )
    print("company_overview:", data.get("company_overview", "")[:100], "...")

else:
    print("해당 키로 문서를 찾을 수 없습니다.")
