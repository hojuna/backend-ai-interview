import json
import os
from typing import Dict, List

import litellm
from dotenv import load_dotenv

# .env 파일에서 환경변수 자동 로드
load_dotenv()


def ask_llm(prompt: str, model: str = "gemini/gemini-2.5-flash") -> str:
    max_retries = 2
    last_content = ""
    for _ in range(max_retries + 1):
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            response_format={"type": "json_object"},
        )
        content = str(
            response.choices[0].message.content) if response.choices else ""
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


def generate_questions(
    persona: str,
    keywords: dict,
    user_info: dict,
    rag_info: dict,
    num_questions: int = 10,
) -> List[Dict]:
    prompt = f"""
    아래 페르소나를 가진 면접관이 신입 개발자에게 할 만한 면접 질문 {num_questions}개를 JSON 배열로 생성해줘.
    페르소나: {persona}
    키워드: {json.dumps(keywords, ensure_ascii=False)}
    사용자 정보: {json.dumps(user_info, ensure_ascii=False)}
    회사 정보: {json.dumps(rag_info, ensure_ascii=False)}
    항상 예시 형식을 꼭 지켜줘 questions 키 안에 배열로 반환해줘.
    키워드, 페르소나, 회사 정보를 참고해서 질문을 생성해줘. (질문 생성시 중요도 순위 회사정보 > 페르소나 > 키워드)
    질문 별로 너무 중복 되지 않고 면접 흐름을 고려해서 면접자를 잘 평가할 수 있도록 질문을 생성해줘.
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
아래는 신입 개발자 면접 질문과 지원자의 답변입니다.
FAANG 및 Microsoft 인터뷰 원칙을 참고하여, 아래 6개 항목에 대해 평가해 주세요.

각 항목별로 1~5점 점수와 구체적인 피드백을 JSON으로 반환해 주세요.
각 항목의 평가 기준과 예시를 반드시 참고해서 평가해 주세요.

최종적으로 각 항목별 점수에 아래 가중치를 곱해 100점 만점의 총점을 산출해 주세요.
- 1~4번 항목: 각 20%
- 5, 6번 항목: 각 10%

### 평가 항목, 기준, 예시

1. 기술 이해도 (Technical Understanding) [20%]
- 평가 포인트: 개념을 정확히 알고 있는가? 핵심 용어를 올바르게 사용하는가?
- 챗봇 질문 예시: "HashMap이 뭔가요? 해시 함수와 충돌 처리 방식도 설명해볼 수 있나요?"
- 자동 분석 기준 예시: 해시 함수 언급 여부, 충돌 해결 방식(예: 체이닝, 오픈 어드레싱) 언급 여부
- 예시 피드백: 4/5 – 해시 구조 개념은 잘 설명했으나, 충돌 해결 방식까지는 연결하지 못함.

2. 문제 해결력 / 로직 설명 (Problem Solving Skills) [20%]
- 평가 포인트: 문제 접근 방식이 논리적인가? 효율성(시간/공간 복잡도)을 고려했는가? 다양한 test case나 edge case를 고려했는가?
- 챗봇 질문 예시: "숫자 배열에서 중복 없이 한 번만 등장하는 수를 찾는 함수를 어떻게 구현할 수 있을까요?"
- 예시 피드백: 3/5 – 정답에는 도달했지만 시간 복잡도 최적화에 대한 고려는 부족함.

3. 기초 지식 응용력 (Applied Knowledge) [20%]
- 평가 포인트: 익힌 개념을 새로운 문제에 적용할 수 있는가? 주어진 조건 외의 요구사항도 추론 가능한가?
- 챗봇 질문 예시: "Stack은 잘 알고 계신 것 같은데, 재귀 함수 호출 흐름과 연결 지어 설명해보실 수 있나요?"
- 예시 피드백: 3/5 – Stack 자체는 이해했으나 재귀 흐름으로의 확장이 부족함.

4. 의사소통 능력 / 설명의 명확성 (Communication Skills) [10%]
- 평가 포인트: 설명이 논리적이고 명확한가? 용어를 청자의 수준에 맞게 풀어내는가? 불필요하게 장황하지 않은가?
- 챗봇 질문 예시: "Stack과 Queue의 차이를 초보자에게 설명해본다면 어떻게 말할까요?"
- 예시 피드백: 3/5 – 개념 전달은 되었으나 예시 부족하고 길게 설명함.

5. 태도 및 자기 인식 (Attitude) [10%]
- 평가 포인트: 모르는 건 인정하는가? 피드백 수용 태도는 어떤가? 학습 의지나 성장 마인드가 있는가?
- 챗봇 질문 예시: "이 문제를 해결하지 못했다면, 다음에 어떻게 접근해보실 건가요?"
- 예시 피드백: 5/5 – 모르는 부분은 솔직히 인정했고, 학습 계획까지 언급함.

질문: {question}
답변: {answer}

아래와 같은 JSON 형식으로 모든 카테고리에 대한 평가를 답변해 주세요.
{{
  "categories": [
    {{"name": "기술 이해도", "score": 4, "feedback": "해시 구조 개념은 잘 설명했으나, 충돌 해결 방식까지는 연결하지 못함."}},
    {{"name": "문제 해결력", "score": 3, "feedback": "정답에는 도달했지만 시간 복잡도 최적화에 대한 고려는 부족함."}},
    {{"name": "기초 지식 응용력", "score": 3, "feedback": "Stack 자체는 이해했으나 재귀 흐름으로의 확장이 부족함."}},
    {{"name": "의사소통 능력", "score": 3, "feedback": "개념 전달은 되었으나 예시 부족하고 길게 설명함."}},
    {{"name": "태도 및 자기 인식", "score": 5, "feedback": "모르는 부분은 솔직히 인정했고, 학습 계획까지 언급함."}},
  ],
  "total_score": 78  // 100점 만점 환산 총점
}}
"""
    result = ask_llm(prompt)
    try:
        data = json.loads(result)
        if isinstance(data, dict) and "categories" in data:
            return data
        return {}
    except Exception:
        return {}


