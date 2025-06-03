import json
import os  # .env 파일 관리
import sys
import time

import google.generativeai as genai  # Gemini API
import trafilatura
from bs4 import BeautifulSoup  # Trafilatura 실패 시 최소한의 fallback용
from dotenv import load_dotenv  # .env 파일 관리
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


# --- Gemini API 설정 및 호출 함수 ---
def configure_gemini():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(".env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")

    genai.configure(api_key=api_key)
    print("Gemini API 설정 완료.")


def call_gemini_api(text_content, company_hint="", title_hint=""):
    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json"},
    )

    RAG_DB_STRUCTURE_EXAMPLE_FOR_LLM = """
    참고용 데이터 구조 예시 (실제 LLM의 응답은 아래 '추출할 항목'에 명시된 형식의 객체여야 합니다):
    RAG_DB = {
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
        "company_overview": "카카오는 다양한 플랫폼 서비스를 제공하는…",
    },
    }
    """
    prompt = f"""주어진 채용 공고 텍스트에서 다음 정보를 추출하여 주어진 형식으로만 응답해줘.
다른 설명이나 추가 텍스트는 절대 포함하지 말고, 순수 JSON 객체만 반환해야 해.
만약 특정 정보가 명확하지 않거나 없다면, 해당 필드 값으로 "정보 없음" 또는 "N/A"를 사용해줘.

주어진 예시 형식은 다음과 같아
{RAG_DB_STRUCTURE_EXAMPLE_FOR_LLM}

추출할 항목:
1. "company_name": 공고를 게시한 회사 또는 자회사의 정확한 이름. (힌트: "{company_hint}")
2. "job_title": 채용 직무의 명칭. (힌트: "{title_hint}")
3. "job_posting": 채용공고의 제목 및 내용 요약
4. "hiring_values": 회사가 추구하는 인재상, 가치, 또는 조직 문화와 관련된 핵심 내용 요약 (간결하게).
5. "tech_stack": 해당 직무에서 사용되거나 요구되는 주요 기술 스택 목록 (문자열 배열 또는 쉼표로 구분된 단일 문자열 형태 선호).
6. "sample_interview_questions": "tech_stack"을 보고 한개 생성해줘.
7. "company_overview": 회사, 팀 또는 해당 직무의 조직에 대한 간략한 소개.

job_title은 아래 가능한 맞는 선택지에서 선택해줘
Backend Engineer, Frontend Engineer, Full Stack Engineer, DevOps Engineer, Security Engineer, Data Engineer, AI Engineer, iOS Developer, Android Developer, Project Manager, Cloud Engineer, MLOps Engineer , other

company_name은 아래 가능한 맞는 선택지에서 선택해줘
Naver, Kakao, Line, Coupang, Baemin, Daangn, Toss, Liner, Scatterlab

공고 텍스트 (매우 길 경우 일부 내용이 생략되었을 수 있음):
\"\"\"
{text_content[:30000]} 
\"\"\"

JSON 응답:
""".strip()
    # Gemini 모델의 입력 토큰 제한 고려 (gemini-1.5-flash는 컨텍스트 창이 매우 큼)
    # trafilatura로 정제된 텍스트라도 매우 길 수 있으므로, 30000자 정도로 제한 (약 1만 토큰 내외 가정)

    try:
        print(
            f"    Gemini API 호출 시도... (텍스트 길이: {len(text_content)} 자, 힌트 회사: '{company_hint}', 힌트 직무: '{title_hint}')"
        )

        response = model.generate_content(prompt)

        json_string = response.text
        # Gemini가 간혹 ```json ... ``` 마크다운으로 감싸서 줄 때가 있으므로 제거
        if json_string.strip().startswith("```json"):
            json_string = json_string.strip()[7:-3].strip()
        elif json_string.strip().startswith("```"):
            json_string = json_string.strip()[3:-3].strip()

        extracted_info = json.loads(json_string)
        print("    Gemini API로부터 JSON 파싱 성공.")

        if isinstance(extracted_info, list):
            extracted_info = extracted_info[0]
        return extracted_info

    except Exception as e_gemini:
        print(f"    Gemini API 호출 또는 JSON 파싱 중 오류: {e_gemini}")
        # API 응답 객체가 있다면 상세 정보 출력 (디버깅용)
        if "response" in locals() and response:
            if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                print(f"    Gemini API Prompt Feedback: {response.prompt_feedback}")
            if hasattr(response, "candidates") and response.candidates:
                for candidate in response.candidates:
                    if (
                        hasattr(candidate, "finish_reason")
                        and candidate.finish_reason != 1
                    ):  # 1 (STOP) 외 다른 이유
                        print(f"    Candidate Finish Reason: {candidate.finish_reason}")
                        if hasattr(candidate, "safety_ratings"):
                            print(
                                f"    Candidate Safety Ratings: {candidate.safety_ratings}"
                            )
        return None


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("lang=ko_KR")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    chrome_options.binary_location = (
        "/home/comoz/chrome/opt/google/chrome/google-chrome"  # 본인 경로로 수정
    )
    driver = webdriver.Chrome(options=chrome_options)
    return driver


# --- LLM 중심의 일반화된 상세 정보 추출 함수 ---
def extract_details_with_llm(
    driver, site_name, list_page_company_hint="", list_page_title_hint=""
):
    current_url = driver.current_url
    print(f"  -> {site_name} 상세 정보 추출 중 (LLM Full): {current_url}")

    # LLM이 최종 결정하므로, 힌트가 없거나 N/A면 빈 문자열로 LLM에 전달하는 것이 나을 수 있음
    company_hint_for_llm = (
        list_page_company_hint
        if list_page_company_hint and "N/A" not in list_page_company_hint
        else ""
    )
    title_hint_for_llm = (
        list_page_title_hint
        if list_page_title_hint and "N/A" not in list_page_title_hint
        else ""
    )

    # 최종 반환될 값들의 기본값 (힌트 또는 N/A)
    actual_job_title = title_hint_for_llm or f"N/A {site_name} 직무(LLM 처리 전)"
    actual_company_name = company_hint_for_llm or f"N/A {site_name} 회사(LLM 처리 전)"

    job_posting_text_trafilatura = f"{site_name} Trafilatura 내용 추출 실패."
    tech_stack_str = "정보 없음"  # LLM이 채울 기본값
    hiring_values_str = "정보 없음"
    company_overview_str = (
        f"{actual_company_name} 개요 정보 없음"
        if actual_company_name
        else "회사 개요 정보 없음"
    )
    other_details_str = ""
    sample_interview_questions = [
        "채용 공고에서 직접 제공되지 않음. 외부 자료 참고 필요."
    ]

    try:
        # 각 사이트별 상세 페이지 메인 컨테이너 선택자 (페이지 로드 확인용)
        detail_page_main_container_selector = "body"  # 가장 일반적인 선택자
        if site_name == "네이버":
            detail_page_main_container_selector = "div.detail_wrap"
        elif site_name == "카카오":
            detail_page_main_container_selector = "div.area_cont"
        elif site_name == "라인":
            detail_page_main_container_selector = "div.content_inner"
        elif site_name == "쿠팡":
            detail_page_main_container_selector = "div.main-col"
        elif site_name == "배민":
            detail_page_main_container_selector = "div.recruit-detail"
        elif site_name == "당근":
            detail_page_main_container_selector = "div.c-pUjPT > main"
        elif site_name == "스캐터랩":
            detail_page_main_container_selector = "div.sc-ca7289f-5.gwcvAJ"

        print(
            f"    {site_name}: WebDriverWait 대기 시작 (선택자: {detail_page_main_container_selector})"
        )
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, detail_page_main_container_selector)
            )
        )
        print(
            f"    {site_name}: WebDriverWait 통과 (선택자: {detail_page_main_container_selector})"
        )
        time.sleep(1.5)

        html_content = driver.page_source

        job_posting_text_trafilatura = trafilatura.extract(
            html_content, include_comments=False, include_tables=True, favor_recall=True
        )
        if not job_posting_text_trafilatura:
            print(
                f"    {site_name}: Trafilatura 추출 실패. BeautifulSoup으로 body 텍스트 추출 시도."
            )
            soup_fallback = BeautifulSoup(html_content, "html.parser")
            body_element = soup_fallback.find("body")
            if body_element:
                job_posting_text_trafilatura = body_element.get_text(
                    separator="\n", strip=True
                )
            if not job_posting_text_trafilatura:
                job_posting_text_trafilatura = f"{site_name} 본문 내용 추출 최종 실패."

        print(
            f"    {site_name} Trafilatura 추출 내용 (일부): {(job_posting_text_trafilatura or '')[:100]}..."
        )

        if (
            job_posting_text_trafilatura
            and "추출 실패" not in job_posting_text_trafilatura
        ):
            extracted_llm_data = call_gemini_api(
                job_posting_text_trafilatura,
                company_hint=company_hint_for_llm,
                title_hint=title_hint_for_llm,
            )
            if extracted_llm_data:
                print(
                    f"    {site_name}: LLM 추출 데이터 (일부): {json.dumps(extracted_llm_data, ensure_ascii=False, indent=2)[:300]}..."
                )
                actual_company_name = (
                    extracted_llm_data.get("company_name") or actual_company_name
                )
                actual_job_title = (
                    extracted_llm_data.get("job_title") or actual_job_title
                )

                tech_stack_data = extracted_llm_data.get("tech_stack", "정보 없음")
                tech_stack_str = (
                    ", ".join(tech_stack_data)
                    if isinstance(tech_stack_data, list)
                    else str(tech_stack_data)
                )

                hiring_values_str = extracted_llm_data.get("hiring_values", "정보 없음")
                company_overview_llm = extracted_llm_data.get("company_overview")
                company_overview_str = (
                    company_overview_llm
                    if company_overview_llm
                    and company_overview_llm not in ["정보 없음", "N/A"]
                    else f"{actual_company_name} 개요 정보 없음"
                )
            else:
                print(
                    f"    {site_name}: LLM API로부터 유효한 데이터 추출 실패. 힌트 또는 기본값을 사용합니다."
                )
        else:
            print(
                f"    {site_name}: 본문 텍스트 부족으로 LLM 호출 안함. 힌트 또는 기본값을 사용합니다."
            )
            tech_stack_str = f"{site_name} 기술 스택 (본문 추출 실패)"  # LLM 호출 못했으므로 업데이트
            hiring_values_str = f"{site_name} 인재상 (본문 추출 실패)"
            company_overview_str = f"{actual_company_name} 개요 (본문 추출 실패)"

        print(
            f"    {site_name} 최종 확정 (LLM 또는 힌트 기반): 회사='{actual_company_name}', 직무='{actual_job_title}'"
        )

        return {
            "data": {
                "job_posting": job_posting_text_trafilatura,
                "hiring_values": hiring_values_str,
                "tech_stack": tech_stack_str,
                "sample_interview_questions": sample_interview_questions,
                "company_overview": company_overview_str,
                "other_details": other_details_str,
            },
            "title": actual_job_title,
            "company": actual_company_name,
        }
    except Exception as e:
        print(
            f"    {site_name} 상세 정보 추출 중 오류 ({current_url}): {type(e).__name__} - {e}"
        )
        return {}


