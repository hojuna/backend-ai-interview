import time
# import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import trafilatura
import json
# (LLM 관련 import는 현재 주석 처리 상태 유지)

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("lang=ko_KR")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

# --- 공통 상세 정보 추출 함수 ---
def extract_job_details_for_text_check(driver, site_name, list_page_company_hint="", list_page_title_hint=""):
    current_url = driver.current_url
    actual_job_title = list_page_title_hint if list_page_title_hint and "N/A" not in list_page_title_hint else f"N/A {site_name} 직무 (목록힌트없음)"
    actual_company_name = list_page_company_hint if list_page_company_hint and "N/A" not in list_page_company_hint else f"N/A {site_name} 회사 (목록힌트없음)"
    print(f"  -> {site_name} 상세 정보 텍스트 추출 테스트 중: {current_url} (힌트: {actual_company_name} - {actual_job_title})")

    job_posting_text_trafilatura = f"{site_name} Trafilatura 내용 추출 실패."
    tech_stack_str = f"{site_name} 기술 스택 (LLM 분석 예정)"
    hiring_values_str = f"{site_name} 인재상/문화 (LLM 분석 예정)"
    company_overview_str = f"{actual_company_name} 개요 (LLM 분석 예정)" 
    other_details_str = ""
    sample_interview_questions = ["채용 공고에서 직접 제공되지 않음. 외부 자료 참고 필요."]

    try:
        detail_page_main_container_selector = "body" 
        if site_name == "네이버":
            detail_page_main_container_selector = "div.detail_wrap" 
        elif site_name == "카카오":
            detail_page_main_container_selector = "div.area_cont" 
        elif site_name == "라인":
            detail_page_main_container_selector = "div.content_inner"
        elif site_name == "쿠팡":
            detail_page_main_container_selector = "div.main-col"
        
        print(f"    {site_name}: WebDriverWait 대기 시작 (선택자: {detail_page_main_container_selector})")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, detail_page_main_container_selector)))
        print(f"    {site_name}: WebDriverWait 통과 (선택자: {detail_page_main_container_selector})")
        time.sleep(1.5) 

        html_content = driver.page_source
        
        job_posting_text_trafilatura = trafilatura.extract(html_content,
                                                           include_comments=False, include_tables=True, favor_recall=True)
        if not job_posting_text_trafilatura:
            job_posting_text_trafilatura = f"{site_name} Trafilatura 본문 내용 추출 실패."
            detail_soup_fallback = BeautifulSoup(html_content, "html.parser")
            body_element = detail_soup_fallback.find("body")
            if body_element:
                job_posting_text_trafilatura = body_element.get_text(separator='\n', strip=True)
        
        company_overview_str = f"{actual_company_name} 개요 (LLM 분석 예정)"

        print(f"    {site_name} 사용 정보 (목록 힌트): 회사='{actual_company_name}', 직무='{actual_job_title}'")
        print(f"    {site_name} Trafilatura 추출 내용 (일부): {(job_posting_text_trafilatura or '')[:100]}...")

        return {
            "data": {"job_posting": job_posting_text_trafilatura, "hiring_values": hiring_values_str,
                     "tech_stack": tech_stack_str, "sample_interview_questions": sample_interview_questions,
                     "company_overview": company_overview_str, "other_details": other_details_str },
            "title": actual_job_title, 
            "company": actual_company_name 
        }
    except Exception as e:
        print(f"    {site_name} 상세 정보 텍스트 추출 중 오류 ({current_url}): {type(e).__name__} - {e}")
        return {"data": {"job_posting": f"오류: {e}", "hiring_values": "N/A", "tech_stack": "N/A", 
                         "sample_interview_questions": ["N/A"], "company_overview": "N/A", "other_details": ""},
                "title": list_page_title_hint if list_page_title_hint and "N/A" not in list_page_title_hint else f"{site_name} 오류 직무", 
                "company": list_page_company_hint if list_page_company_hint and "N/A" not in list_page_company_hint else f"{site_name} 오류 회사"}

