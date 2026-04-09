# Document Preprocessing Update

작성일: 2026-04-10

## 변경 목적
- 배경 나무 무늬와 종이 테두리가 skeletonize 대상으로 들어가는 문제를 줄입니다.
- 전체 이미지 threshold 대신 문서 영역을 먼저 분리한 뒤, 종이 내부의 필기만 추출하도록 바꿉니다.

## 반영 내용
- `skeletonizer_test.py`의 `load_and_preprocess`를 문서 중심 파이프라인으로 변경
- 큰 밝은 사각형을 문서로 검출하고 perspective crop 수행
- 문서 내부 grayscale을 조명 보정한 뒤 black-hat으로 어두운 필기 강조
- Otsu + adaptive threshold 결합으로 글자 마스크 생성
- 작은 연결 요소와 과도하게 큰 테두리 성분 제거
- `adaptive_preprocess`는 동일한 공통 파이프라인 사용

## 기대 효과
- 배경 목재 결, 반사, 얼룩이 stroke로 추출되는 비율 감소
- 종이 테두리가 대형 stroke로 잡히는 현상 완화
- 손글씨만 남긴 이진화 결과를 기반으로 skeleton 품질 개선
