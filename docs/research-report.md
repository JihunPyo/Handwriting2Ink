# Goodnotes 필기 복원 웹서비스 구현 계획

## 핵심 결론

지금 구상한 서비스는 **기술적으로는 충분히 구현 가능한 방향**입니다. 다만 성공 여부는 두 가지를 초반에 빨리 검증하느냐에 달려 있습니다. 첫째, **맥북의 Goodnotes에서 올가미 복사로 얻은 클립보드 payload를 iPad Chrome에서 실제로 재주입할 수 있는지**입니다. 둘째, **Goodnotes UI 자동화와 포맷 재현이 Goodnotes의 공식 라이선스·약관 범위 안에 들어가는지**입니다. Goodnotes는 공식적으로 Lasso 기반의 copy/paste를 지원하고, 이미지의 copy/paste도 지원하며, iOS에서 외부 앱으로부터 `.goodnotes`, `.goodnotes.zip`, PDF, 이미지 파일을 가져올 수 있습니다. 또한 Goodnotes for macOS는 iOS 버전의 거의 모든 기능을 지원한다고 안내합니다. 그래서 “맥 GUI 워커가 Goodnotes를 대신 조작한다”는 큰 구조 자체는 제품 기능 면에서는 자연스럽습니다. citeturn3view6turn3view5turn6search1turn9search11

반대로, **클라이언트가 iPad의 Chrome 브라우저**라는 점은 매우 중요한 제약입니다. Chrome은 iOS/iPadOS에서 WebKit을 사용하므로, 데스크톱 Chromium에서 가능한 기능을 그대로 기대하면 안 됩니다. 브라우저 Clipboard API는 secure context에서만 동작하고, 사용자 활성화가 필요하며, WebKit은 이 사용자 활성화 추적이 Blink보다 더 엄격하게 동작하는 것으로 알려져 있습니다. 따라서 “서버에서 결과를 받은 뒤 아무 때나 자동으로 클립보드에 넣는다” 같은 흐름은 실패할 가능성이 높고, **결과를 미리 받아둔 뒤 사용자가 직접 누르는 버튼 안에서 즉시 clipboard write를 수행하는 구조**로 설계해야 합니다. citeturn3view4turn3view1turn3view3turn11search20

첨부한 zip을 기준으로 보면 현재 자산은 이미 꽤 좋습니다. 핵심은 `pipeline.py`, `stroke_extractor.py`, `simulate_drawing.py`로 이어지는 **이미지→스트로크 추출 자산**입니다. 다만 지금 상태는 CLI 실험 코드와 시각화 결과물 중심이라서, 웹서비스로 가려면 **서비스용 JSON 출력, 맥 자동화 에이전트, 잡 큐, 클립보드/포맷 브리지, 장애 복구 로직**을 새로 붙여야 합니다. 즉, 지금부터의 핵심 개발은 “알고리즘 발명”보다 “제품화 계층을 세우는 일”에 가깝습니다.

## 권장 아키텍처

권장 구조는 **클라이언트**, **오케스트레이터 API**, **추출 워커**, **맥 GUI 워커**의 네 계층입니다. 중요한 점은, 처음부터 이를 논리적으로 나눠야 한다는 것입니다. 물리적으로는 한 대의 맥북에서 시작해도 되지만, **이미지에서 스트로크를 뽑는 계산 단계**와 **Goodnotes를 실제로 조작하는 GUI 단계**는 꼭 분리된 프로세스로 보관하는 편이 좋습니다. 그래야 나중에 추출만 별도 서버로 옮기거나, 맥 워커만 여러 대로 늘릴 수 있습니다.

