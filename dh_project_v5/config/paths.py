import os

# 프로젝트 루트 경로
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 주요 폴더
DATA_DIR = os.path.join(BASE_DIR, 'data')
MODELS_DIR= os.path.join(BASE_DIR, 'models')

#개별 파일 경로
DATASET_FILE = os.path.join(DATA_DIR, 'combine_4.csv') # 수집한 데이터셋 파일
HELP_IMG = os.path.join(DATA_DIR,'hand_img.png') # 도움말 이미지
ICON_IMG = os.path.join(DATA_DIR,'세종머왕.png') # 앱 아이콘
FONT_PATH = os.path.join(DATA_DIR, 'GowunDodum-Regular.ttf')
TRAINED_MODEL = os.path.join(MODELS_DIR, 'trained_model.pkl')