# --- 네이버 스크래핑 함수 ---
def scrape_naver_jobs_to_rag_format(max_jobs_to_fetch_details=300):
    site_name = "네이버"
    list_url = "https://recruit.navercorp.com/rcrt/list.do?subJobCdArr=1010001%2C1010002%2C1010003%2C1010004%2C1010005%2C1010006%2C1010007%2C1010009%2C1010020&sysCompanyCdArr=&empTypeCdArr=&entTypeCdArr=&workAreaCdArr=&sw=&subJobCdData=1010001&subJobCdData=1010002&subJobCdData=1010003&subJobCdData=1010004&subJobCdData=1010005&subJobCdData=1010006&subJobCdData=1010007&subJobCdData=1010009&subJobCdData=1010020"
    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0  # 함수 내에서 초기화
    print(f"{site_name} 채용 목록 크롤링 시작: {list_url}")
    try:
        driver.get(list_url)
        list_container_selector = "ul.card_list"
        job_card_item_selector = f"{list_container_selector} > li.card_item"
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, list_container_selector))
        )
        num_total_cards = len(
            driver.find_elements(By.CSS_SELECTOR, job_card_item_selector)
        )
        print(f"총 {num_total_cards}개의 {site_name} 공고 카드를 찾았습니다.")
        if num_total_cards == 0:
            driver.quit()
            return {}
        jobs_to_process = min(num_total_cards, max_jobs_to_fetch_details)

        for i in range(jobs_to_process):
            # 페이지네이션이 없으므로 "페이지X-" 부분은 생략하고 카드 인덱스만 사용
            hint_title_naver = f"N/A {site_name} 직무 (카드{i+1})"
            hint_company_naver = f"N/A {site_name} 회사 (카드{i+1})"
            print(f"\n{i+1}/{jobs_to_process}번째 {site_name} 공고 처리 중...")
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, job_card_item_selector)
                )
            )
            all_cards = driver.find_elements(By.CSS_SELECTOR, job_card_item_selector)
            if i >= len(all_cards):
                break
            card_el = all_cards[i]
            try:
                card_html_temp = card_el.get_attribute("outerHTML")
                card_soup_temp = BeautifulSoup(card_html_temp, "html.parser")
                title_box_in_list = card_soup_temp.select_one("div.card_title_box")
                if title_box_in_list:
                    info_el_list = title_box_in_list.select(
                        "dl.card_info > dd.info_text"
                    )
                    if len(info_el_list) > 0:
                        hint_company_naver = info_el_list[0].text.strip()
                    if len(info_el_list) > 2:
                        hint_title_naver = info_el_list[2].text.strip()
                else:
                    title_tag_temp = card_soup_temp.select_one(
                        "div.card_body > h4.card_title"
                    )
                    if title_tag_temp:
                        hint_title_naver = title_tag_temp.text.strip()
                    comp_tag_temp = card_soup_temp.select_one(
                        "div.card_body > span.card_company"
                    )
                    if comp_tag_temp:
                        hint_company_naver = comp_tag_temp.text.strip()
                print(
                    f"  목록 정보 (힌트용): {hint_company_naver} - {hint_title_naver}"
                )

                link_el = card_el.find_element(By.CSS_SELECTOR, "a.card_link")
                driver.execute_script(
                    "arguments[0].scrollIntoViewIfNeeded(true);", link_el
                )
                time.sleep(0.5)
                print(f"  -> '{hint_title_naver}' 상세 보기 링크 클릭 시도...")
                link_el.click()
                WebDriverWait(driver, 15).until(EC.url_contains("/rcrt/view.do"))

                # LLM 사용하는 함수 호출
                extraction_result = extract_details_with_llm(
                    driver,
                    site_name,
                    list_page_company_hint=hint_company_naver,
                    list_page_title_hint=hint_title_naver,
                )
                if extraction_result == {}:
                    continue
                actual_data, actual_company, actual_title = (
                    extraction_result["data"],
                    extraction_result["company"],
                    extraction_result["title"],
                )

                # 최종 키는 LLM이 확정한 값 또는 힌트/기본값
                if not actual_company.startswith(
                    (f"N/A {site_name}", f"{site_name} 오류")
                ) and not actual_title.startswith(
                    (f"N/A {site_name}", f"{site_name} 오류")
                ):
                    rag_db_python_format[(actual_company, actual_title)] = actual_data
                    print(
                        f"  -> {site_name} 정보 저장 완료: {actual_company} - {actual_title}"
                    )
                else:
                    print(
                        f"  !!! {site_name} 최종 회사/직무명 미확정. DB 저장 건너뜀. (URL: {driver.current_url})"
                    )

                print(f"  -> {site_name} 목록 페이지로 돌아갑니다...")
                driver.back()
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, list_container_selector)
                    )
                )
                print(f"  -> {site_name} 목록 페이지 로드 확인.")
                time.sleep(1)
            except Exception as e_card:
                print(f"  {site_name} 카드 '{hint_title_naver}' 처리 중 오류: {e_card}")
                if list_url not in driver.current_url:
                    try:
                        driver.get(list_url)
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, list_container_selector)
                            )
                        )
                    except:
                        print(f"     {site_name} 목록 페이지 강제 이동 실패.")
                time.sleep(2)
    except Exception as e_main:
        print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if "driver" in locals() and driver:
            driver.quit()
    print(
        f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)"
    )
    return rag_db_python_format


