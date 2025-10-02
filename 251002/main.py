# ======================= 실행 전 라이브러리 로드 & 설정 =======================
import sys
import os
import cv2
import mediapipe as mp
import numpy as np
from collections import deque
import time
from pathlib import Path

# PyQt5 관련 모듈
from PyQt5.QtWidgets import (
    QWidget, QLabel, QTextEdit, QHBoxLayout, QVBoxLayout, QPushButton, QDialog, QTextBrowser, QShortcut, QApplication, QPlainTextEdit, QLineEdit, QComboBox
)
from PyQt5.QtGui import QImage, QPixmap, QKeySequence, QIcon
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QPoint

# MediaPipe Hands 모델 로드
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# ---직접 만든 모듈에서 클래스와 함수 로드---
from manage_model import SignLanguageModel, FeatureExtractor
from hangul_processor import HangulAssembler
from settings import font_path, rec_cool_time, history_maxlen, display_duration

from hangul_processor import putText_korean


# ======================= PyQt5 GUI 및 영상 처리 스레드 =======================

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    update_text_signal = pyqtSignal(str)

    def __init__(self, sl_model_instance): # SignLanguageModel 객체를 통째로 수신
    #def __init__(self, model, encoder):
        super().__init__()
        self._run_flag = True
        #self.model = model
        #self.encoder = encoder
        self.sl_model = sl_model_instance # 모델 객체 저장
        
        self.last_rec_time = 0
        self.rec_cool_time = rec_cool_time
        self.display_duration = display_duration
        self.cap = cv2.VideoCapture(0)
        self._is_paused = False # <<< 추가: 일시정지 상태 플래그

            # <<< 추가: 일시정지/재시작을 위한 메서드 >>>
    def pause(self):
        self._is_paused = True

    def resume(self):
        self._is_paused = False

    def run(self):
        history = deque(maxlen=history_maxlen)
        display_label = ''
        display_start_time = None

        with mp_hands.Hands(max_num_hands=2,
                              min_detection_confidence=0.5,
                              min_tracking_confidence=0.5) as hands:
            while self._run_flag and self.cap.isOpened():
                # <<< 추가: 일시정지 상태이면 루프를 건너뜀 >>>
                if self._is_paused:
                    time.sleep(0.01) # CPU 사용 방지를 위해 잠시 대기
                    continue

                ret, frame = self.cap.read()
                if not ret: break
                
                frame = cv2.flip(frame, 1)
                result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                
                current_time = time.time()
                guide_text = "손을 보여주세요"
                hands_present = False

                if result.multi_hand_landmarks:
                    hands_present = True
                    # (이하 특징 추출 로직은 동일)
                    init_zeros = {'angles': np.zeros(15), 'coords': np.zeros(60), 'distances': np.zeros(4), 'orientation': np.zeros(6)}
                    lh_features, rh_features = init_zeros.copy(), init_zeros.copy()
                    
                    for i, hand_landmarks in enumerate(result.multi_hand_landmarks):
                        
                        handedness = result.multi_handedness[i].classification[0].label
                        
                        joint = np.array([[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark])
                        
                        features = {
                            'angles': FeatureExtractor.calculate_angles(joint),
                            'coords': (joint[1:]-joint[0]).flatten(),
                            'distances': FeatureExtractor.calculate_distances(joint),
                            'orientation': FeatureExtractor.calculate_orientation_vectors(joint)
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
                    #predicted_label = self.encoder.inverse_transform(self.model.predict(feature_vector))[0]
                    predicted_label = self.sl_model.predict(feature_vector)

                    history.append(predicted_label)

                    if len(history) == 5 and len(set(history)) == 1:
                        
                        # 레이블 인식 및 쿨타임 타이머 작동
                        if current_time - self.last_rec_time > self.rec_cool_time:
                            mapped_label = history[-1]
                            # 사람이 인식할 수 있는 시간으로 변경
                            readable_time = time.strftime("%H시 %M분 %S초", time.localtime(current_time))
                            print(f"인식!! {mapped_label} ({readable_time})")
                            
                            # 인식한 레이블 -> GUI에 전달
                            self.update_text_signal.emit(mapped_label)

                            # 화면 표시용 변수 업데이터 & 쿨타임 타이머 초기화
                            display_label = mapped_label
                            display_start_time = current_time
                            self.last_rec_time = current_time # 마지막 인식 시간 업데이
                            history.clear()
                
                if hands_present:
                    if display_start_time and ((current_time - display_start_time) < self.display_duration):
                        display_text = display_label
                    else: display_text = "인식 중..."
                else: display_text = guide_text
                
                frame = putText_korean(frame, display_text, (50, 420), font_path, 40, (0, 255, 0))
                self.change_pixmap_signal.emit(frame)
        
        self.cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()

class HelpWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("도움말")
        self.resize(600, 650)
        lay, title, body = QVBoxLayout(self), QLabel("<b>수어 예시</b>"), QTextBrowser()
        img_path = Path(r"C:\Users\KCCISTC\Desktop\workspace\hand_img.png")
        if not img_path.exists(): body.setText("도움말 이미지 파일을 찾을 수 없습니다.")
        else: body.setHtml(f'<h3>수어 예시표 입니다.</h3><br><img src="{img_path.as_uri()}" width="550"><br>')
        lay.addWidget(title); lay.addWidget(body)

class SettingsWindow(QDialog):
    speed_changed = pyqtSignal(float)
    def __init__(self, current_speed, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정"); self.resize(350, 200)
        self.info_label1 = QLabel("인식 속도 조절"); self.info_label2 = QLabel("숫자가 낮을수록 인식 간격이 짧아져 빨라집니다.")
        self.speed_combo = QComboBox(); self.apply_button = QPushButton("적용")
        self.speed_options = {"매우 느림 (5.0초)": 5.0, "느림 (4.0초)": 4.0, "보통 (3.0초)": 3.0, "빠름 (2.0초)": 2.0, "매우 빠름 (1.0초)": 1.0}
        for text, value in self.speed_options.items(): self.speed_combo.addItem(text, value)
        for i, value in enumerate(self.speed_options.values()):
            if value == current_speed: self.speed_combo.setCurrentIndex(i); break
        layout = QVBoxLayout(self); layout.addWidget(self.info_label1); layout.addWidget(self.info_label2)
        layout.addWidget(self.speed_combo); layout.addStretch(1); layout.addWidget(self.apply_button)
        self.apply_button.clicked.connect(self.apply_settings)
    def apply_settings(self):
        selected_speed = self.speed_combo.currentData(); self.speed_changed.emit(selected_speed); self.accept()

class SignLanguageTranslatorApp(QWidget):
    def __init__(self, sl_model):
        super().__init__()
        self.setWindowTitle("수어 번역 프로그램")
        self.current_rec_speed = 3.0 
        self.is_paused = False

        # --- UI 위젯 생성 ---
        self.camera_view = QLabel(self); self.camera_view.setObjectName("cameraView"); self.camera_view.setMinimumSize(600, 480)
        self.pause_button = QPushButton("일시정지")
        self.settings_button = QPushButton("설정")
        self.help_button = QPushButton("도움말")
        self.log_box = QPlainTextEdit(self); self.log_box.setReadOnly(True)
        self.bottom_input = QLineEdit(self)

        style_sheet = """
            QWidget { background-color: #2E2E2E; color: #F0F0F0; font-family: "Malgun Gothic"; font-size: 11pt; }
            #cameraView { border: 2px solid #00A0A0; border-radius: 5px; }
            QPushButton { background-color: #555555; border: 1px solid #777777; padding: 5px; border-radius: 5px; }
            QPushButton:hover { background-color: #6A6A6A; }
            QPushButton:pressed { background-color: #4A4A4A; }
            QPlainTextEdit { background-color: #3C3C3C; border: 1px solid #555555; border-radius: 5px; font-size: 12pt; padding: 5px; }
            QLineEdit { background-color: #3C3C3C; border: 1px solid #555555; border-radius: 5px; font-size: 12pt; padding: 5px; selection-background-color: #00A0A0; selection-color: white; }
            QComboBox { border: 1px solid #777777; border-radius: 3px; padding: 1px 18px 1px 3px; min-width: 6em; background-color: #555555;}
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 20px; border-left-width: 1px; border-left-color: #777777; border-left-style: solid; border-top-right-radius: 3px; border-bottom-right-radius: 3px; }
        """
        self.setStyleSheet(style_sheet)
        
        # --- 레이아웃 설정 ---
        button_layout = QHBoxLayout(); button_layout.addStretch(1)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.settings_button); button_layout.addWidget(self.help_button)
        right_pane_layout = QVBoxLayout(); right_pane_layout.addLayout(button_layout); right_pane_layout.addWidget(self.log_box, stretch=10); right_pane_layout.addWidget(self.bottom_input, stretch=1)
        right_widget = QWidget(); right_widget.setLayout(right_pane_layout); right_widget.setFixedWidth(350)
        main_layout = QHBoxLayout(self); main_layout.addWidget(self.camera_view, stretch=2); main_layout.addWidget(right_widget, stretch=1)
        self.setLayout(main_layout); self.resize(980, 520)

        # --- 시그널과 슬롯 연결 ---
        self.pause_button.clicked.connect(self.toggle_pause_resume)
        self.help_button.clicked.connect(self.toggle_help_window)
        self.settings_button.clicked.connect(self.open_settings_window)
        self.bottom_input.returnPressed.connect(self.finalize_sentence)

        # --- 기타 초기화 ---
        self.help_window, self.settings_window = None, None
        self.assembler = HangulAssembler()
        self.thread = VideoThread(sl_model)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.update_text_signal.connect(self.update_text)
        self.thread.start()

        # 단축키
        self.quit_shortcut = QShortcut(QKeySequence('q'), self); self.quit_shortcut.activated.connect(self.close)
        self.help_shortcut = QShortcut(QKeySequence(Qt.Key_F1), self); self.help_shortcut.activated.connect(self.toggle_help_window)

        # 윈도우 아이콘
        self.setWindowIcon(QIcon("data/세종머왕.png"))  # 윈도우 좌측 상단 아이콘
    
    # --- 일시정지/재시작 토글 메서드 ---
    def toggle_pause_resume(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.thread.pause()
            self.pause_button.setText("다시 시작")
        else:
            self.thread.resume()
            self.pause_button.setText("일시정지")

    def open_settings_window(self):
        if self.settings_window is None or not self.settings_window.isVisible():
            self.settings_window = SettingsWindow(self.current_rec_speed, self)
            self.settings_window.speed_changed.connect(self.update_recognition_speed)
            self.settings_window.show()
        else:
            self.settings_window.activateWindow()

    def update_recognition_speed(self, new_speed):
        self.current_rec_speed = new_speed; self.thread.rec_cool_time = new_speed; self.thread.display_duration = new_speed
        print(f"인식 속도가 {new_speed}초로 변경되었습니다.")

    def finalize_sentence(self):
        text = self.bottom_input.text()
        if text: self.log_box.appendPlainText(text)
        self.bottom_input.clear(); self.assembler = HangulAssembler()
        
    def update_text(self, new_char):
        if new_char == 'end':
            text_to_send = self.assembler.get_current_text_and_reset()
            if text_to_send:
                self.log_box.appendPlainText(text_to_send)
            self.bottom_input.clear()
            return
        current_text = self.assembler.add_char(new_char)
        self.bottom_input.setText(current_text)
        
    def toggle_help_window(self):
        if self.help_window is None or not self.help_window.isVisible():
            self.help_window = HelpWindow(self); self.help_window.setModal(False)
            self.help_window.move(self.frameGeometry().topRight() + QPoint(10, 0)); self.help_window.show()
        else:
            self.help_window.close()
            
    def update_image(self, cv_img):
        qt_img = self.convert_cv_qt(cv_img); self.camera_view.setPixmap(qt_img)
        
    def convert_cv_qt(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB); h, w, ch = rgb_image.shape; p = QPixmap.fromImage(QImage(rgb_image.data, w, h, ch * w, QImage.Format_RGB888))
        return p.scaled(self.camera_view.width(), self.camera_view.height(), Qt.KeepAspectRatio)
        
    def closeEvent(self, event):
        if self.help_window and self.help_window.isVisible(): self.help_window.close()
        if self.settings_window and self.settings_window.isVisible(): self.settings_window.close()
        self.thread.stop(); event.accept(); cv2.destroyAllWindows(); cv2.waitKey(1)

# ======================= PART 03. 메인 실행 부분 =======================
if __name__ == "__main__":
    # 1. SignLanguageModel 클래스를 사용해 저장된 모델 로드
    sl_model = SignLanguageModel.load()
    
    if sl_model:
        # 2. GUI 앱 실행, 로드된 모델 객체 전달
        app = QApplication(sys.argv)
        window = SignLanguageTranslatorApp(sl_model)
        window.show()
        sys.exit(app.exec_())
    else:
        print("모델 로드에 실패하여 프로그램을 종료합니다.")
        print("먼저 train.py를 실행하여 모델을 학습하고 저장해주세요.")
        sys.exit()
    
'''
    trained_model, label_encoder = train_model(dataset_file)
    if trained_model and label_encoder:
        app = QApplication(sys.argv)
        window = SignLanguageTranslatorApp(trained_model, label_encoder)
        window.show()
        sys.exit(app.exec_())
    else:
        print("모델 학습에 실패하여 프로그램을 종료합니다.")

'''