# GoodNotes 필기 복원 iPad 앱 최종 구현 계획서

## 1. 프로젝트 개요

본 프로젝트의 목표는 사용자가 iPad 앱에서 필기 이미지를 업로드하면, 이를 GoodNotes에서 붙여넣을 수 있는 필기 객체로 복원하는 것이다.

최종 사용 흐름은 다음과 같다.

```text
1. 사용자가 iPad 앱에서 필기 이미지 선택
2. iPad 앱이 이미지를 서버에 업로드
3. 서버가 이미지에서 strokes.json 생성
4. Mac 워커가 strokes.json을 받아 GoodNotes에 실제 필기 재생
5. Mac 워커가 GoodNotes에서 올가미 복사 수행
6. Mac 워커가 GoodNotes pasteboard binary 추출
7. 서버가 binary 파일을 iPad 앱에 전달
8. iPad 앱이 binary를 UIPasteboard에 기록
9. 사용자가 GoodNotes에서 붙여넣기
```

본 프로젝트는 웹 클라이언트가 아니라 iPad 네이티브 앱을 사용한다. iPad 앱에서 GoodNotes pasteboard binary를 `UIPasteboard`에 기록하는 실험은 이미 성공한 것으로 본다.

---

## 2. 확정된 전체 아키텍처

```text
[iPad App]
이미지 선택
→ 서버 업로드
→ job 상태 조회
→ GoodNotes binary 다운로드
→ UIPasteboard에 기록

[Render/Railway FastAPI Server]
이미지 수신
→ OCR layout 수행
→ stroke extraction 수행
→ strokes.json 생성
→ job 상태 관리
→ Mac 워커에 strokes.json 제공
→ Mac 워커가 보낸 binary 저장
→ iPad 앱에 binary 제공

[Mac GUI Worker]
서버에서 stroke_ready job 조회
→ strokes.json 다운로드
→ GoodNotes에 stroke 재생
→ 올가미 복사
→ NSPasteboard에서 GoodNotes binary 추출
→ 서버로 binary 업로드
```

최종 데이터 흐름은 다음과 같다.

```text
Image
→ strokes.json
→ GoodNotes drawing
→ GoodNotes lasso copy
→ goodnotes_clipboard_item0.bin
→ iPad UIPasteboard
→ GoodNotes paste
```

---

## 3. 구성요소별 책임

## 3.1 iPad 앱

iPad 앱은 얇은 클라이언트로 유지한다. 이미지 처리나 GoodNotes payload 생성은 앱에서 수행하지 않는다.

### 주요 책임

```text
1. 이미지 선택
2. 서버에 이미지 업로드
3. job_id 수신
4. job 상태 polling
5. 최종 binary 파일 다운로드
6. binary를 UIPasteboard에 기록
7. GoodNotes로 이동하여 붙여넣기 안내
```

### iPad 앱에서 고정할 pasteboard type

```swift
let pasteboardType="com.goodnotesapp.goodnotes5.notes"
```

### iPad 앱 클립보드 기록 방식

```swift
UIPasteboard.general.items=[
    [
        "com.goodnotesapp.goodnotes5.notes": data
    ]
]
```

### iPad 앱 화면 구성

MVP 기준 화면은 다음으로 충분하다.

```text
1. 시작 화면
   - 이미지 선택 버튼

2. 업로드 화면
   - 업로드 진행 표시

3. 처리 대기 화면
   - 서버 처리 중
   - Mac 워커 처리 중
   - GoodNotes binary 생성 중

4. 결과 화면
   - “GoodNotes 클립보드에 복사” 버튼
   - “GoodNotes로 이동해서 붙여넣기 해주세요” 안내
```

### iPad 앱 상태 문구 예시

```text
이미지를 업로드하고 있습니다.
필기 stroke를 추출하고 있습니다.
GoodNotes에서 필기 객체를 생성하고 있습니다.
복원 데이터가 준비되었습니다.
클립보드에 복사되었습니다. GoodNotes에서 붙여넣기 해주세요.
```

---

## 3.2 Render/Railway 서버

서버는 FastAPI 기반으로 구현한다. 서버는 단순 중계가 아니라 이미지 처리와 `strokes.json` 생성을 담당한다.

### 주요 책임