# --- 카카오 스크래핑 함수 ---
def scrape_kakao_jobs_to_rag_format(max_jobs_to_fetch_details=300):
    list_url = "https://careers.kakao.com/jobs?skillSet=Android%2CiOS%2CWindows%2CWeb_front%2CCloud%2CDB%2CNetwork%2CAlgorithm_ML%2CStatistics_Analysis%2CServer&part=TECHNOLOGY&company=KAKAO&keyword=&employeeType=&page=1"  # 현재는 page=1만
    driver = setup_driver()
    rag_db_python_format = {}
    site_name = "카카오"
    collected_jobs_count = 0  # 함수 내에서 초기화
    print(f"{site_name} 채용 목록 크롤링 시작: {list_url}")
    try:
        driver.get(list_url)
        list_container_selector = "ul.list_jobs"
        job_item_selector = f"{list_container_selector} > a"

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, job_item_selector)
                )
            )
        except Exception as e_wait:
            print(
                f"{site_name} 공고 카드({job_item_selector}) 기다리는 중 오류: {e_wait}"
            )
            driver.quit()
            return {}

        num_total_cards = len(driver.find_elements(By.CSS_SELECTOR, job_item_selector))
        print(
            f"총 {num_total_cards}개의 {site_name} 공고 카드({job_item_selector})를 찾았습니다."
        )
        if num_total_cards == 0:
            driver.quit()
            return {}
        jobs_to_process = min(num_total_cards, max_jobs_to_fetch_details)

        for i in range(jobs_to_process):
            hint_title_kakao = f"N/A {site_name} 직무 (카드{i+1})"
            hint_company_kakao = f"N/A {site_name} 회사 (카드{i+1})"
            print(f"\n{i+1}/{jobs_to_process}번째 {site_name} 공고 처리 중...")
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, job_item_selector)
                )
            )
            all_cards = driver.find_elements(By.CSS_SELECTOR, job_item_selector)
            if i >= len(all_cards):
                break
            card_el_anchor = all_cards[i]
            try:
                try:
                    title_sel = "span.link_tag.cursor_hand.false"
                    title_tag = card_el_anchor.find_element(By.CSS_SELECTOR, title_sel)
                    if title_tag:
                        hint_title_kakao = title_tag.text.strip()
                except:
                    try:
                        title_tag_alt = card_el_anchor.find_element(
                            By.CSS_SELECTOR, "strong.tit_job"
                        )
                        hint_title_kakao = title_tag_alt.text.strip()
                    except:
                        print(f"    {site_name} 카드 No.{i+1} 임시 제목 추출 실패")
                try:
                    company_sel = "dl.item_subinfo:first-of-type dd"
                    company_tag = card_el_anchor.find_element(
                        By.CSS_SELECTOR, company_sel
                    )
                    if company_tag:
                        hint_company_kakao = company_tag.text.strip()
                except:
                    try:
                        company_tag_alt = card_el_anchor.find_element(
                            By.CSS_SELECTOR, "span.txt_info"
                        )
                        hint_company_kakao = company_tag_alt.text.split("·")[0].strip()
                    except:
                        print(f"    {site_name} 카드 No.{i+1} 임시 회사명 추출 실패")
                print(
                    f"  목록 정보 (힌트용): {hint_company_kakao} - {hint_title_kakao}"
                )

                link_el_to_click = card_el_anchor
                driver.execute_script(
                    "arguments[0].scrollIntoViewIfNeeded(true);", link_el_to_click
                )
                time.sleep(0.5)
                print(f"  -> '{hint_title_kakao}' 상세 보기 링크 클릭 시도...")
                link_el_to_click.click()
                WebDriverWait(driver, 15).until(EC.url_contains("/jobs/"))

                # LLM 사용하는 함수 호출
                extraction_result = extract_details_with_llm(
                    driver,
                    site_name,
                    list_page_company_hint=hint_company_kakao,
                    list_page_title_hint=hint_title_kakao,
                )
                if extraction_result == {}:
                    continue
                actual_data, actual_company, actual_title = (
                    extraction_result["data"],
                    extraction_result["company"],
                    extraction_result["title"],
                )

                # 최종 키는 LLM이 확정한 값 또는 힌트/기본값
                if not actual_company.startswith(
                    (f"N/A {site_name}", f"{site_name} 오류")
                ) and not actual_title.startswith(
                    (f"N/A {site_name}", f"{site_name} 오류")
                ):
                    rag_db_python_format[(actual_company, actual_title)] = actual_data
                    print(
                        f"  -> {site_name} 정보 저장 완료: {actual_company} - {actual_title}"
                    )
                else:
                    print(
                        f"  !!! {site_name} 최종 회사/직무명 미확정. DB 저장 건너뜀. (URL: {driver.current_url})"
                    )

                print(f"  -> {site_name} 목록 페이지로 돌아갑니다...")
                driver.back()
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, list_container_selector)
                    )
                )
                print(f"  -> {site_name} 목록 페이지 로드 확인.")
                time.sleep(1)
            except Exception as e_card:
                print(f"  {site_name} 카드 '{hint_title_kakao}' 처리 중 오류: {e_card}")
                if list_url not in driver.current_url:
                    try:
                        driver.get(list_url)
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, list_container_selector)
                            )
                        )
                    except:
                        print(f"     {site_name} 목록 페이지 강제 이동 실패.")
                time.sleep(2)
    except Exception as e_main:
        print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if "driver" in locals() and driver:
            driver.quit()
    print(
        f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)"
    )
    return rag_db_python_format


# --- 라인 스크래핑 함수 ---
def scrape_line_jobs_to_rag_format(max_jobs_to_fetch_details=300):
    site_name = "라인"
    list_url = "https://careers.linecorp.com/ko/jobs?ca=Engineering&fi=Client-side,Web%20Development,Server-side,Data%20Engineering,Tech%20Management,Analytics"  # 현재는 page=1만
    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0  # 함수 내에서 초기화
    print(f"{site_name} 채용 목록 크롤링 시작: {list_url}")
    try:
        driver.get(list_url)
        list_container_selector = "ul.job_list"
        job_card_item_selector = f"{list_container_selector} > li"

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, job_card_item_selector)
                )
            )
        except Exception as e_wait:
            print(
                f"{site_name} 공고 카드({job_card_item_selector}) 기다리는 중 오류: {e_wait}"
            )
            driver.quit()
            return {}

        num_total_cards = len(
            driver.find_elements(By.CSS_SELECTOR, job_card_item_selector)
        )
        print(f"총 {num_total_cards}개의 {site_name} 공고 카드를 찾았습니다.")
        if num_total_cards == 0:
            driver.quit()
            return {}
        jobs_to_process = min(num_total_cards, max_jobs_to_fetch_details)

        for i in range(jobs_to_process):
            hint_title_line = f"N/A {site_name} 직무 (카드{i+1})"
            hint_company_line = f"N/A {site_name} 회사 (카드{i+1})"
            print(f"\n{i+1}/{jobs_to_process}번째 {site_name} 공고 처리 중...")
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, job_card_item_selector)
                )
            )
            all_cards = driver.find_elements(By.CSS_SELECTOR, job_card_item_selector)
            if i >= len(all_cards):
                break
            card_el_li = all_cards[i]
            try:
                print(f"  목록 정보 (힌트용): {hint_company_line} - {hint_title_line}")

                link_el_to_click = card_el_li.find_element(By.CSS_SELECTOR, "a")
                driver.execute_script(
                    "arguments[0].scrollIntoViewIfNeeded(true);", link_el_to_click
                )
                time.sleep(0.5)
                print(f"  -> '{hint_title_line}' 상세 보기 링크 클릭 시도...")
                link_el_to_click.click()

                WebDriverWait(driver, 15).until(EC.url_contains("/ko/jobs/"))

                # LLM 사용하는 함수 호출
                extraction_result = extract_details_with_llm(
                    driver,
                    site_name,
                    list_page_company_hint=hint_company_line,
                    list_page_title_hint=hint_title_line,
                )
                if extraction_result == {}:
                    continue
                actual_data, actual_company, actual_title = (
                    extraction_result["data"],
                    extraction_result["company"],
                    extraction_result["title"],
                )

                # 최종 키는 LLM이 확정한 값 또는 힌트/기본값
                if not actual_company.startswith(
                    (f"N/A {site_name}", f"{site_name} 오류")
                ) and not actual_title.startswith(
                    (f"N/A {site_name}", f"{site_name} 오류")
                ):
                    rag_db_python_format[(actual_company, actual_title)] = actual_data
                    print(
                        f"  -> {site_name} 정보 저장 완료: {actual_company} - {actual_title}"
                    )
                else:
                    print(
                        f"  !!! {site_name} 최종 회사/직무명 미확정. DB 저장 건너뜀. (URL: {driver.current_url})"
                    )

                print(f"  -> {site_name} 목록 페이지로 돌아갑니다...")
                driver.back()
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, list_container_selector)
                    )
                )
                print(f"  -> {site_name} 목록 페이지 로드 확인.")
                time.sleep(1)
            except Exception as e_card:
                print(f"  {site_name} 카드 '{hint_title_line}' 처리 중 오류: {e_card}")
                if list_url not in driver.current_url:
                    try:
                        driver.get(list_url)
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, list_container_selector)
                            )
                        )
                    except:
                        print(f"     {site_name} 목록 페이지 강제 이동 실패.")
                time.sleep(2)
    except Exception as e_main:
        print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if "driver" in locals() and driver:
            driver.quit()
    print(
        f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)"
    )
    return rag_db_python_format


