import json
import os
from collections import defaultdict
from glob import glob

from app.services.llm_service import ask_llm

DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/extracted_keywords.json")

PROMPT_TEMPLATE = """아래의 json 데이터를 참고해서, 신입 개발자 면접 질문을 만들 때 쓸 수 있는 핵심 키워드를 다음 5가지 카테고리별로 추출해줘:

1. 기술적 역량 (Technical Skills)
   - 프로그래밍 언어, 프레임워크, 데이터베이스, 개발 도구, 알고리즘/자료구조, 네트워크/보안 등

2. 태도/자세 (Attitude)
   - 커뮤니케이션, 팀워크, 책임감, 적극성, 문제해결 능력, 시간 관리 등

3. 학습/성장 (Learning & Growth)
   - 자기주도학습, 새로운 기술 습득, 지식 공유, 성장 마인드셋, 기술 트렌드 파악 등

4. 프로젝트 경험 (Project Experience)
   - 프로젝트 기획/설계, 문제 해결 과정, 팀 프로젝트 경험, 프로젝트 성과/결과 등

5. 비즈니스 이해 (Business Understanding)
   - 도메인 지식, 사용자 중심 사고, 비즈니스 가치 창출, 서비스 개선 제안, ROI 이해 등

각 카테고리별로 키워드를 추출해주세요.
반드시 아래 형식의 JSON으로 반환해줘.

예시:
{{
  "technical_skills": ["키워드1", "키워드2", "키워드3"],
  "attitude": ["키워드1", "키워드2", "키워드3"],
  "learning_growth": ["키워드1", "키워드2", "키워드3"],
  "project_experience": ["키워드1", "키워드2", "키워드3"],
  "business_understanding": ["키워드1", "키워드2", "키워드3"]
}}

데이터:
{data}
""".strip()


def extract_keywords_from_data(data):
    prompt = PROMPT_TEMPLATE.format(
        data=(
            json.dumps(data, ensure_ascii=False)
            if isinstance(data, (dict, list))
            else data
        )
    )
    try:
        result = ask_llm(prompt)
        result_json = json.loads(result)
        return result_json
    except Exception as e:
        print(f"[ERROR] 데이터 처리 중 오류 발생: {e}")
        return {}


def extract_keywords_from_file(filepath):
    print(f"\n==== {os.path.basename(filepath)} ====")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        all_keywords = defaultdict(set)
        # 데이터가 리스트인 경우 각 항목을 순회
        if isinstance(data, list):
            for idx, item in enumerate(data):
                print(f"항목 {idx + 1}/{len(data)} 처리 중...")
                keywords = extract_keywords_from_data(item)
                for category, words in keywords.items():
                    all_keywords[category].update(words)
        # 데이터가 딕셔너리인 경우
        elif isinstance(data, dict):
            keywords = extract_keywords_from_data(data)
            for category, words in keywords.items():
                all_keywords[category].update(words)
        # 그 외의 경우 (문자열 등)
        else:
            keywords = extract_keywords_from_data(data)
            for category, words in keywords.items():
                all_keywords[category].update(words)

        return {k: list(v) for k, v in all_keywords.items()}

    except Exception as e:
        print(f"[ERROR] {filepath}: {e}")
        return {}


def main():
    json_files = glob(os.path.join(DATA_DIR, "*.json"))
    print(f"총 {len(json_files)}개의 JSON 파일을 처리합니다.")

    final_keywords = defaultdict(set)
    for file in json_files:
        keywords = extract_keywords_from_file(file)
        for category, words in keywords.items():
            final_keywords[category].update(words)
        print(f"추출된 키워드:")
        for category, words in keywords.items():
            print(f"- {category}: {words}")

    # 최종 결과를 카테고리별로 하나의 리스트로 저장
    final_result = {k: list(v) for k, v in final_keywords.items()}
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print(f"\n[저장 완료] {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
