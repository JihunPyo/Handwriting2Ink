#아래와 같은 구조로 서비스를 개발하라. 이 구조에 위반하는 구현은 절대 해서는 안됨.
[iPad 앱]
이미지 선택
→ FastAPI 서버에 업로드
→ job 상태 조회
→ 최종 GoodNotes binary 다운로드
→ UIPasteboard에 기록

[Railway 서버]
이미지 수신
→ job 생성
→ OCR layout 실행
→ stroke extraction 실행
→ strokes.json 생성
→ Mac 워커에게 작업 제공
→ Mac 워커가 보낸 binary 저장
→ iPad 앱에 binary 전달

[Mac GUI 워커]
서버에서 stroke_ready job 조회
→ strokes.json 다운로드
→ GoodNotes에 실제 stroke 재생
→ 올가미 복사
→ pasteboard binary 추출
→ 서버에 binary 업로드