# --- 쿠팡 스크래핑 함수 ---
def scrape_coupang_jobs_to_rag_format(
    max_jobs_to_fetch_details=300, max_pages_to_crawl=5
):  # 페이지네이션 반영
    site_name = "쿠팡"
    base_list_url_cleaned = "https://www.coupang.jobs/kr/jobs/?search=engineer&location=Seoul%2C+South+Korea&pagesize=20"

    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0

    print(
        f"{site_name} 채용 목록 크롤링 시작 (최대 {max_pages_to_crawl} 페이지, 공고 {max_jobs_to_fetch_details}개 목표)"
    )

    try:
        for page_num in range(1, max_pages_to_crawl + 1):
            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(
                    f"  목표 공고 수({max_jobs_to_fetch_details}개)에 도달하여 크롤링을 중단합니다."
                )
                break

            current_page_url = f"{base_list_url_cleaned}&page={page_num}"
            print(
                f"\n--- {site_name} 페이지 {page_num} 크롤링 시작: {current_page_url} ---"
            )

            driver.get(current_page_url)
            list_container_selector = "div.grid.job-listing"
            job_card_item_selector = f"{list_container_selector} div.card.card-job"

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, job_card_item_selector)
                    )
                )
            except Exception as e_wait:
                print(
                    f"  {site_name} 페이지 {page_num}: 공고 카드({job_card_item_selector})를 찾을 수 없거나 대기 시간 초과: {e_wait}"
                )
                print(
                    f"  페이지 {page_num}에 더 이상 공고가 없거나 선택자가 잘못되었을 수 있습니다. 다음 페이지 시도를 중단합니다."
                )
                break

            all_cards_on_page = driver.find_elements(
                By.CSS_SELECTOR, job_card_item_selector
            )
            num_cards_on_this_page = len(all_cards_on_page)
            print(
                f"  {site_name} 페이지 {page_num}: {num_cards_on_this_page}개의 공고 카드를 찾았습니다."
            )

            if num_cards_on_this_page == 0:
                print(f"  페이지 {page_num}에 공고가 없습니다. 크롤링을 중단합니다.")
                break

            for i in range(num_cards_on_this_page):
                if collected_jobs_count >= max_jobs_to_fetch_details:
                    print(
                        f"    목표 공고 수({max_jobs_to_fetch_details}개) 도달. 현재 카드 처리 중단."
                    )
                    break

                current_card_elements_refreshed = driver.find_elements(
                    By.CSS_SELECTOR, job_card_item_selector
                )
                if i >= len(current_card_elements_refreshed):
                    print(
                        f"    Stale element 참조 방지 또는 인덱스 오류: 인덱스 {i} / 현재 카드 수 {len(current_card_elements_refreshed)}"
                    )
                    break
                card_el = current_card_elements_refreshed[i]

                list_page_title_hint = (
                    f"N/A {site_name} 직무 (페이지{page_num}-카드{i+1})"
                )
                list_page_company_hint = (
                    f"N/A {site_name} 회사 (페이지{page_num}-카드{i+1})"
                )
                print(
                    f"\n  페이지 {page_num}의 {i+1}/{num_cards_on_this_page}번째 {site_name} 공고 처리 중 ({list_page_title_hint})..."
                )

                try:
                    print(
                        f"    목록 정보 (힌트용): {list_page_company_hint} - {list_page_title_hint}"
                    )

                    link_el_to_click = None
                    try:
                        link_el_to_click = card_el.find_element(
                            By.CSS_SELECTOR, "a.stretched-link.js-view-job"
                        )
                    except:
                        try:
                            link_el_to_click = card_el.find_element(
                                By.CSS_SELECTOR, "div.card-body h2.card-title a"
                            )
                        except Exception as e_link_find:
                            print(
                                f"      {site_name} 카드 No.{i+1} 상세 링크 요소를 두 선택자 모두로 찾지 못했습니다: {e_link_find}"
                            )
                            continue

                    driver.execute_script(
                        "arguments[0].scrollIntoViewIfNeeded(true);", link_el_to_click
                    )
                    time.sleep(0.5)

                    print(
                        f"    -> '{list_page_title_hint}' 상세 보기 링크 클릭 시도 (JavaScript 사용)..."
                    )
                    driver.execute_script("arguments[0].click();", link_el_to_click)

                    expected_url_pattern = "/kr/jobs/"
                    WebDriverWait(driver, 15).until(
                        EC.url_contains(expected_url_pattern)
                    )
                    print(f"    -> 새 URL로 이동됨: {driver.current_url}")

                    # LLM 사용하는 함수 호출
                    extraction_result = extract_details_with_llm(
                        driver, site_name, list_page_company_hint, list_page_title_hint
                    )
                    if extraction_result == {}:
                        continue
                    actual_data, actual_company, actual_title = (
                        extraction_result["data"],
                        extraction_result["company"],
                        extraction_result["title"],
                    )

                    # 최종 키는 LLM이 확정한 값 또는 힌트/기본값
                    if not actual_company.startswith(
                        (f"N/A {site_name}", f"{site_name} 오류")
                    ) and not actual_title.startswith(
                        (f"N/A {site_name}", f"{site_name} 오류")
                    ):
                        rag_db_python_format[(actual_company, actual_title)] = (
                            actual_data
                        )
                        print(
                            f"  -> {site_name} 정보 저장 완료: {actual_company} - {actual_title}"
                        )
                    else:
                        print(
                            f"  !!! {site_name} 최종 회사/직무명 미확정. DB 저장 건너뜀. (URL: {driver.current_url})"
                        )

                    collected_jobs_count += 1
                    print(
                        f"    -> {site_name} 목록 페이지({current_page_url})로 돌아갑니다..."
                    )
                    driver.get(current_page_url)

                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, list_container_selector)
                        )
                    )
                    print(f"    -> {site_name} 목록 페이지 로드 확인.")
                    time.sleep(1)
                except Exception as e_card:
                    print(
                        f"    {site_name} 페이지 {page_num}의 카드 '{list_page_title_hint}' 처리 중 오류: {e_card}"
                    )
                    if current_page_url not in driver.current_url:
                        print(
                            f"      현재 URL: {driver.current_url}. 목록 페이지({current_page_url})로 강제 이동 시도."
                        )
                        try:
                            driver.get(current_page_url)
                            WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located(
                                    (By.CSS_SELECTOR, list_container_selector)
                                )
                            )
                        except:
                            print(
                                f"        {site_name} 목록 페이지({page_num}) 강제 이동 실패."
                            )
                    time.sleep(2)

            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(
                    f"  목표 공고 수({max_jobs_to_fetch_details}개) 도달. 다음 페이지 크롤링 중단."
                )
                break

        print(f"--- {site_name} 페이지 {page_num} 크롤링 완료 ---")
        if (
            page_num < max_pages_to_crawl
            and collected_jobs_count < max_jobs_to_fetch_details
        ):
            time.sleep(2)
        else:
            print(
                f"  모든 지정된 페이지를 크롤링했거나 목표 개수에 도달하여 {site_name} 크롤링을 종료합니다."
            )

    except Exception as e_main:
        print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if "driver" in locals() and driver:
            print(f"{site_name} 드라이버 종료 중...")
            driver.quit()

    print(
        f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)"
    )
    return rag_db_python_format


