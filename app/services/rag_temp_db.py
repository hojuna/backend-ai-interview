# 임시 RAG 벡터 DB (dict 기반)

RAG_FAKE_DB = {
    ("Naver", "Backend engineer"): {
        "job_posting": "네이버 백엔드 엔지니어 채용 공고 내용...",
        "hiring_values": "기술 혁신, 협업, 성장",
        "tech_stack": "Java, Spring, MySQL, AWS",
        "sample_interview_questions": [
            "네이버에서의 대용량 트래픽 처리 경험이 있나요?",
            "Spring 프레임워크의 장점은?",
        ],
        "company_overview": "네이버는 대한민국 대표 IT 기업으로...",
    },
    ("Kakao", "Frontend engineer"): {
        "job_posting": "카카오 프론트엔드 엔지니어 채용 공고 내용...",
        "hiring_values": "유연성, 창의성, 사용자 중심",
        "tech_stack": "React, TypeScript, GraphQL",
        "sample_interview_questions": [
            "React의 상태 관리 방법은?",
            "GraphQL의 장점은?",
        ],
        "company_overview": "카카오는 다양한 플랫폼 서비스를 제공하는...",
    },
}


def search_rag(company_name: str, job_role: str) -> dict:
    # 실제 벡터 DB 검색 대신 dict에서 조회
    key = (company_name, job_role)
    return RAG_FAKE_DB.get(key, {})
