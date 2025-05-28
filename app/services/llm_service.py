import json
import os
from typing import Dict, List

import litellm
from dotenv import load_dotenv

# .env 파일에서 환경변수 자동 로드
load_dotenv()


def ask_llm(prompt: str, model: str = "gemini/gemini-2.0-flash") -> str:
    max_retries = 2
    last_content = ""
    for _ in range(max_retries + 1):
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            response_format={"type": "json_object"},
        )
        content = str(response.choices[0].message.content) if response.choices else ""
        try:
            test = json.loads(content)
            if isinstance(test, dict):
                return content
            if isinstance(test, list) and len(test) > 0:
                # 리스트의 첫 번째 요소를 다시 json string으로 변환
                return json.dumps(test[0])
        except Exception:
            continue
    return content


def generate_questions(persona: str, num_questions: int = 10) -> List[Dict]:
    prompt = f"""
    아래 페르소나를 가진 면접관이 신입 개발자에게 할 만한 면접 질문 {num_questions}개를 JSON 배열로 생성해줘.
    페르소나: {persona}
    항상 예시 형식을 꼭 지켜줘 questions 키 안에 배열로 반환해줘.
    예시 형식:
    {{
        "questions": [
            {{
                "question": "질문 내용",
            }},
        ]
    }}
    """.strip()
    result = ask_llm(prompt)
    try:
        data = json.loads(result)
        print(data)
        return data.get("questions", [])
    except Exception:
        return []


def evaluate_answer(question: str, answer: str) -> Dict:
    prompt = f"""
    아래 면접 질문과 답변을 평가해줘. 6개 항목(기술 이해도, 문제 해결력, 기초 지식 응용력, 코드 구현력, 의사소통, 태도)별 1~5점 점수와 피드백을 JSON으로 반환해.
    질문: {question}
    답변: {answer}

    답변 json 형식:
    {{
        "score": [각 항목별 1~5점 점수 6개(리스트)],
        "feedback": 피드백
    }}
    """
    result = ask_llm(prompt)
    try:
        data = json.loads(result)
        # score가 int/float로 오면 리스트로 감싸기
        if (
            isinstance(data, dict)
            and "score" in data
            and not isinstance(data["score"], list)
        ):
            data["score"] = [data["score"]]
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def generate_persona(
    rag_info: dict,
) -> dict:
    prompt = f"""
    아래 회사 정보와 채용 공고, 기술스택, 가치관, 샘플 질문을 참고해서
    신입 개발자 면접관의 페르소나(성격, 질문 스타일, 중시하는 가치 등)를 3~4문장으로 요약해줘.
    회사 개요: {rag_info.get('company_overview', '')}
    채용 공고: {rag_info.get('job_posting', '')}
    기술스택: {rag_info.get('tech_stack', '')}
    가치관: {rag_info.get('hiring_values', '')}
    샘플 질문: {rag_info.get('sample_interview_questions', '')}

    답변 json 형식:
    {{"persona": "페르소나 요약"}}
    """.strip()

    persona = ask_llm(prompt)
    try:
        persona_dict = json.loads(persona)
        if isinstance(persona_dict, list) and len(persona_dict) > 0:
            persona_dict = persona_dict[0]
        if isinstance(persona_dict, dict):
            return persona_dict
        return {}
    except Exception:
        return {}


def insufficient_judgment(persona: str, q_and_a_history: list) -> Dict:
    prompt = f"""
    아래 페르소나를 가진 면접관이 면접자에게 질문한 질문과 답변이야.
    페르소나: {persona}

    아래 답변을 평가해줘. 추가적인 질문이 필요하다 하면 True, 필요하지 않다 하면 False를 반환해.
    만약 True라면 질문과 연결되는 추가적인 질문을 생성해줘.
    질문과 답변 기록: {q_and_a_history}
    출력 json 형식:
    {{
        "followup": 추가적인 질문 필요 여부,
        "question": 추가적인 질문 or 빈 문자열
    }}
    """
    result = ask_llm(prompt)
    try:
        data = json.loads(result)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def final_eval(logs: list) -> dict:
    """
    logs: [{question, answer, evaluation: [{score: [...], feedback: ...}]}]
    아래와 같은 구조로 반환:
    {
        'total_score': float,  # 전체 평균
        'question_count': int,
        'category_scores': {카테고리: 평균점수, ...},
        'category_feedbacks': {카테고리: [피드백, ...], ...},
        'questions': [
            {
                'question': str,
                'answer': str,
                'scores': [...],
                'feedback': str
            },
            ...
        ],
        'final_feedback': str  # LLM 요약
    }
    """
    categories = [
        "기술 이해도",
        "문제 해결력",
        "기초 지식 응용력",
        "코드 구현력",
        "의사소통",
        "태도",
    ]
    category_scores = {cat: [] for cat in categories}
    category_feedbacks = {cat: [] for cat in categories}
    questions = []
    total_scores = []
    for log in logs:
        evals = log.get("evaluation")
        if not evals or not isinstance(evals, list) or len(evals) == 0:
            continue
        eval_item = evals[0] if isinstance(evals[0], dict) else None
        if not eval_item:
            continue
        scores = eval_item.get("score")
        feedback = eval_item.get("feedback")
        if not scores or not isinstance(scores, list) or len(scores) != 6:
            continue
        for i, cat in enumerate(categories):
            try:
                score = float(scores[i])
                category_scores[cat].append(score)
                if feedback:
                    category_feedbacks[cat].append(feedback)
            except Exception:
                pass
        total_scores.extend(
            [
                float(s)
                for s in scores
                if isinstance(s, (int, float, str))
                and str(s).replace(".", "", 1).isdigit()
            ]
        )
        questions.append(
            {
                "question": log.get("question"),
                "answer": log.get("answer"),
                "scores": scores,
                "feedback": feedback,
            }
        )
    # 평균 계산
    avg_total = round(sum(total_scores) / len(total_scores), 2) if total_scores else 0.0
    avg_category = {
        cat: round(sum(vals) / len(vals), 2) if vals else 0.0
        for cat, vals in category_scores.items()
    }
    # LLM 최종 피드백
    summary_prompt = f"""
    아래는 신입 개발자 모의면접 세션의 질문/응답/평가 기록입니다. 전체 면접을 요약하고, 강점/개선점/최종 총평을 10줄 이내로 정리해줘.\n{logs}
    답변 json 형식:
    {{
        "final_feedback": "최종 총평"
    }}
    """
    final_feedback = ask_llm(summary_prompt)
    try:
        final_feedback_dict = json.loads(final_feedback)
        if isinstance(final_feedback_dict, dict):
            final_feedback = final_feedback_dict.get("final_feedback", "")
        else:
            final_feedback = ""
    except Exception:
        final_feedback = ""
    return {
        "total_score": avg_total,
        "question_count": len(questions),
        "category_scores": avg_category,
        "category_feedbacks": category_feedbacks,
        "questions": questions,
        "final_feedback": final_feedback,
    }


def answer_question_with_llm(question: str) -> str:
    """
    질문 dict 리스트를 받아 각 질문에 대해 실제 LLM(ask_llm)로 답변 리스트를 반환한다.
    예: [{"question": "자기소개 해주세요."}, ...] -> ["저는 ...", ...]
    """
    prompt = (
        f"아래 면접 질문에 대해 신입 개발자 지원자 입장에서 답변해줘.\n질문: {question}"
    )

    response = litellm.completion(
        model="gemini/gemini-2.0-flash",
        messages=[{"role": "user", "content": prompt}],
        stream=False,
    )
    return response.choices[0].message.content