# --- 네이버 스크래핑 함수 ---
def scrape_naver_jobs_to_rag_format(max_jobs_to_fetch_details=300):
    site_name = "네이버"
    list_url = "https://recruit.navercorp.com/rcrt/list.do?subJobCdArr=1010001%2C1010002%2C1010003%2C1010004%2C1010005%2C1010006%2C1010007%2C1010009%2C1010020&sysCompanyCdArr=&empTypeCdArr=&entTypeCdArr=&workAreaCdArr=&sw=&subJobCdData=1010001&subJobCdData=1010002&subJobCdData=1010003&subJobCdData=1010004&subJobCdData=1010005&subJobCdData=1010006&subJobCdData=1010007&subJobCdData=1010009&subJobCdData=1010020"
    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0 # 함수 내에서 초기화
    print(f"{site_name} 채용 목록 크롤링 시작: {list_url}")
    try:
        driver.get(list_url)
        list_container_selector = "ul.card_list"
        job_card_item_selector = f"{list_container_selector} > li.card_item"
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, list_container_selector)))
        num_total_cards = len(driver.find_elements(By.CSS_SELECTOR, job_card_item_selector))
        print(f"총 {num_total_cards}개의 {site_name} 공고 카드를 찾았습니다.")
        if num_total_cards == 0: driver.quit(); return {}
        jobs_to_process = min(num_total_cards, max_jobs_to_fetch_details)

        for i in range(jobs_to_process):
            # 페이지네이션이 없으므로 "페이지X-" 부분은 생략하고 카드 인덱스만 사용
            hint_title_naver = f"N/A {site_name} 직무 (카드{i+1})" 
            hint_company_naver = f"N/A {site_name} 회사 (카드{i+1})"
            print(f"\n{i+1}/{jobs_to_process}번째 {site_name} 공고 처리 중...")
            WebDriverWait(driver,10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, job_card_item_selector)))
            all_cards = driver.find_elements(By.CSS_SELECTOR, job_card_item_selector)
            if i >= len(all_cards): break
            card_el = all_cards[i]
            try:
                card_html_temp = card_el.get_attribute('outerHTML')
                card_soup_temp = BeautifulSoup(card_html_temp, 'html.parser')
                title_box_in_list = card_soup_temp.select_one('div.card_title_box')
                if title_box_in_list: 
                    info_el_list = title_box_in_list.select('dl.card_info > dd.info_text')
                    if len(info_el_list) > 0: hint_company_naver = info_el_list[0].text.strip()
                    if len(info_el_list) > 2: hint_title_naver = info_el_list[2].text.strip()
                else: 
                    title_tag_temp = card_soup_temp.select_one('div.card_body > h4.card_title') 
                    if title_tag_temp: hint_title_naver = title_tag_temp.text.strip()
                    comp_tag_temp = card_soup_temp.select_one('div.card_body > span.card_company')
                    if comp_tag_temp: hint_company_naver = comp_tag_temp.text.strip()
                print(f"  목록 정보 (힌트용): {hint_company_naver} - {hint_title_naver}")
                
                link_el = card_el.find_element(By.CSS_SELECTOR, "a.card_link") 
                driver.execute_script("arguments[0].scrollIntoViewIfNeeded(true);", link_el)
                time.sleep(0.5)
                print(f"  -> '{hint_title_naver}' 상세 보기 링크 클릭 시도...")
                link_el.click()
                WebDriverWait(driver,15).until(EC.url_contains("/rcrt/view.do"))
                
                extraction_result = extract_job_details_for_text_check(driver, site_name, 
                                                                       list_page_company_hint=hint_company_naver, 
                                                                       list_page_title_hint=hint_title_naver)
                actual_data, actual_company, actual_title = extraction_result['data'], extraction_result['company'], extraction_result['title']
                
                # 모든 사이트 N/A도 저장
                rag_db_python_format[(actual_company, actual_title)] = actual_data
                if actual_company.startswith(f"N/A {site_name}") or actual_title.startswith(f"N/A {site_name}"):
                    print(f"    -> {site_name} 본문 임시 저장 (N/A 또는 일부 N/A 키 사용): {actual_company} - {actual_title}")
                else:
                    print(f"    -> {site_name} 본문 저장 완료 (키: {actual_company} - {actual_title}")
                collected_jobs_count += 1
                
                print(f"  -> {site_name} 목록 페이지로 돌아갑니다...")
                driver.back()
                WebDriverWait(driver,10).until(EC.presence_of_element_located((By.CSS_SELECTOR, list_container_selector)))
                print(f"  -> {site_name} 목록 페이지 로드 확인.")
                time.sleep(1)
            except Exception as e_card:
                print(f"  {site_name} 카드 '{hint_title_naver}' 처리 중 오류: {e_card}")
                if list_url not in driver.current_url: 
                    try: driver.get(list_url); WebDriverWait(driver,10).until(EC.presence_of_element_located((By.CSS_SELECTOR, list_container_selector))) 
                    except: print(f"     {site_name} 목록 페이지 강제 이동 실패.")
                time.sleep(2)
    except Exception as e_main: print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if 'driver' in locals() and driver: driver.quit()
    print(f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)")
    return rag_db_python_format

