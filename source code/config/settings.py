# 카메라 및 화면 설정 -> utils/camera_controller.py 
CAMERA_INDEX = 0
REQ_WIDTH = 640
REQ_HEIGHT = 480
REOPEN_INTERVAL_SEC = 1.0
READ_FAIL_SLEEP_SEC = 0.3

# 인식 설정 -> engine/gesture_recognizer.py & ui/video_thread.py & ui/ui_app.py
REC_HISTORY_LEN = 5
REC_COOL_TIME = 3.0
DISPLAY_DURATION = 3.0
SHOW_LANDMARKS = True
CONFIDENCE_THRESHOLD = 0.5