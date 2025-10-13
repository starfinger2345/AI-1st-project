"""
실시간 영상 프레임에서 제스처를 인식
(Mediapipe 처리, 특징 추출, 예측, 히스토리/쿨다운/화면 표시 로직을 모듈화한 파일)
"""

import time
from collections import deque
import numpy as np
import cv2
import mediapipe as mp

from engine.features import calculate_angles, calculate_distances, calculate_orientation_vectors
from ui.visualizer import putText_korean
from config.paths import FONT_PATH


class GestureRecognizer:
    """
    Mediapipe 기반 프레임 인식 담당.
    - Mediapipe Hands 인스턴스를 보유하고 multi_hand_landmarks를 처리합니다.
    - 모델 + encoder를 입력으로 받아 예측을 수행합니다.
    - 안정화(최근 N개 동일 판정) + 쿨다운 로직을 포함합니다.
    - 원본 video_thread.py의 손 랜드마크 -> features 계산 -> 예측 -> 히스토리/쿨다운 -> putText_korean 시각화 흐름을 옮겨왔습니다.
    """
    def __init__(self, model, encoder,
                 rec_history_len: int,
                 rec_cool_time: float,
                 display_duration: float,
                 show_landmarks: bool,
                 conf_thres: float):
        """
        DESCRIPTION:
            제스처 인식기 객체를 초기화 (모델 / 인코더 / Mediapipe 객체를 설정, 인식 결과의 안정화를 위한 히스토리 / 쿨다운 / 시각화 변수들을 정의)
        Args:
            self.camera_index(int) : 카메라 장치의 인덱스. Defaults to 0.
            self.mp_hands          : mediapipe hands 모듈
            self.mp_drawing        : mediapipe drawing_utils 모듈(랜드마크 시각화용)
            self.hands             : mediapipe Hands 객체(손 인식을 위한 메인 객체)
            self.history           : 최근 인식 결과를 저장하는 deque(안정화용)
            self.last_rec_time     : 마지막 인식 확정 시각(쿨다운용)
            self.rec_cool_time     : 인식 쿨다운 시간(초) (레이블 확정 후 다음 확정까지 대기 시간)
            self.display_duration  : 확정된 레이블이 화면에 표시되는 시간(초)
            self.last_rec_label    : 마지막으로 확정된 레이블
            self.display_label     : 화면에 표시될 레이블
            self.display_start_time: 레이블(display_label)이 화면에 표시되기 시작한 시각
            self.show_landmarks    : 랜드마크 시각화 여부 설정 (기본값: True)
        """
        self.model = model
        self.encoder = encoder
        
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        
        self.hands = self.mp_hands.Hands(max_num_hands = 2,
                                         min_detection_confidence = conf_thres,
                                         min_tracking_confidence = conf_thres)
        self.history = deque(maxlen=rec_history_len)
        self.last_rec_time = 0.0
        self.rec_cool_time = rec_cool_time
        self.display_duration = display_duration
        self.last_rec_label = ""
        self.display_start_time = None
        self.show_landmarks = show_landmarks
        
        
    def set_show_landmarks(self, flag: bool):
        """ 랜드마크 시각화 여부 설정 """
        self.show_landmarks = flag
        
    def close(self):
        """ Mediapipe (사용 중인) 자원 해제 """
        try:
            if self.hands:
                self.hands.close()
                self.hands = None # 해제 후 None으로 설정
        except Exception:
            pass
        
        
    def process_frame(self, frame: np.ndarray):
        """
        DESCRIPTION:
            프레임(한 장)을 받아 손 인식, 특징 추출, 예측, 안정화(히스토리/쿨다운 처리), 시각화 수행.
            프레임을 받아 처리하고 (시각화된) 프레임과 인식 확정된 레이블을 반환.
        
        RETURN:
            처리된 영상 프레임 & 확정된 레이블 문자열 (없다면 None)
        """
        
        if frame is None:
            return None, None
        
        current_time = time.time()
        guide_text = "손을 보여주세요"
        hands_present = False
        
        
        # 초기값
        init_zeros = {
            'angles': np.zeros(15, dtype=np.float32),
            'coords': np.zeros(60, dtype=np.float32),
            'distances': np.zeros(4, dtype=np.float32),
            'orientations': np.zeros(6, dtype=np.float32)
        }
        
        lh_features = init_zeros.copy()
        rh_features = init_zeros.copy()
        mapped_label_to_emit = None
    
        # Mediapipe 처리
        results = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if results.multi_hand_landmarks:
            hands_present = True
            for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                if self.show_landmarks:
                    try:
                        self.mp_drawing.draw_landmarks(frame,
                                                       hand_landmarks,
                                                       self.mp_hands.HAND_CONNECTIONS)
                    except Exception:
                        pass
                    
                handedness = results.multi_handedness[i].classification[0].label
                joint = np.array([[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark])
                
                features = {
                    'angles': calculate_angles(joint),
                    'coords': (joint[1:] - joint[0]).flatten(),  # 기준점(손목) 보정
                    'distances': calculate_distances(joint),
                    'orientations': calculate_orientation_vectors(joint)
                }
                if handedness == 'Left':
                    lh_features = features
                elif handedness == 'Right':
                    rh_features = features
                    
            # 특징 벡터 구성
            feature_vector = np.concatenate([
                lh_features['angles'], rh_features['angles'],
                lh_features['coords'], rh_features['coords'],
                lh_features['distances'], rh_features['distances'],
                lh_features['orientations'], rh_features['orientations']
            ]).reshape(1, -1).astype(np.float32)
            
            try:
                prediction = self.model.predict(feature_vector)
                predicted_label = self.encoder.inverse_transform(prediction)[0]
            except Exception:
                predicted_label = None
                
            if predicted_label:
                self.history.append(predicted_label)
                
            # 안정화: 최근 N개(history 길이) 동일 판정
            if len(self.history) == self.history.maxlen and len(set(self.history)) == 1:
                if (current_time - self.last_rec_time) > self.rec_cool_time:
                    
                    mapped_label_to_emit = self.history[-1]
                    
                    self.last_rec_label = mapped_label_to_emit
                    self.display_label = mapped_label_to_emit
                    
                    self.display_start_time = current_time
                    self.last_rec_time = current_time
                    self.history.clear()
                    
        # 표시할 텍스트 결정
        if hands_present:
            if self.display_start_time and ((current_time - self.display_start_time) < self.display_duration):
                display_text = self.display_label
            else:
                display_text = "인식 중..."
        else:
            display_text = guide_text
            self.display_start_time = None  # 손이 없으면 표시 시간 초기화
        
        # 텍스트 시각화
        try:
            #frame = putText_korean(frame, display_text, (50, 420), str(FONT_PATH), 1.0, (0, 0, 0), 2, cv2.LINE_AA)
            frame = putText_korean(frame, display_text, (50, 420), FONT_PATH, 40, (0, 0, 0))
        except Exception:
            # 실패 시 최소한의 OpenCV putText로 대체
            frame = cv2.putText(frame, display_text, (50, 420), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
            
        return frame, mapped_label_to_emit