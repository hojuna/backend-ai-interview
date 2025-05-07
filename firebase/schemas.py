# schemas.py

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- 공통 또는 Firestore 데이터 구조 반영 스키마 ---

class EducationSchema(BaseModel): # 연관 FR: FR-1.0 (학력, 전공, 졸업연도)
    school: str = Field(..., description="학교명")
    major: str = Field(..., description="전공")
    gradYear: Optional[int] = Field(None, description="졸업연도 (YYYY)")

class QuestionSchema(BaseModel): # 연관 FR: FR-3.1 (질문 생성), FR-3.3 (DB 저장), FR-6.2 (꼬리질문)
    id: str = Field(..., description="질문 고유 ID")
    text: str = Field(..., description="질문 내용")
    type: str = Field(..., description="질문 유형 (e.g., 'basic', 'technical', 'behavioral', 'follow-up')")
    turn: Optional[int] = Field(None, description="해당 질문이 제시된 턴 번호")

class EvaluationSchema(BaseModel): # 연관 FR: FR-5.1 (점수 및 피드백 구조)
    score: Dict[str, Any] = Field(..., description="루브릭 기반 점수 상세 (e.g., {'clarity': 5, 'technical_depth': 4})")
    feedback: str = Field(..., description="종합 피드백 또는 항목별 피드백")

class InteractionLogSchema(BaseModel): # 답변(FR-4.2) 및 평가(FR-5.2) 저장
    id: Optional[str] = Field(None, description="Firestore 문서 ID")
    turn: int = Field(..., description="대화 턴 번호")
    question_id: Optional[str] = Field(None, description="질문 ID")
    question_text: Optional[str] = Field(None, description="질문 내용") # 편의를 위한 필드
    answer_text: Optional[str] = Field(None, description="사용자 답변") # FR-4.2
    evaluation: Optional[EvaluationSchema] = Field(None, description="답변에 대한 평가") # FR-5.2
    interaction_time: Optional[datetime] = Field(None, description="답변/평가 시간 (사용자 이벤트 시간)")
    created_at: Optional[datetime] = Field(None, description="서버 기록 시간")

class ReportSchema(BaseModel): # 리포트 데이터 구조. 연관 FR: FR-7.2, FR-7.3 (내용), FR-7.6 (URL 만료)
    id: Optional[str] = Field(None, description="Firestore 문서 ID")
    session_id: Optional[str] = Field(None, description="연결된 세션 ID (응답 시 유용)")
    url: Optional[str] = Field(None, description="리포트 파일 URL (PDF 또는 HTML 웹페이지)")
    report_type: str = Field(..., description="리포트 타입 ('pdf', 'html')") # FR-7.2
    status: str = Field("pending", description="리포트 생성 상태 ('pending', 'generating', 'completed', 'failed')")
    expires_at: Optional[datetime] = Field(None, description="리포트 URL 만료 시간") # FR-7.6 (image_59840a.png 참고)
    created_at: Optional[datetime] = Field(None, description="리포트 정보 생성 시간")

class SessionFirestoreSchema(BaseModel): # 세션 DB의 전체 구조. 연관 FR: FR-1.3 (JSON 형태로 저장)
    code: str # FR-0.2 (면접 코드)
    pw_hash: Optional[str] = None # FR-0.1 (비밀번호 해시 저장)
    name: Optional[str] = None # FR-0.1 (이름), FR-1.0
    email: Optional[EmailStr] = None # FR-1.0
    education: Optional[EducationSchema] = None # FR-1.0
    career_summary: Optional[str] = None # FR-1.1
    company_name: Optional[str] = None # FR-1.2
    job_role: Optional[str] = None # FR-1.2
    self_intro: Optional[str] = None # FR-1.2
    persona_config: Optional[Dict[str, Any]] = None # 페르소나 생성 관련 내부 데이터
    persona_text: Optional[str] = None # FR-2.1 (생성된 페르소나)
    questions_generated: Optional[List[QuestionSchema]] = None # FR-3.3 (생성된 질문 리스트)
    status: str = Field("ready", description="세션 진행 상태")
    created_at: datetime
    updated_at: Optional[datetime] = None


# --- API 요청(Request Payload) 및 응답(Response) 스키마 ---

class MessageResponse(BaseModel):
    message: str

# EP1: POST /sessions (세션 생성)
class SessionCreateResponse(BaseModel): # 연관 FR: FR-0.2 (세션 ID, 면접 코드 반환)
    code: str = Field(..., description="발급된 6자리 면접 코드")
    session_id: str = Field(..., description="내부 세션 Firestore 문서 ID")

# EP2: POST /sessions/{code} (면접 세션 요청 - 이름, 비밀번호 입력)
class SessionJoinPayload(BaseModel): # 연관 FR: FR-0.1 (이름, 비밀번호 입력)
    name: str = Field(..., description="면접자 이름/닉네임")
    password: str = Field(..., description="면접자 설정 간단 비밀번호", min_length=4)

# EP3: POST /sessions/{code}/profile (면접자 프로필 정보 입력)
class ProfilePayload(BaseModel): # 연관 FR: FR-1.0 (이름,학력,졸업연도,이메일), FR-1.1 (경력요약)
    email: Optional[EmailStr] = Field(None, description="이메일 주소") # FR-1.0
    education: EducationSchema # FR-1.0
    career_summary: Optional[str] = Field(None, description="경력 요약 (선택)") # FR-1.1

