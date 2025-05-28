## 서버 실행
# uvicorn app.main:app --reload 

## 테스트 실행
PYTHONPATH=. pytest --log-file=test.log --log-file-level=INFO app/tests/test_sessions.py