def generate_persona(
    rag_info: dict,
    company: str,
    position: str,
) -> dict:
    prompt = f"""
    아래 회사 정보와 채용 공고, 기술스택, 가치관을 참고해서
    신입 개발자 면접관의 성향을 페르소나(성격, 질문 스타일, 중시하는 가치 등)로 요약해줘.
    - 성격은 일단 디폴트로 무뚝뚝한 면접관으로 함
    회사 개요: {rag_info.get('company_overview', '')}
    채용 공고: {rag_info.get('job_posting', '')}
    기술스택: {rag_info.get('tech_stack', '')}
    가치관: {rag_info.get('hiring_values', '')}

    ### 지원자가 입력한 회사 정보와 지원 직무 정보
    회사 이름: {company}
    채용 직무: {position}
    위 정보를 반영하여 한국어로 department를 생성해줘.

    persona_name은 그냥 랜덤으로 한국인 이름으로 생성해줘

    답변 json 형식:
    {{
        "persona": "페르소나 요약",
        "department": "페르소나 부서(예시 네이버 모바일 개발팀)",
        "persona_name": "페르소나 이름 (예시: 김철수)"
    }}
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

    꼬리질문의 판단 기준 : 
    - 질문에 답변이 최악인 경우는 그냥 넘어간다.
    - 질문에 답변이 모호한 경우 면접자가 확실히 알고있는지 판단해서 필요하면 추가적인 꼬리 질문을 생성한다.
    - 너무 쉬운 질문은 그냥 넘어간다.
    - 너무 어려운 질문은 그냥 넘어간다.
    - 질문 자체가 모호할 경우 넘어간다.
    - 면접자가 확실히 알고있는 질문은 그냥 넘어간다.
    - 그외로도 너무 잦은 꼬리 질문을 남발하지 않도록 보수적으로 판단한다.

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


def summarize_category_feedback(category, feedbacks):
    if not feedbacks:
        return ""
    prompt = f"""
    아래는 '{category}'에 대한 면접 평가 피드백 모음입니다.
    이 피드백들을 참고해서 '{category}'에 대한 종합 피드백을 한 줄로 요약해줘.
    {feedbacks}
    해당 카테고리에 대한 질문이 없어 평가가 불가능한 경우 "평가가 불가능합니다" 라고 작성해줘
    답변 json 형식: {{"summary": "..."}}
    """
    result = ask_llm(prompt)
    try:
        data = json.loads(result)
        if isinstance(data, dict) and "summary" in data:
            return data["summary"]
        if isinstance(data, str):
            return data
        return ""
    except Exception:
        return result.strip()


def final_eval(logs: list) -> dict:
    """
    logs: [{question, answer, evaluation: [{categories: [{name, score, feedback}, ...]}]}]
    아래와 같은 구조로 반환:
    {
        'total_score': float,  # 전체 평균
        'question_count': int,
        'category_scores': {카테고리: 평균점수, ...},
        'category_feedbacks': {카테고리: 종합 피드백(한 줄), ...},
        'questions': [
            {
                'question': str,
                'answer': str,
                'scores': [...],
                'feedbacks': [...],
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
        "의사소통 능력",
        "태도 및 자기 인식",
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
        cats = eval_item.get("categories", [])
        if not cats or len(cats) != 6:
            continue
        scores = []
        feedbacks = []
        for i, cat in enumerate(categories):
            try:
                cat_item = next(
                    (c for c in cats if c.get("name") == cat), None)
                if cat_item is not None:
                    score = float(cat_item.get("score", 0))
                    feedback = cat_item.get("feedback", "")
                    # 코드 구현력 0점(평가 불가)은 평균 계산에서 제외
                    if cat == "코드 구현력" and score == 0:
                        category_feedbacks[cat].append(feedback)
                        scores.append(score)  # 질문별 상세 점수에는 남김
                        feedbacks.append(feedback)
                        continue
                    category_scores[cat].append(score)
                    category_feedbacks[cat].append(feedback)
                    scores.append(score)
                    feedbacks.append(feedback)
            except Exception:
                pass
        # 전체 평균 계산에서 코드 구현력 0점은 제외
        filtered_scores = [
            s
            for idx, s in enumerate(scores)
            if not (categories[idx] == "코드 구현력" and s == 0)
        ]
        total_scores.extend(filtered_scores)
        questions.append(
            {
                "question": log.get("question"),
                "answer": log.get("answer"),
                "scores": scores,
                "feedbacks": feedbacks,
            }
        )
    # 평균 계산
    avg_total = round(sum(total_scores) / len(total_scores),
                      2) if total_scores else 0.0
    avg_category = {
        cat: round(sum(vals) / len(vals), 2) if vals else 0.0
        for cat, vals in category_scores.items()
    }
    # 카테고리별 종합 피드백 생성
    category_feedbacks_summary = {}
    for cat in categories:
        category_feedbacks_summary[cat] = summarize_category_feedback(
            cat, category_feedbacks[cat]
        )
    # LLM 최종 피드백
    summary_prompt = f"""
당신은 최고의 면접 평가 전문가입니다. 면접 평가 전문가로서 면접 평가 기준과 예시를 참고해서 면접 평가를 작성해줘.
너무 평가 기준과 이전의 평가 기록에 너무 얽매이지 말고 면접자의 답변을 전체적으로 참고해서 평가를 작성해줘.

아래는 신입 개발자 모의면접 세션의 질문/응답/평가 기록입니다.
FAANG 및 Microsoft 인터뷰 원칙을 참고하여, 아래 6개 항목에 대해 종합적으로 평가해 주세요.

각 항목별 평가 기준과 예시를 반드시 참고해서 전체 면접의 강점, 개선점, 최종 총평을 10줄 이내로 작성해 주세요.

최종 총평에는 아래 6개 항목의 기준과 예시를 반드시 참고해 주세요.

1. 기술 이해도 (Technical Understanding) [20%]
- 평가 포인트: 개념을 정확히 알고 있는가? 핵심 용어를 올바르게 사용하는가?
- 챗봇 질문 예시: "HashMap이 뭔가요? 해시 함수와 충돌 처리 방식도 설명해볼 수 있나요?"
- 자동 분석 기준 예시: 해시 함수 언급 여부, 충돌 해결 방식(예: 체이닝, 오픈 어드레싱) 언급 여부
- 예시 피드백: 4/5 – 해시 구조 개념은 잘 설명했으나, 충돌 해결 방식까지는 연결하지 못함.

2. 문제 해결력 / 로직 설명 (Problem Solving Skills) [20%]
- 평가 포인트: 문제 접근 방식이 논리적인가? 효율성(시간/공간 복잡도)을 고려했는가? 다양한 test case나 edge case를 고려했는가?
- 챗봇 질문 예시: "숫자 배열에서 중복 없이 한 번만 등장하는 수를 찾는 함수를 어떻게 구현할 수 있을까요?"
- 예시 피드백: 3/5 – 정답에는 도달했지만 시간 복잡도 최적화에 대한 고려는 부족함.

3. 기초 지식 응용력 (Applied Knowledge) [20%]
- 평가 포인트: 익힌 개념을 새로운 문제에 적용할 수 있는가? 주어진 조건 외의 요구사항도 추론 가능한가?
- 챗봇 질문 예시: "Stack은 잘 알고 계신 것 같은데, 재귀 함수 호출 흐름과 연결 지어 설명해보실 수 있나요?"
- 예시 피드백: 3/5 – Stack 자체는 이해했으나 재귀 흐름으로의 확장이 부족함.

4. 의사소통 능력 / 설명의 명확성 (Communication Skills) [10%]
- 평가 포인트: 설명이 논리적이고 명확한가? 용어를 청자의 수준에 맞게 풀어내는가? 불필요하게 장황하지 않은가?
- 챗봇 질문 예시: "Stack과 Queue의 차이를 초보자에게 설명해본다면 어떻게 말할까요?"
- 예시 피드백: 3/5 – 개념 전달은 되었으나 예시 부족하고 길게 설명함.

5. 태도 및 자기 인식 (Attitude) [10%]
- 평가 포인트: 모르는 건 인정하는가? 피드백 수용 태도는 어떤가? 학습 의지나 성장 마인드가 있는가?
- 챗봇 질문 예시: "이 문제를 해결하지 못했다면, 다음에 어떻게 접근해보실 건가요?"
- 예시 피드백: 5/5 – 모르는 부분은 솔직히 인정했고, 학습 계획까지 언급함.

면접 세션 기록:
{logs}

아래와 같은 JSON 형식으로 답변해 주세요.
{{
    "final_feedback": "최종 총평"
}}
""".strip()
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
        "category_feedbacks": category_feedbacks_summary,
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
        model="gemini/gemini-2.5-flash",
        messages=[{"role": "user", "content": prompt}],
        stream=False,
    )
    return response.choices[0].message.content