```text
1. 이미지 업로드 수신
2. job 생성
3. 원본 이미지 저장
4. 기존 Python 파이프라인 실행
5. OCR layout 생성
6. stroke extraction 실행
7. strokes.json 저장
8. Mac 워커용 job 제공
9. Mac 워커가 업로드한 GoodNotes binary 저장
10. iPad 앱에 job 상태와 binary 다운로드 제공
```

### 서버에서 수행할 기존 파이프라인

서버는 현재 Python 코드의 다음 흐름을 사용한다.

```text
ocr_layout.py
→ render_strokes.py
→ strokes.json 생성
```

상위 실행은 `pipeline.py`를 기준으로 한다.

MVP에서는 서버가 다음 명령을 내부적으로 실행하는 방식으로 구현한다.

```bash
python pipeline.py \
  --input <uploaded_image_path> \
  --output_dir <job_output_dir> \
  --save_stroke_data
```

생성되어야 하는 핵심 산출물은 다음이다.

```text
original_image
layout_overlay.png
crop_stroke_composite_black.png
crop_stroke_composite_strokes.json
run_meta.json
```

서버는 이 중 `crop_stroke_composite_strokes.json`을 Mac 워커에게 제공한다.

---

## 3.3 Mac GUI 워커

Mac 워커는 이미지 처리 코드를 직접 실행하지 않는다. 서버에서 생성한 `strokes.json`만 받아 GoodNotes 자동화에 집중한다.

### 주요 책임

```text
1. 서버에서 처리 가능한 job polling
2. strokes.json 다운로드
3. GoodNotes 실행 및 포커스 확인
4. 전용 GoodNotes 문서 열기
5. 화면 필기 영역 좌표 확인
6. strokes.json 좌표를 화면 좌표로 변환
7. GoodNotes에 실제 stroke 재생
8. 올가미 도구 선택
9. 전체 필기 선택
10. 복사 실행
11. NSPasteboard에서 GoodNotes binary 추출
12. binary 파일을 서버에 업로드
13. job 완료 보고
```

### Mac 워커 입력

```text
job_id
strokes.json
target_rect 또는 page_rect
pen 설정
```

### Mac 워커 출력

```text
goodnotes_clipboard_item0.bin
pasteboard_type
binary_size
worker_log.json
debug_screenshot.png
```

### GoodNotes pasteboard type

```text
com.goodnotesapp.goodnotes5.notes
```

---

## 4. 배포 및 기술 스택

## 4.1 서버

서버는 Render 또는 Railway 중 하나에 배포한다.

### 권장 서버 스택

```text
Language: Python 3.11+
API Framework: FastAPI
Image Processing: OpenCV, PaddleOCR, scikit-image, numpy
DB: PostgreSQL
File Storage: 초기 MVP는 서버 파일시스템, 이후 S3/R2/Supabase Storage
Queue: 초기 MVP는 DB polling, 이후 Redis queue
Deployment: Render 또는 Railway
```

### MVP에서 Redis를 바로 쓰지 않는 이유

처음에는 Mac 워커가 1대이고, 처리량도 낮을 가능성이 높다. 따라서 복잡한 queue를 먼저 도입하기보다 DB 상태 기반 polling이 더 단순하다.

```text
Mac 워커가 2~3초마다 /worker/jobs/next 호출
→ stroke_ready 상태의 job이 있으면 claim
→ 처리 완료 후 binary 업로드
```

향후 다중 Mac 워커를 운영하게 되면 Redis queue 또는 background worker 구조로 확장한다.

---

## 4.2 iPad 앱

```text
Language: Swift
UI Framework: SwiftUI
Networking: URLSession
Image Picker: PhotosPicker 또는 PHPickerViewController
Clipboard: UIPasteboard
Minimum Target: iPadOS 16 이상 권장
```

---

## 4.3 Mac 워커

MVP는 Python 기반으로 구현한다.

```text
Language: Python
Input Control: pyautogui
Pasteboard Dump: Swift script 또는 macOS CLI
Server Communication: requests
Config: config.json 또는 .env
```

장기적으로는 Swift 기반 macOS 워커로 전환한다.

```text
Language: Swift
UI Automation: Accessibility API
Mouse Input: Quartz CGEvent
Pasteboard: NSPasteboard
Networking: URLSession
Packaging: macOS app 또는 LaunchAgent
```

---

## 5. Job 상태 정의

서버는 모든 작업을 job 단위로 관리한다.

```text
created
→ uploaded
→ extracting_strokes
→ stroke_ready
→ assigned_to_worker
→ drawing_in_goodnotes
→ copying_from_goodnotes
→ uploading_binary
→ bin_ready
→ delivered
→ failed
```

