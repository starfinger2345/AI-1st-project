# -*- coding: utf-8 -*-
"""콘솔창에 필요 없는 문구 차단"""
import os
os.environ.pop("QT_PLUGIN_PATH", None)  # OpenCV가 오염시킨 경로 제거
os.environ["QT_QPA_PLATFORM"] = "xcb"   # Wayland 대신 X11 사용
import warnings
import logging
import contextlib
# 불필요한 warning 차단
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"   # TensorFlow 로그 (0=모두, 1=INFO, 2=WARNING, 3=ERROR만)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
# Mediapipe / Protobuf 경고 억제
logging.getLogger("absl").setLevel(logging.ERROR)
logging.getLogger("mediapipe").setLevel(logging.ERROR)
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("google.protobuf").setLevel(logging.ERROR)


import sys
import joblib
from pathlib import Path
from PyQt5.QtWidgets import QApplication

from ui.ui_app import SignLanguageTranslatorApp



def main():
    try:
        # models 폴더 경로 설정
        models_dir = Path("models")
        # 훈련된 모델과 인코더 불러오기
        trained_model = joblib.load(models_dir / "train_model.pkl")
        label_encoder = joblib.load(models_dir / "encoder.pkl")
        print("===== 모델 및 인코더 로드 완료 =====")
    except FileNotFoundError:
        print("!!! 모델 파일이 없습니다 !!!\n`train.py`를 먼저 실행하여 모델을 훈련하고 저장하세요.")
    except Exception as e:
        print("모델 불러오기 실패:",e)
        return
    
    app = QApplication(sys.argv)
    window = SignLanguageTranslatorApp(trained_model, label_encoder)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()