# --- 카카오 스크래핑 함수 ---
def scrape_kakao_jobs_to_rag_format(max_jobs_to_fetch_details=300):
    # (네이버와 동일한 저장 로직 적용)
    list_url = "https://careers.kakao.com/jobs?skillSet=Android%2CiOS%2CWindows%2CWeb_front%2CCloud%2CDB%2CNetwork%2CAlgorithm_ML%2CStatistics_Analysis%2CServer&part=TECHNOLOGY&company=KAKAO&keyword=&employeeType=&page=1" # 현재는 page=1만
    driver = setup_driver()
    rag_db_python_format = {}
    site_name = "카카오"
    collected_jobs_count = 0 # 함수 내에서 초기화
    print(f"{site_name} 채용 목록 크롤링 시작: {list_url}")
    try:
        driver.get(list_url)
        list_container_selector = "ul.list_jobs"
        job_item_selector = f"{list_container_selector} > a" 

        try: WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, job_item_selector)))
        except Exception as e_wait: print(f"{site_name} 공고 카드({job_item_selector}) 기다리는 중 오류: {e_wait}"); driver.quit(); return {}
        
        num_total_cards = len(driver.find_elements(By.CSS_SELECTOR, job_item_selector))
        print(f"총 {num_total_cards}개의 {site_name} 공고 카드({job_item_selector})를 찾았습니다.")
        if num_total_cards == 0: driver.quit(); return {}
        jobs_to_process = min(num_total_cards, max_jobs_to_fetch_details)

        for i in range(jobs_to_process):
            hint_title_kakao = f"N/A {site_name} 직무 (카드{i+1})"
            hint_company_kakao = f"N/A {site_name} 회사 (카드{i+1})"
            print(f"\n{i+1}/{jobs_to_process}번째 {site_name} 공고 처리 중...")
            WebDriverWait(driver,10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, job_item_selector)))
            all_cards = driver.find_elements(By.CSS_SELECTOR, job_item_selector)
            if i >= len(all_cards): break
            card_el_anchor = all_cards[i]
            try:
                try:
                    title_sel = "span.link_tag.cursor_hand.false" 
                    title_tag = card_el_anchor.find_element(By.CSS_SELECTOR, title_sel)
                    if title_tag: hint_title_kakao = title_tag.text.strip()
                except:
                    try: title_tag_alt = card_el_anchor.find_element(By.CSS_SELECTOR, "strong.tit_job"); hint_title_kakao = title_tag_alt.text.strip()
                    except: print(f"    {site_name} 카드 No.{i+1} 임시 제목 추출 실패")
                try:
                    company_sel = "dl.item_subinfo:first-of-type dd"
                    company_tag = card_el_anchor.find_element(By.CSS_SELECTOR, company_sel)
                    if company_tag: hint_company_kakao = company_tag.text.strip()
                except:
                    try: company_tag_alt = card_el_anchor.find_element(By.CSS_SELECTOR, "span.txt_info"); hint_company_kakao = company_tag_alt.text.split("·")[0].strip()
                    except: print(f"    {site_name} 카드 No.{i+1} 임시 회사명 추출 실패")
                print(f"  목록 정보 (힌트용): {hint_company_kakao} - {hint_title_kakao}")

                link_el_to_click = card_el_anchor 
                driver.execute_script("arguments[0].scrollIntoViewIfNeeded(true);", link_el_to_click)
                time.sleep(0.5)
                print(f"  -> '{hint_title_kakao}' 상세 보기 링크 클릭 시도...")
                link_el_to_click.click()
                WebDriverWait(driver,15).until(EC.url_contains("/jobs/"))

                extraction_result = extract_job_details_for_text_check(driver, site_name, 
                                                                        list_page_company_hint=hint_company_kakao, 
                                                                        list_page_title_hint=hint_title_kakao)
                actual_data, actual_company, actual_title = extraction_result['data'], extraction_result['company'], extraction_result['title']
                
                # 모든 사이트 N/A도 저장
                rag_db_python_format[(actual_company, actual_title)] = actual_data
                if actual_company.startswith(f"N/A {site_name}") or actual_title.startswith(f"N/A {site_name}"):
                    print(f"    -> {site_name} 본문 임시 저장 (N/A 또는 일부 N/A 키 사용): {actual_company} - {actual_title}")
                else:
                    print(f"    -> {site_name} 본문 저장 완료 (키: {actual_company} - {actual_title}")
                collected_jobs_count += 1
                
                print(f"  -> {site_name} 목록 페이지로 돌아갑니다...")
                driver.back()
                WebDriverWait(driver,10).until(EC.presence_of_element_located((By.CSS_SELECTOR, list_container_selector)))
                print(f"  -> {site_name} 목록 페이지 로드 확인.")
                time.sleep(1)
            except Exception as e_card:
                print(f"  {site_name} 카드 '{hint_title_kakao}' 처리 중 오류: {e_card}")
                if list_url not in driver.current_url:
                    try: driver.get(list_url); WebDriverWait(driver,10).until(EC.presence_of_element_located((By.CSS_SELECTOR, list_container_selector)))
                    except: print(f"     {site_name} 목록 페이지 강제 이동 실패.")
                time.sleep(2)
    except Exception as e_main: print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if 'driver' in locals() and driver: driver.quit()
    print(f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)")
    return rag_db_python_format