# --- 배민(우아한형제들) 스크래핑 함수 ---
def scrape_baemin_jobs_to_rag_format(
    max_jobs_to_fetch_details=300, max_pages_to_crawl=1
):  # 기본 max_pages_to_crawl=1 (더보기 버튼 미구현)
    site_name = "배민"

    list_url = "https://career.woowahan.com/?keyword=&category=jobGroupCodes%3ABA005001&jobCodes=BA007041,BA007003,BA007005,BA007006,BA007001&employmentTypeCodes=BA002002,BA002003,BA002001&serviceSectionCodes=BA006010,BA006018,BA006004,BA006013,BA006015,BA006009,BA006017,BA006012,BA006006,BA006003,BA006001#recruit-list"

    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0

    print(
        f"{site_name} 채용 목록 크롤링 시작 (현재 첫 페이지만 처리, 최대 공고 {max_jobs_to_fetch_details}개 목표)"
    )

    try:
        for page_num in range(1, 2):
            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(
                    f"  목표 공고 수({max_jobs_to_fetch_details}개)에 도달하여 크롤링을 중단합니다."
                )
                break

            current_page_url = list_url
            if page_num > 1:
                print(
                    f"  {site_name}은 현재 첫 페이지만 지원합니다. page_num {page_num} 건너뜁니다."
                )
                break

            print(
                f"\n--- {site_name} 페이지 {page_num} 크롤링 시작: {current_page_url} ---"
            )
            driver.get(current_page_url)

            list_container_selector = "ul.recruit-type-list"
            job_card_item_selector = f"{list_container_selector} > li"

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, job_card_item_selector)
                    )
                )
            except Exception as e_wait:
                print(
                    f"  {site_name} 페이지 {page_num}: 공고 카드({job_card_item_selector}) 기다리는 중 오류: {e_wait}"
                )
                print(
                    f"  '{job_card_item_selector}' 선택자가 정확한지, 페이지에 공고가 있는지 확인해주세요."
                )
                break

            all_cards_on_page = driver.find_elements(
                By.CSS_SELECTOR, job_card_item_selector
            )
            num_cards_on_this_page = len(all_cards_on_page)
            print(
                f"  {site_name} 페이지 {page_num}: {num_cards_on_this_page}개의 공고 카드를 찾았습니다."
            )

            if num_cards_on_this_page == 0:
                print(f"  페이지 {page_num}에 공고가 없습니다. 크롤링을 중단합니다.")
                break

            for i in range(num_cards_on_this_page):
                if collected_jobs_count >= max_jobs_to_fetch_details:
                    print(
                        f"    목표 공고 수({max_jobs_to_fetch_details}개) 도달. 현재 카드 처리 중단."
                    )
                    break

                # Stale Element 참조 방지를 위해 요소를 다시 찾음
                current_card_elements_refreshed = driver.find_elements(
                    By.CSS_SELECTOR, job_card_item_selector
                )
                if i >= len(current_card_elements_refreshed):
                    print(f"    Stale elem  ent 참조 방지 또는 인덱스 오류")
                    break
                card_el_li = current_card_elements_refreshed[i]  # <li> 요소

                # 목록 페이지의 힌트용 회사명/직무명 (기본값)
                list_page_title_hint = (
                    f"N/A {site_name} 직무 (페이지{page_num}-카드{i+1})"
                )
                list_page_company_hint = (
                    f"N/A {site_name} 회사 (페이지{page_num}-카드{i+1})"
                )

                try:
                    try:
                        title_tag = card_el_li.find_element(
                            By.CSS_SELECTOR, "a strong[data-testid='title']"
                        )
                        if title_tag:
                            list_page_title_hint = title_tag.text.strip()
                    except:
                        print(f"    {site_name} 카드 No.{i+1} 임시 제목 추출 실패")
                    try:
                        company_tag = card_el_li.find_element(
                            By.CSS_SELECTOR, "a span[data-testid='title']"
                        )
                        if company_tag:
                            list_page_company_hint = company_tag.text.strip()
                    except:
                        print(f"    {site_name} 카드 No.{i+1} 임시 회사명 추출 실패")
                    print(
                        f"    목록 정보 (힌트용): {list_page_company_hint} - {list_page_title_hint}"
                    )

                    link_el_to_click = card_el_li.find_element(By.CSS_SELECTOR, "a")

                    driver.execute_script(
                        "arguments[0].scrollIntoViewIfNeeded(true);", link_el_to_click
                    )
                    time.sleep(0.5)
                    print(
                        f"    -> '{list_page_title_hint}' 상세 보기 링크 클릭 시도 (JavaScript 사용)..."
                    )
                    driver.execute_script("arguments[0].click();", link_el_to_click)

                    expected_url_pattern = "/recruitment/"
                    WebDriverWait(driver, 15).until(
                        EC.url_contains(expected_url_pattern)
                    )
                    print(f"    -> 새 URL로 이동됨: {driver.current_url}")

                    # LLM 사용하는 함수 호출
                    extraction_result = extract_details_with_llm(
                        driver, site_name, list_page_company_hint, list_page_title_hint
                    )
                    if extraction_result == {}:
                        continue
                    actual_data, actual_company, actual_title = (
                        extraction_result["data"],
                        extraction_result["company"],
                        extraction_result["title"],
                    )

                    # 최종 키는 LLM이 확정한 값 또는 힌트/기본값
                    if not actual_company.startswith(
                        (f"N/A {site_name}", f"{site_name} 오류")
                    ) and not actual_title.startswith(
                        (f"N/A {site_name}", f"{site_name} 오류")
                    ):
                        rag_db_python_format[(actual_company, actual_title)] = (
                            actual_data
                        )
                        print(
                            f"  -> {site_name} 정보 저장 완료: {actual_company} - {actual_title}"
                        )
                    else:
                        print(
                            f"  !!! {site_name} 최종 회사/직무명 미확정. DB 저장 건너뜀. (URL: {driver.current_url})"
                        )

                    collected_jobs_count += 1
                    print(
                        f"    -> {site_name} 목록 페이지({current_page_url})로 돌아갑니다..."
                    )
                    driver.get(current_page_url)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, list_container_selector)
                        )
                    )
                    print(f"    -> {site_name} 목록 페이지 로드 확인.")
                    time.sleep(1)
                except Exception as e_card:
                    print(
                        f"    {site_name} 페이지 {page_num}의 카드 '{list_page_title_hint}' 처리 중 오류: {e_card}"
                    )
                    if current_page_url not in driver.current_url:
                        print(
                            f"      현재 URL: {driver.current_url}. 목록 페이지({current_page_url})로 강제 이동 시도."
                        )
                        try:
                            driver.get(current_page_url)
                            WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located(
                                    (By.CSS_SELECTOR, list_container_selector)
                                )
                            )
                        except:
                            print(
                                f"        {site_name} 목록 페이지({page_num}) 강제 이동 실패."
                            )
                    time.sleep(2)

            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(
                    f"  목표 공고 수({max_jobs_to_fetch_details}개) 도달. 다음 페이지 크롤링 중단."
                )
                break

        print(f"--- {site_name} 페이지 {page_num} 크롤링 완료 ---")
        print(f"  {site_name}은(는) 현재 첫 페이지만 지원합니다. 크롤링을 종료합니다.")

    except Exception as e_main:
        print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if "driver" in locals() and driver:
            print(f"{site_name} 드라이버 종료 중...")
            driver.quit()

    print(
        f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)"
    )
    return rag_db_python_format


# --- 당근(Daangn) 스크래핑 함수 ---
def scrape_daangn_jobs_to_rag_format(max_jobs_to_fetch_details=300):
    site_name = "당근"
    base_url_for_site = "https://about.daangn.com"

    filter_names = [
        "data",
        "software-engineer-android",
        "software-engineer-backend",
        "software-engineer-frontend",
        "software-engineer-ios",
        "software-engineer-machine-learning",
    ]
    list_urls_to_scrape = [
        f"https://about.daangn.com/jobs/{filter_name}/#_filter"
        for filter_name in filter_names
    ]

    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0

    print(
        f"{site_name} 채용 목록 크롤링 시작 (총 {len(list_urls_to_scrape)}개 필터 URL, 전체 공고 {max_jobs_to_fetch_details}개 목표)"
    )

    try:
        for list_url in list_urls_to_scrape:
            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(
                    f"  전체 목표 공고 수({max_jobs_to_fetch_details}개) 도달. 다음 필터 URL 크롤링 중단."
                )
                break

            print(f"\n--- {site_name} 필터 URL 크롤링 시작: {list_url} ---")
            driver.get(list_url)
            time.sleep(2)  # 페이지 기본 로딩을 위한 최소 시간 부여

            list_container_selector = "ul.c-jpGEAj"
            try:
                print(f"  목록 컨테이너({list_container_selector}) 대기 중...")
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, list_container_selector)
                    )
                )
                print(f"  목록 컨테이너({list_container_selector}) 발견됨.")
            except Exception as e_container_wait:
                print(
                    f"  {site_name} 필터 URL({list_url})에서 목록 컨테이너({list_container_selector}) 기다리는 중 오류: {e_container_wait}"
                )
                print(
                    f"  해당 필터에 목록 컨테이너가 없거나 선택자가 잘못되었을 수 있습니다. 다음 필터로 넘어갑니다."
                )
                continue
            job_card_item_selector = f"{list_container_selector} > div > li.c-deAcZv"

            # 카드가 실제로 로드되는지 확인하기 위해 짧게라도 대기
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, job_card_item_selector)
                    )  # 첫번째 카드라도 뜨는지
                )
            except:
                print(
                    f"  {site_name} 필터 URL({list_url})에서 첫번째 공고 카드({job_card_item_selector})를 찾지 못했습니다. 공고가 없을 수 있습니다."
                )
                # 공고가 없을 수 있으므로 오류로 간주하지 않고 다음 필터로 진행
                # continue

            all_cards_on_page = driver.find_elements(
                By.CSS_SELECTOR, job_card_item_selector
            )
            num_cards_on_this_page = len(all_cards_on_page)
            print(
                f"  {site_name} 필터 URL({list_url})에서 {num_cards_on_this_page}개의 공고 카드(li.c-deAcZv)를 찾았습니다."
            )

            if num_cards_on_this_page == 0:
                print(f"  해당 필터에 공고 카드가 없습니다.")
                continue

            for i in range(num_cards_on_this_page):
                if collected_jobs_count >= max_jobs_to_fetch_details:
                    print(
                        f"    전체 목표 공고 수({max_jobs_to_fetch_details}개) 도달. 현재 카드 처리 중단."
                    )
                    break

                current_card_elements_refreshed = driver.find_elements(
                    By.CSS_SELECTOR, job_card_item_selector
                )
                if i >= len(current_card_elements_refreshed):
                    print(f"    Stale element 참조 방지 또는 인덱스 오류")
                    break
                card_el_li = current_card_elements_refreshed[i]

                current_filter_name = (
                    list_url.split("/")[-2]
                    if len(list_url.split("/")) > 1
                    else "unknown_filter"
                )
                list_page_title_hint = (
                    f"N/A {site_name} 직무 (필터:{current_filter_name}-카드{i+1})"
                )
                list_page_company_hint = "당근"

                try:
                    print(
                        f"    목록 정보 (힌트용): {list_page_company_hint} - {list_page_title_hint}"
                    )

                    link_el_to_click = card_el_li.find_element(
                        By.CSS_SELECTOR, "a.c-hCDnza"
                    )

                    detail_page_relative_url = link_el_to_click.get_attribute("href")
                    if not detail_page_relative_url:
                        print(
                            f"    {site_name} 카드 No.{i+1} 상세 링크 href 속성을 찾지 못했습니다. 건너뜁니다."
                        )
                        continue

                    from urllib.parse import urljoin

                    detail_page_full_url = urljoin(
                        base_url_for_site, detail_page_relative_url
                    )

                    print(
                        f"    -> '{list_page_title_hint}' 상세 페이지로 이동: {detail_page_full_url}"
                    )

                    current_list_page_for_return = driver.current_url
                    driver.get(detail_page_full_url)

                    WebDriverWait(driver, 15).until(
                        EC.url_contains("/jobs/")
                    )  # 사용자 제공: 상세 URL에 /jobs/ 포함

                    # LLM 사용하는 함수 호출
                    extraction_result = extract_details_with_llm(
                        driver, site_name, list_page_company_hint, list_page_title_hint
                    )
                    if extraction_result == {}:
                        continue
                    actual_data, actual_company, actual_title = (
                        extraction_result["data"],
                        extraction_result["company"],
                        extraction_result["title"],
                    )

                    # 최종 키는 LLM이 확정한 값 또는 힌트/기본값
                    if not actual_company.startswith(
                        (f"N/A {site_name}", f"{site_name} 오류")
                    ) and not actual_title.startswith(
                        (f"N/A {site_name}", f"{site_name} 오류")
                    ):
                        rag_db_python_format[(actual_company, actual_title)] = (
                            actual_data
                        )
                        print(
                            f"  -> {site_name} 정보 저장 완료: {actual_company} - {actual_title}"
                        )
                    else:
                        print(
                            f"  !!! {site_name} 최종 회사/직무명 미확정. DB 저장 건너뜀. (URL: {driver.current_url})"
                        )

                    collected_jobs_count += 1
                    print(
                        f"    -> {site_name} 목록 페이지({current_list_page_for_return})로 돌아갑니다..."
                    )
                    driver.get(current_list_page_for_return)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, list_container_selector)
                        )
                    )
                    print(f"    -> {site_name} 목록 페이지 로드 확인.")
                    time.sleep(1)

                except Exception as e_card:
                    print(
                        f"    {site_name} 필터 URL({list_url})의 카드 '{list_page_title_hint}' 처리 중 오류: {e_card}"
                    )
                    if list_url not in driver.current_url:
                        try:
                            print(
                                f"      현재 URL: {driver.current_url}. 목록 페이지({list_url})로 강제 이동 시도."
                            )
                            driver.get(list_url)
                            WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located(
                                    (By.CSS_SELECTOR, list_container_selector)
                                )
                            )
                        except:
                            print(
                                f"        {site_name} 목록 페이지({list_url}) 강제 이동 실패."
                            )
                    time.sleep(2)

            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(
                    f"  전체 목표 공고 수({max_jobs_to_fetch_details}개) 도달. 현재 필터의 나머지 카드 처리 중단."
                )
                break

        print(f"--- {site_name} 필터 URL {list_url} 크롤링 완료 ---")
        if (
            list_url != list_urls_to_scrape[-1]
            and collected_jobs_count < max_jobs_to_fetch_details
        ):
            time.sleep(3)

    except Exception as e_main:
        print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if "driver" in locals() and driver:
            print(f"{site_name} 드라이버 종료 중...")
            driver.quit()

    print(
        f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)"
    )
    return rag_db_python_format


