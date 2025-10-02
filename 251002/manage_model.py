import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder

from settings import dataset_file, model_file

class FeatureExtractor:
    """
    손 랜드마크 데이터로부터 -> 특징 벡터를 추출.
    (모든 메서드는 특정 인스턴스 상태에 의존하지 않으므로 static method로 정의.)
    """
    @staticmethod
    def calculate_angles(joint):
        v1 = joint[[0,1,2,3,0,5,6,7,0,9,10,11,0,13,14,15,0,17,18,19],:]
        v2 = joint[[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20],:]
        v = v2 - v1
        # 0으로 나누는 것을 방지
        '''
        norm_v = np.linalg.norm(v, axis=1)[:, np.newaxis]
        v = np.divide(v, norm_v, out=np.zeros_like(v), where=norm_v!=0)
        angle = np.arccos(np.einsum('nt,nt->n',
            v[[0,1,2,4,5,6,8,9,10,12,13,14,16,17,18],:],
            v[[1,2,3,5,6,7,9,10,11,13,14,15,17,18,19],:]))
        return np.degrees(angle).astype(np.float32)
        '''
        angle = np.arccos(np.einsum('nt,nt->n',
            v[[0,1,2,4,5,6,8,9,10,12,13,14,16,17,18],:],
            v[[1,2,3,5,6,7,9,10,11,13,14,15,17,18,19],:]))
        angle = np.degrees(angle)
        return angle.astype(np.float32)
        
    @staticmethod
    def calculate_distances(joint):
        thumb_tip = joint[4]
        other_tips = joint[[8, 12, 16, 20]]
        return np.linalg.norm(other_tips - thumb_tip, axis=1).astype(np.float32)

    @staticmethod
    def calculate_orientation_vectors(joint):
        v_direction = joint[9] - joint[0]
        if np.linalg.norm(v_direction) == 0: v_direction = np.zeros(3)
        else: v_direction = v_direction / np.linalg.norm(v_direction)

        v1 = joint[5] - joint[0]
        v2 = joint[17] - joint[0]
        v_normal = np.cross(v1, v2)
        if np.linalg.norm(v_normal) == 0: v_normal = np.zeros(3)
        else: v_normal = v_normal / np.linalg.norm(v_normal)

        return np.concatenate([v_direction, v_normal]).astype(np.float32)
        '''
        v_direction = joint[9] - joint[0]
        v_direction_norm = np.linalg.norm(v_direction)
        v_direction = np.divide(v_direction, v_direction_norm, out=np.zeros_like(v_direction), where=v_direction_norm!=0)
        
        v1 = joint[5] - joint[0]
        v2 = joint[17] - joint[0]
        v_normal = np.cross(v1, v2)
        v_normal_norm = np.linalg.norm(v_normal)
        v_normal = np.divide(v_normal, v_normal_norm, out=np.zeros_like(v_normal), where=v_normal_norm!=0)

        return np.concatenate([v_direction, v_normal]).astype(np.float32)
        '''
    
    @classmethod
    def extract_feature(cls, row_data):
        """단일 행(카메라 프레임 1개)의 랜드마크 데이터로부터 -> 특징을 추출합니다."""
        lh_landmarks = row_data[:63].reshape(21, 3); rh_landmarks = row_data[63:].reshape(21, 3)

        lh_angles = cls.calculate_angles(lh_landmarks) if np.any(lh_landmarks) else np.zeros(15, dtype=np.float32)
        rh_angles = cls.calculate_angles(rh_landmarks) if np.any(rh_landmarks) else np.zeros(15, dtype=np.float32)
        lh_coords = (lh_landmarks[1:] - lh_landmarks[0]).flatten() if np.any(lh_landmarks) else np.zeros(60, dtype=np.float32)
        rh_coords = (rh_landmarks[1:] - rh_landmarks[0]).flatten() if np.any(rh_landmarks) else np.zeros(60, dtype=np.float32)
        lh_distances = cls.calculate_distances(lh_landmarks) if np.any(lh_landmarks) else np.zeros(4, dtype=np.float32)
        rh_distances = cls.calculate_distances(rh_landmarks) if np.any(rh_landmarks) else np.zeros(4, dtype=np.float32)
        lh_orientation = cls.calculate_orientation_vectors(lh_landmarks) if np.any(lh_landmarks) else np.zeros(6, dtype=np.float32)
        rh_orientation = cls.calculate_orientation_vectors(rh_landmarks) if np.any(rh_landmarks) else np.zeros(6, dtype=np.float32)
        
        return np.concatenate([lh_angles, rh_angles, lh_coords, rh_coords, lh_distances, rh_distances, lh_orientation, rh_orientation])


class SignLanguageModel:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        self.encoder = LabelEncoder()

    def _load_and_preprocess_data(self):
        """CSV 파일에서 데이터를 로드하고 전처리."""
        print("===데이터셋 로드 및 전처리 시작===")
        try:
            labels_str = np.genfromtxt(dataset_file, delimiter=',', skip_header=1, usecols=0, encoding="utf-8", dtype=str)
            landmarks_data = np.genfromtxt(dataset_file, delimiter=',', skip_header=1, usecols=range(1, 127), encoding="utf-8").astype(np.float32)
        except Exception as e:
            print(f"데이터 파일 로드 오류: {e}")
            return None, None

        all_features = np.array([FeatureExtractor.extract_feature(row) for row in landmarks_data])
        encoded_labels = self.encoder.fit_transform(labels_str)
        print("데이터 전처리 완료!")
        return all_features, encoded_labels

    def train(self):
        """모델 학습."""
        X, y = self._load_and_preprocess_data()
        if X is None: return

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        print("--- 랜덤 포레스트 모델 학습 시작 ---")
        self.model.fit(X_train, y_train)
        
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        print("\n--- 학습 완료 ---")
        print(f"모델 테스트 정확도: {accuracy * 100:.2f}%")

    def save(self, filepath=model_file):
        """학습된 모델과 인코더를 파일에 저장."""
        joblib.dump({'model': self.model, 'encoder': self.encoder}, filepath)
        print(f"모델이 '{filepath}' 파일로 저장되었습니다.")

    @classmethod
    def load(cls, filepath=model_file):
        """파일에서 모델과 인코더를 로드하여 => 클래스 인스턴스를 반환."""
        try:
            data = joblib.load(filepath)
            instance = cls()
            instance.model = data['model']
            instance.encoder = data['encoder']
            print(f"'{filepath}'에서 모델을 성공적으로 불러왔습니다.")
            return instance
        except Exception as e:
            print(f"모델 로드 중 오류 발생: {e}")
            return None

    def predict(self, feature_vector):
        """단일 특징 벡터에 대한 예측을 수행하고 라벨명을 반환."""
        predicted_index = self.model.predict(feature_vector.reshape(1, -1))
        return self.encoder.inverse_transform(predicted_index)[0]
