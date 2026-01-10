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
    QLabel, QFileDialog, QMessageBox, QTabWidget, QScrollArea,
    QGroupBox, QSizePolicy, QFrame, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPalette, QColor, QCursor, QDoubleValidator
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


class CollapsibleSection(QWidget):
    """접기/펼치기 가능한 섹션 위젯"""

    def __init__(self, title="", parent=None):
        super().__init__(parent)

        self.toggle_button = QPushButton(title)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px;
                background-color: #4472C4;
                color: white;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3562B4;
            }
        """)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.clicked.connect(self.toggle_content)

        self.content_area = QWidget()
        self.content_area.setVisible(False)
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 5, 10, 5)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)

    def toggle_content(self):
        """내용 영역 토글"""
        is_checked = self.toggle_button.isChecked()
        self.content_area.setVisible(is_checked)
        # 버튼 텍스트에 화살표 표시
        current_text = self.toggle_button.text()
        if current_text.startswith("▶ "):
            self.toggle_button.setText("▼ " + current_text[2:])
        elif current_text.startswith("▼ "):
            self.toggle_button.setText("▶ " + current_text[2:])

    def set_title(self, title):
        """제목 설정 (접힌 상태 화살표 포함)"""
        self.toggle_button.setText("▶ " + title)

    def add_widget(self, widget):
        """내용 영역에 위젯 추가"""
        self.content_layout.addWidget(widget)


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
                try:
                    wl = float(parent.wavelength_inputs[i].text())
                    if 200.0 <= wl <= 800.0 and wl > 0:
                        wavelengths_info.append(wl)
                except ValueError:
                    pass

        if not wavelengths_info:
            return

        times = parent.data.iloc[:, 1].values
        current_time = parent.time_spinbox.value()
        reference_time = parent.reference_spinbox.value()

        # Correlation Window 값 가져오기
        correlation_window = parent.correlation_window
        half_window = correlation_window / 2.0

        # 가장 가까운 시간 인덱스 찾기
        current_idx = int(np.argmin(np.abs(times - current_time)))
        ref_idx = int(np.argmin(np.abs(times - reference_time)))

        # 스펙트럼 데이터 가져오기
        ref_spectrum = parent.data.iloc[ref_idx, 2:].values.astype(float)
        current_spectrum = parent.data.iloc[current_idx, 2:].values.astype(float)

        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

        # ========================================
        # 탭 1: Overview (공식 + 요약 정보)
        # ========================================
        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)
        overview_layout.setContentsMargins(5, 5, 5, 5)

        # 스크롤 영역 추가 (개선)
        overview_scroll = QScrollArea()
        overview_scroll.setWidgetResizable(True)
        overview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        overview_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        overview_content = QWidget()
        overview_scroll_layout = QVBoxLayout(overview_content)
        overview_scroll_layout.setContentsMargins(5, 5, 5, 5)

        # Figure 크기 증가 (스크롤 가능하도록)
        overview_fig = Figure(figsize=(6, 10))
        overview_canvas = FigureCanvas(overview_fig)
        overview_canvas.setMinimumSize(400, 600)  # 최소 크기 설정
        overview_ax = overview_fig.add_subplot(111)
        overview_ax.axis('off')

        # 각 파장별 Correlation Score 계산
        wavelength_results = []
        for wl in wavelengths_info:
            start_idx, end_idx = parent.get_window_indices(wl)

            x = ref_spectrum[start_idx:end_idx + 1]
            y = current_spectrum[start_idx:end_idx + 1]

            x_mean = np.mean(x)
            y_mean = np.mean(y)
            numerator = np.sum((x - x_mean) * (y - y_mean))
            denom_x = np.sum((x - x_mean)**2)
            denom_y = np.sum((y - y_mean)**2)
            denominator = np.sqrt(denom_x * denom_y)
            r_value = numerator / denominator if denominator != 0 else 0.0

            wavelength_results.append({'wl': wl, 'r': r_value})

        # Overview 텍스트 (8pt 폰트)
        overview_text = (
            r"$\mathbf{Pearson\ Correlation\ Coefficient}$" + "\n\n"
            r"$r = \frac{\sum_{i=1}^{n}(x_i - \bar{x})(y_i - \bar{y})}{\sqrt{\sum_{i=1}^{n}(x_i - \bar{x})^2 \cdot \sum_{i=1}^{n}(y_i - \bar{y})^2}}$" + "\n\n"
            r"$\mathbf{Where:}$" + "\n"
            r"$x_i$ = Reference spectrum intensity at index $i$" + "\n"
            r"$y_i$ = Current spectrum intensity at index $i$" + "\n"
            r"$\bar{x}$ = Mean of reference spectrum" + "\n"
            r"$\bar{y}$ = Mean of current spectrum" + "\n"
            f"$n$ = Number of data points in ±{half_window:.1f}nm range" + "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            r"$\mathbf{Current\ Settings}$" + "\n\n"
            f"  Reference Time: {reference_time:.2f} sec\n"
            f"  Current Time: {current_time:.2f} sec\n"
            f"  Correlation Window: {correlation_window:.1f} nm (±{half_window:.1f} nm)\n"
            f"  Selected Wavelengths: {', '.join([f'{wl:.1f}' for wl in wavelengths_info])} nm\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            r"$\mathbf{Correlation\ Score\ Summary}$" + "\n\n"
        )
        for result in wavelength_results:
            overview_text += f"  λ = {result['wl']:.1f} nm:  r = {result['r']:.6f}\n"

        overview_ax.text(0.02, 0.98, overview_text,
                        transform=overview_ax.transAxes,
                        fontsize=8,
                        verticalalignment='top',
                        fontfamily='monospace')

        overview_fig.tight_layout()
        overview_scroll_layout.addWidget(overview_canvas)
        overview_scroll.setWidget(overview_content)
        overview_layout.addWidget(overview_scroll)

        self.tab_widget.addTab(overview_tab, "Overview")

        # ========================================
        # 탭 2+: 각 파장별 상세 계산 과정 (QLabel + HTML 사용)
        # ========================================
        self.ax.clear()

        for i, wl in enumerate(wavelengths_info):
            line_color = colors[i % len(colors)]

            # 파장별 탭 생성
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(3, 3, 3, 3)

            # 메인 스크롤 영역
            main_scroll = QScrollArea()
            main_scroll.setWidgetResizable(True)
            main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

            scroll_content = QWidget()
            scroll_layout = QVBoxLayout(scroll_content)
            scroll_layout.setSpacing(8)
            scroll_layout.setContentsMargins(5, 5, 5, 5)

            # 동적 Window 범위 계산
            start_idx, end_idx = parent.get_window_indices(wl)

            # 파장 배열 생성
            wavelength_range = np.arange(200.0 + start_idx * 0.5, 200.0 + (end_idx + 1) * 0.5, 0.5)

            x = ref_spectrum[start_idx:end_idx + 1]
            y = current_spectrum[start_idx:end_idx + 1]
            n = len(x)

            # 통계값 계산
            x_mean = np.mean(x)
            y_mean = np.mean(y)
            x_std = np.std(x)
            y_std = np.std(y)

            # 개별 계산
            x_diff = x - x_mean
            y_diff = y - y_mean
            xy_product = x_diff * y_diff
            x_diff_sq = x_diff ** 2
            y_diff_sq = y_diff ** 2

            # 합계
            sum_xy = np.sum(xy_product)
            sum_x_sq = np.sum(x_diff_sq)
            sum_y_sq = np.sum(y_diff_sq)

            denominator_val = np.sqrt(sum_x_sq * sum_y_sq)
            r_value = sum_xy / denominator_val if denominator_val != 0 else 0.0

            # ===== 헤더 정보 =====
            header_label = QLabel(
                f"<div style='padding: 10px; background-color: #f0f0f0; border-radius: 5px;'>"
                f"<b style='font-size: 14px;'>λ = {wl:.1f} nm</b> "
                f"(Range: {wl-half_window:.1f} - {wl+half_window:.1f} nm)<br>"
                f"Reference Time: {reference_time:.2f} sec | Current Time: {current_time:.2f} sec<br>"
                f"Correlation Window: {correlation_window:.1f} nm | Data Points: {n}"
                f"</div>"
            )
            header_label.setWordWrap(True)
            scroll_layout.addWidget(header_label)

            # ===== 섹션 1: 데이터 테이블 (Collapsible + QLabel HTML) =====
            data_section = CollapsibleSection()
            data_section.set_title(f"Raw Data Table ({n} points)")

            # HTML 테이블 생성
            table_html = """
            <div style='font-family: monospace; font-size: 9px; padding: 5px;'>
            <table border='1' cellpadding='4' cellspacing='0' style='border-collapse: collapse; width: 100%;'>
            <tr style='background-color: #4472C4; color: white;'>
                <th>Idx</th><th>λ (nm)</th><th>xi (Ref)</th><th>yi (Cur)</th>
                <th>xi-x̄</th><th>yi-ȳ</th><th>(xi-x̄)(yi-ȳ)</th>
            </tr>
            """

            for j in range(n):
                wl_j = wavelength_range[j] if j < len(wavelength_range) else wl - half_window + j * 0.5
                bg_color = '#f9f9f9' if j % 2 == 0 else '#ffffff'
                table_html += f"""
                <tr style='background-color: {bg_color};'>
                    <td align='center'>{j}</td>
                    <td align='right'>{wl_j:.1f}</td>
                    <td align='right'>{x[j]:.2f}</td>
                    <td align='right'>{y[j]:.2f}</td>
                    <td align='right'>{x_diff[j]:.2f}</td>
                    <td align='right'>{y_diff[j]:.2f}</td>
                    <td align='right'>{xy_product[j]:.2f}</td>
                </tr>
                """

            table_html += "</table></div>"

            table_label = QLabel(table_html)
            table_label.setWordWrap(True)
            table_label.setTextFormat(Qt.RichText)

            # 테이블용 스크롤 영역
            table_scroll = QScrollArea()
            table_scroll.setWidgetResizable(True)
            table_scroll.setMinimumHeight(200)
            table_scroll.setMaximumHeight(350)
            table_scroll.setWidget(table_label)

            data_section.add_widget(table_scroll)
            scroll_layout.addWidget(data_section)

            # ===== 섹션 2: 통계 요약 (Collapsible + QLabel HTML) =====
            stats_section = CollapsibleSection()
            stats_section.set_title("Statistics Summary")

            stats_html = f"""
            <div style='font-family: monospace; font-size: 11px; padding: 10px; background-color: #fafafa; border-radius: 5px;'>
            <b style='color: #4472C4;'>Reference Spectrum (xi):</b><br>
            &nbsp;&nbsp;Sum: Σxi = {np.sum(x):.2f}<br>
            &nbsp;&nbsp;Mean: x̄ = Σxi/n = {np.sum(x):.2f}/{n} = <b>{x_mean:.4f}</b><br>
            &nbsp;&nbsp;Std: σx = {x_std:.4f}<br>
            &nbsp;&nbsp;Min: {np.min(x):.2f}<br>
            &nbsp;&nbsp;Max: {np.max(x):.2f}<br><br>

            <b style='color: #4472C4;'>Current Spectrum (yi):</b><br>
            &nbsp;&nbsp;Sum: Σyi = {np.sum(y):.2f}<br>
            &nbsp;&nbsp;Mean: ȳ = Σyi/n = {np.sum(y):.2f}/{n} = <b>{y_mean:.4f}</b><br>
            &nbsp;&nbsp;Std: σy = {y_std:.4f}<br>
            &nbsp;&nbsp;Min: {np.min(y):.2f}<br>
            &nbsp;&nbsp;Max: {np.max(y):.2f}<br>
            </div>
            """

            stats_label = QLabel(stats_html)
            stats_label.setWordWrap(True)
            stats_label.setTextFormat(Qt.RichText)

            data_section2 = QWidget()
            data_section2_layout = QVBoxLayout(data_section2)
            data_section2_layout.setContentsMargins(0, 0, 0, 0)
            data_section2_layout.addWidget(stats_label)

            stats_section.add_widget(data_section2)
            scroll_layout.addWidget(stats_section)

            # ===== 섹션 3: 계산 과정 (Collapsible + QLabel HTML) =====
            calc_section = CollapsibleSection()
            calc_section.set_title("Calculation Steps")

            calc_html = f"""
            <div style='font-family: monospace; font-size: 11px; padding: 10px; background-color: #fafafa; border-radius: 5px;'>

            <b style='color: #2E7D32;'>Step 1: Calculate Means</b><br>
            <hr style='border: 1px solid #ddd;'>
            &nbsp;&nbsp;x̄ = Σxi / n = {np.sum(x):.2f} / {n} = <b>{x_mean:.4f}</b><br>
            &nbsp;&nbsp;ȳ = Σyi / n = {np.sum(y):.2f} / {n} = <b>{y_mean:.4f}</b><br><br>

            <b style='color: #2E7D32;'>Step 2: Calculate Deviations</b><br>
            <hr style='border: 1px solid #ddd;'>
            &nbsp;&nbsp;(xi - x̄): range [{np.min(x_diff):.2f}, {np.max(x_diff):.2f}]<br>
            &nbsp;&nbsp;(yi - ȳ): range [{np.min(y_diff):.2f}, {np.max(y_diff):.2f}]<br><br>

            <b style='color: #2E7D32;'>Step 3: Calculate Sum of Squared Deviations</b><br>
            <hr style='border: 1px solid #ddd;'>
            &nbsp;&nbsp;Σ(xi - x̄)² = <b>{sum_x_sq:.4f}</b><br>
            &nbsp;&nbsp;Σ(yi - ȳ)² = <b>{sum_y_sq:.4f}</b><br><br>

            <b style='color: #2E7D32;'>Step 4: Calculate Covariance (numerator)</b><br>
            <hr style='border: 1px solid #ddd;'>
            &nbsp;&nbsp;Σ(xi - x̄)(yi - ȳ) = <b>{sum_xy:.4f}</b><br><br>

            <b style='color: #2E7D32;'>Step 5: Calculate Denominator</b><br>
            <hr style='border: 1px solid #ddd;'>
            &nbsp;&nbsp;√[Σ(xi - x̄)² × Σ(yi - ȳ)²]<br>
            &nbsp;&nbsp;= √[{sum_x_sq:.4f} × {sum_y_sq:.4f}]<br>
            &nbsp;&nbsp;= √[{sum_x_sq * sum_y_sq:.4f}]<br>
            &nbsp;&nbsp;= <b>{denominator_val:.4f}</b><br><br>

            <b style='color: #2E7D32;'>Step 6: Final Calculation</b><br>
            <hr style='border: 1px solid #ddd;'>
            &nbsp;&nbsp;r = Σ(xi - x̄)(yi - ȳ) / √[Σ(xi - x̄)² × Σ(yi - ȳ)²]<br>
            &nbsp;&nbsp;r = {sum_xy:.4f} / {denominator_val:.4f}<br>
            &nbsp;&nbsp;<span style='font-size: 14px; color: #1565C0;'><b>r = {r_value:.6f}</b></span><br>

            </div>
            """

            calc_label = QLabel(calc_html)
            calc_label.setWordWrap(True)
            calc_label.setTextFormat(Qt.RichText)

            calc_widget = QWidget()
            calc_widget_layout = QVBoxLayout(calc_widget)
            calc_widget_layout.setContentsMargins(0, 0, 0, 0)
            calc_widget_layout.addWidget(calc_label)

            calc_section.add_widget(calc_widget)
            scroll_layout.addWidget(calc_section)

            # ===== 섹션 4: 최종 결과 (항상 표시) =====
            result_label = QLabel(
                f"<div style='padding: 15px; background-color: #e8f4e8; border: 2px solid #4CAF50; border-radius: 5px; margin-top: 10px;'>"
                f"<span style='font-size: 16px; color: #2E7D32; font-weight: bold;'>"
                f"Correlation Score (r) = {r_value:.6f}</span>"
                f"</div>"
            )
            result_label.setTextFormat(Qt.RichText)
            scroll_layout.addWidget(result_label)

            # 하단 여백 추가
            scroll_layout.addStretch()

            # 스크롤 영역에 컨텐츠 설정
            scroll_content.setLayout(scroll_layout)
            main_scroll.setWidget(scroll_content)
            tab_layout.addWidget(main_scroll)

            self.tab_widget.addTab(tab, f"λ={wl:.1f}nm")

            # ===== 우측 그래프: Correlation Score 시계열 =====
            r_values = []
            for t_idx in range(len(times)):
                t_spectrum = parent.data.iloc[t_idx, 2:].values.astype(float)
                t_y = t_spectrum[start_idx:end_idx + 1]
                t_y_mean = np.mean(t_y)
                t_num = np.sum((x - x_mean) * (t_y - t_y_mean))
                t_denom_y = np.sum((t_y - t_y_mean)**2)
                t_denom = np.sqrt(sum_x_sq * t_denom_y)
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
        self.ax.set_title(f"Correlation Score (Window: {correlation_window:.1f}nm)")
        self.ax.legend(loc='upper right', fontsize=8)
        self.ax.grid(True, linestyle='--', alpha=0.3)

        self.canvas.draw()

    def closeEvent(self, event):
        """창 닫힘 이벤트"""
        self.closed.emit()
        event.accept()


class FullSpectrumDetailWindow(QWidget):
    """창4: Full Spectrum Correlation 상세 정보 팝업"""

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.parent_window = parent
        self.init_ui()

    def init_ui(self):
        """GUI 초기화"""
        self.setWindowTitle("Full Spectrum Correlation Detail")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)

        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 탭 위젯
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ccc; background: white; }
            QTabBar::tab { padding: 8px 16px; }
            QTabBar::tab:selected { background: #4472C4; color: white; }
        """)
        main_layout.addWidget(self.tab_widget)

    def update_content(self, parent):
        """내용 업데이트"""
        if parent.data is None:
            return

        self.tab_widget.clear()

        times = parent.data.iloc[:, 1].values
        current_time = parent.time_spinbox.value()
        reference_time = parent.reference_spinbox.value()

        current_idx = int(np.argmin(np.abs(times - current_time)))
        ref_idx = int(np.argmin(np.abs(times - reference_time)))

        ref_spectrum = parent.data.iloc[ref_idx, 2:].values.astype(float)
        current_spectrum = parent.data.iloc[current_idx, 2:].values.astype(float)

        n = len(ref_spectrum)  # 1201

        # 통계 계산
        x = ref_spectrum
        y = current_spectrum
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        x_std = np.std(x)
        y_std = np.std(y)

        x_diff = x - x_mean
        y_diff = y - y_mean
        xy_product = x_diff * y_diff

        sum_xy = np.sum(xy_product)
        sum_x_sq = np.sum(x_diff ** 2)
        sum_y_sq = np.sum(y_diff ** 2)

        denominator_val = np.sqrt(sum_x_sq * sum_y_sq)
        r_value = sum_xy / denominator_val if denominator_val != 0 else 0.0

        # ========================================
        # 탭 1: Formula & Parameters
        # ========================================
        formula_tab = QWidget()
        formula_layout = QVBoxLayout(formula_tab)
        formula_layout.setContentsMargins(10, 10, 10, 10)

        formula_scroll = QScrollArea()
        formula_scroll.setWidgetResizable(True)
        formula_content = QWidget()
        formula_scroll_layout = QVBoxLayout(formula_content)

        formula_html = f"""
        <div style='font-family: Arial; font-size: 11px; padding: 10px;'>

        <h2 style='color: #4472C4;'>Full Spectrum Pearson Correlation Coefficient</h2>

        <div style='background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0;'>
        <p style='font-size: 14px; text-align: center;'>
        <b>r = Σ(xᵢ - x̄)(yᵢ - ȳ) / √[Σ(xᵢ - x̄)² × Σ(yᵢ - ȳ)²]</b>
        </p>
        </div>

        <h3 style='color: #2E7D32;'>Parameters</h3>
        <hr>

        <table style='width: 100%; border-collapse: collapse;'>
        <tr style='background-color: #e3f2fd;'>
            <td style='padding: 8px; border: 1px solid #ddd;'><b>Symbol</b></td>
            <td style='padding: 8px; border: 1px solid #ddd;'><b>Name</b></td>
            <td style='padding: 8px; border: 1px solid #ddd;'><b>Description</b></td>
        </tr>
        <tr>
            <td style='padding: 8px; border: 1px solid #ddd;'>xᵢ</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Reference Spectrum Intensity</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Reference 시점의 파장별 발광 강도 (i = 1 to 1201)</td>
        </tr>
        <tr style='background-color: #f9f9f9;'>
            <td style='padding: 8px; border: 1px solid #ddd;'>yᵢ</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Current Spectrum Intensity</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>현재 시점의 파장별 발광 강도 (i = 1 to 1201)</td>
        </tr>
        <tr>
            <td style='padding: 8px; border: 1px solid #ddd;'>x̄</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Reference Mean</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Reference 스펙트럼의 평균값</td>
        </tr>
        <tr style='background-color: #f9f9f9;'>
            <td style='padding: 8px; border: 1px solid #ddd;'>ȳ</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Current Mean</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>현재 스펙트럼의 평균값</td>
        </tr>
        <tr>
            <td style='padding: 8px; border: 1px solid #ddd;'>n</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Number of Data Points</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>전체 스펙트럼 데이터 포인트 수 (1201개, 200-800nm)</td>
        </tr>
        <tr style='background-color: #f9f9f9;'>
            <td style='padding: 8px; border: 1px solid #ddd;'>r</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Correlation Coefficient</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>상관계수 (-1 ≤ r ≤ 1)</td>
        </tr>
        </table>

        <h3 style='color: #2E7D32; margin-top: 20px;'>Interpretation</h3>
        <hr>
        <ul>
            <li><b>r = 1</b>: 완벽한 양의 상관관계 (동일한 스펙트럼)</li>
            <li><b>r = 0</b>: 상관관계 없음</li>
            <li><b>r = -1</b>: 완벽한 음의 상관관계</li>
        </ul>

        <h3 style='color: #2E7D32; margin-top: 20px;'>Current Settings</h3>
        <hr>
        <p>
        <b>Reference Time:</b> {reference_time:.2f} sec<br>
        <b>Current Time:</b> {current_time:.2f} sec<br>
        <b>Wavelength Range:</b> 200.0 - 800.0 nm<br>
        <b>Data Points (n):</b> {n}
        </p>

        <div style='background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin-top: 15px; border: 2px solid #4CAF50;'>
        <p style='font-size: 16px; text-align: center; margin: 0;'>
        <b style='color: #2E7D32;'>Current Full Spectrum r = {r_value:.6f}</b>
        </p>
        </div>

        </div>
        """

        formula_label = QLabel(formula_html)
        formula_label.setWordWrap(True)
        formula_label.setTextFormat(Qt.RichText)
        formula_scroll_layout.addWidget(formula_label)
        formula_scroll.setWidget(formula_content)
        formula_layout.addWidget(formula_scroll)

        self.tab_widget.addTab(formula_tab, "Formula & Parameters")

        # ========================================
        # 탭 2: Calculation Details
        # ========================================
        calc_tab = QWidget()
        calc_layout = QVBoxLayout(calc_tab)
        calc_layout.setContentsMargins(10, 10, 10, 10)

        calc_scroll = QScrollArea()
        calc_scroll.setWidgetResizable(True)
        calc_content = QWidget()
        calc_scroll_layout = QVBoxLayout(calc_content)

        calc_html = f"""
        <div style='font-family: monospace; font-size: 11px; padding: 10px;'>

        <h3 style='color: #4472C4;'>Full Spectrum Correlation Calculation</h3>
        <p>
        <b>Reference Time:</b> {reference_time:.2f} sec<br>
        <b>Current Time:</b> {current_time:.2f} sec<br>
        <b>Wavelength Range:</b> 200.0 - 800.0 nm (0.5nm interval)<br>
        <b>Data Points:</b> n = {n}
        </p>
        <hr>

        <h4 style='color: #2E7D32;'>Statistics Summary</h4>
        <div style='background-color: #fafafa; padding: 10px; border-radius: 5px;'>
        <b>Reference Spectrum (xᵢ):</b><br>
        &nbsp;&nbsp;Sum: Σxᵢ = {np.sum(x):.2f}<br>
        &nbsp;&nbsp;Mean: x̄ = {x_mean:.4f}<br>
        &nbsp;&nbsp;Std Dev: σx = {x_std:.4f}<br>
        &nbsp;&nbsp;Min: {np.min(x):.2f}<br>
        &nbsp;&nbsp;Max: {np.max(x):.2f}<br><br>

        <b>Current Spectrum (yᵢ):</b><br>
        &nbsp;&nbsp;Sum: Σyᵢ = {np.sum(y):.2f}<br>
        &nbsp;&nbsp;Mean: ȳ = {y_mean:.4f}<br>
        &nbsp;&nbsp;Std Dev: σy = {y_std:.4f}<br>
        &nbsp;&nbsp;Min: {np.min(y):.2f}<br>
        &nbsp;&nbsp;Max: {np.max(y):.2f}<br>
        </div>

        <h4 style='color: #2E7D32; margin-top: 15px;'>Step-by-Step Calculation</h4>

        <div style='background-color: #fff8e1; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 1: Calculate Means</b><br>
        &nbsp;&nbsp;x̄ = Σxᵢ / n = {np.sum(x):.2f} / {n} = <b>{x_mean:.4f}</b><br>
        &nbsp;&nbsp;ȳ = Σyᵢ / n = {np.sum(y):.2f} / {n} = <b>{y_mean:.4f}</b>
        </div>

        <div style='background-color: #e3f2fd; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 2: Calculate Deviations</b><br>
        &nbsp;&nbsp;(xᵢ - x̄): range [{np.min(x_diff):.2f}, {np.max(x_diff):.2f}]<br>
        &nbsp;&nbsp;(yᵢ - ȳ): range [{np.min(y_diff):.2f}, {np.max(y_diff):.2f}]
        </div>

        <div style='background-color: #f3e5f5; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 3: Calculate Sum of Squared Deviations</b><br>
        &nbsp;&nbsp;Σ(xᵢ - x̄)² = <b>{sum_x_sq:.4f}</b><br>
        &nbsp;&nbsp;Σ(yᵢ - ȳ)² = <b>{sum_y_sq:.4f}</b>
        </div>

        <div style='background-color: #e8f5e9; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 4: Calculate Covariance (Numerator)</b><br>
        &nbsp;&nbsp;Σ(xᵢ - x̄)(yᵢ - ȳ) = <b>{sum_xy:.4f}</b>
        </div>

        <div style='background-color: #fff3e0; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 5: Calculate Denominator</b><br>
        &nbsp;&nbsp;√[Σ(xᵢ - x̄)² × Σ(yᵢ - ȳ)²]<br>
        &nbsp;&nbsp;= √[{sum_x_sq:.4f} × {sum_y_sq:.4f}]<br>
        &nbsp;&nbsp;= √[{sum_x_sq * sum_y_sq:.4f}]<br>
        &nbsp;&nbsp;= <b>{denominator_val:.4f}</b>
        </div>

        <div style='background-color: #ffebee; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 6: Final Calculation</b><br>
        &nbsp;&nbsp;r = Σ(xᵢ - x̄)(yᵢ - ȳ) / √[Σ(xᵢ - x̄)² × Σ(yᵢ - ȳ)²]<br>
        &nbsp;&nbsp;r = {sum_xy:.4f} / {denominator_val:.4f}<br>
        &nbsp;&nbsp;<span style='font-size: 14px;'><b>r = {r_value:.6f}</b></span>
        </div>

        <div style='background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin-top: 15px; border: 2px solid #4CAF50;'>
        <p style='font-size: 16px; text-align: center; margin: 0;'>
        <b style='color: #2E7D32;'>Full Spectrum Correlation (r) = {r_value:.6f}</b>
        </p>
        </div>

        </div>
        """

        calc_label = QLabel(calc_html)
        calc_label.setWordWrap(True)
        calc_label.setTextFormat(Qt.RichText)
        calc_scroll_layout.addWidget(calc_label)
        calc_scroll.setWidget(calc_content)
        calc_layout.addWidget(calc_scroll)

        self.tab_widget.addTab(calc_tab, "Calculation Details")

    def closeEvent(self, event):
        """창 닫힘 이벤트"""
        self.closed.emit()
        event.accept()