### 상태 설명

| 상태                     | 의미                               |
| ---------------------- | -------------------------------- |
| created                | job 생성 완료                        |
| uploaded               | 이미지 업로드 완료                       |
| extracting_strokes     | 서버에서 OCR 및 stroke 추출 중           |
| stroke_ready           | strokes.json 생성 완료               |
| assigned_to_worker     | Mac 워커가 job을 가져감                 |
| drawing_in_goodnotes   | Mac 워커가 GoodNotes에 stroke 재생 중   |
| copying_from_goodnotes | Mac 워커가 올가미 복사 및 pasteboard 추출 중 |
| uploading_binary       | Mac 워커가 binary 업로드 중             |
| bin_ready              | iPad 앱이 받을 수 있는 binary 준비 완료     |
| delivered              | iPad 앱이 binary를 다운로드함            |
| failed                 | 실패                               |

---

## 6. API 설계

## 6.1 iPad 앱용 API

### 1. 이미지 업로드 및 job 생성

```http
POST /api/jobs
Content-Type: multipart/form-data
```

요청 필드:

```text
file: image/jpeg 또는 image/png
```

응답 예시:

```json
{
  "job_id": "job_20260531_001",
  "status": "uploaded"
}
```

서버는 업로드 직후 stroke extraction을 시작한다.

---

### 2. job 상태 조회

```http
GET /api/jobs/{job_id}
```

응답 예시:

```json
{
  "job_id": "job_20260531_001",
  "status": "bin_ready",
  "message": "GoodNotes 복원 데이터가 준비되었습니다.",
  "binary_ready": true
}
```

---

### 3. binary 다운로드

```http
GET /api/jobs/{job_id}/binary
```

응답:

```text
Content-Type: application/octet-stream
Body: goodnotes_clipboard_item0.bin
```

iPad 앱은 이 응답 body를 `Data`로 읽어 `UIPasteboard`에 기록한다.

---

### 4. delivered 상태 보고

```http
POST /api/jobs/{job_id}/delivered
```

iPad 앱이 binary 다운로드 및 클립보드 기록을 완료했을 때 호출한다.

---

## 6.2 Mac 워커용 API

Mac 워커 API는 반드시 worker token으로 보호한다.

### 1. 다음 job 조회

```http
GET /api/worker/jobs/next
Authorization: Bearer <WORKER_TOKEN>
```

응답 예시:

```json
{
  "job_id": "job_20260531_001",
  "status": "assigned_to_worker",
  "strokes_url": "/api/worker/jobs/job_20260531_001/strokes"
}
```

처리할 job이 없을 때:

```json
{
  "job": null
}
```

---

### 2. strokes.json 다운로드

```http
GET /api/worker/jobs/{job_id}/strokes
Authorization: Bearer <WORKER_TOKEN>
```

응답:

```text
Content-Type: application/json
Body: strokes.json
```

---

### 3. worker 상태 보고

```http
POST /api/worker/jobs/{job_id}/status
Authorization: Bearer <WORKER_TOKEN>
Content-Type: application/json
```

요청 예시:

```json
{
  "status": "drawing_in_goodnotes",
  "message": "GoodNotes에 stroke를 재생하는 중입니다."
}
```

---

### 4. binary 업로드

```http
POST /api/worker/jobs/{job_id}/binary
Authorization: Bearer <WORKER_TOKEN>
Content-Type: multipart/form-data
```

요청 필드:

```text
file: goodnotes_clipboard_item0.bin
pasteboard_type: com.goodnotesapp.goodnotes5.notes
binary_size: number
```

응답 예시:

```json
{
  "job_id": "job_20260531_001",
  "status": "bin_ready"
}
```

---

### 5. 실패 보고

```http
POST /api/worker/jobs/{job_id}/fail
Authorization: Bearer <WORKER_TOKEN>
Content-Type: application/json
```

요청 예시:

```json
{
  "error_code": "PASTEBOARD_TYPE_NOT_FOUND",
  "error_message": "GoodNotes pasteboard type was not found after copy."
}
```

---

## 7. 데이터베이스 설계

## 7.1 jobs 테이블

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    input_filename TEXT,
    input_path TEXT,
    output_dir TEXT,
    strokes_path TEXT,
    binary_path TEXT,
    pasteboard_type TEXT,
    binary_size INTEGER,
    stroke_count INTEGER,
    assigned_worker_id TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

