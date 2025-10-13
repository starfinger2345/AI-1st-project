# -*- coding: utf-8 -*-
import sys
import cv2
from PyQt5.QtWidgets import (
    QWidget, QLabel, QTextEdit, QHBoxLayout, QVBoxLayout,
    QPushButton, QShortcut, QPlainTextEdit, QLineEdit, QApplication
)
from PyQt5.QtGui import QImage, QPixmap, QKeySequence, QIcon, QFontDatabase
from PyQt5.QtCore import Qt, QPoint, QEvent

from config.paths import ICON_IMG, FONT_PATH
from engine.hangul_assembler import HangulAssembler
from ui.video_thread import VideoThread
from ui.windows import HelpWindow, SettingsWindow
from engine.hand_tts import HandTTS


class SignLanguageTranslatorApp(QWidget):
    def __init__(self, model, encoder):
        super().__init__()
        self.setWindowTitle("수어 번역 프로그램")
        try:
            self.setWindowIcon(QIcon(ICON_IMG))
        except Exception:
            pass
        
        self.current_rec_speed = 3.0
        self.is_paused = False
        self.show_landmarks = True

        self.camera_view = QLabel(self)
        self.camera_view.setObjectName("cameraView")
        self.camera_view.setMinimumSize(600, 480)

        self.pause_button = QPushButton("일시정지")
        self.settings_button = QPushButton("설정")
        self.help_button = QPushButton("도움말")

        self.log_box = QPlainTextEdit(self); self.log_box.setReadOnly(True)
        self.bottom_input = QLineEdit(self)
        
        # bottom_input에 이벤트 필터 설치 -> 포커스 유무 상태
        self.bottom_input.installEventFilter(self)
        
        
        # 폰트 로딩
        # FONT_PATH에 있는 폰트를 QFontDatabase에 추가
        font_id = QFontDatabase.addApplicationFont(str(FONT_PATH))
        # 폰트 패밀리 이름 로드
        font_family = QFontDatabase.applicationFontFamilies(font_id)[0]

        style_sheet = f"""
            QWidget {{ background-color: #2E2E2E; color: #F0F0F0; font-family: "{font_family}"; font-size: 11pt; }}
            #cameraView {{ border: 2px solid #00A0A0; border-radius: 5px; }}
            QPushButton {{ background-color: #555555; border: 1px solid #777777; padding: 5px; border-radius: 5px; }}
            QPushButton:hover {{ background-color: #6A6A6A; }} QPushButton:pressed {{ background-color: #4A4A4A; }}
            QPlainTextEdit, QLineEdit {{ background-color: #3C3C3C; border: 1px solid #555555; border-radius: 5px; font-size: 12pt; padding: 5px; }}
            QLineEdit {{ selection-background-color: #00A0A0; selection-color: white; }}
            QComboBox {{ border: 1px solid #777777; border-radius: 3px; padding: 1px 18px 1px 3px; min-width: 6em; background-color: #555555;}}
            QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 20px; border-left-width: 1px; border-left-color: #777777; border-left-style: solid; border-top-right-radius: 3px; border-bottom-right-radius: 3px; }}
            QCheckBox::indicator {{ width: 15px; height: 15px; }}
        """
        self.setStyleSheet(style_sheet)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.settings_button)
        button_layout.addWidget(self.help_button)

        right_pane_layout = QVBoxLayout()
        right_pane_layout.addLayout(button_layout)
        right_pane_layout.addWidget(self.log_box, stretch=10)
        right_pane_layout.addWidget(self.bottom_input, stretch=1)

        right_widget = QWidget()
        right_widget.setLayout(right_pane_layout)
        right_widget.setFixedWidth(350)

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.camera_view, stretch=2)
        main_layout.addWidget(right_widget, stretch=1)
        self.setLayout(main_layout)
        self.resize(980, 520)

        self.pause_button.clicked.connect(self.toggle_pause_resume)
        self.help_button.clicked.connect(self.toggle_help_window)
        self.settings_button.clicked.connect(self.open_settings_window)
        self.bottom_input.returnPressed.connect(self.finalize_sentence)

        self.help_window, self.settings_window = None, None
        self.assembler = HangulAssembler()

        self.thread = VideoThread(model, encoder)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.update_text_signal.connect(self.update_text)
        self.thread.start()

        self.quit_shortcut = QShortcut(QKeySequence('q'), self, context = Qt.WindowShortcut)
        self.quit_shortcut.activated.connect(self.close)   
        #self.quit_shortcut.activated.connect(self._handle_quit_shortcut); self.quit_shortcut.setEnabled(True) # 초기값: 비활성화  
        self.help_shortcut = QShortcut(QKeySequence(Qt.Key_F1), self)
        self.help_shortcut.activated.connect(self.toggle_help_window)

        self.tts = HandTTS(self)

    def toggle_pause_resume(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.thread.pause(); self.pause_button.setText("다시 시작")
        else:
            self.thread.resume(); self.pause_button.setText("일시정지")

    def open_settings_window(self):
        if self.settings_window is None or not self.settings_window.isVisible():
            current_volume = self.tts.get_volume() if hasattr(self, "tts") else 100
            self.settings_window = SettingsWindow(
                self.current_rec_speed,
                self.show_landmarks,
                current_volume,       # ← 볼륨 int
                self                  # ← parent
            )
            self.settings_window.speed_changed.connect(self.update_recognition_speed)
            self.settings_window.landmark_visibility_changed.connect(self.update_landmark_visibility)
            self.settings_window.volume_changed.connect(self.update_tts_volume)
            self.settings_window.show()
        else:
            self.settings_window.activateWindow()

    def update_recognition_speed(self, new_speed):
        self.current_rec_speed = new_speed
        self.thread.set_recognition_speed(new_speed) # VideoThread의 메서드를 통해 GestureRecognizer의 속성 업데이트
        #self.thread.rec_cool_time = new_speed
        #self.thread.display_duration = new_speed
        print(f"인식 속도가 {new_speed}초로 변경되었습니다.")

    def update_landmark_visibility(self, is_visible):
        self.show_landmarks = is_visible
        self.thread.set_landmark_visibility(is_visible)
        print(f"랜드마크 표시: {'ON' if is_visible else 'OFF'}")

    def finalize_sentence(self):
        text = self.bottom_input.text()
        if text: self.log_box.appendPlainText(text)
        self.bottom_input.clear()
        self.assembler = HangulAssembler()

    def update_text(self, new_char):
        if new_char == 'end':
            text_to_send = self.assembler.get_current_text_and_reset()
            if text_to_send: 
                self.log_box.appendPlainText(text_to_send)
                self.tts.speak(text_to_send)  # end 동작시 tts 실행
            self.bottom_input.clear()
            return
        current_text = self.assembler.add_char(new_char)
        self.bottom_input.setText(current_text)

    def toggle_help_window(self):
        if self.help_window is None or not self.help_window.isVisible():
            self.help_window = HelpWindow(self); self.help_window.setModal(False)
            self.help_window.move(self.frameGeometry().topRight() + QPoint(10, 0))
            self.help_window.show()
        else:
            self.help_window.close()

    def update_image(self, cv_img):
        qt_img = self.convert_cv_qt(cv_img); self.camera_view.setPixmap(qt_img)

    def convert_cv_qt(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        p = QPixmap.fromImage(QImage(rgb_image.data, w, h, ch * w, QImage.Format_RGB888))
        return p.scaled(self.camera_view.width(), self.camera_view.height(), Qt.KeepAspectRatio)
    
    
    def _handle_quit_shortcut(self):
        """ 'q'키가 눌렸을 때 프로그램을 종료 """
        # 현재 포커스가 bottom_input에 있다면 포커스 잃게 한다
        self.bottom_input.clearFocus()
        self.close()

    def mousePressEvent(self, event):
        """입력창 외부를 클릭 시, 포커스 해제"""
        if self.bottom_input.hasFocus():
            self.bottom_input.clearFocus()
        super().mousePressEvent(event)
        
    def eventFilter(self, source, event):
        """Linedit의 포커스 이벤트에 따라 q 단축키 활성화 유무 결정"""
        if source == self.bottom_input:
            if event.type() == QEvent.FocusIn:
                # 입력창에 포커스가 들어오면 q 단축키 비활성화
                self.quit_shortcut.setEnabled(False)
            elif event.type() == QEvent.FocusOut:
                # 입력창에서 포커스가 벗어나면 q 단축키 활성화
                self.quit_shortcut.setEnabled(True)
            
        return super().eventFilter(source, event)
    
    def keyPressEvent(self, event):
        """키보드 입력 이벤트 (q 단축키) 처리"""
        if event.key() == Qt.Key_Q:
            if not self.bottom_input.hasFocus():
                self.close()
            else:
                event.ignore()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.help_window and self.help_window.isVisible(): self.help_window.close()
        if self.settings_window and self.settings_window.isVisible(): self.settings_window.close()
        self.thread.stop()
        self.thread.wait() # 스레드가 완전히 종료될 때까지 대기
        event.accept()
        cv2.destroyAllWindows(); cv2.waitKey(1)
    
    def update_tts_volume(self, volume: int):
        self.tts.set_volume(volume)
        print(f"TTS 볼륨이 {volume}%로 변경되었습니다.")
