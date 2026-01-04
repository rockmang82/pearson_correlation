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
    QLabel, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


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
        # 클릭 이벤트 연결
        self.canvas_b.mpl_connect('button_press_event', self.on_graph_click)
        right_layout.addWidget(self.canvas_b, stretch=1)

        # 메인 레이아웃에 패널 추가
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, stretch=1)

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

                # Current Time 수직선과 파장 라인 교차점에 Correlation Score 표시
                self.ax_timeseries.annotate(
                    f'r={r_value:.3f}',
                    xy=(self.current_time, current_intensity),
                    xytext=(5, 5 + i * 15),  # 파장별로 Y 오프셋 적용하여 겹침 방지
                    textcoords='offset points',
                    fontsize=10,
                    fontweight='bold',
                    color=color,
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                              edgecolor=color, alpha=0.8)
                )

        # 현재 시간 수직선 (빨간색 점선)
        self.ax_timeseries.axvline(
            self.current_time,
            color='#FF0000', linestyle='--', linewidth=1.5,
            label='Current Time'
        )

        # Reference 시간 수직선 (회색 점선)
        self.ax_timeseries.axvline(
            self.reference_time,
            color='#555555', linestyle=':', linewidth=1.0,
            alpha=0.5, label='Reference Time'
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

    def on_reference_changed(self):
        """Reference Time SpinBox Enter 입력 핸들러"""
        if self.data is None:
            return
        value = self.reference_spinbox.value()
        self.reference_time = value
        self.update_timeseries_graph()

    def on_wavelength_changed(self):
        """파장 변경 핸들러"""
        # 데이터가 로드되지 않았으면 무시
        if self.data is None:
            return

        self.update_spectrum_graph()
        self.update_timeseries_graph()

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


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    window = OESAnalyzer()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
