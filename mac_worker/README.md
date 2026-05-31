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