# --- 토스(Toss) 스크래핑 함수 ---
def scrape_toss_jobs_to_rag_format(max_jobs_to_fetch_details=300):
    site_name = "토스"
    base_url_for_site = "https://toss.im"

    filter_names = ["Engineering", "Data"]
    list_urls_to_scrape = [
        f"https://toss.im/career/jobs?main_category={filter_name}"
        for filter_name in filter_names
    ]

    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0

    print(
        f"{site_name} 채용 목록 크롤링 시작 (총 {len(list_urls_to_scrape)}개 필터 URL, 전체 공고 {max_jobs_to_fetch_details}개 목표)"
    )

    try:
        for list_url in list_urls_to_scrape:
            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(
                    f"  전체 목표 공고 수({max_jobs_to_fetch_details}개) 도달. 다음 필터 URL 크롤링 중단."
                )
                break

            current_filter_name_for_log = list_url.split("=")[-1]
            print(
                f"\n--- {site_name} 필터 '{current_filter_name_for_log}' 크롤링 시작: {list_url} ---"
            )
            driver.get(list_url)
            time.sleep(2)

            list_container_selector = "ul.css-16k97ld"
            job_item_anchor_selector = f"{list_container_selector} > a"

            try:
                print(f"  공고 카드(a 태그)({job_item_anchor_selector}) 대기 중...")
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, job_item_anchor_selector)
                    )
                )
                print(f"  공고 카드(a 태그)({job_item_anchor_selector}) 발견됨.")
            except Exception as e_wait:
                print(
                    f"  {site_name} 필터 URL({list_url})에서 공고 카드({job_item_anchor_selector}) 기다리는 중 오류: {e_wait}"
                )
                print(
                    f"  '{job_item_anchor_selector}' 선택자가 정확한지, 해당 필터에 공고가 있는지 확인해주세요."
                )
                continue

            all_cards_on_page = driver.find_elements(
                By.CSS_SELECTOR, job_item_anchor_selector
            )
            num_cards_on_this_page = len(all_cards_on_page)
            print(
                f"  {site_name} 필터 URL({list_url})에서 {num_cards_on_this_page}개의 공고 카드(a 태그)를 찾았습니다."
            )

            if num_cards_on_this_page == 0:
                print(f"  해당 필터에 공고 카드가 없습니다.")
                continue

            for i in range(num_cards_on_this_page):
                if collected_jobs_count >= max_jobs_to_fetch_details:
                    print(
                        f"    전체 목표 공고 수({max_jobs_to_fetch_details}개) 도달. 현재 카드 처리 중단."
                    )
                    break

                current_card_elements_refreshed = driver.find_elements(
                    By.CSS_SELECTOR, job_item_anchor_selector
                )
                if i >= len(current_card_elements_refreshed):
                    print(f"    Stale element 참조 방지 또는 인덱스 오류")
                    break
                card_el_anchor = current_card_elements_refreshed[i]

                # 목록 페이지의 힌트용 회사명/직무명 (기본값)
                list_page_title_hint = f"N/A {site_name} 직무 (필터:{current_filter_name_for_log}-카드{i+1})"
                list_page_company_hint = f"N/A {site_name} 회사 (필터:{current_filter_name_for_log}-카드{i+1})"

                try:
                    try:
                        title_tag = card_el_anchor.find_element(
                            By.CSS_SELECTOR,
                            "strong[class*='title'], strong[data-testid*='title']",
                        )
                        if title_tag:
                            list_page_title_hint = title_tag.text.strip()
                    except:
                        print(f"    {site_name} 카드 No.{i+1} 임시 제목 추출 실패")
                    try:
                        company_tag = card_el_anchor.find_element(
                            By.CSS_SELECTOR,
                            "span[class*='company'], span[data-testid*='company']",
                        )
                        if company_tag:
                            list_page_company_hint = company_tag.text.strip()
                        else:
                            list_page_company_hint = "토스"
                    except:
                        list_page_company_hint = "토스"
                        print(
                            f"    {site_name} 카드 No.{i+1} 임시 회사명 추출 실패, '{list_page_company_hint}'(으)로 기본 설정"
                        )
                    print(
                        f"    목록 정보 (힌트용): {list_page_company_hint} - {list_page_title_hint}"
                    )

                    link_el_to_click = card_el_anchor

                    detail_page_href = link_el_to_click.get_attribute("href")
                    if not detail_page_href:
                        print(
                            f"    {site_name} 카드 No.{i+1} 상세 링크 href 속성을 찾지 못했습니다. 건너뜁니다."
                        )
                        continue

                    detail_page_full_url = detail_page_href
                    if not detail_page_href.startswith("http"):
                        from urllib.parse import urljoin

                        detail_page_full_url = urljoin(
                            base_url_for_site, detail_page_href
                        )

                    print(
                        f"    -> '{list_page_title_hint}' 상세 페이지로 이동: {detail_page_full_url}"
                    )

                    current_list_page_for_return = driver.current_url
                    driver.get(detail_page_full_url)

                    WebDriverWait(driver, 15).until(
                        EC.url_contains("/career/job-detail")
                    )

                    # LLM 사용하는 함수 호출
                    extraction_result = extract_details_with_llm(
                        driver, site_name, list_page_company_hint, list_page_title_hint
                    )
                    if extraction_result == {}:
                        continue
                    actual_data, actual_company, actual_title = (
                        extraction_result["data"],
                        extraction_result["company"],
                        extraction_result["title"],
                    )

                    # 최종 키는 LLM이 확정한 값 또는 힌트/기본값
                    if not actual_company.startswith(
                        (f"N/A {site_name}", f"{site_name} 오류")
                    ) and not actual_title.startswith(
                        (f"N/A {site_name}", f"{site_name} 오류")
                    ):
                        rag_db_python_format[(actual_company, actual_title)] = (
                            actual_data
                        )
                        print(
                            f"  -> {site_name} 정보 저장 완료: {actual_company} - {actual_title}"
                        )
                    else:
                        print(
                            f"  !!! {site_name} 최종 회사/직무명 미확정. DB 저장 건너뜀. (URL: {driver.current_url})"
                        )

                    collected_jobs_count += 1
                    print(
                        f"    -> {site_name} 목록 페이지({current_list_page_for_return})로 돌아갑니다..."
                    )
                    driver.get(current_list_page_for_return)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, list_container_selector)
                        )
                    )
                    print(f"    -> {site_name} 목록 페이지 로드 확인.")
                    time.sleep(1)

                except Exception as e_card:
                    print(
                        f"    {site_name} 필터({current_filter_name_for_log})의 카드 '{list_page_title_hint}' 처리 중 오류: {e_card}"
                    )
                    if current_list_page_for_return not in driver.current_url:
                        try:
                            print(
                                f"      현재 URL: {driver.current_url}. 목록 페이지({current_list_page_for_return})로 강제 이동 시도."
                            )
                            driver.get(current_list_page_for_return)
                            WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located(
                                    (By.CSS_SELECTOR, list_container_selector)
                                )
                            )
                        except:
                            print(
                                f"        {site_name} 목록 페이지({current_list_page_for_return}) 강제 이동 실패."
                            )
                    time.sleep(2)

            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(
                    f"  전체 목표 공고 수({max_jobs_to_fetch_details}개) 도달. 현재 필터의 나머지 카드 처리 중단."
                )
                break

        print(f"--- {site_name} 필터 URL {list_url} 크롤링 완료 ---")
        if (
            list_url != list_urls_to_scrape[-1]
            and collected_jobs_count < max_jobs_to_fetch_details
        ):
            time.sleep(3)

    except Exception as e_main:
        print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if "driver" in locals() and driver:
            print(f"{site_name} 드라이버 종료 중...")
            driver.quit()

    print(
        f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)"
    )
    return rag_db_python_format