실제 데이터 흐름은 아래처럼 설계하는 것이 가장 안정적입니다. 사용자가 iPad Chrome에서 이미지를 업로드하면, API는 job을 생성하고 원본 이미지를 저장합니다. 그다음 decapd 파이프라인을 호출하는 추출 워커가 작동해 **정규화된 `strokes.json`**, 썸네일, overlay, skeleton preview를 생성합니다. 이 결과를 클라이언트가 WebSocket으로 받아 결과 화면에 표시합니다. 사용자가 “복원” 혹은 “클립보드 준비”를 누르면, 오케스트레이터는 그 job을 **직렬화된 맥 GUI 큐**에 넣고, 맥 워커가 Goodnotes를 실행·준비한 뒤 실제 마우스 드로잉, 올가미 선택, Copy 수행, pasteboard 덤프 수집까지 끝냅니다. 마지막으로 서버는 이를 `restore_bundle`로 포장해 클라이언트로 전달하고, 클라이언트는 사용자 클릭 시점에 이 번들을 이용해 클립보드 write를 시도하거나, 실패 시 파일 import/share 경로로 넘어갑니다. Clipboard와 Web Share는 모두 secure context와 사용자 활성화에 묶여 있고, FastAPI는 WebSocket을 지원하므로 이 구조가 구현상도 잘 맞습니다. citeturn3view1turn13view0turn13view1turn12search0

여기서 가장 중요한 설계 원칙은 **Goodnotes 워커를 “단일 좌석(single-seat) 자원”으로 취급하는 것**입니다. Apple의 UI scripting 문서는 GUI 스크립트가 실제 사용자 동작처럼 마우스 클릭과 키 입력을 흉내 내는 방식이라고 설명하며, 앱별 Accessibility 허용이 필요하다고 안내합니다. 또 pasteboard는 앱 간 데이터 전달의 핵심 인터페이스입니다. 즉, 이 단계는 본질적으로 “한 세션의 전경 앱 + 운영체제 클립보드”를 다루는 작업이라, 웹 서버처럼 무한 동시 처리 자원으로 생각하면 안 됩니다. 아키텍처는 처음부터 이를 전제로 해야 합니다. citeturn5view2turn4search0turn1search0

## 권장 기술 스택

웹 클라이언트는 **React 기반 TypeScript 프런트엔드**가 가장 무난합니다. Next.js 같은 프레임워크를 써도 좋지만, 핵심은 프레임워크 이름보다 **모바일 우선 UI**, **job 상태 관리**, **결과 번들 사전 다운로드**, **사용자 클릭 순간의 Clipboard/Web Share 처리**입니다. iPad Chrome이 사실상 WebKit 제약을 받기 때문에, 데스크톱 Chrome 전용 기능에 기대면 안 됩니다. Clipboard API와 Web Share API는 모두 secure context와 사용자 활성화를 요구하므로, UI는 “업로드 → 처리 상태 → 결과 미리보기 → 사용자가 누르는 최종 액션”의 2-step 흐름으로 설계하는 편이 맞습니다. 첨부해 준 결과 화면 예시처럼 preview 탭과 최종 액션 버튼을 나누는 방향이 이 제약과 잘 맞습니다. citeturn3view4turn3view1turn13view0turn13view1

백엔드는 **FastAPI + PostgreSQL + S3 호환 오브젝트 스토리지 + Redis Streams** 조합을 추천합니다. 이유는 간단합니다. 지금 파이프라인이 이미 Python 중심이라서 FastAPI로 감싸면 코드 재사용량이 가장 크고, FastAPI는 WebSocket을 공식적으로 지원합니다. 반면 긴 작업 전체를 FastAPI `BackgroundTasks`에 그냥 얹는 것은 좋지 않습니다. 공식 문서도 BackgroundTasks를 “응답을 반환한 뒤 실행하는 작업”의 용도로 설명합니다. 당신의 경우는 몇 초짜리 후처리가 아니라 **내구성, 재시도, 직렬화, 워커 장애 복구**가 모두 필요한 장기 작업입니다. 그래서 메시지 브로커는 Redis Pub/Sub보다 **Redis Streams**가 맞습니다. Redis 문서에 따르면 Pub/Sub는 at-most-once semantics라 구독 측 장애가 나면 메시지가 유실될 수 있지만, Streams는 append-only log와 consumer groups 기반으로 더 안정적인 처리 구조를 제공할 수 있습니다. citeturn12search0turn12search1turn12search2turn12search14

