# ======================= 실행 전 라이브러리 로드 & 설정 =======================
import sys
import os
import cv2
import mediapipe as mp
import numpy as np
from collections import deque
import time

# PyQt5 관련 모듈
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout, QTextEdit
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QThread, pyqtSignal, Qt

# MediaPipe Hands 모델 로드
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# ---직접 만든 모듈에서 클래스와 함수 로드---
from manage_model import SignLanguageModel, FeatureExtractor
from hangul_processor import HangulAssembler
from config import font_path, rec_cool_time, history_maxlen, display_duration

from hangul_processor import putText_korean

from manage_model import FeatureExtractor
# FeatureExtractor의 static method를 전역 함수로 간단히 참조
calculate_angles = FeatureExtractor.calculate_angles
calculate_distances = FeatureExtractor.calculate_distances
calculate_orientation_vectors = FeatureExtractor.calculate_orientation_vectors



# ======================= PyQt5 GUI 및 영상 처리 스레드 =======================

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    update_text_signal = pyqtSignal(str)

    def __init__(self, sl_model_instance): # SignLanguageModel 객체를 통째로 수신
        super().__init__()
        self._run_flag = True
        self.sl_model = sl_model_instance # 모델 객체 저장
        
        self.last_rec_time = 0
        
        self.cap = cv2.VideoCapture(0)
        
        self.rec_cool_time = rec_cool_time

    def run(self):
        history = deque(maxlen=history_maxlen)
        entered_string = []
        display_label = ''
        display_start_time = None

        with mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
            while self._run_flag and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret: # 카메라가 강제 종료되면 ret이 False가 되어 루프 탈출
                    break

                frame = cv2.flip(frame, 1)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands.process(frame_rgb)
                guide_text = "손을 보여주세요"
                current_time = time.time()


                if result.multi_hand_landmarks:
                    init_zeros = {'angles': np.zeros(15), 'coords': np.zeros(60), 'distances': np.zeros(4), 'orientation': np.zeros(6)}
                    lh_features, rh_features = init_zeros.copy(), init_zeros.copy()
                    
                    for i, hand_landmarks in enumerate(result.multi_hand_landmarks):
                        handedness = result.multi_handedness[i].classification[0].label
                        joint = np.array([[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark])

                        features = {
                            'angles': calculate_angles(joint),
                            'coords': (joint[1:] - joint[0]).flatten(),
                            'distances': calculate_distances(joint),
                            'orientation': calculate_orientation_vectors(joint)
                        }

                        if handedness == "Left": lh_features = features
                        elif handedness == "Right": rh_features = features
                        mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)


                    # 정보를 1차원 배열로 변환
                    feature_vector = np.concatenate([
                        lh_features['angles'], rh_features['angles'],
                        lh_features['coords'], rh_features['coords'],
                        lh_features['distances'], rh_features['distances'],
                        lh_features['orientation'], rh_features['orientation']
                    ]).reshape(1, -1)
                    
                    # SignLanguageModel 객체로 예측 수행
                    predicted_label = self.sl_model.predict(feature_vector)
                    
                    history.append(predicted_label)

                    if len(history) == 5 and len(set(history)) == 1:
                        # 레이블 인식 및 쿨타임 타이머 작동
                        if current_time - self.last_rec_time > self.rec_cool_time:
                            mapped_label = history[-1]
                            # 사람이 인식할 수 있는 시간으로 변경
                            readable_time = time.strftime("%H시 %M분 %S초", time.localtime(current_time))
                            print(f"인식!!: {mapped_label} ({readable_time})")

                            # 인식한 레이블 -> GUI에 전달
                            self.update_text_signal.emit(mapped_label)

                            # 화면 표시용 변수 업데이터 & 쿨타임 타이머 초기화
                            display_label = mapped_label
                            display_start_time = current_time
                            self.last_rec_time = current_time  # 마지막 인식 시간 업데이트
                            history.clear()

                if display_start_time and ((current_time - display_start_time) < display_duration):
                    display_text = display_label
                else:
                    display_text = guide_text

                frame = putText_korean(frame, display_text, (50, 420), font_path, 40, (0, 255, 0))
                self.change_pixmap_signal.emit(frame)
        self.cap.release()

    def stop(self):
        self._run_flag = False
        if self.cap.isOpened(): # 카메라를 강제로 해제 >> cap.read() 대기 상태를 중단
            self.cap.release()
        self.wait() # 스레드가 완전히 종료될 때까지 대기




class HandGestureApp(QWidget):
    def __init__(self, sl_model_instance):
        super().__init__()
        self.setWindowTitle("수어 번역 프로그램 ('q'를 눌러 종료)")
        self.display_width = 640
        self.display_height = 480

        # UI 요소 생성
        self.image_label = QLabel(self)
        self.image_label.resize(self.display_width, self.display_height)
        self.image_label.setStyleSheet("border: 2px solid black;")

        self.chat_box = QTextEdit(self)
        self.chat_box.setReadOnly(True)
        self.chat_box.setFixedWidth(200) # 대화창 너비 고정
        self.chat_box.setStyleSheet("font-size: 20px; border: 2px solid black;")

        # 수평 레이아웃으로 변경
        hbox = QHBoxLayout()
        hbox.addWidget(self.image_label)
        hbox.addWidget(self.chat_box)
        self.setLayout(hbox)

        # HangulAssembler 인스턴스 생성
        self.assembler = HangulAssembler()

        # 비디오 스레드 생성 및 시작
        self.thread = VideoThread(sl_model_instance)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.update_text_signal.connect(self.update_chat)
        self.thread.start()

    def update_image(self, cv_img):
        qt_img = self.convert_cv_qt(cv_img)
        self.image_label.setPixmap(qt_img)

    def update_chat(self, new_char):
        # assembler에 새 글자 추가하고, 반환된 전체 텍스트로 화면을 업데이트
        full_text = self.assembler.add_char(new_char)
        self.chat_box.setText(full_text)
        self.chat_box.verticalScrollBar().setValue(self.chat_box.verticalScrollBar().maximum()) # 자동 스크롤

    def convert_cv_qt(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.display_width, self.display_height, Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)

    # 'q' 키를 누르면 종료 (이벤트 핸들러)
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Q:
            self.close()
        

    def closeEvent(self, event):
        self.thread.stop()
        event.accept()
        cv2.destroyAllWindows()
        cv2.waitKey(1)


if __name__ == "__main__":
    # 1. SignLanguageModel 클래스를 사용해 저장된 모델 로드
    sl_model = SignLanguageModel.load()
    
    if sl_model:
        # 2. GUI 앱 실행, 로드된 모델 객체 전달
        app = QApplication(sys.argv)
        window = HandGestureApp(sl_model)
        window.show()
        sys.exit(app.exec_())
    else:
        print("모델 로드에 실패하여 프로그램을 종료합니다.")
        print("먼저 train.py를 실행하여 모델을 학습하고 저장해주세요.")
        sys.exit()
