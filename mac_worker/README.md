# H2I Mac Worker Skeleton

이 워커는 서버에서 `stroke_ready` 상태의 job을 가져와 `strokes.json`을 다운로드하고, GoodNotes binary를 서버로 업로드하는 연결 골격이다.

기본 `mock` 모드에서는 실제 GoodNotes를 조작하지 않고 fake binary를 생성한다.

## 실행

```bash
conda run -n DV python mac_worker/worker.py --once
```

## 실제 GoodNotes replay 모드

```bash
conda run -n DV python mac_worker/worker.py --mode replay --once
```

`replay` 모드에서는 `mac_worker/goodnotes_controller.py`를 호출한다. `config.json`의 `execute_goodnotes_controller`가 `false`이면 dry-run으로 실행한 뒤 stale pasteboard 업로드를 막기 위해 job을 실패 처리한다. 실제 입력, 올가미 복사, binary 추출을 수행하려면 `true`로 바꾸고 GoodNotes 창, 펜 도구, 화면 좌표를 먼저 고정해야 한다. 기존 `execute_goodnotes_writer` 값도 호환용으로 계속 인식한다.

## GoodNotes 실행 전 점검

실제 마우스 입력 전에 로컬 환경과 설정을 먼저 확인한다.

```bash
conda run -n DV python mac_worker/preflight.py --check-swift
```

`--check-swift`는 pasteboard binary 추출 스크립트와 Quartz replay 스크립트를 함께 typecheck한다.

특정 `strokes.json`까지 함께 확인하려면 다음처럼 실행한다.

```bash
conda run -n DV python mac_worker/preflight.py \
  --strokes server/storage/jobs/<job_id>/crop_stroke_composite_strokes.json \
  --check-swift
```

GoodNotes가 실행 중이어야 하는 상황까지 필수 조건으로 검사하려면 `--require-goodnotes-running`을 붙인다.

```bash
conda run -n DV python mac_worker/preflight.py \
  --require-goodnotes-running \
  --require-display \
  --require-frontmost-goodnotes \
  --check-swift
```

`config.json`에서 실제 replay 안정화에 사용하는 값은 다음이다.

```text
target_rect: GoodNotes 필기 영역의 x,y,width,height
fit: contain 또는 stretch
sample_step: stroke point 샘플링 간격
min_point_distance: 매핑 후 이 거리(px) 미만으로 움직인 중복/초근접 point 제거
input_backend: quartz 또는 pyautogui. 기본값은 quartz
quartz_point_delay: Quartz backend의 point 사이 입력 지연
quartz_stroke_delay: Quartz backend의 stroke 사이 입력 지연
quartz_mouse_down_delay: Quartz backend에서 mouseDown 직후 drag 시작 전 대기 시간
quartz_post_draw_delay: Quartz backend에서 stroke 입력 후 올가미 전환 전 대기 시간
driver: pyautogui fallback에서 drag 또는 down_move
point_delay: pyautogui fallback의 point 사이 입력 지연
stroke_delay: pyautogui fallback의 stroke 사이 입력 지연
countdown: 실제 입력 전 대기 시간
execute_goodnotes_writer: true일 때만 실제 마우스 입력 수행
execute_goodnotes_controller: true일 때 worker replay에서 실제 GoodNotes 입력과 올가미 복사 수행
activate_goodnotes: 실제 입력 전 GoodNotes 앱 활성화
require_frontmost_goodnotes: 실제 입력 직전 GoodNotes 전면 앱 여부 확인
```

## 최소 실입력 샘플

GoodNotes 전용 문서, 펜 도구, `target_rect`를 고정한 뒤에는 먼저 단일 stroke 샘플로 입력을 확인한다.

```bash
conda run -n DV python goodnotes_writer.py \
  --strokes mac_worker/samples/single_stroke.json \
  --target_rect 320,180,980,720 \
  --sample_step 1 \
  --point_delay 0.01 \
  --stroke_delay 0.05 \
  --countdown 5 \
  --activate_goodnotes \
  --require_frontmost_goodnotes \
  --pen_hotkey cmd+p \
  --execute
```

이 명령은 실제 마우스 입력을 수행하므로 GoodNotes의 빈 테스트 페이지가 포커스된 상태에서만 실행한다.

아무것도 그려지지 않으면 먼저 좌표 변환을 제거하고 절대좌표 입력을 확인한다.

```bash
conda run -n DV python mac_worker/calibrate_input.py \
  --line 700,520,920,520 \
  --driver down_move \
  --duration 0.8 \
  --countdown 5 \
  --activate_goodnotes \
  --require_frontmost_goodnotes \
  --execute
```

이 선이 보이면 `target_rect`를 실제 종이 영역으로 다시 잡아야 한다. 이 선도 보이지 않으면 GoodNotes 펜 도구, 입력 권한, 또는 드라이버 방식을 먼저 확인해야 한다.

## GoodNotes GUI 컨트롤러 smoke test

`goodnotes_controller.py`는 GoodNotes 입력 계층만 분리해서 확인한다. 첫 목표는 GoodNotes를 전면/전체화면으로 올리고, `cmd+p`로 펜 도구를 선택한 뒤, 화면 또는 종이 영역 중앙에 15px 가로선을 입력하는 것이다.

```bash
conda run -n DV python mac_worker/goodnotes_controller.py --execute
```

GoodNotes 펜 선택은 기본적으로 `cmd+p` 단축키를 사용한다. 올가미 선택은 `cmd+l` 단축키를 사용하며, 테스트 선을 그린 직후 올가미 전환까지 확인하려면 다음처럼 실행한다.

```bash
conda run -n DV python mac_worker/goodnotes_controller.py \
  --line_length 200 \
  --select_lasso_after_draw \
  --execute
```