맥 GUI 워커는 **Swift 기반의 네이티브 macOS 에이전트**로 만드는 것을 권합니다. 이유는 Goodnotes를 조작하는 핵심 API가 AppKit/Accessibility/Quartz/Pasteboard 계열이기 때문입니다. Apple 문서는 Quartz Event Services를 저수준 입력 이벤트 관리 기능으로 설명하고, UI scripting은 accessibility 프레임워크 위에서 돌아가며 앱별로 수동 허용이 필요하다고 안내합니다. 또한 `AXIsProcessTrustedWithOptions`로 현재 프로세스가 신뢰된 Accessibility client인지 점검할 수 있고, `NSPasteboard`는 pasteboard 작업의 핵심 인터페이스입니다. UTType 계층은 표준 타입과 전용 타입을 다루는 데 적합합니다. 즉, **이미지→스트로크 추출은 Python subprocess로 유지하고**, **Goodnotes 조작·클립보드 읽기·앱 상태 제어는 Swift 에이전트가 맡는 하이브리드 구조**가 가장 실용적입니다. citeturn0search3turn5view2turn1search0turn4search0turn4search1turn4search5

내부 데이터 포맷은 처음부터 두 개로 나누는 것이 좋습니다. 하나는 서버 간 표준인 `strokes.json`이며, 다른 하나는 클라이언트 반환용 `restore_bundle.zip`입니다. `strokes.json`에는 페이지 크기, 좌표계, 펜 속성, stroke 배열, 디버그 메타데이터를 넣고, `restore_bundle`에는 pasteboard item type 목록, raw bytes, fallback file, manifest를 함께 담습니다. 이 중립 포맷이 있어야 나중에 “브라우저 클립보드 경로”, “`.goodnotes` 파일 경로”, “이미지 fallback 경로”를 같은 서버 계약 위에서 병행할 수 있습니다. 특히 Goodnotes 공식 문서는 **현재 지원 포맷을 `.goodnotes`와 `.goodnotes.zip` 중심으로 설명**하고 있으므로, API 계약을 처음부터 `.goodnotes5` 같은 이름에 종속시키는 것은 피하는 편이 안전합니다. citeturn6search1turn6search0

## 핵심 기술 문제와 대응

가장 큰 문제는 **브라우저 클립보드와 Goodnotes의 실제 pasteboard 형식이 정확히 맞물리느냐**입니다. MDN에 따르면 `ClipboardItem`은 여러 MIME 타입을 가질 수 있고, Clipboard API는 시스템 클립보드에 비동기적으로 읽고 쓸 수 있습니다. 하지만 실전에서는 브라우저 엔진 차이가 매우 큽니다. WebKit 버그 트래커에는 `await` 이후의 `clipboard.write()`가 Safari 계열에서 거부되는 사례가 남아 있고, WebKit 측 설명도 사용자 활성화 추적 방식 차이를 직접 언급합니다. 반면 Chromium은 web custom formats를 모바일 Chromium 104+부터 지원한다고 설명하지만, 이건 **Chromium 엔진일 때의 이야기**입니다. iPad Chrome은 WebKit을 쓰므로, “Chromium custom clipboard formats로 Goodnotes private type을 밀어 넣겠다”는 전제는 사용할 수 없습니다. 그래서 반드시 해야 하는 첫 스파이크는 다음입니다. 맥 Goodnotes에서 올가미 Copy를 수행한 뒤 `NSPasteboard`에 올라온 실제 type 목록과 raw payload를 덤프하고, iPad Chrome에서 **그 exact type이 write 가능한지**를 검사해야 합니다. 이게 통과하면 현재 구상이 유지되고, 안 되면 파일 import 경로를 보조선으로 가져가야 합니다. citeturn3view0turn3view1turn3view3turn11search14turn3view4

