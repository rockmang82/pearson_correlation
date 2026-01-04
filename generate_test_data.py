"""
플라즈마 OES 테스트 데이터 생성 스크립트

샘플 .dat 파일을 생성하여 OES 분석기를 테스트할 수 있습니다.
"""

import numpy as np
import pandas as pd


def generate_test_data(filename='sample_oes_data.dat', num_samples=100):
    """
    테스트용 OES 데이터 생성

    Parameters:
    - filename: 출력 파일명
    - num_samples: 생성할 샘플 수 (시간 포인트 개수)
    """
    # 파장 배열 생성 (200.0 ~ 800.0, 0.5 간격)
    wavelengths = np.arange(200.0, 800.5, 0.5)
    num_wavelengths = len(wavelengths)  # 1201개

    # 시간 배열 생성 (0.5초 간격)
    run_times = np.arange(0.5, 0.5 + num_samples * 0.5, 0.5)

    # 데이터프레임 초기화
    columns = ['Name', 'Run Time'] + [f'{wl:.1f}' for wl in wavelengths]
    data = []

    # 각 시간 포인트에 대한 스펙트럼 생성
    for t in run_times:
        # 센서명은 'A'로 고정
        row = ['A', t]

        # 가우시안 피크 기반 스펙트럼 생성
        # 주요 피크: 486.1nm (Hβ), 656.3nm (Hα), 750.0nm (임의)
        spectrum = np.zeros(num_wavelengths)

        # 기본 베이스라인 노이즈
        baseline = 100 + np.random.normal(0, 10, num_wavelengths)

        # 시간에 따라 변화하는 3개의 가우시안 피크
        peak1_center = 486.1
        peak1_amplitude = 1000 + 200 * np.sin(2 * np.pi * t / 20)
        peak1_width = 2.0
        peak1 = peak1_amplitude * np.exp(
            -((wavelengths - peak1_center) ** 2) / (2 * peak1_width ** 2)
        )

        peak2_center = 656.3
        peak2_amplitude = 1500 + 300 * np.sin(2 * np.pi * t / 30 + 1)
        peak2_width = 2.5
        peak2 = peak2_amplitude * np.exp(
            -((wavelengths - peak2_center) ** 2) / (2 * peak2_width ** 2)
        )

        peak3_center = 750.0
        peak3_amplitude = 800 + 150 * np.sin(2 * np.pi * t / 25 + 2)
        peak3_width = 3.0
        peak3 = peak3_amplitude * np.exp(
            -((wavelengths - peak3_center) ** 2) / (2 * peak3_width ** 2)
        )

        # 전체 스펙트럼 = 베이스라인 + 피크들
        spectrum = baseline + peak1 + peak2 + peak3

        # 추가 노이즈
        spectrum += np.random.normal(0, 20, num_wavelengths)

        # 음수 값 제거
        spectrum = np.maximum(spectrum, 0)

        # 정수로 변환
        spectrum = spectrum.astype(int)

        row.extend(spectrum.tolist())
        data.append(row)

    # 데이터프레임 생성
    df = pd.DataFrame(data, columns=columns)

    # 파일 저장 (탭 구분자)
    df.to_csv(filename, sep='\t', index=False, encoding='utf-8')
    print(f"테스트 데이터 생성 완료: {filename}")
    print(f"- 샘플 수: {num_samples}")
    print(f"- 시간 범위: {run_times[0]:.1f} ~ {run_times[-1]:.1f} 초")
    print(f"- 파장 범위: 200.0 ~ 800.0 nm (0.5nm 간격)")
    print(f"- 주요 피크: 486.1nm, 656.3nm, 750.0nm")


if __name__ == '__main__':
    generate_test_data()
