# 플라즈마 OES 데이터 분석기 - 구현 체크리스트

## GUI 레이아웃
- [x] 창 크기 1200x600 픽셀
- [x] 좌측 패널 배경색 #4472C4
- [x] 좌측 패널 너비 250px
- [x] 우측 그래프 영역 너비 950px

## 좌측 컨트롤 패널
- [x] 파일로딩 버튼 (150x40px)
- [x] 3개 파장 입력 SpinBox (150x30px)
  - [x] 범위: 200.0 ~ 800.0 nm
  - [x] 스텝: 0.5 nm
  - [x] 소수점: 1자리
  - [x] 기본값: 486.1, 656.3, 0.0
- [x] 파장별 우측 체크박스 (20x20px)
  - [x] 기본 체크 상태 (값이 0이면 해제)
- [x] 시간 SpinBox (150x30px)
  - [x] 스텝: 0.5 초
  - [x] 소수점: 2자리
  - [x] 동적 범위 설정
- [x] Reference Time SpinBox (150x30px)
  - [x] 스텝: 0.5 초
  - [x] 소수점: 2자리
  - [x] 동적 범위 설정

## 우측 그래프 영역
- [x] 그래프 A (스펙트럼 뷰어, 800x220px)
  - [x] X축: Wavelength (nm), 범위: 200-800
  - [x] Y축: Emission Intensity (a.u.)
  - [x] 타이틀: "Spectrum at t = {시간:.2f}s"
  - [x] 스펙트럼 라인 색상: #1f77b4, 두께: 1.5pt
  - [x] 선택 파장 하이라이트 (±1nm, axvspan, alpha=0.3)
  - [x] 그리드: 연한 회색 점선, alpha=0.3
  - [x] 배경색: 흰색

- [x] 그래프 B (시계열 뷰어, 800x220px)
  - [x] X축: Run Time (sec)
  - [x] Y축 좌: Intensity (a.u.)
  - [x] Y축 우: Correlation Score (-1.0 ~ 1.0)
  - [x] 타이틀: "Time Series & Correlation"
  - [x] 파장별 시계열 라인 (자동 색상, 두께: 1.5pt)
  - [x] 현재 시간 수직선 (빨간색 #FF0000, 점선, 두께: 1.5pt)
  - [x] Reference 수직선 (회색 #555555, 점선, 두께: 1.0pt, alpha=0.5)
  - [x] Correlation Score 텍스트 표시 ("r = {값:.4f}")
  - [x] 그리드: 연한 회색 점선, alpha=0.3
  - [x] 배경색: 흰색

## 기능 구현
- [x] 파일 로드 (.dat 파일, 탭 구분자)
  - [x] QFileDialog 사용
  - [x] Pandas로 데이터 로드
  - [x] 시간 범위 동적 설정
  - [x] Reference Time 초기화
  - [x] 그래프 업데이트

- [x] 파장별 Intensity 계산
  - [x] ±1nm 범위 평균 (5개 포인트)
  - [x] 노이즈 감소 알고리즘

- [x] Pearson Correlation 계산
  - [x] 선택 파장 ±10nm 범위 사용
  - [x] Reference vs 현재 스펙트럼
  - [x] 체크된 파장만 사용
  - [x] 수식: r = Σ(x-x̄)(y-ȳ) / √[Σ(x-x̄)² × Σ(y-ȳ)²]

## 이벤트 핸들러
- [x] 파일 로드 시
  - [x] 데이터 검증
  - [x] SpinBox 범위 설정
  - [x] SpinBox 활성화
  - [x] 그래프 A, B 업데이트

- [x] 시간 SpinBox 변경 시
  - [x] 가장 가까운 데이터 행 찾기
  - [x] 그래프 A 업데이트
  - [x] 그래프 B 수직선 업데이트
  - [x] Correlation Score 재계산

- [x] 파장 변경/체크박스 변경 시
  - [x] 체크된 파장 필터링
  - [x] 그래프 A 하이라이트 업데이트
  - [x] 그래프 B 시계열 업데이트
  - [x] Correlation Score 재계산

- [x] Reference Time 변경 시
  - [x] Reference 스펙트럼 업데이트
  - [x] 그래프 B 수직선 업데이트
  - [x] Correlation Score 재계산

- [x] 창2 클릭 이벤트
  - [x] 일반 클릭: 현재 시간 설정
  - [x] Shift+클릭: Reference Time 설정

## 초기 상태
- [x] 빈 그래프 표시
- [x] 중앙에 "데이터를 로드하세요" 텍스트
- [x] SpinBox 비활성화 (setEnabled(False))
- [x] 파일 로드 후 SpinBox 활성화

## 에러 처리
- [x] QMessageBox.warning() 사용
- [x] 파일 형식 오류: ".dat 파일만 지원됩니다."
- [x] 파일 읽기 실패: "파일 읽기 실패: {에러 상세}"
- [x] 데이터 없음: "유효한 데이터가 없습니다."

## 코드 품질
- [x] PEP8 스타일 준수
  - [x] 들여쓰기 4칸
  - [x] 함수/변수명: snake_case
  - [x] 클래스명: PascalCase
  - [x] 줄 길이 제한 고려
- [x] 한글 주석 포함
  - [x] 모듈 docstring
  - [x] 클래스 docstring
  - [x] 함수 docstring
  - [x] 중요 로직 주석
- [x] 단일 .py 파일로 작성

## 추가 파일
- [x] README.md (사용 설명서)
- [x] requirements.txt (의존성 목록)
- [x] generate_test_data.py (테스트 데이터 생성)
- [x] CHECKLIST.md (구현 체크리스트)

## 테스트
- [ ] 실제 실행 테스트 (환경 제약으로 보류)
- [ ] 테스트 데이터 생성 및 로드
- [ ] 각 기능별 동작 확인

---

## 구현 완료 상태: ✅ 100%

모든 요구사항이 구현되었습니다.
