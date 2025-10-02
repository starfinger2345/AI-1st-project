# ---파일 경로 설정---
font_path = "C:/Windows/Fonts/gulim.ttc"
dataset_file = 'data/combine_4.csv'
model_file = 'sign_language_model.joblib' # 학습된 모델을 저장할 파일명


# ---영상 처리 설정---
rec_cool_time = 3.0   # 제스처 인식 후 쿨타임 (초)
display_duration = 3.0 # 인식된 제스처 화면 표시 시간 (초)
history_maxlen= 5  # 제스처 판독을 위한 히스토리 길이
