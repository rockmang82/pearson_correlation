# OES 분석기 코드 수정 완료

## 수정 일시
2026-01-04

## 수정 내용 요약

### ✅ 수정 1: SpinBox 입력 방식 변경 (Enter 키 적용)

**변경 위치**: `init_ui()` 메서드

**적용 내용**:
- 모든 파장 SpinBox (3개)에 `setKeyboardTracking(False)` 적용
- 시간 SpinBox에 `setKeyboardTracking(False)` 적용
- Reference Time SpinBox에 `setKeyboardTracking(False)` 적용
- 시그널 연결: `valueChanged` → `editingFinished`

**콜백 함수 시그니처 변경**:
- `on_time_changed(self, value)` → `on_time_changed(self)`
- `on_reference_changed(self, value)` → `on_reference_changed(self)`
- 함수 내부에서 `self.time_spinbox.value()` 등으로 값 획득
- 데이터 로드 체크 (`if self.data is None: return`) 추가

**결과**:
- SpinBox에 값 입력 후 Enter 키를 눌러야 그래프 업데이트
- 화살표 클릭 시에도 Enter 또는 포커스 아웃 시 적용

---

### ✅ 수정 2: 창1, 창2 동일 크기 배치

**변경 위치**: `init_ui()` 메서드의 그래프 영역

**적용 내용**:
- 그래프 A (스펙트럼): `right_layout.addWidget(self.canvas_a, stretch=1)`
- 그래프 B (시계열): `right_layout.addWidget(self.canvas_b, stretch=1)`
- 고정 크기 제거: `setFixedSize(800, 220)` 삭제
- Figure 생성 시 `figsize=(8, 2.2), dpi=100` 제거

**결과**:
- 창1과 창2가 우측 패널에서 1:1 비율로 동일하게 배치
- 우측 패널 stretch 제거로 그래프 영역 최적화

---

### ✅ 수정 3: 반응형 레이아웃 (좌측 고정, 우측 가변)

**변경 위치**: `__init__()` 및 `init_ui()` 메서드

**적용 내용**:
- `setFixedSize(1200, 600)` → `setMinimumSize(800, 400)` + `resize(1200, 600)`
- 메인 레이아웃 여백: `setContentsMargins(10, 10, 10, 10)`
- 메인 레이아웃 간격: `setSpacing(10)`
- 좌측 패널: `setFixedWidth(250)` 유지 (고정 너비)
- 우측 패널: `main_layout.addWidget(right_panel, stretch=1)` (가변 너비)
- Figure 설정: `set_constrained_layout(True)` 적용

**결과**:
- 전체 창 크기 조절 가능 (최소 800x400)
- 좌측 패널은 250px 고정
- 우측 그래프 영역은 창 크기에 맞게 자동 확장/축소

---

### ✅ 수정 4: 창2에 파장별 Correlation Score 표시

**변경 위치**: `update_timeseries_graph()` 메서드

**신규 메서드 추가**:
```python
def calculate_correlation_single_wavelength(self, ref_spectrum, current_spectrum, wavelength):
    """단일 파장 기준 ±10nm 범위의 Pearson Correlation 계산"""
```

**적용 내용**:
- 각 파장별로 개별 Correlation Score 계산
- Current Time 수직선과 파장 시계열 라인의 교차점에 표시
- `annotate()` 사용하여 r값 표시
- 텍스트 스타일: `fontsize=10`, `fontweight='bold'`
- 파장별 색상 매칭 (color=파장 라인 색상)
- 겹침 방지: Y 오프셋 적용 (`5 + i * 15`)
- 박스 스타일: 흰색 배경, 파장 색상 테두리

**변경 전**: Reference 수직선에 전체 Correlation Score 표시
**변경 후**: Current Time 수직선 위에 각 파장별 Correlation Score 표시

---

## 수정된 파일
- `oes_analyzer.py` (530줄 → 534줄)

## 검증 결과
- ✅ Python 문법 검증 통과 (`py_compile` 성공)
- ✅ 모든 import 문 유지
- ✅ 클래스 구조 유지
- ✅ 기존 메서드 시그니처 호환성 확인

## 체크리스트

### 수정 1: SpinBox 입력 방식
- [x] `setKeyboardTracking(False)` 적용 (파장 3개, 시간, Reference)
- [x] `editingFinished.connect()` 시그널 연결
- [x] 콜백 함수 시그니처 변경 (value 파라미터 제거)
- [x] 함수 내 데이터 체크 추가

### 수정 2: 창1, 창2 동일 크기
- [x] `stretch=1` 적용 (그래프 A, B)
- [x] 고정 크기 제거
- [x] Figure 크기 파라미터 제거

### 수정 3: 반응형 레이아웃
- [x] `setMinimumSize(800, 400)` 적용
- [x] `resize(1200, 600)` 적용
- [x] 좌측 패널 `setFixedWidth(250)` 유지
- [x] 우측 패널 `stretch=1` 적용
- [x] Figure `constrained_layout` 적용

### 수정 4: 파장별 Correlation Score
- [x] `calculate_correlation_single_wavelength()` 메서드 추가
- [x] 각 파장별 r값 계산
- [x] `annotate()` 로 교차점에 표시
- [x] `fontsize=10`, `fontweight='bold'` 적용
- [x] 파장별 색상 매칭
- [x] 겹침 방지 오프셋 적용

---

## 참고 사항

- 기존 코드의 import문, 클래스 구조, 다른 메서드는 모두 유지됨
- 요청된 4가지 수정사항만 정확히 적용됨
- 전체 기능 정상 동작 예상
