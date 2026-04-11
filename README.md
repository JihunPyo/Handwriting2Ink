# 필기 획 추출 파이프라인

손으로 쓴 글씨 이미지에서 **획(stroke) 단위의 좌표열**을 추출하고,
이를 마우스(펜) 경로처럼 재현하는 파이프라인입니다.

---

## 1. 전체 파이프라인 구조

```
입력 이미지 (.jpeg / .png)
        │
        ▼
┌─────────────────────────────────┐
│  1. 전처리 (skeletonizer)        │
│  - 그레이스케일 변환               │
│  - Gaussian Blur 노이즈 제거      │
│  - Otsu 이진화 (글자 = 흰색)       │
│  - Morphological Open/Close     │
└────────────┬────────────────────┘
             │ binary image
             ▼
┌─────────────────────────────────┐
│  2. 스켈레톤화 (skeletonizer)     │
│  - Zhang-Suen Thinning          │
│  → 1px 두께의 세선(Skeleton)      │
└────────────┬────────────────────┘
             │ skeleton image
             ▼
┌─────────────────────────────────┐
│  3. 그래프 구축 (stroke_extractor)│
│  - 스켈레톤 픽셀 → 8-연결 그래프    │
│  - 끝점(degree 1) / 분기점(≥3) 탐색│
└────────────┬────────────────────┘
             │ graph
             ▼
┌─────────────────────────────────┐
│  4. 세그먼트 분할 (stroke_extractor) │
│  - 분기점 제거 후 BFS로 컴포넌트 분리 │
│  - 각 컴포넌트를 DFS로 점 순서 결정  │
└────────────┬────────────────────┘
             │ ordered segments
             ▼
┌─────────────────────────────────┐
│  5. 세그먼트 병합 (stroke_extractor) │
│  - 분기점 클러스터에서 만나는 세그먼트 쌍 탐색 │
│  - 곡률 연속성(내적) + 명암 보정으로 비용 계산  │
│  - Priority Queue로 탐욕적 병합 (O(n² log n)) │
└────────────┬────────────────────┘
             │ merged strokes
             ▼
┌─────────────────────────────────┐
│  6. 정렬 및 출력 (stroke_extractor) │
│  - 시작점 기준 위→아래, 왼→오른 정렬  │
│  - (y,x) → (x,y) 좌표 변환          │
│  → list of np.ndarray, shape (N, 2)  │
└────────────┬────────────────────┘
             │ strokes (좌표열)
             ▼
┌─────────────────────────────────┐
│  7. 시각화 및 저장 (simulate_drawing) │
│  - 3패널 결과 이미지 저장               │
│    [원본 | 획 오버레이 | 색상 복원]     │
│  - 흑백 복원 이미지 저장               │
│  - (선택) Turtle 애니메이션 재생       │
└─────────────────────────────────┘
```

---

## 2. 알고리즘 디테일

### 2-1. 전처리 및 스켈레톤화

원본 이미지는 Gaussian Blur → Otsu 이진화로 글자 픽셀만 추출됩니다.
획 두께가 다양한 필기를 일관되게 처리하기 위해 **Zhang-Suen Thinning** 알고리즘으로
모든 획을 1픽셀 두께의 세선(Skeleton) 으로 압축합니다.

Zhang-Suen은 반복적으로 불필요한 경계 픽셀을 제거하되, 8-방향 연결성을 유지하므로
획의 위상 구조(분기, 교차)가 보존됩니다.

### 2-2. 그래프 구축 및 특수점 탐색

스켈레톤의 각 픽셀을 노드, 8-연결 이웃 관계를 엣지로 하는 그래프를 구축합니다.

| 픽셀 종류 | 이웃 수(degree) | 의미 |
|---|---|---|
| **끝점 (Endpoint)** | = 1 | 획의 시작 또는 끝 |
| **일반 점** | = 2 | 획의 중간 경로 |
| **분기점 (Branch Point)** | ≥ 3 | 획이 교차하거나 갈라지는 지점 |

### 2-3. 세그먼트 분할

