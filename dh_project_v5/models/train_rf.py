# -*- coding: utf-8 -*-
"""모델 훈련"""
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score

from engine.preprocessor import load_and_preprocess

def train_model(dataset_file):
    """
    DESCRIPTION
        1. engine/preprocessor/load_and_preprocessor: 전처리된 데이터 준비
        2. 데이터 분리(훈련 데이터 / 테스트 데이터)
        3. 렌덤포레스트 분류기 모델로 훈련
        4. 테스트 정확도 & F1-score 계산
        
    RETURN
        1. model   : 훈련된 모델 객체
        2. encoder : 인코더 객체 
    """
    X, y, encoder = load_and_preprocess(dataset_file)
    if X is None: return None, None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    print("--- 랜덤 포레스트 모델 학습 시작 ---")
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred) * 100
    print(f"\n--- 학습 완료 ---\n모델 테스트 정확도: {acc:.4f}%")
    f1 = f1_score(y_test, y_pred, average='micro')
    print(f"f1_score: {f1:.6f}")
    return model, encoder
