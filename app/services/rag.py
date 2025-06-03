import asyncio
import json
import os
import random
from typing import Dict, List, Sequence

from dotenv import load_dotenv
from litellm import rerank

load_dotenv()

JINA_MODEL = "jina_ai/jina-reranker-v2-base-multilingual"
JINA_API_KEY = os.getenv("JINA_AI_API_KEY")


def load_keywords(
    json_path: str = "data/extracted_keywords.json",
) -> Dict[str, Sequence[str]]:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_top_keywords_by_category(
    user_info: dict, top_n: int = 3
) -> Dict[str, List[str]]:
    if not JINA_API_KEY:
        raise RuntimeError("JINA_AI_API_KEY 환경변수가 설정되어 있지 않습니다.")
    os.environ["JINA_AI_API_KEY"] = JINA_API_KEY
    data = load_keywords()
    # dict의 value들을 모두 문자열로 변환 후 공백으로 이어붙임
    user_text = " ".join(str(v) for v in user_info.values() if v)
    result = {}
    for category, keywords in data.items():
        if not keywords:
            result[category] = []
            continue
        response = rerank(
            model=JINA_MODEL,
            query=user_text,
            documents=list(keywords),
            top_n=10,  # 상위 10개까지 자름
        )
        if asyncio.iscoroutine(response):
            response = asyncio.run(response)
        results = None
        if hasattr(response, "results"):
            results = response.results
        elif isinstance(response, dict) and "results" in response:
            results = response["results"]
        else:
            results = []
        if results is None:
            results = []
        top_keywords = []
        for item in results:
            if isinstance(item, dict):
                if (
                    "document" in item
                    and isinstance(item["document"], dict)
                    and "text" in item["document"]
                ):
                    top_keywords.append(item["document"]["text"])
            elif hasattr(item, "document") and hasattr(item.document, "text"):
                top_keywords.append(item.document.text)
        if len(top_keywords) > 3:
            top_keywords = random.sample(top_keywords, 3)
        result[category] = top_keywords
    return result


if __name__ == "__main__":
    # 테스트용 사용자 정보 dict 예시
    user_info = {
        "company": "네이버",
        "position": "백엔드 엔지니어",
        "name": "홍길동",
        "age": 25,
        "gender": "남성",
        "self_intro": "저는 다양한 프로젝트에서 Python과 Docker를 활용해 백엔드 개발을 했고, 팀워크와 빠른 학습을 중요하게 생각합니다.",
    }
    result = get_top_keywords_by_category(user_info, top_n=3)
    import pprint

    pprint.pprint(result, width=120, compact=True)
