# -*- coding: utf-8 -*-
"""데이터 로드 및 전처리"""

import numpy as np
from sklearn.preprocessing import LabelEncoder

from engine.features import calculate_angles, calculate_distances, calculate_orientation_vectors

def load_and_preprocess(dataset_file):
    """
    DESCRIPTION
        1. 지정된 CSV 데이터셋 파일을 로드
        2. 손 랜드마크 데이터에서 -> 각도, 거리, 방향 벡터 등의 특징을 추출하여 전처리
    RETURN
        1. all_feature    : 특징 데이터 배열
        2. encoded_labels : 인코딩된 레이블
        3. encoder        : 인코더 객체
    """
    print("데이터셋 로드 및 전처리 시작...")
    try:
        labels_str = np.genfromtxt(dataset_file, delimiter=',', skip_header=1, usecols=0,
                                   encoding="UTF-8", dtype=str)
        landmarks_data = np.genfromtxt(dataset_file, delimiter=',', skip_header=1,
                                       usecols=range(1, 127), encoding="UTF-8").astype(np.float32)
    except Exception as e:
        print(f"데이터 파일 로드 오류: {e}")
        return None, None, None

    all_features = []
    for row in landmarks_data:
        lh_landmarks = row[:63].reshape(21, 3)
        rh_landmarks = row[63:].reshape(21, 3)

        lh_angles = calculate_angles(lh_landmarks) if np.any(lh_landmarks) else np.zeros(15, dtype=np.float32)
        rh_angles = calculate_angles(rh_landmarks) if np.any(rh_landmarks) else np.zeros(15, dtype=np.float32)

        lh_coords = (lh_landmarks[1:] - lh_landmarks[0]).flatten() if np.any(lh_landmarks) else np.zeros(60, dtype=np.float32)
        rh_coords = (rh_landmarks[1:] - rh_landmarks[0]).flatten() if np.any(rh_landmarks) else np.zeros(60, dtype=np.float32)

        lh_distances = calculate_distances(lh_landmarks) if np.any(lh_landmarks) else np.zeros(4, dtype=np.float32)
        rh_distances = calculate_distances(rh_landmarks) if np.any(rh_landmarks) else np.zeros(4, dtype=np.float32)

        lh_orientation = calculate_orientation_vectors(lh_landmarks) if np.any(lh_landmarks) else np.zeros(6, dtype=np.float32)
        rh_orientation = calculate_orientation_vectors(rh_landmarks) if np.any(rh_landmarks) else np.zeros(6, dtype=np.float32)

        features = np.concatenate([lh_angles, rh_angles, lh_coords, rh_coords,
                                   lh_distances, rh_distances, lh_orientation, rh_orientation])
        all_features.append(features)

    all_features = np.array(all_features, dtype=np.float32)
    encoder = LabelEncoder()
    encoded_labels = encoder.fit_transform(labels_str)
    print("데이터 전처리 완료!")
    return all_features, encoded_labels, encoder

