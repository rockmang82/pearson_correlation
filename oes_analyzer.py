"""
플라즈마 OES 데이터 분석기 - Pearson Correlation 시각화
Author: Claude
Date: 2026-01-04

플라즈마 OES(광방출분광법) 데이터를 스펙트럼 및 시계열로 시각화하고,
Reference Spectrum 대비 현재 시점의 Pearson Correlation Score를 계산하여 표시하는
PyQt5 기반 GUI 프로그램
"""

import sys
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QDoubleSpinBox, QCheckBox,
    QLabel, QFileDialog, QMessageBox, QTabWidget, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPalette, QColor, QCursor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# 한글 폰트 설정 (Windows: 맑은 고딕)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지

try:
    from adjustText import adjust_text
    ADJUSTTEXT_AVAILABLE = True
except ImportError:
    ADJUSTTEXT_AVAILABLE = False
    print("Warning: adjustText not installed. Text overlap prevention disabled.")


class CorrelationDetailWindow(QWidget):
    """창3: Pearson Correlation 상세 정보 팝업"""

    closed = pyqtSignal()  # 창 닫힘 시그널

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.parent_window = parent
        self.init_ui()

    def init_ui(self):
        """GUI 초기화"""
        self.setWindowTitle("Pearson Correlation Detail")
        self.setMinimumSize(800, 400)
        self.resize(1000, 500)

        # 메인 레이아웃
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ===== 좌측 패널 (공식 및 계산 결과) =====
        left_panel = QWidget()
        left_panel.setStyleSheet("background-color: white; border-radius: 5px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # 탭 위젯 (파장별 분리)
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ccc; background: white; }
            QTabBar::tab { padding: 8px 16px; }
            QTabBar::tab:selected { background: #4472C4; color: white; }
        """)
        left_layout.addWidget(self.tab_widget)

        # ===== 우측 패널 (Correlation Score 시계열 그래프) =====
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: white; border-radius: 5px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)

        # Matplotlib Figure
        self.figure = Figure()
        self.figure.set_constrained_layout(True)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        right_layout.addWidget(self.canvas)

        # 패널 추가 (1:1 비율)
        main_layout.addWidget(left_panel, stretch=1)
        main_layout.addWidget(right_panel, stretch=1)

    def update_content(self, parent):
        """내용 업데이트 - 부모 창에서 데이터 직접 접근"""
        if parent.data is None:
            return

        # 탭 초기화
        self.tab_widget.clear()

        # 체크된 파장 정보 수집
        wavelengths_info = []
        for i in range(3):
            if parent.wavelength_checkboxes[i].isChecked():
                wl = parent.wavelength_inputs[i].value()
                if wl > 0:
                    wavelengths_info.append(wl)

        if not wavelengths_info:
            return

        times = parent.data.iloc[:, 1].values
        current_time = parent.time_spinbox.value()
        reference_time = parent.reference_spinbox.value()

        # 가장 가까운 시간 인덱스 찾기
        current_idx = int(np.argmin(np.abs(times - current_time)))
        ref_idx = int(np.argmin(np.abs(times - reference_time)))

        # 스펙트럼 데이터 가져오기 (열 2부터가 파장 데이터)
        ref_spectrum = parent.data.iloc[ref_idx, 2:].values.astype(float)
        current_spectrum = parent.data.iloc[current_idx, 2:].values.astype(float)

        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

        # 우측 그래프 초기화
        self.ax.clear()

        for i, wl in enumerate(wavelengths_info):
            line_color = colors[i % len(colors)]

            # ===== 탭 생성 (각 파장별) =====
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(10, 10, 10, 10)

            # 스크롤 영역
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_content = QWidget()
            scroll_layout = QVBoxLayout(scroll_content)

            # ±10nm 범위 인덱스 계산
            center_idx = int((wl - 200.0) / 0.5)
            start_idx = max(0, center_idx - 20)
            end_idx = min(len(ref_spectrum) - 1, center_idx + 20)

            x = ref_spectrum[start_idx:end_idx + 1]
            y = current_spectrum[start_idx:end_idx + 1]

            # 통계값 계산
            x_mean = np.mean(x)
            y_mean = np.mean(y)
            numerator = np.sum((x - x_mean) * (y - y_mean))
            denom_x = np.sum((x - x_mean)**2)
            denom_y = np.sum((y - y_mean)**2)
            denominator = np.sqrt(denom_x * denom_y)
            r_value = numerator / denominator if denominator != 0 else 0.0

            # 공식 표시용 Figure
            formula_fig = Figure(figsize=(5, 6))
            formula_canvas = FigureCanvas(formula_fig)
            formula_ax = formula_fig.add_subplot(111)
            formula_ax.axis('off')

            # 공식 텍스트 (mathtext 사용, raw string)
            formula_text = (
                r"$\mathbf{Pearson\ Correlation\ Coefficient}$" + "\n\n"
                r"$r = \frac{\sum_{i=1}^{n}(x_i - \bar{x})(y_i - \bar{y})}{\sqrt{\sum_{i=1}^{n}(x_i - \bar{x})^2 \cdot \sum_{i=1}^{n}(y_i - \bar{y})^2}}$" + "\n\n"
                r"$\mathbf{Variables:}$" + "\n"
                r"$x_i$ = Reference spectrum intensity" + "\n"
                r"$y_i$ = Current spectrum intensity" + "\n"
                r"$\bar{x}$ = Mean of reference" + "\n"
                r"$\bar{y}$ = Mean of current" + "\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                r"$\mathbf{Calculation\ for\ \lambda = " + f"{wl:.1f}" + r"\ nm}$" + "\n"
                f"(Range: {wl-10:.1f} - {wl+10:.1f} nm)\n\n"
                f"Reference Time: {reference_time:.2f} s\n"
                f"Current Time: {current_time:.2f} s\n\n"
                r"$\bar{x}_{ref}$ = " + f"{x_mean:.2f}\n"
                r"$\bar{y}_{current}$ = " + f"{y_mean:.2f}\n\n"
                r"$\sum(x_i - \bar{x})(y_i - \bar{y})$ = " + f"{numerator:.2f}\n\n"
                r"$\sqrt{\sum(x_i - \bar{x})^2}$ = " + f"{np.sqrt(denom_x):.2f}\n"
                r"$\sqrt{\sum(y_i - \bar{y})^2}$ = " + f"{np.sqrt(denom_y):.2f}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                r"$r = \frac{" + f"{numerator:.2f}" + r"}{" + f"{np.sqrt(denom_x):.2f}" + r" \times " + f"{np.sqrt(denom_y):.2f}" + r"}$" + "\n\n"
                r"$\mathbf{r = " + f"{r_value:.6f}" + r"}$"
            )

            formula_ax.text(0.05, 0.95, formula_text,
                           transform=formula_ax.transAxes,
                           fontsize=10,
                           verticalalignment='top',
                           fontfamily='monospace')

            formula_fig.tight_layout()
            scroll_layout.addWidget(formula_canvas)
            scroll.setWidget(scroll_content)
            tab_layout.addWidget(scroll)

            self.tab_widget.addTab(tab, f"λ={wl:.1f}nm")

            # ===== 우측 그래프: Correlation Score 시계열 =====
            r_values = []
            for t_idx in range(len(times)):
                t_spectrum = parent.data.iloc[t_idx, 2:].values.astype(float)
                t_y = t_spectrum[start_idx:end_idx + 1]
                t_y_mean = np.mean(t_y)
                t_num = np.sum((x - x_mean) * (t_y - t_y_mean))
                t_denom_y = np.sum((t_y - t_y_mean)**2)
                t_denom = np.sqrt(denom_x * t_denom_y)
                t_r = t_num / t_denom if t_denom != 0 else 0.0
                r_values.append(t_r)

            self.ax.plot(times, r_values, color=line_color,
                        linewidth=1.5, label=f'{wl:.1f} nm')

        # 수직선 (Current Time, Reference Time)
        self.ax.axvline(x=current_time, color='#FF0000',
                       linestyle='--', linewidth=1.5, label='Current')
        self.ax.axvline(x=reference_time, color='#555555',
                       linestyle='--', linewidth=1.5, label='Reference')

        # 그래프 설정
        self.ax.set_xlabel("Run Time (sec)")
        self.ax.set_ylabel("Correlation Score")
        self.ax.set_ylim(-1.0, 1.0)
        self.ax.set_title("Correlation Score Time Series")
        self.ax.legend(loc='upper right', fontsize=8)
        self.ax.grid(True, linestyle='--', alpha=0.3)

        self.canvas.draw()

    def closeEvent(self, event):
        """창 닫힘 이벤트"""
        self.closed.emit()
        event.accept()


class OESAnalyzer(QMainWindow):
    """메인 윈도우 클래스"""

    def __init__(self):
        """초기화"""
        super().__init__()
        self.setWindowTitle("플라즈마 OES 데이터 분석기")
        self.setMinimumSize(800, 400)  # 최소 크기 설정
        self.resize(1200, 600)  # 초기 크기 (고정 아님)

        # 데이터 변수 초기화
        self.data = None  # 로드된 데이터프레임
        self.wavelengths_data = None  # 파장 배열 (200.0 ~ 800.0)
        self.reference_time = None  # Reference 시간
        self.current_time = None  # 현재 선택된 시간

        # 드래그 상태 관리
        self.dragging_line = None  # 'current' 또는 'reference' 또는 None
        self.current_vline = None  # Current Time 수직선 객체
        self.reference_vline = None  # Reference Time 수직선 객체

        # Detail Window
        self.detail_window = None

        # GUI 컴포넌트 초기화
        self.init_ui()

    def init_ui(self):
        """GUI 컴포넌트 생성 및 배치"""
        # 메인 위젯 및 레이아웃
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ===== 좌측 컨트롤 패널 =====
        left_panel = QWidget()
        left_panel.setFixedWidth(250)
        # 배경색 설정 (#4472C4)
        palette = left_panel.palette()
        palette.setColor(QPalette.Window, QColor(68, 114, 196))
        left_panel.setAutoFillBackground(True)
        left_panel.setPalette(palette)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)

        # 1. 파일로딩 버튼
        self.load_button = QPushButton("파일로딩")
        self.load_button.setFixedSize(150, 40)
        self.load_button.clicked.connect(self.load_file)
        left_layout.addWidget(self.load_button)

        # 2. 파장 입력 필드 (3개)
        self.wavelength_inputs = []
        self.wavelength_checkboxes = []
        default_wavelengths = [486.1, 656.3, 0.0]

        for i, default_wl in enumerate(default_wavelengths, 1):
            # 레이블
            label = QLabel(f"파장{i} (nm)")
            label.setStyleSheet("color: white;")
            left_layout.addWidget(label)

            # 파장 입력 + 체크박스 수평 레이아웃
            wl_layout = QHBoxLayout()
            wl_layout.setSpacing(5)

            # SpinBox
            spinbox = QDoubleSpinBox()
            spinbox.setFixedSize(150, 30)
            spinbox.setRange(200.0, 800.0)
            spinbox.setSingleStep(0.5)
            spinbox.setDecimals(1)
            spinbox.setValue(default_wl)
            spinbox.setKeyboardTracking(False)
            spinbox.editingFinished.connect(self.on_wavelength_changed)

            # CheckBox
            checkbox = QCheckBox()
            checkbox.setFixedSize(20, 20)
            checkbox.setChecked(default_wl != 0.0)  # 값이 0이 아니면 체크
            checkbox.stateChanged.connect(self.on_wavelength_changed)

            wl_layout.addWidget(spinbox)
            wl_layout.addWidget(checkbox)
            wl_layout.addStretch()

            left_layout.addLayout(wl_layout)

            self.wavelength_inputs.append(spinbox)
            self.wavelength_checkboxes.append(checkbox)

        # 3. 시간 입력 필드
        time_label = QLabel("시간 (sec)")
        time_label.setStyleSheet("color: white;")
        left_layout.addWidget(time_label)

        self.time_spinbox = QDoubleSpinBox()
        self.time_spinbox.setFixedSize(150, 30)
        self.time_spinbox.setSingleStep(0.5)
        self.time_spinbox.setDecimals(2)
        self.time_spinbox.setEnabled(False)
        self.time_spinbox.setKeyboardTracking(False)
        self.time_spinbox.editingFinished.connect(self.on_time_changed)
        left_layout.addWidget(self.time_spinbox)

        # 4. Reference Time 입력 필드
        ref_time_label = QLabel("Reference Time (sec)")
        ref_time_label.setStyleSheet("color: white;")
        left_layout.addWidget(ref_time_label)

        self.reference_spinbox = QDoubleSpinBox()
        self.reference_spinbox.setFixedSize(150, 30)
        self.reference_spinbox.setSingleStep(0.5)
        self.reference_spinbox.setDecimals(2)
        self.reference_spinbox.setEnabled(False)
        self.reference_spinbox.setKeyboardTracking(False)
        self.reference_spinbox.editingFinished.connect(self.on_reference_changed)
        left_layout.addWidget(self.reference_spinbox)

        # 5. Pearson Correlation Detail 체크박스
        self.detail_checkbox = QCheckBox("Pearson Correlation Detail")
        self.detail_checkbox.setStyleSheet("color: white; font-size: 11px;")
        self.detail_checkbox.stateChanged.connect(self.on_detail_checkbox_changed)
        left_layout.addWidget(self.detail_checkbox)

        left_layout.addStretch()

        # ===== 우측 그래프 영역 =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 그래프 A: 스펙트럼 뷰어
        self.figure_a = Figure()
        self.figure_a.set_constrained_layout(True)
        self.canvas_a = FigureCanvas(self.figure_a)
        self.ax_spectrum = self.figure_a.add_subplot(111)
        right_layout.addWidget(self.canvas_a, stretch=1)

        # 그래프 B: 시계열 뷰어
        self.figure_b = Figure()
        self.figure_b.set_constrained_layout(True)
        self.canvas_b = FigureCanvas(self.figure_b)
        self.ax_timeseries = self.figure_b.add_subplot(111)
        # 클릭 이벤트 연결 (기존)
        self.canvas_b.mpl_connect('button_press_event', self.on_graph_click)
        right_layout.addWidget(self.canvas_b, stretch=1)

        # 메인 레이아웃에 패널 추가
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, stretch=1)

        # 드래그 이벤트 설정
        self.setup_drag_events()

        # 초기 상태 그래프 표시
        self.show_empty_graphs()

    def show_empty_graphs(self):
        """초기 상태: 빈 그래프 표시"""
        # 그래프 A
        self.ax_spectrum.clear()
        self.ax_spectrum.set_xlim(200, 800)
        self.ax_spectrum.set_ylim(0, 1)
        self.ax_spectrum.set_xlabel("Wavelength (nm)")
        self.ax_spectrum.set_ylabel("Emission Intensity (a.u.)")
        self.ax_spectrum.set_title("Spectrum at t = 0.00s")
        self.ax_spectrum.grid(True, linestyle='--', alpha=0.3, color='lightgray')
        self.ax_spectrum.text(
            500, 0.5, "데이터를 로드하세요",
            ha='center', va='center', fontsize=12, color='gray'
        )
        self.canvas_a.draw()

        # 그래프 B
        self.ax_timeseries.clear()
        self.ax_timeseries.set_xlim(0, 1)
        self.ax_timeseries.set_ylim(0, 1)
        self.ax_timeseries.set_xlabel("Run Time (sec)")
        self.ax_timeseries.set_ylabel("Intensity (a.u.)")
        self.ax_timeseries.set_title("Time Series & Correlation")
        self.ax_timeseries.grid(True, linestyle='--', alpha=0.3, color='lightgray')
        self.ax_timeseries.text(
            0.5, 0.5, "데이터를 로드하세요",
            ha='center', va='center', fontsize=12, color='gray'
        )
        self.canvas_b.draw()

    def load_file(self):
        """.dat 파일 로드"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "파일 선택", "", "Data Files (*.dat);;All Files (*)"
        )

        if not file_path:
            return

        # 파일 형식 검증
        if not file_path.endswith('.dat'):
            QMessageBox.warning(
                self, "파일 형식 오류",
                "파일 형식 오류: .dat 파일만 지원됩니다."
            )
            return

        try:
            # 데이터 로드
            self.data = pd.read_csv(file_path, sep='\t', encoding='utf-8')

            # 데이터 검증
            if self.data.empty or len(self.data.columns) < 3:
                QMessageBox.warning(
                    self, "데이터 오류",
                    "데이터 오류: 유효한 데이터가 없습니다."
                )
                self.data = None
                return

            # 파장 배열 생성 (200.0 ~ 800.0, 0.5 간격)
            self.wavelengths_data = np.arange(200.0, 800.5, 0.5)

            # Run Time 범위 설정
            run_times = self.data.iloc[:, 1].values
            min_time = run_times.min()
            max_time = run_times.max()

            # 시간 SpinBox 범위 설정 및 활성화
            self.time_spinbox.setRange(min_time, max_time)
            self.time_spinbox.setValue(min_time)
            self.time_spinbox.setEnabled(True)

            # Reference Time 초기화
            self.reference_spinbox.setRange(min_time, max_time)
            self.reference_spinbox.setValue(min_time)
            self.reference_spinbox.setEnabled(True)

            self.current_time = min_time
            self.reference_time = min_time

            # 그래프 업데이트
            self.update_spectrum_graph()
            self.update_timeseries_graph()

        except Exception as e:
            QMessageBox.warning(
                self, "파일 읽기 실패",
                f"파일 읽기 실패: {str(e)}"
            )
            self.data = None

    def get_intensity_at_wavelength(self, spectrum_row, target_wavelength):
        """
        target_wavelength ± 1nm 범위의 평균 intensity 반환

        Parameters:
        - spectrum_row: 스펙트럼 데이터 행 (1201개 포인트)
        - target_wavelength: 대상 파장 (nm)

        Returns:
        - 평균 intensity 값
        """
        center_idx = int((target_wavelength - 200.0) / 0.5)
        indices = [center_idx + i for i in range(-2, 3)]  # -2, -1, 0, 1, 2
        valid_indices = [i for i in indices if 0 <= i < 1201]
        return np.mean([spectrum_row[i] for i in valid_indices])

    def calculate_correlation(self, ref_spectrum, current_spectrum, wavelengths):
        """
        선택된 파장들 주변 ±10nm 범위만 사용하여 Pearson Correlation 계산

        Parameters:
        - ref_spectrum: Reference 시점의 전체 스펙트럼 (1201 포인트)
        - current_spectrum: 현재 시점의 전체 스펙트럼 (1201 포인트)
        - wavelengths: 선택된 파장 리스트 (체크된 것만)

        Returns:
        - r: Pearson correlation coefficient (-1 ~ 1)
        """
        if len(wavelengths) == 0:
            return 0.0

        indices = set()
        for wl in wavelengths:
            center_idx = int((wl - 200.0) / 0.5)
            # ±10nm = ±20 indices (0.5nm 간격)
            for i in range(center_idx - 20, center_idx + 21):
                if 0 <= i < 1201:
                    indices.add(i)

        indices = sorted(list(indices))
        x = np.array([ref_spectrum[i] for i in indices])
        y = np.array([current_spectrum[i] for i in indices])

        # Pearson correlation 계산
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sqrt(np.sum((x - x_mean)**2) * np.sum((y - y_mean)**2))

        return numerator / denominator if denominator != 0 else 0.0

    def get_spectrum_at_time(self, time_value):
        """
        주어진 시간에 가장 가까운 스펙트럼 데이터 반환

        Parameters:
        - time_value: 시간 (초)

        Returns:
        - spectrum: 스펙트럼 데이터 (1201 포인트)
        """
        if self.data is None:
            return None

        run_times = self.data.iloc[:, 1].values
        idx = np.argmin(np.abs(run_times - time_value))
        # 열 2부터 1202까지가 스펙트럼 데이터
        spectrum = self.data.iloc[idx, 2:].values.astype(float)
        return spectrum

    def get_selected_wavelengths(self):
        """체크된 파장만 반환"""
        wavelengths = []
        for i in range(3):
            if self.wavelength_checkboxes[i].isChecked():
                wl = self.wavelength_inputs[i].value()
                if wl > 0:
                    wavelengths.append(wl)
        return wavelengths

    def calculate_correlation_single_wavelength(self, ref_spectrum, current_spectrum, wavelength):
        """
        단일 파장 기준 ±10nm 범위의 Pearson Correlation 계산

        Parameters:
        - ref_spectrum: Reference 시점 스펙트럼 (1201 포인트)
        - current_spectrum: 현재 시점 스펙트럼 (1201 포인트)
        - wavelength: 기준 파장 (nm)

        Returns:
        - r: Pearson correlation coefficient (-1 ~ 1)
        """
        center_idx = int((wavelength - 200.0) / 0.5)

        # ±10nm = ±20 인덱스
        start_idx = max(0, center_idx - 20)
        end_idx = min(1200, center_idx + 20)

        x = np.array(ref_spectrum[start_idx:end_idx + 1])
        y = np.array(current_spectrum[start_idx:end_idx + 1])

        # Pearson correlation
        x_mean, y_mean = np.mean(x), np.mean(y)
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sqrt(np.sum((x - x_mean)**2) * np.sum((y - y_mean)**2))

        return numerator / denominator if denominator != 0 else 0.0

    def update_spectrum_graph(self):
        """그래프 A 업데이트: 스펙트럼 뷰어"""
        if self.data is None:
            return

        self.ax_spectrum.clear()

        # 현재 시간의 스펙트럼 데이터 가져오기
        spectrum = self.get_spectrum_at_time(self.current_time)

        if spectrum is None or len(spectrum) != 1201:
            return

        # 스펙트럼 플롯
        self.ax_spectrum.plot(
            self.wavelengths_data, spectrum,
            color='#1f77b4', linewidth=1.5
        )

        # 선택된 파장 하이라이트 (±1nm 범위)
        selected_wavelengths = self.get_selected_wavelengths()
        colors = ['red', 'green', 'blue']

        for i, wl in enumerate(selected_wavelengths):
            color = colors[i % len(colors)]
            self.ax_spectrum.axvspan(
                wl - 1.0, wl + 1.0,
                alpha=0.3, color=color
            )

        # 축 설정
        self.ax_spectrum.set_xlim(200, 800)
        self.ax_spectrum.set_xlabel("Wavelength (nm)")
        self.ax_spectrum.set_ylabel("Emission Intensity (a.u.)")
        self.ax_spectrum.set_title(f"Spectrum at t = {self.current_time:.2f}s")
        self.ax_spectrum.grid(True, linestyle='--', alpha=0.3, color='lightgray')

        self.canvas_a.draw()

    def update_timeseries_graph(self):
        """그래프 B 업데이트: 시계열 뷰어"""
        if self.data is None:
            return

        self.ax_timeseries.clear()

        # 이중 Y축 생성
        ax_corr = self.ax_timeseries.twinx()

        run_times = self.data.iloc[:, 1].values
        selected_wavelengths = self.get_selected_wavelengths()

        # Reference 및 현재 스펙트럼 가져오기
        ref_spectrum = self.get_spectrum_at_time(self.reference_time)
        current_spectrum = self.get_spectrum_at_time(self.current_time)

        # Correlation Score 텍스트 객체 리스트 (adjustText용)
        texts = []

        # 파장별 시계열 데이터 플롯 (좌측 Y축)
        colors = ['tab:blue', 'tab:orange', 'tab:green']
        for i, wl in enumerate(selected_wavelengths):
            intensities = []
            for _, row in self.data.iterrows():
                spectrum = row.iloc[2:].values.astype(float)
                intensity = self.get_intensity_at_wavelength(spectrum, wl)
                intensities.append(intensity)

            color = colors[i % len(colors)]
            self.ax_timeseries.plot(
                run_times, intensities,
                label=f"{wl:.1f} nm",
                color=color, linewidth=1.5
            )

            # 각 파장별 Correlation Score 계산 및 표시
            if ref_spectrum is not None and current_spectrum is not None:
                r_value = self.calculate_correlation_single_wavelength(
                    ref_spectrum, current_spectrum, wl
                )

                # 현재 시점에서의 Intensity 값 (Y 좌표)
                current_intensity = self.get_intensity_at_wavelength(current_spectrum, wl)

                # 텍스트 객체 생성 (annotate 대신 text 사용)
                txt = self.ax_timeseries.text(
                    self.current_time, current_intensity,
                    f'r={r_value:.3f}',
                    fontsize=10,
                    fontweight='bold',
                    color=color,
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                              edgecolor=color, alpha=0.8)
                )
                texts.append(txt)

        # 현재 시간 수직선 (빨간색 점선) - 객체 저장
        self.current_vline = self.ax_timeseries.axvline(
            x=self.current_time,
            color='#FF0000', linestyle='--', linewidth=1.5,
            label='Current Time'
        )

        # Reference 시간 수직선 (회색 점선, 스타일 변경) - 객체 저장
        self.reference_vline = self.ax_timeseries.axvline(
            x=self.reference_time,
            color='#555555', linestyle='--', linewidth=1.5,
            alpha=1.0, label='Reference Time'
        )

        # adjustText로 텍스트 겹침 자동 조정
        if ADJUSTTEXT_AVAILABLE and texts:
            adjust_text(
                texts,
                ax=self.ax_timeseries,
                arrowprops=dict(arrowstyle='-', color='gray', lw=0.5),
                expand_points=(1.5, 1.5),
                force_points=(0.5, 0.5)
            )

        # 축 설정
        self.ax_timeseries.set_xlabel("Run Time (sec)")
        self.ax_timeseries.set_ylabel("Intensity (a.u.)")
        self.ax_timeseries.set_title("Time Series & Correlation")
        self.ax_timeseries.grid(True, linestyle='--', alpha=0.3, color='lightgray')
        self.ax_timeseries.legend(loc='upper left')

        # 우측 Y축 설정 (Correlation Score)
        ax_corr.set_ylabel("Correlation Score")
        ax_corr.set_ylim(-1.0, 1.0)

        self.canvas_b.draw()

    def on_time_changed(self):
        """시간 SpinBox Enter 입력 핸들러"""
        if self.data is None:
            return
        value = self.time_spinbox.value()
        self.current_time = value
        self.update_spectrum_graph()
        self.update_timeseries_graph()
        self.update_detail_window()

    def on_reference_changed(self):
        """Reference Time SpinBox Enter 입력 핸들러"""
        if self.data is None:
            return
        value = self.reference_spinbox.value()
        self.reference_time = value
        self.update_timeseries_graph()
        self.update_detail_window()

    def on_wavelength_changed(self):
        """파장 변경 핸들러"""
        # 데이터가 로드되지 않았으면 무시
        if self.data is None:
            return

        self.update_spectrum_graph()
        self.update_timeseries_graph()
        self.update_detail_window()

    def on_graph_click(self, event):
        """그래프 클릭 이벤트 핸들러"""
        if event.inaxes != self.ax_timeseries:
            return

        if event.xdata is None:
            return

        clicked_time = event.xdata

        # Shift+클릭: Reference Time 설정
        if event.key == 'shift':
            self.reference_spinbox.setValue(clicked_time)
        else:
            # 일반 클릭: 현재 시간 설정
            self.time_spinbox.setValue(clicked_time)

    def setup_drag_events(self):
        """창2 그래프에 드래그 이벤트 연결"""
        # 기존 이벤트 연결 제거 후 재연결
        self.canvas_b.mpl_connect('button_press_event', self.on_drag_press)
        self.canvas_b.mpl_connect('button_release_event', self.on_drag_release)
        self.canvas_b.mpl_connect('motion_notify_event', self.on_drag_motion)

        # 드래그 상태 초기화
        self.dragging_line = None

    def on_drag_press(self, event):
        """마우스 버튼 누름 - 드래그 시작"""
        if event.inaxes != self.ax_timeseries:
            return
        if self.data is None:
            return
        if event.xdata is None:
            return

        # 현재 수직선 위치
        current_time = self.time_spinbox.value()
        ref_time = self.reference_spinbox.value()

        # X축 범위 기준 허용 오차 계산 (전체 범위의 2%)
        x_min, x_max = self.ax_timeseries.get_xlim()
        tolerance = (x_max - x_min) * 0.02

        # 어떤 수직선을 클릭했는지 판단
        if abs(event.xdata - current_time) < tolerance:
            self.dragging_line = 'current'
        elif abs(event.xdata - ref_time) < tolerance:
            self.dragging_line = 'reference'
        else:
            self.dragging_line = None

    def on_drag_release(self, event):
        """마우스 버튼 릴리즈 - 드래그 종료"""
        if self.dragging_line is None:
            return
        if event.xdata is None:
            self.dragging_line = None
            return

        # 데이터 범위 내로 클램프
        times = self.data.iloc[:, 1].values
        new_time = float(np.clip(event.xdata, times.min(), times.max()))

        # SpinBox 업데이트 (블로킹 시그널로 무한루프 방지)
        if self.dragging_line == 'current':
            self.time_spinbox.blockSignals(True)
            self.time_spinbox.setValue(new_time)
            self.time_spinbox.blockSignals(False)
            self.on_time_changed()
        elif self.dragging_line == 'reference':
            self.reference_spinbox.blockSignals(True)
            self.reference_spinbox.setValue(new_time)
            self.reference_spinbox.blockSignals(False)
            self.on_reference_changed()

        self.dragging_line = None
        # 커서 복원
        QApplication.restoreOverrideCursor()

    def on_drag_motion(self, event):
        """마우스 이동 - 커서 변경"""
        if self.data is None:
            return

        # 드래그 중이 아닐 때만 커서 변경 로직 실행
        if self.dragging_line is not None:
            return

        # axes 밖이면 기본 커서
        if event.inaxes != self.ax_timeseries or event.xdata is None:
            QApplication.restoreOverrideCursor()
            return

        current_time = self.time_spinbox.value()
        ref_time = self.reference_spinbox.value()

        x_min, x_max = self.ax_timeseries.get_xlim()
        tolerance = (x_max - x_min) * 0.02

        # 수직선 근처면 좌우 화살표 커서
        if abs(event.xdata - current_time) < tolerance or abs(event.xdata - ref_time) < tolerance:
            QApplication.setOverrideCursor(QCursor(Qt.SizeHorCursor))
        else:
            QApplication.restoreOverrideCursor()

    def find_nearest_time_index(self, time_value):
        """주어진 시간에 가장 가까운 인덱스 반환"""
        if self.data is None:
            return 0
        run_times = self.data.iloc[:, 1].values
        idx = np.argmin(np.abs(run_times - time_value))
        return idx

    def get_spectrum_at_index(self, idx):
        """인덱스에 해당하는 스펙트럼 반환"""
        if self.data is None or idx >= len(self.data):
            return None
        spectrum = self.data.iloc[idx, 2:].values.astype(float)
        return spectrum

    def on_detail_checkbox_changed(self, state):
        """Pearson Correlation Detail 체크박스 상태 변경"""
        if state == Qt.Checked:
            self.show_detail_window()
        else:
            self.hide_detail_window()

    def show_detail_window(self):
        """창3 표시"""
        if not hasattr(self, 'detail_window') or self.detail_window is None:
            self.detail_window = CorrelationDetailWindow(self)
            self.detail_window.closed.connect(self.on_detail_window_closed)

        self.update_detail_window()
        self.detail_window.show()
        self.detail_window.raise_()

    def hide_detail_window(self):
        """창3 숨김"""
        if hasattr(self, 'detail_window') and self.detail_window is not None:
            self.detail_window.hide()

    def on_detail_window_closed(self):
        """창3 닫힘 시 체크박스 해제"""
        self.detail_checkbox.setChecked(False)

    def update_detail_window(self):
        """창3 내용 업데이트"""
        if not hasattr(self, 'detail_window') or self.detail_window is None:
            return
        if not self.detail_window.isVisible():
            return
        if self.data is None:
            return

        # 부모 객체(self)를 전달하여 데이터 접근
        self.detail_window.update_content(self)


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    window = OESAnalyzer()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