이 스파이크를 할 때 클라이언트 구현도 방식이 중요합니다. Clipboard와 Share는 모두 사용자 활성화가 필요하므로, **결과 번들을 버튼 누르기 전에 백그라운드로 받아두고**, 사용자가 “클립보드로 복사” 버튼을 누르는 순간 `navigator.clipboard.write()` 또는 `navigator.share()`를 즉시 수행해야 합니다. Share API는 파일 전달도 할 수 있고, Goodnotes는 iOS에서 외부 앱이나 Files 앱을 통한 import를 공식 지원합니다. 따라서 direct paste가 가장 먼저 시도되어야 하지만, 실패할 때를 대비한 **공식 지원 fallback은 `.goodnotes` / `.goodnotes.zip` 파일을 Share/Open In Goodnotes로 넘기는 경로**입니다. 이 fallback은 현재 확정한 서버쪽 Goodnotes 파이프라인을 거의 건드리지 않으면서도 사용자 경험을 살릴 수 있는 최소 변경안입니다. citeturn13view0turn13view1turn3view7turn6search1

두 번째 문제는 **macOS GUI 자동화의 안정성**입니다. Apple 문서는 UI scripting이 버튼 클릭, 메뉴 선택, 키 입력 같은 사용자 상호작용을 흉내 내는 방식이며, Accessibility 권한이 없으면 실패한다고 명시합니다. 또한 Accessibility Inspector로 UI 요소 구조를 파악할 수 있다고 안내합니다. 이 말은 곧, Goodnotes가 업데이트되어 툴바 구조나 메뉴 이름이 바뀌면 워커가 깨질 수 있다는 뜻입니다. 그래서 에이전트는 단순 좌표 클릭만 해서는 안 됩니다. **앱 실행 상태 확인, 문서 준비 확인, 도구 상태 확인, zoom/scroll 초기화, 실패 시 화면 원점 복귀, 수동 재동기화 버튼**이 모두 필요합니다. 메뉴/버튼 전환은 AX 기반으로, 실제 캔버스 드로잉은 Quartz 이벤트 기반으로, 화면 위치 보정은 좌표 템플릿이나 이미지 anchor 기반으로 섞는 게 현실적입니다. citeturn5view2turn0search3turn1search0

세 번째 문제는 **처리량과 확장성**입니다. 지금 서비스는 보기에는 웹 서비스지만, 실제 병목은 Goodnotes GUI 세션 하나에 있습니다. 따라서 **추출 단계는 병렬**, **Goodnotes 복원 단계는 직렬**로 설계해야 합니다. 예를 들어 이미지 업로드와 stroke extraction은 여러 개를 동시에 돌리되, “Goodnotes에 실제 그리기” 큐는 워커당 1개만 처리하게 해야 합니다. 이 구조는 Redis Streams consumer group과 lease lock으로 깔끔하게 구현할 수 있습니다. 나중에 처리량이 필요해지면, 추출 워커는 늘리고 맥 워커도 여러 대로 수평 확장하면 됩니다. 여기서 핵심은 처음부터 job 상태를 `uploaded → extracted → queued_for_gui → drawing → copied → bundled → delivered → failed`로 나누는 것입니다. citeturn12search2turn12search14turn5view2turn4search0