class MultiPeakROIDetailWindow(QWidget):
    """창5: Multi-Peak ROI Correlation 상세 정보 팝업"""

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.parent_window = parent
        self.init_ui()

    def init_ui(self):
        """GUI 초기화"""
        self.setWindowTitle("Multi-Peak ROI Correlation Detail")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ccc; background: white; }
            QTabBar::tab { padding: 8px 16px; }
            QTabBar::tab:selected { background: #9467BD; color: white; }
        """)
        main_layout.addWidget(self.tab_widget)

    def update_content(self, parent):
        """내용 업데이트"""
        if parent.data is None:
            return

        self.tab_widget.clear()

        # 파장 정보 가져오기
        wavelengths = []
        for i in range(2):
            if parent.wavelength_checkboxes[i].isChecked():
                try:
                    wl = float(parent.wavelength_inputs[i].text())
                    if 200.0 <= wl <= 800.0:
                        wavelengths.append(wl)
                except ValueError:
                    pass

        if len(wavelengths) < 2:
            return

        times = parent.data.iloc[:, 1].values
        current_time = parent.time_spinbox.value()
        reference_time = parent.reference_spinbox.value()
        correlation_window = parent.correlation_window
        half_window = correlation_window / 2.0

        current_idx = int(np.argmin(np.abs(times - current_time)))
        ref_idx = int(np.argmin(np.abs(times - reference_time)))

        ref_spectrum = parent.data.iloc[ref_idx, 2:].values.astype(float)
        current_spectrum = parent.data.iloc[current_idx, 2:].values.astype(float)

        # Multi-Peak ROI 인덱스 계산
        indices = set()
        for wl in wavelengths:
            start_idx, end_idx = parent.get_window_indices(wl)
            for i in range(start_idx, end_idx + 1):
                indices.add(i)

        indices = sorted(list(indices))
        n = len(indices)

        x = np.array([ref_spectrum[i] for i in indices])
        y = np.array([current_spectrum[i] for i in indices])

        # 통계 계산
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        x_std = np.std(x)
        y_std = np.std(y)

        x_diff = x - x_mean
        y_diff = y - y_mean

        sum_xy = np.sum(x_diff * y_diff)
        sum_x_sq = np.sum(x_diff ** 2)
        sum_y_sq = np.sum(y_diff ** 2)

        denominator_val = np.sqrt(sum_x_sq * sum_y_sq)
        r_value = sum_xy / denominator_val if denominator_val != 0 else 0.0

        # ========================================
        # 탭 1: Overview (공식 + 요약)
        # ========================================
        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)
        overview_layout.setContentsMargins(10, 10, 10, 10)

        overview_scroll = QScrollArea()
        overview_scroll.setWidgetResizable(True)
        overview_content = QWidget()
        overview_scroll_layout = QVBoxLayout(overview_content)

        # 범위 문자열 생성
        range_str = f"({wavelengths[0]:.1f} ± {half_window:.1f}) ∪ ({wavelengths[1]:.1f} ± {half_window:.1f}) nm"

        overview_html = f"""
        <div style='font-family: Arial; font-size: 11px; padding: 10px;'>

        <h2 style='color: #9467BD;'>Multi-Peak ROI Pearson Correlation</h2>

        <div style='background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0;'>
        <p style='font-size: 14px; text-align: center;'>
        <b>r = Σ(xᵢ - x̄)(yᵢ - ȳ) / √[Σ(xᵢ - x̄)² × Σ(yᵢ - ȳ)²]</b>
        </p>
        </div>

        <h3 style='color: #2E7D32;'>Multi-Peak ROI Definition</h3>
        <hr>
        <p>
        두 파장의 Correlation Window 범위 <b>합집합</b>을 사용하여 계산합니다.
        </p>
        <p style='background-color: #e8f5e9; padding: 10px; border-radius: 5px;'>
        <b>ROI Range:</b> {range_str}
        </p>

        <h3 style='color: #2E7D32;'>Parameters</h3>
        <hr>

        <table style='width: 100%; border-collapse: collapse;'>
        <tr style='background-color: #e8d5f5;'>
            <td style='padding: 8px; border: 1px solid #ddd;'><b>Symbol</b></td>
            <td style='padding: 8px; border: 1px solid #ddd;'><b>Name</b></td>
            <td style='padding: 8px; border: 1px solid #ddd;'><b>Description</b></td>
        </tr>
        <tr>
            <td style='padding: 8px; border: 1px solid #ddd;'>λ₁</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Wavelength 1</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>{wavelengths[0]:.1f} nm</td>
        </tr>
        <tr style='background-color: #f9f9f9;'>
            <td style='padding: 8px; border: 1px solid #ddd;'>λ₂</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Wavelength 2</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>{wavelengths[1]:.1f} nm</td>
        </tr>
        <tr>
            <td style='padding: 8px; border: 1px solid #ddd;'>Window</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Correlation Window</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>±{half_window:.1f} nm (total {correlation_window:.1f} nm)</td>
        </tr>
        <tr style='background-color: #f9f9f9;'>
            <td style='padding: 8px; border: 1px solid #ddd;'>n</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Data Points</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>{n} points (union of both ranges)</td>
        </tr>
        <tr>
            <td style='padding: 8px; border: 1px solid #ddd;'>xᵢ</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Reference Intensity</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Reference 시점의 ROI 내 스펙트럼 강도</td>
        </tr>
        <tr style='background-color: #f9f9f9;'>
            <td style='padding: 8px; border: 1px solid #ddd;'>yᵢ</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>Current Intensity</td>
            <td style='padding: 8px; border: 1px solid #ddd;'>현재 시점의 ROI 내 스펙트럼 강도</td>
        </tr>
        </table>

        <h3 style='color: #2E7D32; margin-top: 20px;'>Current Settings</h3>
        <hr>
        <p>
        <b>Reference Time:</b> {reference_time:.2f} sec<br>
        <b>Current Time:</b> {current_time:.2f} sec<br>
        <b>Wavelength 1:</b> {wavelengths[0]:.1f} nm (±{half_window:.1f} nm)<br>
        <b>Wavelength 2:</b> {wavelengths[1]:.1f} nm (±{half_window:.1f} nm)<br>
        <b>Total Data Points:</b> {n}
        </p>

        <div style='background-color: #e8d5f5; padding: 15px; border-radius: 5px; margin-top: 15px; border: 2px solid #9467BD;'>
        <p style='font-size: 16px; text-align: center; margin: 0;'>
        <b style='color: #7B1FA2;'>Multi-Peak ROI r = {r_value:.6f}</b>
        </p>
        </div>

        </div>
        """

        overview_label = QLabel(overview_html)
        overview_label.setWordWrap(True)
        overview_label.setTextFormat(Qt.RichText)
        overview_scroll_layout.addWidget(overview_label)
        overview_scroll.setWidget(overview_content)
        overview_layout.addWidget(overview_scroll)

        self.tab_widget.addTab(overview_tab, "Overview")

        # ========================================
        # 탭 2: Calculation Details (계산 과정)
        # ========================================
        calc_tab = QWidget()
        calc_layout = QVBoxLayout(calc_tab)
        calc_layout.setContentsMargins(10, 10, 10, 10)

        calc_scroll = QScrollArea()
        calc_scroll.setWidgetResizable(True)
        calc_content = QWidget()
        calc_scroll_layout = QVBoxLayout(calc_content)

        calc_html = f"""
        <div style='font-family: monospace; font-size: 11px; padding: 10px;'>

        <h3 style='color: #9467BD;'>Multi-Peak ROI Calculation</h3>
        <p>
        <b>Reference Time:</b> {reference_time:.2f} sec<br>
        <b>Current Time:</b> {current_time:.2f} sec<br>
        <b>λ₁:</b> {wavelengths[0]:.1f} nm | <b>λ₂:</b> {wavelengths[1]:.1f} nm<br>
        <b>Window:</b> ±{half_window:.1f} nm<br>
        <b>ROI Data Points:</b> n = {n}
        </p>
        <hr>

        <h4 style='color: #2E7D32;'>Statistics Summary</h4>
        <div style='background-color: #fafafa; padding: 10px; border-radius: 5px;'>
        <b>Reference Spectrum (xᵢ) - ROI Region:</b><br>
        &nbsp;&nbsp;Sum: Σxᵢ = {np.sum(x):.2f}<br>
        &nbsp;&nbsp;Mean: x̄ = {x_mean:.4f}<br>
        &nbsp;&nbsp;Std Dev: σx = {x_std:.4f}<br>
        &nbsp;&nbsp;Min: {np.min(x):.2f} | Max: {np.max(x):.2f}<br><br>

        <b>Current Spectrum (yᵢ) - ROI Region:</b><br>
        &nbsp;&nbsp;Sum: Σyᵢ = {np.sum(y):.2f}<br>
        &nbsp;&nbsp;Mean: ȳ = {y_mean:.4f}<br>
        &nbsp;&nbsp;Std Dev: σy = {y_std:.4f}<br>
        &nbsp;&nbsp;Min: {np.min(y):.2f} | Max: {np.max(y):.2f}<br>
        </div>

        <h4 style='color: #2E7D32; margin-top: 15px;'>Step-by-Step Calculation</h4>

        <div style='background-color: #fff8e1; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 1: Calculate Means</b><br>
        &nbsp;&nbsp;x̄ = Σxᵢ / n = {np.sum(x):.2f} / {n} = <b>{x_mean:.4f}</b><br>
        &nbsp;&nbsp;ȳ = Σyᵢ / n = {np.sum(y):.2f} / {n} = <b>{y_mean:.4f}</b>
        </div>

        <div style='background-color: #e3f2fd; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 2: Calculate Deviations</b><br>
        &nbsp;&nbsp;(xᵢ - x̄): range [{np.min(x_diff):.2f}, {np.max(x_diff):.2f}]<br>
        &nbsp;&nbsp;(yᵢ - ȳ): range [{np.min(y_diff):.2f}, {np.max(y_diff):.2f}]
        </div>

        <div style='background-color: #f3e5f5; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 3: Calculate Sum of Squared Deviations</b><br>
        &nbsp;&nbsp;Σ(xᵢ - x̄)² = <b>{sum_x_sq:.4f}</b><br>
        &nbsp;&nbsp;Σ(yᵢ - ȳ)² = <b>{sum_y_sq:.4f}</b>
        </div>

        <div style='background-color: #e8f5e9; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 4: Calculate Covariance (Numerator)</b><br>
        &nbsp;&nbsp;Σ(xᵢ - x̄)(yᵢ - ȳ) = <b>{sum_xy:.4f}</b>
        </div>

        <div style='background-color: #fff3e0; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 5: Calculate Denominator</b><br>
        &nbsp;&nbsp;√[Σ(xᵢ - x̄)² × Σ(yᵢ - ȳ)²]<br>
        &nbsp;&nbsp;= √[{sum_x_sq:.4f} × {sum_y_sq:.4f}]<br>
        &nbsp;&nbsp;= √[{sum_x_sq * sum_y_sq:.4f}]<br>
        &nbsp;&nbsp;= <b>{denominator_val:.4f}</b>
        </div>

        <div style='background-color: #fce4ec; padding: 10px; border-radius: 5px; margin: 5px 0;'>
        <b>Step 6: Final Calculation</b><br>
        &nbsp;&nbsp;r = {sum_xy:.4f} / {denominator_val:.4f}<br>
        &nbsp;&nbsp;<span style='font-size: 14px;'><b>r = {r_value:.6f}</b></span>
        </div>

        <div style='background-color: #e8d5f5; padding: 15px; border-radius: 5px; margin-top: 15px; border: 2px solid #9467BD;'>
        <p style='font-size: 16px; text-align: center; margin: 0;'>
        <b style='color: #7B1FA2;'>Multi-Peak ROI Correlation (r) = {r_value:.6f}</b>
        </p>
        </div>

        </div>
        """

        calc_label = QLabel(calc_html)
        calc_label.setWordWrap(True)
        calc_label.setTextFormat(Qt.RichText)
        calc_scroll_layout.addWidget(calc_label)
        calc_scroll.setWidget(calc_content)
        calc_layout.addWidget(calc_scroll)

        self.tab_widget.addTab(calc_tab, "Calculation Details")

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
        self.correlation_window = 10.0  # 기본값 10nm (±5nm)

        # Detail Windows
        self.detail_window = None
        self.full_spectrum_window = None
        self.multi_peak_window = None  # 새로 추가

        # 줌 상태 관리
        self.zoom_history_a = []  # 그래프 A 줌 히스토리 [(xlim, ylim), ...]
        self.zoom_history_b = []  # 그래프 B 줌 히스토리

        # 박스 선택 상태
        self.is_dragging_a = False
        self.is_dragging_b = False
        self.drag_start_a = None  # (x, y) 시작점
        self.drag_start_b = None
        self.rect_a = None  # 선택 사각형 객체
        self.rect_b = None

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
        palette = left_panel.palette()
        palette.setColor(QPalette.Window, QColor(68, 114, 196))
        left_panel.setAutoFillBackground(True)
        left_panel.setPalette(palette)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(10)

        # ===== 1. 파일로딩 버튼 =====
        self.load_button = QPushButton("Load")
        self.load_button.setFixedSize(120, 35)
        self.load_button.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        self.load_button.clicked.connect(self.load_file)

        # 버튼 중앙 정렬
        load_layout = QHBoxLayout()
        load_layout.addStretch()
        load_layout.addWidget(self.load_button)
        load_layout.addStretch()
        left_layout.addLayout(load_layout)

        left_layout.addSpacing(10)

        # ===== 2. 파장 입력 (한 줄에 2개) =====
        # 레이블 행 (8pt)
        wavelength_label_layout = QHBoxLayout()
        wavelength_label_layout.setSpacing(10)

        for i in range(2):  # 3 → 2로 변경
            lbl = QLabel(f"파장{i+1}")
            lbl.setStyleSheet("color: white; font-size: 8pt;")
            lbl.setAlignment(Qt.AlignCenter)
            wavelength_label_layout.addWidget(lbl, stretch=1)

        left_layout.addLayout(wavelength_label_layout)

        # 입력창 행 (QLineEdit, 화살표 없음)
        wavelength_input_layout = QHBoxLayout()
        wavelength_input_layout.setSpacing(10)

        self.wavelength_inputs = []
        default_wavelengths = [486.1, 656.3]  # 2개만

        for i, default_wl in enumerate(default_wavelengths):
            line_edit = QLineEdit()
            line_edit.setFixedHeight(28)
            line_edit.setText(f"{default_wl:.1f}")
            line_edit.setAlignment(Qt.AlignCenter)
            line_edit.setStyleSheet("""
                QLineEdit {
                    background-color: white;
                    border: 1px solid #ccc;
                    border-radius: 2px;
                    font-size: 10px;
                }
            """)
            # 숫자만 입력 가능 (200.0 ~ 800.0)
            validator = QDoubleValidator(200.0, 800.0, 1)
            validator.setNotation(QDoubleValidator.StandardNotation)
            line_edit.setValidator(validator)
            line_edit.editingFinished.connect(self.on_wavelength_changed)

            wavelength_input_layout.addWidget(line_edit, stretch=1)
            self.wavelength_inputs.append(line_edit)

        left_layout.addLayout(wavelength_input_layout)

        # 체크박스 행 (2개)
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(10)

        self.wavelength_checkboxes = []
        default_checked = [True, True]  # 2개만

        for i, checked in enumerate(default_checked):
            checkbox = QCheckBox()
            checkbox.setChecked(checked)
            checkbox.setStyleSheet("margin-left: 20px;")
            checkbox.stateChanged.connect(self.on_wavelength_changed)
            checkbox.stateChanged.connect(self.update_multi_peak_checkbox_state)  # 추가

            # 체크박스 중앙 정렬용 wrapper
            cb_wrapper = QHBoxLayout()
            cb_wrapper.addStretch()
            cb_wrapper.addWidget(checkbox)
            cb_wrapper.addStretch()

            checkbox_layout.addLayout(cb_wrapper, stretch=1)
            self.wavelength_checkboxes.append(checkbox)

        left_layout.addLayout(checkbox_layout)

        left_layout.addSpacing(15)

        # ===== 3. Current Time 입력 =====
        current_time_label = QLabel("Current Time (sec)")
        current_time_label.setStyleSheet("color: white; font-size: 10pt;")
        left_layout.addWidget(current_time_label)

        self.time_spinbox = QDoubleSpinBox()
        self.time_spinbox.setFixedSize(80, 28)
        self.time_spinbox.setButtonSymbols(QDoubleSpinBox.NoButtons)  # 화살표 제거
        self.time_spinbox.setSingleStep(0.5)
        self.time_spinbox.setDecimals(2)
        self.time_spinbox.setEnabled(False)
        self.time_spinbox.setKeyboardTracking(False)
        self.time_spinbox.editingFinished.connect(self.on_time_changed)
        self.time_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 2px;
            }
        """)
        left_layout.addWidget(self.time_spinbox)

        left_layout.addSpacing(10)

        # ===== 4. Reference Time 입력 =====
        ref_time_label = QLabel("Reference Time (sec)")
        ref_time_label.setStyleSheet("color: white; font-size: 10pt;")
        left_layout.addWidget(ref_time_label)

        self.reference_spinbox = QDoubleSpinBox()
        self.reference_spinbox.setFixedSize(80, 28)
        self.reference_spinbox.setButtonSymbols(QDoubleSpinBox.NoButtons)  # 화살표 제거
        self.reference_spinbox.setSingleStep(0.5)
        self.reference_spinbox.setDecimals(2)
        self.reference_spinbox.setEnabled(False)
        self.reference_spinbox.setKeyboardTracking(False)
        self.reference_spinbox.editingFinished.connect(self.on_reference_changed)
        self.reference_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 2px;
            }
        """)
        left_layout.addWidget(self.reference_spinbox)

        left_layout.addSpacing(15)

        # ===== 5. Pearson Correlation Detail 체크박스 =====
        pearson_layout = QHBoxLayout()
        pearson_label = QLabel("Pearson Correlation Detail")
        pearson_label.setStyleSheet("color: white; font-size: 10pt;")
        self.detail_checkbox = QCheckBox()
        self.detail_checkbox.stateChanged.connect(self.on_detail_checkbox_changed)

        pearson_layout.addWidget(pearson_label)
        pearson_layout.addStretch()
        pearson_layout.addWidget(self.detail_checkbox)
        left_layout.addLayout(pearson_layout)

        left_layout.addSpacing(10)

        # ===== 6. Correlation Window 입력 =====
        window_label = QLabel("Window")
        window_label.setStyleSheet("color: white; font-size: 10pt;")
        left_layout.addWidget(window_label)

        self.window_spinbox = QDoubleSpinBox()
        self.window_spinbox.setFixedSize(80, 28)
        self.window_spinbox.setButtonSymbols(QDoubleSpinBox.NoButtons)  # 화살표 제거
        self.window_spinbox.setRange(1.0, 50.0)
        self.window_spinbox.setSingleStep(0.5)
        self.window_spinbox.setDecimals(1)
        self.window_spinbox.setValue(10.0)
        self.window_spinbox.setSuffix(" nm")
        self.window_spinbox.setKeyboardTracking(False)
        self.window_spinbox.editingFinished.connect(self.on_window_changed)
        self.window_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 2px;
            }
        """)
        left_layout.addWidget(self.window_spinbox)

        left_layout.addSpacing(15)

        # ===== 7. Full Spectrum Correlation Detail 체크박스 =====
        full_spectrum_layout = QHBoxLayout()
        full_spectrum_label = QLabel("Full Spectrum Correlation")
        full_spectrum_label.setStyleSheet("color: white; font-size: 10pt;")
        self.full_spectrum_checkbox = QCheckBox()
        self.full_spectrum_checkbox.stateChanged.connect(self.on_full_spectrum_checkbox_changed)

        full_spectrum_layout.addWidget(full_spectrum_label)
        full_spectrum_layout.addStretch()
        full_spectrum_layout.addWidget(self.full_spectrum_checkbox)
        left_layout.addLayout(full_spectrum_layout)

        left_layout.addSpacing(10)

        # ===== 8. Multi-Peak ROI 체크박스 (새로 추가) =====
        multi_peak_layout = QHBoxLayout()
        self.multi_peak_label = QLabel("Multi-Peak ROI")
        self.multi_peak_label.setStyleSheet("color: white; font-size: 10pt;")
        self.multi_peak_checkbox = QCheckBox()
        self.multi_peak_checkbox.setEnabled(False)  # 초기 비활성화 (파장 2개 선택 시 활성화)
        self.multi_peak_checkbox.stateChanged.connect(self.on_multi_peak_checkbox_changed)

        multi_peak_layout.addWidget(self.multi_peak_label)
        multi_peak_layout.addStretch()
        multi_peak_layout.addWidget(self.multi_peak_checkbox)
        left_layout.addLayout(multi_peak_layout)

        left_layout.addStretch()

        # ===== 우측 그래프 영역 =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)

        # ===== 그래프 A: 스펙트럼 뷰어 =====
        self.figure_a = Figure()
        self.figure_a.set_constrained_layout(True)
        self.canvas_a = FigureCanvas(self.figure_a)
        self.ax_spectrum = self.figure_a.add_subplot(111)
        right_layout.addWidget(self.canvas_a, stretch=1)

        # ===== 그래프 B: 시계열 뷰어 =====
        self.figure_b = Figure()
        self.figure_b.set_constrained_layout(True)
        self.canvas_b = FigureCanvas(self.figure_b)
        self.ax_timeseries = self.figure_b.add_subplot(111)
        right_layout.addWidget(self.canvas_b, stretch=1)

        # 메인 레이아웃에 패널 추가
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, stretch=1)

        # 줌 이벤트 연결
        self.setup_zoom_events()

        # 초기 상태 그래프 표시
        self.show_empty_graphs()

    def setup_zoom_events(self):
        """그래프 줌 이벤트 연결"""
        # 그래프 A 이벤트
        self.canvas_a.mpl_connect('button_press_event', self.on_press_a)
        self.canvas_a.mpl_connect('button_release_event', self.on_release_a)
        self.canvas_a.mpl_connect('motion_notify_event', self.on_motion_a)

        # 그래프 B 이벤트
        self.canvas_b.mpl_connect('button_press_event', self.on_press_b)
        self.canvas_b.mpl_connect('button_release_event', self.on_release_b)
        self.canvas_b.mpl_connect('motion_notify_event', self.on_motion_b)

    def on_press_a(self, event):
        """그래프 A 마우스 버튼 누름"""
        if event.inaxes != self.ax_spectrum:
            return

        # 우클릭: 이전 뷰로 복귀
        if event.button == 3:  # 우클릭
            self.zoom_back_a()
            return

        # 좌클릭: 박스 선택 시작
        if event.button == 1:  # 좌클릭
            self.is_dragging_a = True
            self.drag_start_a = (event.xdata, event.ydata)

            # 선택 사각형 생성 (점선)
            self.rect_a = plt.Rectangle(
                (event.xdata, event.ydata), 0, 0,
                fill=False, edgecolor='red', linestyle='--', linewidth=1.5
            )
            self.ax_spectrum.add_patch(self.rect_a)

    def on_motion_a(self, event):
        """그래프 A 마우스 이동 (드래그 중 사각형 업데이트)"""
        if not self.is_dragging_a or event.inaxes != self.ax_spectrum:
            return
        if self.drag_start_a is None or self.rect_a is None:
            return
        if event.xdata is None or event.ydata is None:
            return

        x0, y0 = self.drag_start_a
        x1, y1 = event.xdata, event.ydata

        # 사각형 위치/크기 업데이트
        self.rect_a.set_xy((min(x0, x1), min(y0, y1)))
        self.rect_a.set_width(abs(x1 - x0))
        self.rect_a.set_height(abs(y1 - y0))

        self.canvas_a.draw_idle()

    def on_release_a(self, event):
        """그래프 A 마우스 버튼 릴리즈"""
        if not self.is_dragging_a:
            return

        self.is_dragging_a = False

        # 사각형 제거
        if self.rect_a is not None:
            self.rect_a.remove()
            self.rect_a = None

        if event.inaxes != self.ax_spectrum:
            self.canvas_a.draw_idle()
            return

        if self.drag_start_a is None or event.xdata is None or event.ydata is None:
            self.canvas_a.draw_idle()
            return

        x0, y0 = self.drag_start_a
        x1, y1 = event.xdata, event.ydata

        # 최소 선택 영역 체크 (너무 작으면 클릭으로 처리 - 줌 안함)
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        xlim = self.ax_spectrum.get_xlim()
        ylim = self.ax_spectrum.get_ylim()

        # 전체 범위의 2% 미만이면 클릭으로 처리
        if dx < (xlim[1] - xlim[0]) * 0.02 and dy < (ylim[1] - ylim[0]) * 0.02:
            self.drag_start_a = None
            self.canvas_a.draw_idle()
            return

        # 현재 뷰를 히스토리에 저장
        self.zoom_history_a.append((xlim, ylim))

        # 새 범위 적용
        new_xlim = (min(x0, x1), max(x0, x1))
        new_ylim = (min(y0, y1), max(y0, y1))

        self.ax_spectrum.set_xlim(new_xlim)
        self.ax_spectrum.set_ylim(new_ylim)

        self.drag_start_a = None
        self.canvas_a.draw()

    def zoom_back_a(self):
        """그래프 A 이전 뷰로 복귀"""
        if len(self.zoom_history_a) > 0:
            xlim, ylim = self.zoom_history_a.pop()
            self.ax_spectrum.set_xlim(xlim)
            self.ax_spectrum.set_ylim(ylim)
            self.canvas_a.draw()

    def on_press_b(self, event):
        """그래프 B 마우스 버튼 누름"""
        if event.inaxes != self.ax_timeseries:
            return

        # 우클릭: 이전 뷰로 복귀
        if event.button == 3:
            self.zoom_back_b()
            return

        # 좌클릭: 박스 선택 시작
        if event.button == 1:
            self.is_dragging_b = True
            self.drag_start_b = (event.xdata, event.ydata)

            self.rect_b = plt.Rectangle(
                (event.xdata, event.ydata), 0, 0,
                fill=False, edgecolor='red', linestyle='--', linewidth=1.5
            )
            self.ax_timeseries.add_patch(self.rect_b)

    def on_motion_b(self, event):
        """그래프 B 마우스 이동"""
        if not self.is_dragging_b or event.inaxes != self.ax_timeseries:
            return
        if self.drag_start_b is None or self.rect_b is None:
            return
        if event.xdata is None or event.ydata is None:
            return

        x0, y0 = self.drag_start_b
        x1, y1 = event.xdata, event.ydata

        self.rect_b.set_xy((min(x0, x1), min(y0, y1)))
        self.rect_b.set_width(abs(x1 - x0))
        self.rect_b.set_height(abs(y1 - y0))

        self.canvas_b.draw_idle()

    def on_release_b(self, event):
        """그래프 B 마우스 버튼 릴리즈"""
        if not self.is_dragging_b:
            return

        self.is_dragging_b = False

        if self.rect_b is not None:
            self.rect_b.remove()
            self.rect_b = None

        if event.inaxes != self.ax_timeseries:
            self.canvas_b.draw_idle()
            return

        if self.drag_start_b is None or event.xdata is None or event.ydata is None:
            self.canvas_b.draw_idle()
            return

        x0, y0 = self.drag_start_b
        x1, y1 = event.xdata, event.ydata

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        xlim = self.ax_timeseries.get_xlim()
        ylim = self.ax_timeseries.get_ylim()

        if dx < (xlim[1] - xlim[0]) * 0.02 and dy < (ylim[1] - ylim[0]) * 0.02:
            self.drag_start_b = None
            self.canvas_b.draw_idle()
            return

        self.zoom_history_b.append((xlim, ylim))

        new_xlim = (min(x0, x1), max(x0, x1))
        new_ylim = (min(y0, y1), max(y0, y1))

        self.ax_timeseries.set_xlim(new_xlim)
        self.ax_timeseries.set_ylim(new_ylim)

        self.drag_start_b = None
        self.canvas_b.draw()

    def zoom_back_b(self):
        """그래프 B 이전 뷰로 복귀"""
        if len(self.zoom_history_b) > 0:
            xlim, ylim = self.zoom_history_b.pop()
            self.ax_timeseries.set_xlim(xlim)
            self.ax_timeseries.set_ylim(ylim)
            self.canvas_b.draw()

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

            # 시간 SpinBox 범위 설정
            self.time_spinbox.setRange(min_time, max_time)
            self.reference_spinbox.setRange(min_time, max_time)

            # 초기 시간 설정
            # Current Time: 50sec (범위 초과 시 max_time 사용)
            initial_current_time = min(50.0, max_time)
            # Reference Time: 20sec (범위 초과 시 max_time 사용)
            initial_reference_time = min(20.0, max_time)

            # Reference가 Current보다 크면 안되므로 조정
            if initial_reference_time > initial_current_time:
                initial_reference_time = initial_current_time

            self.time_spinbox.setValue(initial_current_time)
            self.time_spinbox.setEnabled(True)

            self.reference_spinbox.setValue(initial_reference_time)
            self.reference_spinbox.setEnabled(True)

            self.current_time = initial_current_time
            self.reference_time = initial_reference_time

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
        선택된 파장들의 Correlation Window 범위를 사용하여 Pearson Correlation 계산

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
            start_idx, end_idx = self.get_window_indices(wl)
            for i in range(start_idx, end_idx + 1):
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
        for i in range(2):  # 3 → 2로 변경
            if self.wavelength_checkboxes[i].isChecked():
                try:
                    wl = float(self.wavelength_inputs[i].text())
                    if 200.0 <= wl <= 800.0 and wl > 0:
                        wavelengths.append(wl)
                except ValueError:
                    pass
        return wavelengths

    def calculate_correlation_single_wavelength(self, ref_spectrum, current_spectrum, wavelength):
        """
        단일 파장 기준 Correlation Window 범위의 Pearson Correlation 계산

        Parameters:
        - ref_spectrum: Reference 시점 스펙트럼 (1201 포인트)
        - current_spectrum: 현재 시점 스펙트럼 (1201 포인트)
        - wavelength: 기준 파장 (nm)

        Returns:
        - r: Pearson correlation coefficient (-1 ~ 1)
        """
        start_idx, end_idx = self.get_window_indices(wavelength)

        x = np.array(ref_spectrum[start_idx:end_idx + 1])
        y = np.array(current_spectrum[start_idx:end_idx + 1])

        # Pearson correlation
        x_mean, y_mean = np.mean(x), np.mean(y)
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sqrt(np.sum((x - x_mean)**2) * np.sum((y - y_mean)**2))

        return numerator / denominator if denominator != 0 else 0.0

    def calculate_full_spectrum_correlation(self, ref_spectrum, current_spectrum):
        """
        전체 스펙트럼 (200-800nm) Pearson Correlation 계산

        Parameters:
        - ref_spectrum: Reference 시점의 전체 스펙트럼 (1201 포인트)
        - current_spectrum: 현재 시점의 전체 스펙트럼 (1201 포인트)

        Returns:
        - r: Pearson correlation coefficient (-1 ~ 1)
        """
        x = np.array(ref_spectrum)
        y = np.array(current_spectrum)

        x_mean = np.mean(x)
        y_mean = np.mean(y)

        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sqrt(np.sum((x - x_mean)**2) * np.sum((y - y_mean)**2))

        return numerator / denominator if denominator != 0 else 0.0

    def update_multi_peak_checkbox_state(self):
        """파장 체크박스 상태에 따라 Multi-Peak ROI 체크박스 활성화/비활성화"""
        # 파장1, 파장2 모두 체크되어 있는지 확인
        both_checked = (
            len(self.wavelength_checkboxes) >= 2 and
            self.wavelength_checkboxes[0].isChecked() and
            self.wavelength_checkboxes[1].isChecked()
        )

        self.multi_peak_checkbox.setEnabled(both_checked)

        # 비활성화 시 체크 해제
        if not both_checked:
            self.multi_peak_checkbox.setChecked(False)

        # 레이블 색상 변경 (비활성화 시 회색)
        if both_checked:
            self.multi_peak_label.setStyleSheet("color: white; font-size: 10pt;")
        else:
            self.multi_peak_label.setStyleSheet("color: #888888; font-size: 10pt;")

    def calculate_multi_peak_roi_correlation(self, ref_spectrum, current_spectrum):
        """
        Multi-Peak ROI Pearson Correlation 계산
        두 파장의 Correlation Window 범위 합집합 사용

        Parameters:
        - ref_spectrum: Reference 시점의 전체 스펙트럼 (1201 포인트)
        - current_spectrum: 현재 시점의 전체 스펙트럼 (1201 포인트)

        Returns:
        - r: Pearson correlation coefficient (-1 ~ 1)
        - indices: 사용된 인덱스 집합
        """
        # 두 파장 가져오기
        wavelengths = []
        for i in range(2):
            if self.wavelength_checkboxes[i].isChecked():
                try:
                    wl = float(self.wavelength_inputs[i].text())
                    if 200.0 <= wl <= 800.0:
                        wavelengths.append(wl)
                except ValueError:
                    pass

        if len(wavelengths) < 2:
            return 0.0, set()

        # 두 파장의 Window 범위 합집합
        indices = set()
        for wl in wavelengths:
            start_idx, end_idx = self.get_window_indices(wl)
            for i in range(start_idx, end_idx + 1):
                indices.add(i)

        indices = sorted(list(indices))

        if len(indices) == 0:
            return 0.0, set()

        x = np.array([ref_spectrum[i] for i in indices])
        y = np.array([current_spectrum[i] for i in indices])

        # Pearson correlation 계산
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sqrt(np.sum((x - x_mean)**2) * np.sum((y - y_mean)**2))

        r = numerator / denominator if denominator != 0 else 0.0

        return r, set(indices)

    def update_spectrum_graph(self):
        """그래프 A 업데이트: 스펙트럼 뷰어"""
        if self.data is None:
            return

        self.ax_spectrum.clear()

        # 줌 히스토리 초기화 (새 데이터/시간 변경 시)
        self.zoom_history_a.clear()

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

        # ===== Figure 전체 초기화 (버그 수정 핵심) =====
        self.figure_b.clear()
        self.ax_timeseries = self.figure_b.add_subplot(111)

        # 줌 히스토리 초기화
        self.zoom_history_b.clear()

        # 이중 Y축 생성 (매번 새로 생성)
        ax_corr = self.ax_timeseries.twinx()

        run_times = self.data.iloc[:, 1].values
        selected_wavelengths = self.get_selected_wavelengths()

        # Reference 및 현재 스펙트럼 가져오기
        ref_spectrum = self.get_spectrum_at_time(self.reference_time)
        current_spectrum = self.get_spectrum_at_time(self.current_time)

        half_window = self.correlation_window / 2.0

        # Correlation Score 텍스트 객체 리스트
        texts = []

        # 파장별 시계열 데이터 플롯 (좌측 Y축)
        colors = ['tab:blue', 'tab:orange']  # 2개만
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

            # 파장별 Correlation Score 텍스트 표시
            if ref_spectrum is not None and current_spectrum is not None:
                r_value = self.calculate_correlation_single_wavelength(
                    ref_spectrum, current_spectrum, wl
                )
                current_intensity = self.get_intensity_at_wavelength(current_spectrum, wl)

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

        # ===== Full Spectrum Correlation 시계열 =====
        if ref_spectrum is not None:
            full_spectrum_correlations = []

            for t_idx in range(len(run_times)):
                t_spectrum = self.data.iloc[t_idx, 2:].values.astype(float)
                r_full = self.calculate_full_spectrum_correlation(ref_spectrum, t_spectrum)
                full_spectrum_correlations.append(r_full)

            # 우측 보조축에 Full Spectrum Correlation 플롯
            ax_corr.plot(
                run_times, full_spectrum_correlations,
                color='#AAAAAA',
                linewidth=1.5,
                label='Full Spectrum r'
            )

        # ===== Multi-Peak ROI Correlation 시계열 (새로 추가) =====
        if ref_spectrum is not None and len(selected_wavelengths) >= 2:
            multi_peak_correlations = []

            for t_idx in range(len(run_times)):
                t_spectrum = self.data.iloc[t_idx, 2:].values.astype(float)
                r_mp, _ = self.calculate_multi_peak_roi_correlation(ref_spectrum, t_spectrum)
                multi_peak_correlations.append(r_mp)

            # 보라색 시계열 라인
            ax_corr.plot(
                run_times, multi_peak_correlations,
                color='#9467BD',  # 보라색
                linewidth=1.5,
                label='Multi-Peak ROI r'
            )

            # Current Time에서의 값 텍스트 표시 (그래프 중앙)
            current_mp_r, _ = self.calculate_multi_peak_roi_correlation(ref_spectrum, current_spectrum)

            # Y축 범위의 중앙 계산
            ylim = self.ax_timeseries.get_ylim()
            y_center = (ylim[0] + ylim[1]) / 2

            self.ax_timeseries.text(
                self.current_time, y_center,
                f'MP-ROI r={current_mp_r:.3f}',
                fontsize=10,
                fontweight='bold',
                color='#9467BD',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                          edgecolor='#9467BD', alpha=0.8)
            )

        # 현재 시간 수직선
        self.ax_timeseries.axvline(
            x=self.current_time,
            color='#FF0000', linestyle='--', linewidth=1.5,
            label='Current Time'
        )

        # Reference 시간 수직선
        self.ax_timeseries.axvline(
            x=self.reference_time,
            color='#555555', linestyle='--', linewidth=1.5,
            alpha=1.0, label='Reference Time'
        )

        # adjustText로 텍스트 겹침 조정
        if ADJUSTTEXT_AVAILABLE and texts:
            adjust_text(
                texts,
                ax=self.ax_timeseries,
                arrowprops=dict(arrowstyle='-', color='gray', lw=0.5),
                expand_points=(1.5, 1.5),
                force_points=(0.5, 0.5)
            )

        # 좌측 축 설정
        self.ax_timeseries.set_xlabel("Run Time (sec)")
        self.ax_timeseries.set_ylabel("Intensity (a.u.)")
        self.ax_timeseries.set_title(f"Time Series & Correlation (Window: ±{half_window:.1f}nm)")
        self.ax_timeseries.grid(True, linestyle='--', alpha=0.3, color='lightgray')
        self.ax_timeseries.legend(loc='upper left')

        # 우측 Y축 설정
        ax_corr.set_ylabel("Correlation (r)")
        ax_corr.set_ylim(-1.0, 1.0)
        ax_corr.legend(loc='upper right')

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
        self.update_full_spectrum_window()
        self.update_multi_peak_window()  # 추가

    def on_reference_changed(self):
        """Reference Time SpinBox Enter 입력 핸들러"""
        if self.data is None:
            return
        value = self.reference_spinbox.value()
        self.reference_time = value

        self.update_timeseries_graph()
        self.update_detail_window()
        self.update_full_spectrum_window()
        self.update_multi_peak_window()  # 추가

    def on_wavelength_changed(self):
        """파장 변경 핸들러"""
        # 데이터가 로드되지 않았으면 무시
        if self.data is None:
            return

        self.update_spectrum_graph()
        self.update_timeseries_graph()
        self.update_detail_window()
        self.update_full_spectrum_window()
        self.update_multi_peak_window()  # 추가

    def on_window_changed(self):
        """Correlation Window 변경 핸들러"""
        new_window = self.window_spinbox.value()
        self.correlation_window = new_window

        # 데이터가 로드된 경우에만 업데이트
        if self.data is not None:
            self.update_timeseries_graph()
            self.update_detail_window()
            self.update_full_spectrum_window()
            self.update_multi_peak_window()  # 추가

    def get_window_indices(self, wavelength):
        """
        주어진 파장을 중심으로 Correlation Window 범위의 인덱스 반환

        Parameters:
        - wavelength: 중심 파장 (nm)

        Returns:
        - start_idx, end_idx: 시작/끝 인덱스
        """
        # 총 window nm → ±(window/2) nm
        half_window = self.correlation_window / 2.0

        center_idx = int((wavelength - 200.0) / 0.5)
        # 0.5nm 간격이므로 half_window nm = half_window / 0.5 인덱스
        idx_range = int(half_window / 0.5)

        start_idx = max(0, center_idx - idx_range)
        end_idx = min(1200, center_idx + idx_range)

        return start_idx, end_idx


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

    def on_full_spectrum_checkbox_changed(self, state):
        """Full Spectrum Correlation Detail 체크박스 상태 변경"""
        if state == Qt.Checked:
            self.show_full_spectrum_window()
        else:
            self.hide_full_spectrum_window()

    def show_full_spectrum_window(self):
        """창4 표시"""
        if not hasattr(self, 'full_spectrum_window') or self.full_spectrum_window is None:
            self.full_spectrum_window = FullSpectrumDetailWindow(self)
            self.full_spectrum_window.closed.connect(self.on_full_spectrum_window_closed)

        self.update_full_spectrum_window()
        self.full_spectrum_window.show()
        self.full_spectrum_window.raise_()

    def hide_full_spectrum_window(self):
        """창4 숨김"""
        if hasattr(self, 'full_spectrum_window') and self.full_spectrum_window is not None:
            self.full_spectrum_window.hide()

    def on_full_spectrum_window_closed(self):
        """창4 닫힘 시 체크박스 해제"""
        self.full_spectrum_checkbox.setChecked(False)

    def update_full_spectrum_window(self):
        """창4 내용 업데이트"""
        if not hasattr(self, 'full_spectrum_window') or self.full_spectrum_window is None:
            return
        if not self.full_spectrum_window.isVisible():
            return
        if self.data is None:
            return

        self.full_spectrum_window.update_content(self)

    def on_multi_peak_checkbox_changed(self, state):
        """Multi-Peak ROI 체크박스 상태 변경"""
        if state == Qt.Checked:
            self.show_multi_peak_window()
        else:
            self.hide_multi_peak_window()

    def show_multi_peak_window(self):
        """창5 표시"""
        if not hasattr(self, 'multi_peak_window') or self.multi_peak_window is None:
            self.multi_peak_window = MultiPeakROIDetailWindow(self)
            self.multi_peak_window.closed.connect(self.on_multi_peak_window_closed)

        self.update_multi_peak_window()
        self.multi_peak_window.show()
        self.multi_peak_window.raise_()

    def hide_multi_peak_window(self):
        """창5 숨김"""
        if hasattr(self, 'multi_peak_window') and self.multi_peak_window is not None:
            self.multi_peak_window.hide()

    def on_multi_peak_window_closed(self):
        """창5 닫힘 시 체크박스 해제"""
        self.multi_peak_checkbox.setChecked(False)

    def update_multi_peak_window(self):
        """창5 내용 업데이트"""
        if not hasattr(self, 'multi_peak_window') or self.multi_peak_window is None:
            return
        if not self.multi_peak_window.isVisible():
            return
        if self.data is None:
            return

        self.multi_peak_window.update_content(self)


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    window = OESAnalyzer()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
