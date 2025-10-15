import time
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from utils.camera_controller import CameraController
from engine.gesture_recognizer import GestureRecognizer
from config.settings import (CAMERA_INDEX, REQ_WIDTH, REQ_HEIGHT,
                             REC_HISTORY_LEN, REC_COOL_TIME, DISPLAY_DURATION, SHOW_LANDMARKS, CONFIDENCE_THRESHOLD)

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    update_text_signal = pyqtSignal(str)

    def __init__(self, model, encoder):
        super().__init__()
        self._run_flag = True
        self._is_paused = False
        
        # 카메라 및 제스처 인식기 초기화
        self.camera = CameraController(camera_index=CAMERA_INDEX,
                                        req_width=REQ_WIDTH,
                                        req_height=REQ_HEIGHT)
        self.recognizer = GestureRecognizer(model=model,
                                            encoder=encoder,
                                            rec_history_len = REC_HISTORY_LEN,
                                            rec_cool_time = REC_COOL_TIME,
                                            display_duration = DISPLAY_DURATION,
                                            show_landmarks = SHOW_LANDMARKS,
                                            conf_thres = CONFIDENCE_THRESHOLD)
        
        # UI에서 직접 접근하도록 속성 연결-> UI 토글
        self.rec_cool_time = REC_COOL_TIME
        self.display_duration = DISPLAY_DURATION
        self.show_landmarks = SHOW_LANDMARKS
    
    
    # 일시정지/재개 버튼  
    def pause(self): self._is_paused = True       
    def resume(self): self._is_paused = False
    
    def set_camera(self, index:int):
        """UI에서 카메라 인덱스 변경 시 호출"""
        self.camera.set_camera_index(index)
        self.update_text_signal.emit(f"@@@ 카메라 변경: index={index} @@@")
        # 카메라 자원은 CameraController에 의해 재오픈 시 처리
        
    def stop(self):
        """스레드 중단, 자원 해제 (안전하게)"""
        self._run_flag = False
        if hasattr(self, "camera") and self.camera is not None:
            self.camera._safe_release()
            self.camera = None
        if hasattr(self, "recognizer") and self.recognizer is not None:
            self.recognizer = None
        self.quit()
        
        '''
        try:
            if self.camera is not None:
                self.camera.release()
        except Exception:
            pass
        # recognizer 객체가 유효할 때만 close() 호출
        # recognizer 객체가 있고, 그 객체에 hands라는 속성이 존재하며, hands.close()를 실행하는데 오류가 없으면 -> close() 실행 >> 오류 충돌 방지
        try:
            if self.recognizer and hasattr(self.recognizer, "hands"): # recognizer 객체가 None인지 확인, recognizer 객체에 hands라는 속성이 존재하는지 확인
                self.recognizer.close()
        except Exception:
            pass
        
        self.wait()
        '''
        
    def set_landmark_visibility(self, visible: bool):
        """화면에 랜드마크 표시 여부 설정 -> GestureRecognizer에 전달"""
        self.recognizer.set_show_landmarks(visible)
        
    def set_recognition_speed(self, new_speed: float):
        """인식 속도 변경 설정 -> GestureRecognizer에 전달"""
        self.recognizer.rec_cool_time = new_speed
        self.recognizer.display_duration = new_speed
        
        
    
    def run(self):
        """
        메인 루프: 카메라에서 프레임 읽고 제스처 인식, 시각화, 신호 방출
        - 카메라 재연결 시그널 전달
        - 프레임 수신 실패시 재시도
        - 인식 결과(확정 레이블) 발생시 update_text_signal 전송
        - 프레임은 change_pixmap_signal로 전송 (시각화 포함)
        """
        while self._run_flag:
            if self._is_paused:
                time.sleep(0.01)
                continue
            
            # 카메라 객체가 전달 안되면 run() 실행하지 않는다
            if not self._run_flag or self.camera is None or self.recognizer is None:
                break
            
            # 카메라 연결 시도 (카메라 연결되어 있지 않으면 재시도)
            if not self.camera.is_opened():
                success, msg = self.camera._try_open()
                if msg:
                    self.update_text_signal.emit(msg)
                if not success:
                    time.sleep(self.camera.reopen_interval_sec)
                    continue
                
            # 프레임 읽기
            success, frame = self.camera.read()
            if not success or frame is None:
                # 읽기 실패한 경우
                self.update_text_signal.emit("!!! 프레임 수신 실패... 재연결 !!!")
                #self.camera._safe_release() #release를 즉시 하지 않고 다음 루프에서 _try_open()이 처리하도록 한다
                time.sleep(self.camera.read_fail_sleep_sec)
                continue
            
            # 웹캠 좌우반전 방지
            frame = cv2.flip(frame,1)
            
            # 제스처 인식 및 시각화
            try:
                out_frame, mapped_label = self.recognizer.process_frame(frame)
            except Exception as e:
                # frame이 손상되거나 recognizer 내부 에러일 때 안전 복구
                print("!!! 프레임을 정상적으로 처리하지 못했습니다 !!! :", e)
                continue
            
            # 안정적으로 확정된 레이블이 나왔을 때 UI로 전달
            # UI 업데이트
            if mapped_label:
                self.update_text_signal.emit(mapped_label)
            # Pixmap 갱신 시그널 전송
            if out_frame is not None:
                self.change_pixmap_signal.emit(out_frame)
                
            time.sleep(0.001)
            
        # 루프가 끝나면 안전하게 해제
        if self.camera is not None:
            self.camera._safe_release()