## 7.2 job_events 테이블

```sql
CREATE TABLE job_events (
    id SERIAL PRIMARY KEY,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    created_at TIMESTAMP NOT NULL
);
```

## 7.3 workers 테이블

```sql
CREATE TABLE workers (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    current_job_id TEXT,
    last_heartbeat_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

---

## 8. 서버 디렉토리 구조

권장 서버 구조는 다음과 같다.

```text
server/
  app/
    main.py
    api/
      jobs.py
      worker.py
    services/
      stroke_service.py
      storage_service.py
      job_service.py
    pipeline/
      ocr_layout.py
      render_strokes.py
      skeletonizer.py
      stroke_extractor.py
      simulate_drawing.py
      pipeline.py
    models/
      job.py
      worker.py
    db.py
    config.py
  storage/
    jobs/
      <job_id>/
        input.jpg
        layout_overlay.png
        crop_stroke_composite_black.png
        crop_stroke_composite_strokes.json
        goodnotes_clipboard_item0.bin
        run_meta.json
  requirements.txt
  Dockerfile
```

---

## 9. 서버 처리 흐름

## 9.1 이미지 업로드 후 처리

```text
1. iPad 앱이 POST /api/jobs로 이미지 업로드
2. 서버가 job_id 생성
3. storage/jobs/<job_id>/input.jpg 저장
4. job 상태를 uploaded로 설정
5. 서버가 stroke extraction 실행
6. pipeline.py 실행
7. strokes.json 생성 확인
8. job 상태를 stroke_ready로 설정
9. Mac 워커가 가져갈 수 있도록 대기
```

## 9.2 stroke extraction 실행 예시

```python
def run_stroke_pipeline(job_id: str, input_path: str, output_dir: str):
    command=[
        "python",
        "pipeline.py",
        "--input",
        input_path,
        "--output_dir",
        output_dir,
        "--save_stroke_data"
    ]

    subprocess.run(command, check=True)

    strokes_path=os.path.join(
        output_dir,
        "crop_stroke_composite_strokes.json"
    )

    if not os.path.exists(strokes_path):
        raise RuntimeError("strokes.json was not generated.")

    return strokes_path
```

MVP에서는 `subprocess.run()`으로 기존 코드를 호출한다. 이후 안정화 단계에서 `pipeline.py` 내부 로직을 함수형 모듈로 리팩터링한다.

---

## 10. strokes.json 표준

서버가 Mac 워커에게 제공하는 `strokes.json`은 다음 정보를 포함해야 한다.

```json
{
  "input_path": "...",
  "scale": 1.0,
  "crop_scale": 2.0,
  "region_source": "ocr_merged",
  "shape_rendering": "always",
  "coordinate_system": {
    "global_points": "reference image coordinates",
    "point_order": "[x, y]"
  },
  "total_stroke_count": 225,
  "strokes": [
    {
      "id": 1,
      "region_type": "text",
      "bbox": [x, y, w, h],
      "point_count": 42,
      "global_points": [
        [100, 120],
        [101, 121]
      ]
    }
  ]
}
```

Mac 워커는 기본적으로 `global_points`만 사용한다.

---

## 11. Mac 워커 구현 계획

## 11.1 MVP 구조

```text
mac_worker/
  worker.py
  goodnotes_writer.py
  dump_goodnotes_clipboard.swift
  config.json
  logs/
  outputs/
```

## 11.2 worker.py 역할

```text
1. 서버에서 /api/worker/jobs/next 호출
2. job이 있으면 strokes.json 다운로드
3. GoodNotes 준비 상태 확인
4. goodnotes_writer.py 실행
5. 올가미 복사 자동화 수행
6. dump_goodnotes_clipboard.swift 실행
7. goodnotes_clipboard_item0.bin 생성 확인
8. 서버에 binary 업로드
9. 완료 보고
```

## 11.3 Mac 워커 기본 루프

```python
while True:
    job=fetch_next_job()

    if job is None:
        sleep(3)
        continue

    try:
        report_status(job.id, "drawing_in_goodnotes")
        download_strokes(job)

        run_goodnotes_writer(job)

        report_status(job.id, "copying_from_goodnotes")
        run_lasso_copy()

        bin_path=dump_pasteboard()

        upload_binary(job.id, bin_path)

    except Exception as e:
        report_failure(job.id, e)