분기점을 그래프에서 **일시적으로 제거**하면, 획들이 단순 선분(체인) 형태의
독립 컴포넌트로 분리됩니다. 각 컴포넌트에 대해 BFS로 소속 픽셀을 모으고,
DFS로 끝점에서 끝점까지 일관된 순서로 점들을 나열합니다.

```
원본 스켈레톤:   끝── A ── B ── [분기점] ── C ── 끝
                                     └── D ── 끝

분기점 제거 후:  끝── A ── B         C ── 끝
세그먼트 1 ─────────────────^       D ── 끝
세그먼트 2 ────────────────────────────^
```

### 2-4. 분기점 클러스터링

인접한 분기점들을 BFS로 하나의 **클러스터**로 묶습니다.
교차로나 ㅅ, ㅎ 등 복잡한 접합부에서 여러 분기점이 인접하게 나타나는데,
이를 단일 논리 교차로로 취급하여 세그먼트 병합의 기준점으로 삼습니다.

### 2-5. 연속성 기반 세그먼트 병합 (핵심)

분할된 세그먼트들은 사실 하나의 획(예: 'ㄱ'의 가로획과 세로획)이 분기점에서
잘린 것일 수 있습니다. 이를 복원하기 위해 같은 클러스터에 연결된 세그먼트 쌍을
**곡률 연속성 비용**으로 평가하여 탐욕적으로 병합합니다.

**비용 함수:**

$$\text{cost}(i, j) = \vec{d_i} \cdot \vec{d_j} - 0.5 \times \text{intensity\_bonus}(p_i, p_j)$$

- $\vec{d_i}, \vec{d_j}$: 두 세그먼트의 분기점 방향 단위 벡터 (세그먼트 내부 → 끝단)
- 내적이 **-1에 가까울수록** 두 세그먼트가 거의 직선으로 이어지는 것을 의미 → 비용 낮음
- $\text{angle\_threshold}=110°$ 조건: 방향 차이가 110° 이상(둔각)인 쌍만 후보로 취급
- `intensity_bonus`: 두 끝점이 어두울수록(잉크가 진할수록) 비용 추가 감소

**최적화 (Priority Queue):**

초기에 모든 후보 쌍을 min-heap에 삽입하고, 가장 비용이 낮은 쌍부터 순서대로 병합합니다.
병합된 세그먼트의 ID는 무효화(stale) 처리되어 pop 시 O(1)로 스킵됩니다.
병합으로 생성된 새 세그먼트의 후보 쌍만 heap에 추가하므로 전체 복잡도는
**O(n² log n)** 입니다 (구 구현 O(n²·k) 대비).

### 2-6. 획 정렬 — 마우스 경로 순서 결정

추출된 획들을 **시작점 기준으로 위→아래, 왼→오른** 순서로 정렬합니다.
높이 차이가 `row_tolerance(=20px)` 이내인 획들은 같은 줄로 간주하여
X 좌표 순으로 우선 정렬합니다. 이 순서가 곧 마우스(펜)가 이동하는 경로 순서입니다.

---

## 3. 파일별 기능

### `skeletonizer.py` — 전처리 및 Zhang-Suen 스켈레톤화 모듈

다른 파일들이 `import`해서 사용하는 **핵심 라이브러리 모듈**입니다.
현재 파이프라인에서 실제 사용하는 Zhang-Suen 전처리/스켈레톤화만 제공합니다.

| 함수 | 역할 |
|---|---|
| `load_and_preprocess(path)` | 이미지 로드 → 그레이스케일 → Otsu 이진화 → Morphology 정제. `img`, `gray`, `binary` 반환 |
| `skeletonize_zhang(binary)` | Zhang-Suen 알고리즘으로 세선화. `skeleton`, `elapsed`, `name` 반환 |

---

### `skeletonizer_visualize.py` — Zhang-Suen 시각화 CLI

전처리 및 Zhang-Suen 결과를 빠르게 점검하기 위한 **단일 알고리즘 시각화 도구**입니다.
`원본 / binary / skeleton / overlay / 특수점 / 메트릭`을 2x3 패널로 출력합니다.