네 번째 문제는 **목표 포맷의 정의**입니다. Goodnotes 지원 문서에서 현재 공식 import/export 표기는 `.goodnotes`와 `.goodnotes.zip`이고, copy/paste UI도 문서화되어 있지만, **개발자용 pasteboard 명세는 공개적으로 확인되지 않습니다**. 그래서 지금 단계에서 “클라이언트가 `.goodnotes5`로 다시 바꾼다”를 구현 계약으로 확정하면 나중에 발목을 잡을 수 있습니다. 더 안전한 방법은, 서버는 일단 “Goodnotes가 실제로 copy한 payload를 중립 번들로 저장”하고, 클라이언트/브리지 계층이 이를 **직접 pasteboard 재주입** 또는 **`.goodnotes` 파일 변환 후 import** 중 하나로 소화하게 두는 것입니다. 이 전략은 아직 불확실한 포맷 문제를 API 설계와 분리해 줍니다. citeturn6search1turn6search0turn3view6

## 법적 및 운영 리스크

이 프로젝트에서 기술 못지않게 중요한 것이 **Goodnotes 이용약관과 라이선스 해석**입니다. Goodnotes의 일반 약관에는 역공학, 자동화된 수단을 통한 접근, 비공개 영역 접근, 서비스의 구조나 알고리즘을 알아내려는 시도 등을 제한하는 조항이 있습니다. Goodnotes for Business EULA 쪽에는 소프트웨어의 파일 포맷, 비공개 API, 내부 아이디어를 얻으려는 행위와 네트워크를 통한 원격 제공을 제한하는 문구도 있습니다. 이 문구들이 지금 구상한 “GUI 서버가 Goodnotes를 대신 조작하고, 그 결과 클립보드 payload 또는 포맷을 재현해 외부 사용자에게 돌려주는 구조”에 어느 정도까지 적용되는지는 계약 형태와 사용 맥락에 따라 달라질 수 있지만, **외부 사용자 대상 서비스화**로 가면 분명히 검토 대상입니다. 최소한 프로덕션 전환 전에 법무 검토 또는 Goodnotes 측 확인이 필요합니다. citeturn14search0turn14search1turn14search2

운영 측면에서는 **권한과 버전 고정**이 핵심입니다. UI scripting은 앱별 Accessibility 허용이 필요하고, pasteboard의 일반 동작도 프로그램 접근 시 확인 프롬프트가 개입할 수 있습니다. 따라서 맥 워커는 처음 배포할 때 한 번의 “온보딩 절차”를 거쳐야 합니다. 여기에 더해 Goodnotes/macOS 자동 업데이트를 곧바로 production에 반영하지 말고, **스테이징 워커에서 UI 회귀 테스트를 통과한 뒤에만 배포**하는 방식이 필요합니다. pasteboard 구조나 툴바 UI가 바뀌면 서비스가 조용히 망가질 수 있기 때문입니다. citeturn5view2turn4search8turn4search12

데이터 보안은 업계 상식 수준으로 강하게 가져가면 됩니다. 업로드 이미지는 개인 필기일 가능성이 높으므로, 원본 이미지·중간 산출물·복원 번들의 보관 기간은 짧게 두고, 기본값은 자동 삭제로 잡는 편이 좋습니다. 특히 Clipboard/Web Share는 HTTPS secure context를 요구하므로, 개발 초반부터 로컬 테스트 환경까지 포함해 TLS를 전제로 두는 것이 좋습니다. citeturn3view1turn13view1

## 단계별 구현 로드맵

가장 현실적인 로드맵은 **초기 스파이크 → 알파 제품화 → 베타 안정화**의 세 묶음으로 가는 방식입니다.

먼저 **초기 스파이크 단계**에서는 기능을 많이 만들지 말고, 성공/실패를 가를 질문만 해결해야 합니다. 여기서 해야 할 일은 네 가지입니다. decapd 파이프라인을 함수형 모듈로 감싸서 `strokes.json`을 안정적으로 출력하게 만들기, Goodnotes Mac에서 lasso copy 후 `NSPasteboard` item/type/raw bytes를 덤프하는 probe 앱 만들기, iPad Chrome에서 그 payload를 `clipboard.write()`로 재주입하는 실험하기, 그리고 약관/EULA 리스크를 제품 범위 기준으로 정리하기입니다. 이 단계의 산출물은 데모가 아니라 **Go/No-Go 판단**이어야 합니다. 브라우저 클립보드가 막히면, 곧바로 `.goodnotes` 파일 delivery fallback을 병행하는 설계로 전환하면 됩니다. citeturn3view3turn13view0turn6search1turn14search0turn14search1