```

## 11.4 goodnotes_writer.py 실행 예시

```bash
python goodnotes_writer.py \
  --strokes ./jobs/<job_id>/strokes.json \
  --target_rect 320,180,980,720 \
  --fit contain \
  --driver drag \
  --execute
```

`target_rect`는 GoodNotes 문서의 실제 필기 가능 영역이다. MVP에서는 수동 캘리브레이션으로 시작한다. 이후 자동 캘리브레이션으로 확장한다.

## 11.5 GoodNotes pasteboard dump

Mac에서 GoodNotes 복사 후 다음 type을 추출한다.

```text
com.goodnotesapp.goodnotes5.notes
```

Swift dump script는 다음 역할만 수행한다.

```text
1. NSPasteboard.general 접근
2. com.goodnotesapp.goodnotes5.notes type 검색
3. data 추출
4. goodnotes_clipboard_item0.bin 저장
```

---

## 12. Mac 워커 운영 조건

GoodNotes GUI 자동화는 환경 변화에 민감하므로 다음 조건을 고정한다.

```text
1. Mac 전용 작업 계정 사용
2. GoodNotes 버전 고정
3. GoodNotes 자동 업데이트 비활성화
4. 전용 GoodNotes 문서 템플릿 생성
5. 창 위치 및 크기 고정
6. 디스플레이 해상도 고정
7. 디스플레이 배율 고정
8. Accessibility 권한 허용
9. Input Monitoring 권한 허용
10. 처리 중 Mac 수동 조작 금지
```

권장 방식:

```text
Mac 워커는 한 번에 job 하나만 처리한다.
처리 실패 시 스크린샷과 로그를 남긴다.
GoodNotes 업데이트 후 회귀 테스트를 수행한다.
```

---

## 13. 실패 처리

실패 코드는 단계별로 분리한다.

| 실패 코드                       | 의미                           |
| --------------------------- | ---------------------------- |
| IMAGE_UPLOAD_FAILED         | iPad 이미지 업로드 실패              |
| STROKE_EXTRACTION_FAILED    | 서버에서 strokes.json 생성 실패      |
| STROKES_JSON_NOT_FOUND      | strokes.json 파일 없음           |
| WORKER_TIMEOUT              | Mac 워커 응답 없음                 |
| GOODNOTES_NOT_READY         | GoodNotes 실행/포커스 실패          |
| GOODNOTES_DRAW_FAILED       | GoodNotes stroke 재생 실패       |
| LASSO_COPY_FAILED           | 올가미 복사 실패                    |
| PASTEBOARD_TYPE_NOT_FOUND   | GoodNotes pasteboard type 없음 |
| BINARY_UPLOAD_FAILED        | Mac 워커 binary 업로드 실패         |
| IPAD_BINARY_DOWNLOAD_FAILED | iPad binary 다운로드 실패          |
| IPAD_CLIPBOARD_WRITE_FAILED | iPad 클립보드 기록 실패              |

사용자에게는 단순 메시지를 보여준다.

```text
복원에 실패했습니다. 이미지를 다시 선택하거나 잠시 후 재시도해주세요.
```

개발자용 상세 오류는 `job_events`와 서버 로그에 기록한다.

---

## 14. 보안 및 데이터 보관 정책

업로드 이미지는 개인 필기일 수 있으므로 저장 기간을 짧게 둔다.

권장 정책:

```text
원본 이미지: 24시간 후 삭제
strokes.json: 24시간 후 삭제
GoodNotes binary: 24시간 후 삭제
worker 로그: 개인정보 없는 메타데이터 중심 저장
debug 이미지: 개발 환경에서만 저장
```

API 보안:

```text
iPad 앱 job_id는 UUID 사용
Mac 워커 API는 WORKER_TOKEN 필요
binary 다운로드 URL은 job_id 기반으로 보호
관리자 API는 별도 인증 필요
```

---

## 15. MVP 구현 순서

## 15.1 1단계: 서버 MVP

목표: 이미지 업로드 후 서버에서 `strokes.json` 생성.

구현 항목:

```text
FastAPI 프로젝트 생성
POST /api/jobs 구현
GET /api/jobs/{job_id} 구현
파일 저장 구조 생성
pipeline.py 서버 실행 연결
strokes.json 생성 확인
job 상태 업데이트
```

완료 기준:

```text
iPad 앱 없이 curl/Postman으로 이미지를 업로드했을 때
서버 storage/jobs/<job_id>/ 아래에 strokes.json이 생성되어야 한다.
```

---

## 15.2 2단계: Mac 워커 MVP

목표: 서버에서 `strokes.json`을 받아 GoodNotes binary 생성.

구현 항목:

```text
GET /api/worker/jobs/next 구현
GET /api/worker/jobs/{job_id}/strokes 구현
Python worker.py 구현
goodnotes_writer.py 연결
pasteboard dump script 연결
POST /api/worker/jobs/{job_id}/binary 구현
```

완료 기준:

```text
서버에 stroke_ready job이 있을 때
Mac 워커가 이를 가져가 GoodNotes에 그리고
goodnotes_clipboard_item0.bin을 서버에 업로드해야 한다.
```

---

## 15.3 3단계: iPad 앱 MVP

목표: 이미지를 업로드하고 binary를 받아 클립보드에 기록.

구현 항목:

```text
SwiftUI 앱 생성
이미지 선택 기능
POST /api/jobs 업로드
GET /api/jobs/{job_id} polling
GET /api/jobs/{job_id}/binary 다운로드
UIPasteboard 기록
GoodNotes 이동 안내
```

완료 기준:

```text
iPad 앱에서 이미지를 업로드한 뒤
처리가 끝나면 GoodNotes binary를 클립보드에 기록하고
GoodNotes에서 붙여넣기가 성공해야 한다.
```

---

## 15.4 4단계: 안정화

목표: 실패율을 낮추고 운영 가능한 구조로 개선.

구현 항목:

```text
Mac 워커 좌표 캘리브레이션 개선
GoodNotes 창 크기 자동 고정
실패 시 스크린샷 저장
job_events 기록
worker heartbeat 구현
자동 재시도 정책 추가
오래된 파일 자동 삭제
관리자용 job 목록 화면 추가
```

---

## 15.5 5단계: Mac 워커 Swift 전환

목표: Python/pyautogui 기반 워커를 Swift/AppKit 기반으로 안정화.

구현 항목:

```text
Accessibility 권한 확인
GoodNotes 실행 및 포커스 제어
Quartz 이벤트 기반 stroke 재생
NSPasteboard binary 추출
서버 API 통신
worker 상태 표시 UI
```

---

## 16. 우선 구현해야 할 핵심 파일

서버:

```text
server/app/main.py
server/app/api/jobs.py
server/app/api/worker.py
server/app/services/stroke_service.py
server/app/services/job_service.py
server/app/services/storage_service.py
```

Mac 워커:

```text
mac_worker/worker.py
mac_worker/goodnotes_writer.py
mac_worker/dump_goodnotes_clipboard.swift
mac_worker/config.json
```

iPad 앱:

```text
GoodNotesRestoreApp/
  ContentView.swift
  ImagePicker.swift
  APIClient.swift
  JobStatusView.swift
  PasteboardWriter.swift