# --- 라이너(Liner) 스크래핑 함수 ---
def scrape_liner_jobs_to_rag_format(max_jobs_to_fetch_details=300):
    site_name = "라이너"
    base_url_for_site = "https://liner.com"  # 상대 URL 조립 시 사용

    list_url = "https://liner.com/ko/careers/jobs"

    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0  # 함수 내에서 초기화

    print(
        f"{site_name} 채용 목록 크롤링 시작: {list_url} (최대 공고 {max_jobs_to_fetch_details}개 목표)"
    )

    try:
        driver.get(list_url)
        time.sleep(2)  # 페이지 초기 로딩 대기

        list_container_selector = "div.css-j7qwjs"
        job_item_anchor_selector = f"{list_container_selector} > a"

        try:
            print(f"  공고 카드(a 태그)({job_item_anchor_selector}) 대기 중...")
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, job_item_anchor_selector)
                )
            )
            print(f"  공고 카드(a 태그)({job_item_anchor_selector}) 발견됨.")
        except Exception as e_wait:
            print(
                f"  {site_name} URL({list_url})에서 공고 카드({job_item_anchor_selector}) 기다리는 중 오류: {e_wait}"
            )
            print(
                f"  '{job_item_anchor_selector}' 선택자가 정확한지, 해당 페이지에 공고가 있는지 확인해주세요."
            )
            driver.quit()
            return {}

        all_cards_on_page = driver.find_elements(
            By.CSS_SELECTOR, job_item_anchor_selector
        )
        num_cards_on_this_page = len(all_cards_on_page)
        print(
            f"  {site_name} URL({list_url})에서 {num_cards_on_this_page}개의 공고 카드(a 태그)를 찾았습니다."
        )

        if num_cards_on_this_page == 0:
            print(f"  해당 페이지에 공고 카드가 없습니다.")
            driver.quit()
            return {}

        jobs_to_process = min(num_cards_on_this_page, max_jobs_to_fetch_details)

        # 상세 페이지 URL들을 먼저 수집 (페이지 이동으로 인한 StaleElement 방지)
        detail_page_links_info = []
        for i in range(jobs_to_process):
            card_el_anchor = all_cards_on_page[i]

            list_page_title_hint = f"N/A {site_name} 직무 (카드{i+1})"
            list_page_company_hint = "라이너"
            try:
                # 라이너 목록 카드(a 태그) 내에서 임시 직무명
                raw_anchor_text = card_el_anchor.text.strip()
                if raw_anchor_text:
                    list_page_title_hint = raw_anchor_text.split("\n")[
                        0
                    ]  # 여러 줄일 경우 첫 줄

            except:
                print(f"    {site_name} 카드 No.{i+1} 임시 제목 추출 실패")

            detail_page_relative_url = card_el_anchor.get_attribute("href")
            if detail_page_relative_url:
                from urllib.parse import urljoin

                detail_page_full_url = urljoin(
                    base_url_for_site, detail_page_relative_url
                )
                detail_page_links_info.append(
                    {
                        "url": detail_page_full_url,
                        "title_hint": list_page_title_hint,
                        "company_hint": list_page_company_hint,
                    }
                )
            else:
                print(
                    f"    {site_name} 카드 No.{i+1} 상세 링크 href 속성을 찾지 못했습니다."
                )

        # 수집된 링크들을 순회하며 상세 정보 추출
        for job_info in detail_page_links_info:
            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(
                    f"    전체 목표 공고 수({max_jobs_to_fetch_details}개) 도달. 상세 정보 추출 중단."
                )
                break

            print(f"\n  다음 공고 상세 정보 추출: {job_info['url']}")
            driver.get(job_info["url"])

            expected_url_pattern = "/ko/careers/jobs/"
            WebDriverWait(driver, 15).until(EC.url_contains(expected_url_pattern))
            print(f"    -> 새 URL로 이동됨: {driver.current_url}")

            # LLM 사용하는 함수 호출
            extraction_result = extract_details_with_llm(
                driver, site_name, list_page_company_hint, list_page_title_hint
            )
            if extraction_result == {}:
                continue
            actual_data, actual_company, actual_title = (
                extraction_result["data"],
                extraction_result["company"],
                extraction_result["title"],
            )

            # 최종 키는 LLM이 확정한 값 또는 힌트/기본값
            if not actual_company.startswith(
                (f"N/A {site_name}", f"{site_name} 오류")
            ) and not actual_title.startswith((f"N/A {site_name}", f"{site_name} 오류")):
                rag_db_python_format[(actual_company, actual_title)] = actual_data
                print(
                    f"  -> {site_name} 정보 저장 완료: {actual_company} - {actual_title}"
                )
            else:
                print(
                    f"  !!! {site_name} 최종 회사/직무명 미확정. DB 저장 건너뜀. (URL: {driver.current_url})"
                )
            collected_jobs_count += 1
            time.sleep(1)  # 각 상세 페이지 처리 후 약간의 대기

    except Exception as e_main:
        print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if "driver" in locals() and driver:
            print(f"{site_name} 드라이버 종료 중...")
            driver.quit()

    print(
        f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)"
    )
    return rag_db_python_format


