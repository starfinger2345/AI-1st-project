"""훈련 모듈: 모델 훈련 및 저장"""

import joblib
from pathlib import Path
from config.paths import DATASET_FILE as dataset_file
from models.train_rf import train_model

if __name__ == "__main__":
    # 모델을 저장할 디렉터리 경로 설정
    models_dir = Path("models")
    # 디렉터리 없으면 생성
    models_dir.mkdir(exist_ok = True)
    
    print("================ 모델 훈련 시작 ================")
    model, encoder = train_model(dataset_file)
    
    if model and encoder:
        try:
            # 파일 경로를 models 디렉터리 아래로 저장
            joblib.dump(model, models_dir / "train_model.pkl")
            joblib.dump(encoder, models_dir / "encoder.pkl")
            print(f"모델 및 인코더 저장 완료 ({models_dir}/model.pkl, {models_dir}/encoder.pkl)")
            print("================ 모델 저장 완료 ================")
        except Exception as e:
            print(f"!!! 모델 저장 실패: {e} !!!")