```

---

## 17. 핵심 개발 원칙

```text
1. iPad 앱은 얇게 유지한다.
2. 서버가 strokes.json 생성을 책임진다.
3. Mac 워커는 GoodNotes 자동화만 책임진다.
4. Mac 워커는 한 번에 job 하나만 처리한다.
5. 모든 단계는 job 상태로 기록한다.
6. 실패 코드는 단계별로 분리한다.
7. MVP에서는 DB polling으로 시작한다.
8. 다중 워커가 필요해질 때 queue를 도입한다.
9. GoodNotes 버전과 Mac 환경은 고정한다.
10. GoodNotes pasteboard type은 com.goodnotesapp.goodnotes5.notes로 유지한다.
```

---

## 18. 최종 결론

최종 구현 구조는 다음으로 확정한다.

```text
iPad App
→ Render/Railway FastAPI Server
→ strokes.json
→ Mac GUI Worker
→ GoodNotes pasteboard binary
→ Server
→ iPad App
→ UIPasteboard
→ GoodNotes paste
```

서버는 Render/Railway에 배포하며, 이미지 처리와 `strokes.json` 생성을 담당한다. Mac 워커는 서버에서 받은 `strokes.json`을 바탕으로 GoodNotes에 실제 필기를 재생하고, 올가미 복사를 통해 GoodNotes binary를 생성한다. iPad 앱은 최종 binary를 다운로드하여 `UIPasteboard`에 기록하는 역할만 수행한다.

이 구조는 현재 검증된 GoodNotes pasteboard 재주입 방식을 기반으로 하며, iPad 앱·서버·Mac 워커의 책임을 명확히 분리한다.