# --- 스캐터랩(Scatter Lab) 스크래핑 함수 ---
def scrape_scatterlab_jobs_to_rag_format(max_jobs_to_fetch_details=300):
    site_name = "스캐터랩"
    base_url_for_site = "https://www.scatterlab.co.kr"  # 상대 URL 조립 시 사용

    # 사용자 제공 URL (이 페이지의 모든 공고 확인)
    list_url = "https://www.scatterlab.co.kr/ko/recruiting?"

    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0  # 함수 내에서 초기화

    print(
        f"{site_name} 채용 목록 크롤링 시작: {list_url} (최대 공고 {max_jobs_to_fetch_details}개 목표)"
    )

    try:
        driver.get(list_url)
        time.sleep(2)  # 페이지 초기 로딩 대기

        list_container_selector = "ul.sc-9b56f69e-0.ffGmZN"
        job_item_anchor_selector = f"{list_container_selector} > a"

        try:
            print(f"  공고 카드(a 태그)({job_item_anchor_selector}) 대기 중...")
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, job_item_anchor_selector)
                )
            )
            print(f"  공고 카드(a 태그)({job_item_anchor_selector}) 발견됨.")
        except Exception as e_wait:
            print(
                f"  {site_name} URL({list_url})에서 공고 카드({job_item_anchor_selector}) 기다리는 중 오류: {e_wait}"
            )
            print(
                f"  '{job_item_anchor_selector}' 선택자가 정확한지, 해당 페이지에 공고가 있는지 확인해주세요."
            )
            driver.quit()
            return {}

        all_cards_on_page = driver.find_elements(
            By.CSS_SELECTOR, job_item_anchor_selector
        )
        num_cards_on_this_page = len(all_cards_on_page)
        print(
            f"  {site_name} URL({list_url})에서 {num_cards_on_this_page}개의 공고 카드(a 태그)를 찾았습니다."
        )

        if num_cards_on_this_page == 0:
            print(f"  해당 페이지에 공고 카드가 없습니다.")
            driver.quit()
            return {}

        jobs_to_process = min(num_cards_on_this_page, max_jobs_to_fetch_details)

        # 상세 페이지 URL들을 먼저 수집 (페이지 이동으로 인한 StaleElement 방지)
        detail_page_links_info = []
        for i in range(jobs_to_process):
            card_el_anchor = all_cards_on_page[i]

            # 목록 페이지의 힌트용 회사명/직무명 (기본값)
            list_page_title_hint = f"N/A {site_name} 직무 (카드{i+1})"
            list_page_company_hint = "스캐터랩"

            try:
                # 스캐터랩 목록 카드(a 태그) 내에서 임시 직무명 추출
                try:
                    title_el = card_el_anchor.find_element(
                        By.CSS_SELECTOR, "div.sc-9b56f69e-3"
                    )  # 예시 선택자
                    if title_el:
                        list_page_title_hint = title_el.text.strip()
                except:
                    print(f"    {site_name} 카드 No.{i+1} 임시 제목 추출 실패")
                try:
                    company_el_hint = card_el_anchor.find_element(
                        By.CSS_SELECTOR, "div.sc-9b56f69e-2"
                    )  # 예시 선택자 (팀이름)
                    if company_el_hint:
                        list_page_company_hint = f"스캐터랩 ({company_el_hint.text.strip()})"  # 팀이름을 회사 힌트에 포함
                except:
                    pass  # 실패해도 기본 "스캐터랩" 유지

            except Exception as e_hint:
                print(f"    {site_name} 카드 No.{i+1} 힌트 정보 추출 중 오류: {e_hint}")

            detail_page_relative_url = card_el_anchor.get_attribute("href")
            if detail_page_relative_url:
                from urllib.parse import urljoin

                detail_page_full_url = urljoin(
                    base_url_for_site, detail_page_relative_url
                )
                detail_page_links_info.append(
                    {
                        "url": detail_page_full_url,
                        "title_hint": list_page_title_hint,
                        "company_hint": list_page_company_hint,
                    }
                )
            else:
                print(
                    f"    {site_name} 카드 No.{i+1} 상세 링크 href 속성을 찾지 못했습니다."
                )

        # 수집된 링크들을 순회하며 상세 정보 추출
        for job_info in detail_page_links_info:
            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(
                    f"    전체 목표 공고 수({max_jobs_to_fetch_details}개) 도달. 상세 정보 추출 중단."
                )
                break

            print(f"\n  다음 공고 상세 정보 추출: {job_info['url']}")
            print(
                f"    목록 정보 (힌트용): {job_info['company_hint']} - {job_info['title_hint']}"
            )
            driver.get(job_info["url"])

            expected_url_pattern = "/ko/o/"
            WebDriverWait(driver, 15).until(EC.url_contains(expected_url_pattern))
            print(f"    -> 새 URL로 이동됨: {driver.current_url}")

            # LLM 사용하는 함수 호출
            extraction_result = extract_details_with_llm(
                driver, site_name, list_page_company_hint, list_page_title_hint
            )
            if extraction_result == {}:
                continue
            actual_data, actual_company, actual_title = (
                extraction_result["data"],
                extraction_result["company"],
                extraction_result["title"],
            )

            # 최종 키는 LLM이 확정한 값 또는 힌트/기본값
            if not actual_company.startswith(
                (f"N/A {site_name}", f"{site_name} 오류")
            ) and not actual_title.startswith((f"N/A {site_name}", f"{site_name} 오류")):
                rag_db_python_format[(actual_company, actual_title)] = actual_data
                print(
                    f"  -> {site_name} 정보 저장 완료: {actual_company} - {actual_title}"
                )
            else:
                print(
                    f"  !!! {site_name} 최종 회사/직무명 미확정. DB 저장 건너뜀. (URL: {driver.current_url})"
                )
            collected_jobs_count += 1
            time.sleep(1)  # 각 상세 페이지 처리 후 약간의 대기

    except Exception as e_main:
        print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if "driver" in locals() and driver:
            print(f"{site_name} 드라이버 종료 중...")
            driver.quit()

    print(
        f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)"
    )
    return rag_db_python_format


# --- __main__ 블록: 데이터 통합 및 JSON 저장 ---
if __name__ == "__main__":
    try:
        configure_gemini()
    except ValueError as e:
        print(
            f"초기 Gemini API 설정 오류: {e}. 스크립트를 계속 진행하지만 LLM 호출은 실패합니다."
        )
        sys.exit()

    # 테스트하고 싶은 사이트의 함수 호출만 주석 해제합니다.
    # 예: 하나의 사이트만 테스트하려면 max_jobs_to_fetch_details=1 로 설정

    all_sites_data = {}  # 모든 사이트 결과를 합칠 딕셔너리

    MAX_JOBS_TO_FETCH_DETAILS = 100
    MAX_PAGES_TO_CRAWL = 100
    # 네이버
    print("===== 네이버 채용 정보 수집 시작 =====")
    naver_data = scrape_naver_jobs_to_rag_format(
        max_jobs_to_fetch_details=MAX_JOBS_TO_FETCH_DETAILS
    )
    if naver_data:
        all_sites_data.update(naver_data)
    print("===== 네이버 채용 정보 수집 완료 =====")

    # 카카오
    print("\n===== 카카오 채용 정보 수집 시작 =====")
    kakao_data = scrape_kakao_jobs_to_rag_format(
        max_jobs_to_fetch_details=MAX_JOBS_TO_FETCH_DETAILS
    )
    if kakao_data:
        all_sites_data.update(kakao_data)
    print("===== 카카오 채용 정보 수집 완료 =====")

    # 라인
    print("\n===== 라인 채용 정보 수집 시작 =====")
    line_data = scrape_line_jobs_to_rag_format(
        max_jobs_to_fetch_details=MAX_JOBS_TO_FETCH_DETAILS
    )
    if line_data:
        all_sites_data.update(line_data)
    print("===== 라인 채용 정보 수집 완료 =====")

    # 쿠팡
    print("\n===== 쿠팡 채용 정보 수집 시작 =====")
    coupang_data = scrape_coupang_jobs_to_rag_format(
        max_jobs_to_fetch_details=MAX_JOBS_TO_FETCH_DETAILS,
        max_pages_to_crawl=MAX_PAGES_TO_CRAWL,
    )
    if coupang_data:
        all_sites_data.update(coupang_data)
    print("===== 쿠팡 채용 정보 수집 완료 =====")

    # 배민
    print("\n===== 배민 채용 정보 수집 시작 =====")
    baemin_data = scrape_baemin_jobs_to_rag_format(
        max_jobs_to_fetch_details=MAX_JOBS_TO_FETCH_DETAILS,
        max_pages_to_crawl=MAX_PAGES_TO_CRAWL,
    )
    if baemin_data:
        all_sites_data.update(baemin_data)
    print("===== 배민 채용 정보 수집 완료 =====")

    # 당근
    print("\n===== 당근 채용 정보 수집 시작 =====")
    daangn_data = scrape_daangn_jobs_to_rag_format(
        max_jobs_to_fetch_details=MAX_JOBS_TO_FETCH_DETAILS
    )
    if daangn_data:
        all_sites_data.update(daangn_data)
    print("===== 당근 채용 정보 수집 완료 =====")

    # 토스
    print("\n===== 토스 채용 정보 수집 시작 =====")
    toss_data = scrape_toss_jobs_to_rag_format(
        max_jobs_to_fetch_details=MAX_JOBS_TO_FETCH_DETAILS
    )
    if toss_data:
        all_sites_data.update(toss_data)
    print("===== 토스 채용 정보 수집 완료 =====")

    # 라이너
    print("\n===== 라이너 채용 정보 수집 시작 =====")
    liner_data = scrape_liner_jobs_to_rag_format(
        max_jobs_to_fetch_details=MAX_JOBS_TO_FETCH_DETAILS
    )
    if liner_data:
        all_sites_data.update(liner_data)
    print("===== 라이너 채용 정보 수집 완료 =====")

    # 스캐터랩
    print("\n===== 스캐터랩 채용 정보 수집 시작 =====")
    scatterlab_data = scrape_scatterlab_jobs_to_rag_format(
        max_jobs_to_fetch_details=MAX_JOBS_TO_FETCH_DETAILS
    )
    if scatterlab_data:
        all_sites_data.update(scatterlab_data)
    print("===== 스캐터랩 채용 정보 수집 완료 =====")

    print(f"\n총 {len(all_sites_data)}개의 공고 정보가 통합되었습니다.")

    if all_sites_data:
        json_output_string_tuple_keys = {}
        for python_tuple_key, data_details_dict in all_sites_data.items():
            string_key = str(python_tuple_key)
            json_output_string_tuple_keys[string_key] = data_details_dict

        json_file_name = "collected_jobs_llm_analyzed.json"  # 파일명 변경
        try:
            with open(json_file_name, "w", encoding="utf-8") as f:
                json.dump(
                    json_output_string_tuple_keys, f, ensure_ascii=False, indent=4
                )
            print(
                f"\n모든 사이트의 통합 데이터가 '{json_file_name}' 파일로 성공적으로 저장되었습니다."
            )
        except Exception as e:
            print(f"\nJSON 파일 저장 중 오류 발생: {e}")

        print("\n--- 수집된 데이터 (LLM 분석 결과 포함) ---")
        for (company, job_title), data_dict in all_sites_data.items():
            print(
                f"\n--- 회사: {company}, 직무: {job_title} ---"
            )  # LLM 또는 힌트 기반 최종값
            print(
                f"  [채용공고 본문 (Trafilatura)]:\n{(data_dict.get('job_posting', '') or '')[:100]}..."
            )
            print(f"  [기술스택 (LLM)]:\n{data_dict.get('tech_stack', '정보 없음')}")
            print(f"  [인재상 (LLM)]:\n{data_dict.get('hiring_values', '정보 없음')}")
            print(
                f"  [회사소개 (LLM)]:\n{data_dict.get('company_overview', '정보 없음')}"
            )
    else:
        print("\n수집된 전체 데이터가 없습니다.")