# EP4: POST /sessions/{code}/interviewinfo (면접 전 정보 입력)
class InterviewInfoPayload(BaseModel): # 연관 FR: FR-1.2 (지원회사,직군,자소서), FR-1.3 (JSON 저장)
    company_name: str = Field(..., description="지원 회사명") # FR-1.2
    job_role: str = Field(..., description="지원 직군") # FR-1.2
    self_intro: Optional[str] = Field(None, description="자기소개서 내용 (선택)") # FR-1.2

# EP5: GET /sessions/{code}/persona (면접관 페르소나 요청)
class PersonaResponse(BaseModel): # 연관 FR: FR-2.1 (페르소나 생성 후 요청)
    persona_text: str = Field(..., description="생성된 페르소나 설명")
    persona_details: Optional[Dict[str, Any]] = Field(None, description="페르소나 관련 추가 정보/설정")

# EP6: POST /sessions/{code}/questions (질문 생성 요청)
class QuestionGenerationRequest(BaseModel): # 연관 FR: FR-3.1 (질문 생성), FR-6.2 (꼬리질문 생성 시 컨텍스트)
    current_turn: Optional[int] = Field(None, description="현재 대화 턴 (꼬리질문 생성 시)")
    last_interaction_id: Optional[str] = Field(None, description="꼬리질문 대상이 되는 이전 인터랙션 ID")
    context: Optional[Dict[str, Any]] = Field(None, description="질문 생성에 필요한 추가 컨텍스트")

class QuestionsListResponse(BaseModel): # 연관 FR: FR-3.1, FR-3.3 (생성된 질문), FR-6.2
    questions: List[QuestionSchema] = Field(..., description="생성된 질문 목록")

# EP7: GET /sessions/{code}/chat (사전 생성된 질문 요청/대화 내역)
class ChatHistoryResponse(BaseModel): # 연관 FR: FR-4.1 (사전 생성된 질문 요청)
    interactions: List[InteractionLogSchema] = Field(..., description="현재까지의 대화 내역 (질문/답변/평가 포함)")
    current_session_status: Optional[str] = Field(None, description="현재 세션 상태")

# EP8: POST /sessions/{code}/chat (답변 입력)
class AnswerPayload(BaseModel): # 연관 FR: FR-4.2 (답변 입력)
    turn: int = Field(..., description="현재 답변하는 턴 번호")
    question_id: str = Field(..., description="답변 대상 질문 ID")
    answer_text: str = Field(..., description="사용자 답변 내용", max_length=2000) # FR-4.2 (2000자 제한)

class AnswerResponse(BaseModel): # 연관 FR: FR-4.2 (답변 저장 후 응답)
    interaction_log: InteractionLogSchema # 저장된 인터랙션 로그 (답변 포함)

# EP9: POST /sessions/{code}/eval (답변 평가 요청)
class EvalRequestPayload(BaseModel): # 연관 FR: FR-5.1 (답변 평가 요청)
    interaction_id: str = Field(..., description="평가할 답변이 포함된 인터랙션 로그 ID")

class EvaluationResponse(BaseModel): # 연관 FR: FR-5.1 (평가 점수/피드백 반환), FR-5.2 (결과 저장)
    interaction_id: str = Field(..., description="평가가 완료된 인터랙션 로그 ID")
    evaluation_result: EvaluationSchema

# EP10: POST /sessions/{code}/chat/follow (꼬리질문 판단 요청)
class FollowUpCheckPayload(BaseModel): # 연관 FR: FR-6.1 (꼬리질문 판단 요청)
    interaction_id: str = Field(..., description="꼬리질문 판단 대상이 되는 인터랙션 로그 ID")

class FollowUpDecisionResponse(BaseModel): # 연관 FR: FR-6.1 (판단 결과)
    should_generate_follow_up: bool = Field(..., description="꼬리질문 생성 필요 여부")
    reason: Optional[str] = Field(None, description="판단 근거 또는 다음 단계 안내")
    next_question_type: Optional[str] = Field(None, description="생성될 꼬리질문의 권장 유형")

# EP11: POST /sessions/{code}/chat/end (면접 종료 확인 요청) - 연관 FR: FR-7.1 (면접 종료 확인), FR-7.3 (리포트 생성과 연관)
# 요청 본문은 없을 수 있음. 응답은 MessageResponse 사용.

# EP12: POST /sessions/{code}/report (리포트 생성 요청)
class ReportGenerationResponse(BaseModel): # 연관 FR: FR-7.2 (리포트 생성 요청)
    report_id: str
    session_id: str
    status: str = Field("generation_initiated", description="리포트 생성 시작됨")
    message: Optional[str] = None

# EP13: GET /sessions/{code}/report (리포트 열람)
class ReportDetailResponse(ReportSchema): # 연관 FR: FR-7.4 (리포트 열람)
    pass # ReportSchema를 그대로 사용하거나 필요한 필드만 선택하여 상속/구성

# EP14: GET /sessions/{code}/report/download (리포트 저장)
class ReportDownloadLinkResponse(BaseModel): # 연관 FR: FR-7.5 (리포트 저장)
    download_url: str = Field(..., description="리포트 다운로드 URL")
    file_name: Optional[str] = Field(None, description="권장 파일명")
    content_type: Optional[str] = Field(None, description="파일 MIME 타입")