버튼 좌표 클릭 방식이 필요하면 `--tool_select_mode point`와 `--pen_point`, `--black_color_point`를 함께 사용한다.

중앙 기준을 화면 중앙이 아니라 종이 영역 중앙으로 고정하려면 다음처럼 `paper_rect`를 지정한다.

```bash
conda run -n DV python mac_worker/goodnotes_controller.py \
  --paper_rect 420,160,1080,760 \
  --execute
```

이미 펜과 검은색이 선택된 상태에서 입력 계층만 확인하려면 `--skip_pen_select`를 명시적으로 사용한다. 기본 컨트롤러 설정은 Swift/Quartz backend를 사용하며, pyautogui fallback을 선택한 경우에는 `drag` 방식이 GoodNotes 필기 입력에서 안정적으로 동작한다.

샘플 `strokes.json`까지 포함해 GoodNotes 전면화, 전체화면 전환, `cmd+p` 펜 선택, 실제 stroke 입력을 한 번에 확인하려면 다음처럼 실행한다.

```bash
conda run -n DV python mac_worker/goodnotes_controller.py \
  --strokes mac_worker/samples/crop_stroke_composite_strokes.json \
  --target_rect 320,180,980,720 \
  --sample_step 10 \
  --quartz_point_delay 0.0015 \
  --quartz_stroke_delay 0.008 \
  --execute
```

`--strokes`가 지정되면 중앙 테스트 선 대신 `strokes.json` 기반 replay를 수행한다. 처음에는 `sample_step`을 크게 잡아 위치와 입력 가능성을 확인할 수 있지만, 실제 품질 확인과 worker 기본 실행은 `sample_step=1`을 사용한다. `sample_step=10`처럼 큰 값은 곡선과 자소가 직선화되어 글씨가 크게 뭉개질 수 있다. 대신 `min_point_distance=1.0`으로 중복/초근접 point만 제거해 mouseDown 상태에서 같은 위치에 오래 머무르는 입력을 줄인다.

기본 `input_backend=quartz`는 `mac_worker/goodnotes_quartz_replay.swift`를 `/private/tmp/h2i_goodnotes_quartz_replay`로 lazy compile한 뒤 `CGEvent` 기반 mouse event를 직접 전송한다. Swift module cache는 `/private/tmp/h2i_clang_module_cache`를 사용한다. Quartz 이벤트를 너무 빠르게 보내면 GoodNotes가 drag point를 일부 병합하거나 놓쳐 글씨 획이 끊길 수 있으므로, 기본값은 `quartz_point_delay=0.0015`, `quartz_stroke_delay=0.008`, `quartz_mouse_down_delay=0.006`으로 둔다. 기존 pyautogui 경로로 비교하거나 되돌리려면 `--input_backend pyautogui`를 명시한다.

```bash
conda run -n DV python mac_worker/goodnotes_controller.py \
  --strokes mac_worker/samples/crop_stroke_composite_strokes.json \
  --target_rect 320,180,980,720 \
  --input_backend pyautogui \
  --point_delay 0.002 \
  --stroke_delay 0.02 \
  --execute
```

stroke 입력 후 자동으로 올가미 선택과 복사까지 확인하려면 `--copy_after_draw`를 붙인다. 이 모드는 매핑된 stroke 화면 bbox에 padding을 더해 올가미 드래그 영역을 계산하고, `cmd+l`, bbox 주변 사각형 드래그, `cmd+c` 순서로 실행한다.

```bash
conda run -n DV python mac_worker/goodnotes_controller.py \
  --strokes mac_worker/samples/crop_stroke_composite_strokes.json \
  --target_rect 320,180,980,720 \
  --sample_step 1 \
  --min_point_distance 1.0 \
  --quartz_point_delay 0.0015 \
  --quartz_stroke_delay 0.008 \
  --copy_after_draw \
  --execute
```

현재 worker 기본 올가미 설정은 실제 GoodNotes 테스트에서 안정적으로 닫힌 `lasso_padding=40`, `lasso_drag_duration=1.5`, `lasso_point_count=160`, `lasso_close_overlap=48`을 사용한다. 올가미가 너무 타이트하거나 주변 stroke를 놓치면 `--lasso_padding 60`처럼 padding을 더 늘린다.
GoodNotes 올가미는 macOS drag event가 필요할 수 있으므로 기본 `lasso_driver`는 `drag`이다. 커서는 움직이는데 파란 올가미 파선이 생기지 않으면 `down_move` 방식이 아니라 `drag` 방식인지 먼저 확인한다. `pyautogui`의 정식 modifier 이름은 `cmd`가 아니라 `command`이므로 config의 복사 단축키는 `command+c`를 사용한다.
Quartz replay 직후 GoodNotes가 아직 ink stroke를 커밋 중이면 `cmd+l`이 늦게 처리되어 올가미 경로가 펜으로 그려질 수 있다. 이 경우 `quartz_post_draw_delay`를 `1.0` 이상으로 늘려 stroke 입력과 올가미 전환 사이의 여유를 더 둔다.
사각형 올가미의 마지막 부분이 물방울처럼 닫히면 `--lasso_close_overlap 32`처럼 시작 변을 겹쳐 지나가게 하거나 `--lasso_point_count 160`으로 중간점을 늘린다. 사각형 모서리 닫힘이 계속 불안정하면 `--lasso_shape ellipse`로 넓게 감싸는 방식도 테스트한다.
펜 replay도 같은 이유로 한 stroke 안에서는 mouseDown을 유지한 채 macOS drag event를 이어서 보낸다. point마다 `dragTo()`를 독립 실행하면 GoodNotes에서 획이 잘게 끊겨 들어가고 획 지우개/올가미 동작이 불안정해질 수 있다.