# --- 라인 스크래핑 함수 ---
def scrape_line_jobs_to_rag_format(max_jobs_to_fetch_details=300):
    # (네이버와 동일한 저장 로직 적용)
    site_name = "라인"
    list_url = "https://careers.linecorp.com/ko/jobs?ca=Engineering&fi=Client-side,Web%20Development,Server-side,Data%20Engineering,Tech%20Management,Analytics" # 현재는 page=1만
    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0 # 함수 내에서 초기화
    print(f"{site_name} 채용 목록 크롤링 시작: {list_url}")
    try:
        driver.get(list_url)
        list_container_selector = "ul.job_list" 
        job_card_item_selector = f"{list_container_selector} > li" 
        
        try: WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, job_card_item_selector)))
        except Exception as e_wait: print(f"{site_name} 공고 카드({job_card_item_selector}) 기다리는 중 오류: {e_wait}"); driver.quit(); return {}

        num_total_cards = len(driver.find_elements(By.CSS_SELECTOR, job_card_item_selector))
        print(f"총 {num_total_cards}개의 {site_name} 공고 카드를 찾았습니다.")
        if num_total_cards == 0: driver.quit(); return {}
        jobs_to_process = min(num_total_cards, max_jobs_to_fetch_details)

        for i in range(jobs_to_process):
            hint_title_line = f"N/A {site_name} 직무 (카드{i+1})" 
            hint_company_line = f"N/A {site_name} 회사 (카드{i+1})" 
            print(f"\n{i+1}/{jobs_to_process}번째 {site_name} 공고 처리 중...")
            WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, job_card_item_selector)))
            all_cards = driver.find_elements(By.CSS_SELECTOR, job_card_item_selector)
            if i >= len(all_cards): break
            card_el_li = all_cards[i]
            try:
                # 라인 목록 카드에서 임시 회사명/직무명 추출 (힌트용) - 실제 라인 선택자로 변경 필요
                # try:
                #     title_tag = card_el_li.find_element(By.CSS_SELECTOR, "YOUR_LINE_LIST_TITLE_SELECTOR") 
                #     if title_tag: hint_title_line = title_tag.text.strip()
                # except: print(f"    {site_name} 카드 No.{i+1} 임시 제목 추출 실패")
                # try:
                #     company_tag = card_el_li.find_element(By.CSS_SELECTOR, "YOUR_LINE_LIST_COMPANY_SELECTOR")
                #     if company_tag: hint_company_line = company_tag.text.strip()
                # except: print(f"    {site_name} 카드 No.{i+1} 임시 회사명 추출 실패")
                print(f"  목록 정보 (힌트용): {hint_company_line} - {hint_title_line}")

                link_el_to_click = card_el_li.find_element(By.CSS_SELECTOR, "a") 
                driver.execute_script("arguments[0].scrollIntoViewIfNeeded(true);", link_el_to_click)
                time.sleep(0.5)
                print(f"  -> '{hint_title_line}' 상세 보기 링크 클릭 시도...")
                link_el_to_click.click()
                
                WebDriverWait(driver,15).until(EC.url_contains("/ko/jobs/")) 
                
                extraction_result = extract_job_details_for_text_check(driver, site_name,
                                                                         list_page_company_hint=hint_company_line,
                                                                         list_page_title_hint=hint_title_line)
                actual_data, actual_company, actual_title = extraction_result['data'], extraction_result['company'], extraction_result['title']
                
                # 모든 사이트 N/A도 저장
                rag_db_python_format[(actual_company, actual_title)] = actual_data
                if actual_company.startswith(f"N/A {site_name}") or actual_title.startswith(f"N/A {site_name}"):
                    print(f"    -> {site_name} 본문 임시 저장 (N/A 또는 일부 N/A 키 사용): {actual_company} - {actual_title}")
                else:
                    print(f"    -> {site_name} 본문 저장 완료 (키: {actual_company} - {actual_title}")
                collected_jobs_count += 1
                
                print(f"  -> {site_name} 목록 페이지로 돌아갑니다...")
                driver.back()
                WebDriverWait(driver,10).until(EC.presence_of_element_located((By.CSS_SELECTOR, list_container_selector)))
                print(f"  -> {site_name} 목록 페이지 로드 확인.")
                time.sleep(1)
            except Exception as e_card:
                print(f"  {site_name} 카드 '{hint_title_line}' 처리 중 오류: {e_card}")
                if list_url not in driver.current_url:
                    try: driver.get(list_url); WebDriverWait(driver,10).until(EC.presence_of_element_located((By.CSS_SELECTOR, list_container_selector)))
                    except: print(f"     {site_name} 목록 페이지 강제 이동 실패.")
                time.sleep(2)
    except Exception as e_main: print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if 'driver' in locals() and driver: driver.quit()
    print(f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)")
    return rag_db_python_format

