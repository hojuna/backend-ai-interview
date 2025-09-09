## 서버 실행
# uvicorn app.main:app --reload 

## 테스트 실행
PYTHONPATH=. pytest --log-file=test.log --log-file-level=INFO app/tests/test_sessions.py


## commit test


## stt socket test
python3 -m http.server 8080

#http://localhost:8080/tools/ws_stt_test.html 로 접속