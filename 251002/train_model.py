from manage_model_test import SignLanguageModel

if __name__ == "__main__":
    # 1. 모델 객체 생성
    sl_model = SignLanguageModel()

    # 2. 모델 학습
    sl_model.train()

    # 3. 학습된 모델 저장
    sl_model.save()