다음 **알파 단계**에서는 웹서비스 뼈대를 세웁니다. 업로드 API, job 상태 테이블, Redis Streams 큐, FastAPI WebSocket 진행률 스트림, object storage, 결과 화면을 먼저 완성합니다. 이 시점에 제공 zip의 실험 코드도 정리해야 합니다. 현재처럼 GUI backend나 turtle 데모 성격의 코드는 서버 프로세스에서 돌리기 어렵기 때문에, 추출 파이프라인은 **무조건 headless-safe** 하게 바꾸고, 결과는 이미지 파일이 아니라 JSON manifest 중심으로 재구성해야 합니다. 그리고 클라이언트는 “원본 / crop / skeleton / stroke JSON / 복원 대기” 탭을 보여주는 식으로, 이미 첨부한 UI 예시 그대로 가져가면 됩니다.

그 다음 **맥 워커 단계**에서는 Swift 에이전트를 붙입니다. 이 에이전트는 워커 부팅 시 Accessibility 신뢰 상태를 점검하고, Goodnotes 실행/복구, 고정 템플릿 문서 열기, 줌/스크롤 초기화, 펜 도구 선택, stroke replay, 올가미 선택, copy 수행, pasteboard 수집, 실패 시 리셋까지 담당합니다. 이 단계에서 중요한 것은 기능보다 **재현성**입니다. 반드시 전용 문서 템플릿, 고정 창 크기, 고정 화면 배율, 고정 Goodnotes 버전, 실패 시 녹화/스크린샷 캡처를 함께 넣어야 합니다. Apple 문서 기준으로 UI scripting은 접근성 프레임워크 허용과 UI 계층 파악이 선행되어야 하므로, 구현보다 먼저 워커 환경 표준화를 끝내야 합니다. citeturn5view2turn1search0turn0search3

마지막 **베타 단계**에서는 사용자 경험을 다듬고 실패 경로를 닫습니다. 클라이언트는 결과 번들을 미리 받아두고, 사용자가 버튼을 누르면 그 이벤트 안에서 곧바로 clipboard write를 시도해야 합니다. 실패하면 곧바로 Share/Open In Goodnotes 버튼을 띄워 `.goodnotes` 또는 fallback 파일을 넘깁니다. 동시에 운영 기준도 잡아야 합니다. 예를 들면 “Goodnotes 앱 업데이트 후 회귀 테스트 통과”, “100건 연속 처리에서 수동 개입 없이 완료율 95% 이상”, “pasteboard type 변화 감지 시 알림”, “job 실패 시 재시도와 수동 회수 경로 보유” 정도가 1차 운영 기준으로 적절합니다. Web Share는 사용자 활성화가 필요하고 Goodnotes는 외부 앱 import를 공식 지원하므로, direct paste가 언제든 실패할 수 있다는 전제를 UX에 반영하는 것이 중요합니다. citeturn13view0turn13view1turn3view7turn6search1

정리하면, **지금 당장 착수해야 하는 일은 전체 앱 개발이 아니라 두 개의 스파이크**입니다. 하나는 “Goodnotes copy payload를 iPad Chrome에서 재주입할 수 있는가”, 다른 하나는 “이 방식이 약관과 라이선스상 허용 가능한가”입니다. 이 두 관문만 통과하면, 그 다음의 웹서비스 구현은 비교적 전형적인 **FastAPI 오케스트레이터 + Redis Streams + Swift 맥 워커 + Python stroke extraction** 문제로 바뀝니다. 그리고 그 구조는 지금 가지고 있는 decapd 자산을 가장 덜 버리면서 제품으로 옮기는 경로입니다.