# --- 쿠팡 스크래핑 함수 ---
def scrape_coupang_jobs_to_rag_format(max_jobs_to_fetch_details=300, max_pages_to_crawl=5): # 페이지네이션 반영
    site_name = "쿠팡"
    base_list_url_cleaned = "https://www.coupang.jobs/kr/jobs/?search=engineer&location=Seoul%2C+South+Korea&pagesize=20"
    
    driver = setup_driver()
    rag_db_python_format = {}
    collected_jobs_count = 0

    print(f"{site_name} 채용 목록 크롤링 시작 (최대 {max_pages_to_crawl} 페이지, 공고 {max_jobs_to_fetch_details}개 목표)")

    try:
        for page_num in range(1, max_pages_to_crawl + 1):
            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(f"  목표 공고 수({max_jobs_to_fetch_details}개)에 도달하여 크롤링을 중단합니다.")
                break

            current_page_url = f"{base_list_url_cleaned}&page={page_num}"
            print(f"\n--- {site_name} 페이지 {page_num} 크롤링 시작: {current_page_url} ---")
            
            driver.get(current_page_url)
            list_container_selector = "div.grid.job-listing" 
            job_card_item_selector = f"{list_container_selector} div.card.card-job" 
            
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, job_card_item_selector))
                )
            except Exception as e_wait:
                print(f"  {site_name} 페이지 {page_num}: 공고 카드({job_card_item_selector})를 찾을 수 없거나 대기 시간 초과: {e_wait}")
                print(f"  페이지 {page_num}에 더 이상 공고가 없거나 선택자가 잘못되었을 수 있습니다. 다음 페이지 시도를 중단합니다.")
                break 

            all_cards_on_page = driver.find_elements(By.CSS_SELECTOR, job_card_item_selector)
            num_cards_on_this_page = len(all_cards_on_page)
            print(f"  {site_name} 페이지 {page_num}: {num_cards_on_this_page}개의 공고 카드를 찾았습니다.")

            if num_cards_on_this_page == 0:
                print(f"  페이지 {page_num}에 공고가 없습니다. 크롤링을 중단합니다.")
                break 

            for i in range(num_cards_on_this_page):
                if collected_jobs_count >= max_jobs_to_fetch_details:
                    print(f"    목표 공고 수({max_jobs_to_fetch_details}개) 도달. 현재 카드 처리 중단.")
                    break 

                current_card_elements_refreshed = driver.find_elements(By.CSS_SELECTOR, job_card_item_selector)
                if i >= len(current_card_elements_refreshed):
                    print(f"    Stale element 참조 방지 또는 인덱스 오류: 인덱스 {i} / 현재 카드 수 {len(current_card_elements_refreshed)}")
                    break 
                card_el = current_card_elements_refreshed[i]

                list_page_title_hint = f"N/A {site_name} 직무 (페이지{page_num}-카드{i+1})"
                list_page_company_hint = f"N/A {site_name} 회사 (페이지{page_num}-카드{i+1})"
                print(f"\n  페이지 {page_num}의 {i+1}/{num_cards_on_this_page}번째 {site_name} 공고 처리 중 ({list_page_title_hint})...")
                
                try:
                    print(f"    목록 정보 (힌트용): {list_page_company_hint} - {list_page_title_hint}")
                    
                    link_el_to_click = None
                    try:
                        link_el_to_click = card_el.find_element(By.CSS_SELECTOR, "a.stretched-link.js-view-job")
                    except:
                        try:
                            link_el_to_click = card_el.find_element(By.CSS_SELECTOR, "div.card-body h2.card-title a")
                        except Exception as e_link_find:
                            print(f"      {site_name} 카드 No.{i+1} 상세 링크 요소를 두 선택자 모두로 찾지 못했습니다: {e_link_find}")
                            continue 

                    driver.execute_script("arguments[0].scrollIntoViewIfNeeded(true);", link_el_to_click)
                    time.sleep(0.5) 
                    
                    print(f"    -> '{list_page_title_hint}' 상세 보기 링크 클릭 시도 (JavaScript 사용)...")
                    driver.execute_script("arguments[0].click();", link_el_to_click)

                    expected_url_pattern = "/kr/jobs/" 
                    WebDriverWait(driver,15).until(EC.url_contains(expected_url_pattern))
                    print(f"    -> 새 URL로 이동됨: {driver.current_url}")
                    
                    extraction_result = extract_job_details_for_text_check(driver, site_name,
                                                                             list_page_company_hint=list_page_company_hint,
                                                                             list_page_title_hint=list_page_title_hint)
                    actual_data, actual_company, actual_title = extraction_result['data'], extraction_result['company'], extraction_result['title']

                    # 모든 사이트 N/A도 저장
                    rag_db_python_format[(actual_company, actual_title)] = actual_data
                    if actual_company.startswith(f"N/A {site_name}") or actual_title.startswith(f"N/A {site_name}"):
                        print(f"    -> {site_name} 본문 임시 저장 (N/A 또는 일부 N/A 키 사용): {actual_company} - {actual_title}")
                    else:
                        print(f"    -> {site_name} 본문 저장 완료 (키: {actual_company} - {actual_title}")
                    collected_jobs_count += 1

                    print(f"    -> {site_name} 목록 페이지({current_page_url})로 돌아갑니다...")
                    driver.get(current_page_url) 
                    
                    WebDriverWait(driver,10).until(EC.presence_of_element_located((By.CSS_SELECTOR, list_container_selector)))
                    print(f"    -> {site_name} 목록 페이지 로드 확인.")
                    time.sleep(1) 
                except Exception as e_card:
                    print(f"    {site_name} 페이지 {page_num}의 카드 '{list_page_title_hint}' 처리 중 오류: {e_card}")
                    if current_page_url not in driver.current_url :
                        print(f"      현재 URL: {driver.current_url}. 목록 페이지({current_page_url})로 강제 이동 시도.")
                        try: 
                            driver.get(current_page_url) 
                            WebDriverWait(driver,10).until(EC.presence_of_element_located((By.CSS_SELECTOR, list_container_selector)))
                        except: print(f"        {site_name} 목록 페이지({page_num}) 강제 이동 실패.")
                    time.sleep(2) 
            
            if collected_jobs_count >= max_jobs_to_fetch_details:
                print(f"  목표 공고 수({max_jobs_to_fetch_details}개) 도달. 다음 페이지 크롤링 중단.")
                break 
        
        print(f"--- {site_name} 페이지 {page_num} 크롤링 완료 ---")
        if page_num < max_pages_to_crawl and collected_jobs_count < max_jobs_to_fetch_details:
             time.sleep(2) 
        else:
            print(f"  모든 지정된 페이지를 크롤링했거나 목표 개수에 도달하여 {site_name} 크롤링을 종료합니다.")

    except Exception as e_main: 
        print(f"{site_name} 전체 크롤링 중 오류: {e_main}")
    finally:
        if 'driver' in locals() and driver: 
            print(f"{site_name} 드라이버 종료 중...")
            driver.quit()
    
    print(f"\n{site_name} 채용 정보 파이썬 딕셔너리 생성 완료 (총 {len(rag_db_python_format)}개)")
    return rag_db_python_format