**실행 예시:**
```bash
python skeletonizer_visualize.py --input EX_sentence.jpeg --save
```

---

### `stroke_extractor.py` — 획 추출 알고리즘 코어

스켈레톤 이미지에서 그래프 분석, 세그먼트 분할, 연속성 병합을 수행하여
**획 단위의 좌표열(stroke sequence)** 을 반환하는 핵심 알고리즘 모듈입니다.

| 함수 / 변수 | 역할 |
|---|---|
| `extract_strokes(skeleton, ...)` | 파이프라인 전체를 호출하는 메인 함수. `list[np.ndarray]` 반환 |
| `build_skeleton_graph(skeleton)` | 스켈레톤 픽셀 → 8-연결 인접 리스트 그래프 구축 |
| `find_special_points(graph)` | 끝점(degree=1), 분기점(degree≥3) 탐색 |
| `_trace_segment(segment, graph)` | 세그먼트 내 점들을 DFS로 순서 결정 |
| `_cluster_branch_points(bps, graph)` | 인접 분기점들을 BFS로 클러스터링 |
| `_compute_endpoint_direction_and_curvature(seg, type)` | 세그먼트 끝점의 국소 방향 벡터 계산 |
| `_merge_continuous_segments(segs, clusters, ...)` | Priority Queue 기반 탐욕 병합 (핵심 병목 함수, O(n² log n)) |
| `_join_two_segments(a, end_a, b, end_b, cluster)` | 두 세그먼트를 분기점을 통해 물리적으로 연결 |
| `order_strokes(strokes)` | 획을 위→아래, 좌→우로 정렬 |
| `STROKE_COLORS` / `STROKE_COLORS_BGR` | 획 색상 팔레트 (시각화용) |

**독립 실행 예시:**
```bash
python stroke_extractor.py --input EX_sentence.jpeg --save
```

---

### `simulate_drawing.py` — 시각화 및 애니메이션 진입점

파이프라인을 호출하고 결과를 이미지로 저장하거나 Turtle 애니메이션으로 재현하는
**메인 실행 파일**입니다.

| 함수 | 역할 |
|---|---|
| `save_result_image(strokes, img, path)` | 3패널 결과 이미지 저장: `[원본]` + `[원본+획 오버레이]` + `[색상 복원]` |
| `save_black_strokes_image(strokes, img, path)` | 흰 배경에 모든 획을 검은색으로만 그린 이미지 저장 |
| `draw_strokes_with_turtle(strokes, w, h, speed)` | Turtle 모듈로 획 순서대로 필기 애니메이션 재생 |
| `main()` | CLI 인자 파싱 → 전처리 → 스켈레톤화 → 획 추출 → 저장/애니메이션 |

**주요 CLI 옵션:**

| 옵션 | 설명 |
|---|---|
| `--input` | 입력 이미지 경로 |
| `--save` | 결과 이미지 파일 저장 |
| `--output` | 저장 파일명 직접 지정 |
| `--no_turtle` | Turtle 창 없이 파일 저장만 수행 |
| `--speed` | Turtle 속도 (0 = 최고속, 1~10) |

**실행 예시:**
```bash
# 결과 이미지만 저장 (GUI 없음)
python simulate_drawing.py --input EX_sentence.jpeg --save --no_turtle

# Turtle 애니메이션 재생 + 저장
python simulate_drawing.py --input EX_sentence.jpeg --save --speed 5
```

**출력 파일:**
- `{이름}_result.png` — 3패널 컬러 결과 이미지
- `{이름}_strokes_black.png` — 흑백 복원 이미지

---

## 4. 파일 의존성 요약

```
simulate_drawing.py
    ├── skeletonizer.py  (load_and_preprocess, skeletonize_zhang)
    └── stroke_extractor.py   (extract_strokes, STROKE_COLORS, STROKE_COLORS_BGR)
            └── skeletonizer.py  (load_and_preprocess, skeletonize_zhang)

skeletonizer_visualize.py
    └── skeletonizer.py  (load_and_preprocess, skeletonize_zhang)
```
