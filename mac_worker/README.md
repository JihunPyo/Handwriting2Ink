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

`replay` 모드에서는 루트의 `goodnotes_writer.py`를 호출한다. `config.json`의 `execute_goodnotes_writer`가 `false`이면 dry-run으로 실행된다. 실제 입력을 수행하려면 `true`로 바꾸고 GoodNotes 창, 펜 도구, 화면 좌표를 먼저 고정해야 한다.

## GoodNotes 실행 전 점검

실제 마우스 입력 전에 로컬 환경과 설정을 먼저 확인한다.

```bash
conda run -n DV python mac_worker/preflight.py --check-swift
```

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
driver: drag 또는 down_move
sample_step: stroke point 샘플링 간격
point_delay: point 사이 입력 지연
stroke_delay: stroke 사이 입력 지연
countdown: 실제 입력 전 대기 시간
execute_goodnotes_writer: true일 때만 실제 마우스 입력 수행
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

이미 펜과 검은색이 선택된 상태에서 입력 계층만 확인하려면 `--skip_pen_select`를 명시적으로 사용한다. GoodNotes 필기 입력은 `drag` 방식에서 정상 동작하는 것으로 확인했으므로, 기본 컨트롤러 설정은 `drag`를 사용한다.

샘플 `strokes.json`까지 포함해 GoodNotes 전면화, 전체화면 전환, `cmd+p` 펜 선택, 실제 stroke 입력을 한 번에 확인하려면 다음처럼 실행한다.

```bash
conda run -n DV python mac_worker/goodnotes_controller.py \
  --strokes mac_worker/samples/crop_stroke_composite_strokes.json \
  --target_rect 320,180,980,720 \
  --sample_step 10 \
  --point_delay 0.001 \
  --stroke_delay 0.01 \
  --execute
```

`--strokes`가 지정되면 중앙 테스트 선 대신 `strokes.json` 기반 replay를 수행한다. 처음에는 `sample_step`을 크게 잡아 위치와 입력 가능성을 확인한 뒤, 품질 확인 시 `5`, `2`, `1` 순서로 줄인다.