# --- __main__ 블록 ---
if __name__ == "__main__":
    # 네이버, 카카오, 라인, 쿠팡 순차적 실행
    
    #naver_data = {} 
    #kakao_data = {}
    #line_data = {}
    #coupang_data = {} # 쿠팡 데이터 변수 추가

    # print("===== 네이버 채용 정보 수집 시작 =====")
    naver_data = scrape_naver_jobs_to_rag_format(max_jobs_to_fetch_details=1)
    # print("===== 네이버 채용 정보 수집 완료 =====")

    # print("\n===== 카카오 채용 정보 수집 시작 =====")
    kakao_data = scrape_kakao_jobs_to_rag_format(max_jobs_to_fetch_details=1)
    # print("===== 카카오 채용 정보 수집 완료 =====")

    # print("\n===== 라인 채용 정보 수집 시작 =====")
    line_data = scrape_line_jobs_to_rag_format(max_jobs_to_fetch_details=1) 
    # print("===== 라인 채용 정보 수집 완료 =====")
    
    print("\n===== 쿠팡 채용 정보 수집 시작 =====")
    coupang_data = scrape_coupang_jobs_to_rag_format(max_jobs_to_fetch_details=1, max_pages_to_crawl=1) # 테스트용
    print("===== 쿠팡 채용 정보 수집 완료 =====")
    
    all_sites_python_dict = {}
    if naver_data: all_sites_python_dict.update(naver_data)
    if kakao_data: all_sites_python_dict.update(kakao_data) 
    if line_data: all_sites_python_dict.update(line_data)
    if coupang_data: all_sites_python_dict.update(coupang_data)
            
    print(f"\n총 {len(all_sites_python_dict)}개의 공고 정보가 통합되었습니다.")

    if all_sites_python_dict:
        json_output_string_tuple_keys = {}
        for python_tuple_key, data_details_dict in all_sites_python_dict.items():
            string_key = str(python_tuple_key) 
            json_output_string_tuple_keys[string_key] = data_details_dict
        
        json_file_name = "collected_jobs_text_only_format.json"
        try:
            with open(json_file_name, 'w', encoding='utf-8') as f:
                json.dump(json_output_string_tuple_keys, f, ensure_ascii=False, indent=4)
            print(f"\n모든 사이트의 통합 데이터가 '{json_file_name}' 파일로 성공적으로 저장되었습니다.")
        except Exception as e:
            print(f"\nJSON 파일 저장 중 오류 발생: {e}")
        
        print("\n--- 수집된 데이터 (본문 위주) ---")
        for (company, job_title), data_dict in all_sites_python_dict.items(): 
            print(f"\n--- 회사 (힌트/기본값): {company}, 직무 (힌트/기본값): {job_title} ---")
            print(f"  [채용공고 본문 (Trafilatura)]:\n{(data_dict.get('job_posting', '') or '')[:200]}...\n")
    else:
        print("\n수집된 전체 데이터가 없습니다.")