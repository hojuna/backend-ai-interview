# backend-ai-interview

## Start Guide
### Installization
pip install -r .\requirements.txt
~~root\reports\
~~json file check

### Run
uvicorn app.main:app --reload

# 🧊 Duri-Intern
> **자소서 + 지원 기업 + 직무**를 입력하면,  
> 실제 면접처럼 질문하고 피드백해주는 **기술면접 특화 AI 시뮬레이터** 👩🏻‍💻

![image](https://github.com/arieum/Computer-Networking_A-Top-Down-Approach/blob/main/Duri-InTern.png)

<br>

## 📍 프로젝트 소개
**Duri-Intern**은 지원자가 입력한 직무, 기업, 자소서 내용을 기반으로, <br />
실제 면접처럼 질문하고 답변을 평가하는 **기술면접 특화 AI 시뮬레이터**입니다. <br/> 
사용자 맞춤형 질문 생성, 꼬리질문, 정량·정성 평가, 리포트 자동화까지 지원하여,
**기술면접에 필요한 실질적인 준비를 돕는 차별화된 AI 플랫폼**입니다.

## 🚀 주요 기능

### 🎯 1. 사용자 기반 맞춤 면접 세팅
- 지원 직무, 기업명, 자소서 내용을 바탕으로 면접 환경 자동 구성
- 입력 정보 기반 **가상의 면접관 페르소나 생성**

### 🧠 2. 기술면접 질문 자동 생성
- 기업 문화와 직무를 반영한 맞춤형 질문 생성
- 블로그/채용공고 크롤링 데이터 기반 실전형 질문

### 💬 3. 시뮬레이션 대화 인터뷰
- 면접관과 실시간 대화 형식
- 답변 → 꼬리질문 → 다음 질문까지 자연스러운 면접 흐름

### 📊 4. 답변 평가 및 피드백
- 6개 항목 기반 LLM 평가 (정량 + 간단 텍스트 피드백)
- 기술면접에 특화된 평가 기준 반영

### 📄 5. 리포트 자동 생성
- 점수화 + 피드백 시각화
- PDF 다운로드 및 학습 이력 저장 가능
<br/>

## 🛠 기술 스택

| 구분           | 사용 기술 |
|----------------|-----------|
| 프론트엔드     | Vite + React |
| 백엔드         | FastAPI, Gemini API, LangChain |
| 데이터 처리     | Python 크롤링 (Velog, Tistory, 사람인) |
<br/>

## 📌 페이지별 기능 소개
| 홈 화면 | 인터뷰 입력 화면 | 
|:---:|:---:|
| <img src="https://github.com/user-attachments/assets/0329d8b7-0301-42cd-9854-20b7e94dd447" width="600px"> | <img src="https://github.com/user-attachments/assets/4125b9ce-2871-42b3-afc5-861e83e49f86" width="600px"> |
| 서비스 소개 및 주요 기능을 <br /> 한눈에 보여주는 랜딩 페이지 | 	지원 기업, 직무, 자소서를 입력해 <br/>맞춤형 면접을 시작하는 단계 |

| 인터뷰 진행 화면 | 인터뷰 결과 화면 |
|:---:|:---:|
| <img src="https://github.com/user-attachments/assets/9b8f39c8-594a-45a5-ad22-3b5c6aa9c2ed" width="600px"> | <img src="https://github.com/user-attachments/assets/8e8bb33e-ad59-4f29-b0c1-0a4e5305e507" width="600px"> |
| 가상의 면접관과 실시간으로 <br/>기술면접을 진행하는 시뮬레이터 | 면접 평가 결과를 점수 및 피드백 형태로 제공하며, <br/> PDF 저장 가능 |

<br/>

## 🔍 프로젝트 정보
### 개발 기간
- 2025.04 ~ 2025.06 (2개월)
  
### 프로젝트 관리
- **[Fronted Repository](https://github.com/knupp7/react-ai-interview)**
- **[Backend Repository](https://github.com/knupp7/backend-ai-interview)**

<br/>

## 👥 버그처리반 팀원 소개
저희 팀은 **프론트 2명, 백엔드 2명**으로 구성되어 있습니다.

<table align="center">
 <tr align="center">
     <td><B>최건우<B></td>
     <td><B>이아림<B></td>
     <td><B>이상엽<B></td>
     <td><B>이호준<B></td>
 </tr>
 <tr align="center">
     <td>
         <a href="https://github.com/rjsdn031">
          <img src="https://github.com/rjsdn031.png" style="max-width: 100px">
         </a>
         <br>
         <a href="https://github.com/rjsdn031"><B>Fronted</B></a>
     </td>
     <td>
         <a href="https://github.com/arieum">
         <img src="https://github.com/arieum.png" style="max-width: 100px">
         </a>
         <br>
         <a href="https://github.com/arieum"><B>Fronted</B></a>
     </td>
     <td>
         <a href="https://github.com/Potass5ium">
         <img src="https://github.com/Potass5ium.png" style="max-width: 100px">
         </a>
         <br>
         <a href="https://github.com/Potass5ium"><B>Backend</B></a>
     </td>
     <td>
         <a href="https://github.com/hojuna">
         <img src="https://github.com/hojuna.png" style="max-width: 100px">
         </a>
         <br>
         <a href="https://github.com/hojuna4"><B>Backed</B></a>
     </td>
 </tr>
</table>

<br/>
