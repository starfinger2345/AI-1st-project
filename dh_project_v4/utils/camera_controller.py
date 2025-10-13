import cv2
import sys
import time


class CameraController:
    """카메라 초기화 및 프레임 캡쳐 담당 클래스"""
    """
    카메라 연결 / 재시도 / 프레임 읽기 책임만 담당합니다.
    (원본 video_thread.py의 _backend_for_os, _try_open, _safe_release,
    카메라 속성 설정 부분을 이 클래스로 옮겼습니다.)
    """
    def __init__(self, camera_index=0, req_width=640, req_height=480,
                 reopen_interval_sec=1.0, read_fail_sleep_sec=0.3):
        """
        Args:
            camera_index (int)          : 카메라 장치의 인덱스. Defaults to 0.
            req_width (int)             : 요청한 프레임 너비. Defaults to 640.
            req_height (int)            : 요청한 프레임높이. Defaults to 480.
            reopen_interval_sec (float) : 카메라 연결 실패 시 재시도 간격. Defaults to 1.0.
            read_fail_sleep_sec (float) : 프레임 읽기 실패 시 대기 시간. Defaults to 0.3.
            self.cap                    : cv2.VideoCapture 객체(카메라 자원을 관리)
            self._last_error            : 마지막 에러 메시지 저장(없으면 None)
        """
        self.camera_index = camera_index
        self.req_width, self.req_height = req_width, req_height
        self.reopen_interval_sec = reopen_interval_sec
        self.read_fail_sleep_sec = read_fail_sleep_sec
        self.cap = None
        self._last_error = None
        
    def _backend_for_os(self):
        """
        운영체제에 맞는 OpenCV 카메라 백엔드 반환
        """
        if sys.platform.startswith("win"):
            return cv2.CAP_DSHOW
        elif sys.platform.startswith("linux"):
            return cv2.CAP_V4L2
        else:
            return 0
    
    def _try_open(self) -> bool:
        """
        카메라 열기 시도하고 성공 여부와 메시지 반환
        성공 시 True 반환. 실패 시 False 반환, self._last_error에 에러 메시지 저장.
        (재시도는 호출하는 쪽에서 처리)
        반환: (success: bool, error_msg: Optional[str])
        """
        backend = self._backend_for_os()
        try:
            self.cap = cv2.VideoCapture(self.camera_index, backend) if backend else cv2.VideoCapture(self.camera_index)
        except Exception as e:
            self.cap = None
            self._last_error = f"!!! 카메라 열기 예외 !!!\n: {e}"
            time.sleep(self.reopen_interval_sec)
            return False, self._last_error

        if not (self.cap and self.cap.isOpened()):
            self._last_error = f"!!! 카메라 미연결/점유 중… (index={self.camera_index}) !!!"
            self._safe_release()
            time.sleep(self.reopen_interval_sec)
            return False, self._last_error

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.req_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.req_height)
        return True, None
    
    def is_opened(self) -> bool:
        """카메라가 열려있는지 여부 반환"""
        return self.cap is not None and self.cap.isOpened()
    
    def read(self):
        """
        카메라에서 프레임 읽어 반환.
        성공 시 (True, frame) 반환. 실패 시 (False, None) 반환, self._last_error에 에러 메시지 저장.
        """
        if not self.is_opened():
            self._last_error = "!!! 카메라가 열려있지 않음 !!!"
            return False, None
        ret, frame = self.cap.read()
        if not ret or frame is None:
            self._last_error = "!!! 프레임 읽기 실패 !!!"
            time.sleep(self.read_fail_sleep_sec)
            return False, None
        return True, frame
    
    def _safe_release(self):
        """카메라 자원 해제"""
        try:
            if self.cap is not None and self.cap.isOpened():
                self.cap.release()
        except Exception:
            pass
        finally:
            self.cap = None
            
    def set_camera_index(self, index: int):
        """카메라 인덱스 변경 및 재연결 (다음 시도 시, 새 인덱스로 열기 시도)"""
        if self.camera_index != index:
            return
        self.camera_index = index
        self.release()
        
        