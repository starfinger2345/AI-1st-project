# -*- coding: utf-8 -*-
"""손 랜드마크에서 특징을 계산"""
import numpy as np

def calculate_angles(joint: np.ndarray) -> np.ndarray:
    """
    DESCRIPTION:
        손가락 관절 사이의 각도 계산
    RETURN:
        계산된 각도 값들의 배열
    """
    v1 = joint[[0,1,2,3,0,5,6,7,0,9,10,11,0,13,14,15,0,17,18,19], :]
    v2 = joint[[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20], :]
    v = v2 - v1
    v = v / np.linalg.norm(v, axis=1)[:, np.newaxis]
    return np.degrees(np.arccos(np.einsum('nt,nt->n',
                     v[[0,1,2,4,5,6,8,9,10,12,13,14,16,17,18], :],
                     v[[1,2,3,5,6,7,9,10,11,13,14,15,17,18,19], :] ))).astype(np.float32)

def calculate_distances(joint: np.ndarray) -> np.ndarray:
    """
    DESCRIPTION:
        엄지 손가락 끝과 다른 네 손가락 끝 사이의 거리를 계산
    RETURN:
        계산된 거리 값들의 배열
    """
    thumb_tip = joint[4]
    other_tips = joint[[8, 12, 16, 20]]
    distances = np.linalg.norm(other_tips - thumb_tip, axis=1)
    return distances.astype(np.float32)

def calculate_orientation_vectors(joint: np.ndarray) -> np.ndarray:
    """
    DESCRIPTION:
        손의 방향을 나타내는 두 개의 벡터(손목-중지 벡터 & 손바닥 평면 법선 벡터)를 계산
    RETURN:
        두 벡터를 연결한 배열
    """
    v_direction = joint[9] - joint[0]
    v_direction = np.zeros(3) if np.linalg.norm(v_direction) == 0 else v_direction / np.linalg.norm(v_direction)
    v1, v2 = joint[5] - joint[0], joint[17] - joint[0]
    v_normal = np.cross(v1, v2)
    v_normal = np.zeros(3) if np.linalg.norm(v_normal) == 0 else v_normal / np.linalg.norm(v_normal)
    return np.concatenate([v_direction, v_normal]).astype(np.float32)
