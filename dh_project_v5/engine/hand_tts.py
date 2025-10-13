# -*- coding: utf-8 -*-
""" 텍스트 음성 변환(TTS)"""
import os, uuid, tempfile
from typing import Optional

# ===========================
# PyQt5 / PyQt6 호환 처리
# ===========================
try:
    from PyQt6.QtCore import QObject, QThread, pyqtSignal, QUrl, QTimer
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    _PYQT = 6
except Exception:
    from PyQt5.QtCore import QObject, QThread, pyqtSignal, QUrl, QTimer
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
    _PYQT = 5

from gtts import gTTS


# ===========================
# 실제 TTS 변환을 백그라운드에서 처리하는 워커 스레드
# ===========================
class _TTSWorker(QThread):
    """
    DESCRIPTION:
        gTTS 라이브러리 사용해 => 텍스트를 MP3 파일로 변환
    RETURN:
        작업 완료 또는 실패 시 시그널을 전송
    """
    done = pyqtSignal(str)   # 변환 완료 → mp3 파일 경로 반환
    error = pyqtSignal(str)  # 변환 실패 → 에러 메시지 반환

    def __init__(self, text:str, lang='ko', out_dir:Optional[str]=None):
        super().__init__()
        self.text = text
        self.lang = lang
        # 결과 mp3 파일을 저장할 폴더 (기본: 시스템 임시폴더)
        self.out_dir = out_dir or tempfile.gettempdir()

    def run(self):
        try:
            # 텍스트가 비어있으면 에러 처리
            if not self.text or not self.text.strip():
                self.error.emit("EMPTY_TEXT"); return

            # 임시 mp3 파일 경로 생성
            fpath = os.path.join(self.out_dir, f"tts_{uuid.uuid4().hex}.mp3")

            # gTTS로 음성 합성 후 mp3 저장
            gTTS(text=self.text, lang=self.lang).save(fpath)

            # 성공 시 mp3 경로 시그널 송출
            self.done.emit(fpath)
        except Exception as e:
            # 에러 발생 시 에러 메시지 송출
            self.error.emit(str(e))


# ===========================
# TTS 전체 제어 클래스
# ===========================
class HandTTS(QObject):
    """TTS 기능을 제어하는 메인 클래스"""
    # 이벤트 시그널 정의
    speakingStarted = pyqtSignal(str)   # 음성 시작 (텍스트 함께 전달)
    speakingFinished = pyqtSignal(str)  # 음성 끝남 ("OK" 반환)
    speakingError = pyqtSignal(str)     # 에러 발생 (에러 메시지 반환)

    def __init__(self, parent=None, lang='ko'):
        super().__init__(parent)
        self._lang = lang
        self._player = None    # QMediaPlayer 객체
        self._audio = None     # PyQt6의 경우 QAudioOutput 필요
        self._current_mp3 = None
        self._init_player()    # 오디오 플레이어 초기화
        self._is_busy = False  # 현재 재생 중인지 여부
        self._pending_text: Optional[str] = None  # 재생 중일 때 예약된 텍스트

    # ---------------------------
    # 오디오 플레이어 초기화
    # ---------------------------
    def _init_player(self):
        """PyQt 버전(5 또는 6)에 따라 오디오 플레이어를 초기화"""    
        if _PYQT == 6:
            self._player = QMediaPlayer(self)

            # PyQt6는 AudioOutput 객체 필수
            try:
                self._audio = QAudioOutput(self)
            except Exception:
                self._audio = QAudioOutput()

            self._player.setAudioOutput(self._audio)

            # 기본 볼륨 (0.0 ~ 1.0)
            try: 
                self._audio.setVolume(1.0)
            except Exception: 
                pass

            # 상태 변화 시그널 연결
            self._player.mediaStatusChanged.connect(self._on_media_status_changed)
            self._player.playbackStateChanged.connect(self._on_state_changed)
        else:
            # PyQt5는 QMediaPlayer만 사용
            self._player = QMediaPlayer(self)

            # 기본 볼륨 (0 ~ 100)
            try: 
                self._player.setVolume(100)
            except Exception: 
                pass

            # 상태 변화 시그널 연결
            self._player.mediaStatusChanged.connect(self._on_media_status_changed)

    # 언어 설정 (기본: 한국어 'ko')
    def set_lang(self, lang='ko'):
        self._lang = lang

    # ---------------------------
    # 텍스트를 받아서 음성 출력
    # ---------------------------
    def speak(self, text:str):
        """지정된 텍스트를 음성으로 변환하여 재생 (재생 중인 경우, 다음 텍스트를 대기열에 추가)"""
        if self._is_busy:
            # 현재 재생 중이면 대기열에 넣음
            self._pending_text = text
            return
        self._is_busy = True
        self.speakingStarted.emit(text)

        # 백그라운드 워커 실행 (gTTS → mp3 생성)
        self._worker = _TTSWorker(text, self._lang)
        self._worker.done.connect(self._on_synth_ready)
        self._worker.error.connect(self._on_synth_error)
        self._worker.start()

    # 재생 중지
    def stop(self):
        """재생 중인 음성을 중지"""
        try: self._player.stop()
        except Exception: pass

    # ---------------------------
    # 워커에서 음성 합성 완료 시 호출
    # ---------------------------
    def _on_synth_ready(self, mp3_path:str):
        self._current_mp3 = mp3_path
        if _PYQT == 6:
            # PyQt6: setSource 방식
            self._player.setSource(QUrl.fromLocalFile(mp3_path))
        else:
            # PyQt5: setMedia + QMediaContent 방식
            self._player.setMedia(QMediaContent(QUrl.fromLocalFile(mp3_path)))

        # 음성 재생 시작
        self._player.play()

    # 워커에서 에러 발생 시 호출
    def _on_synth_error(self, msg:str):
        self._is_busy = False
        self.speakingError.emit(msg)

        # 대기열에 텍스트가 있으면 이어서 실행
        if self._pending_text:
            t = self._pending_text; self._pending_text = None
            QTimer.singleShot(0, lambda: self.speak(t))

    def _on_state_changed(self, s):  # PyQt6 전용
        # 디버깅 용도로 사용 가능 (현재 재생 상태)
        # print("player state:", s)
        pass

    # ---------------------------
    # 미디어 상태 변경 시 호출
    # ---------------------------
    def _on_media_status_changed(self, status):
        """
        미디어 재생 상태가 변경될 때 호출.
        재생이 끝나면 임시 MP3 파일을 삭제하고 다음 텍스트를 재생.
        """
        # status는 숫자 또는 Enum 이름으로 전달됨
        status_str = str(status)

        # EndOfMedia (6번 상태) → 재생 종료
        is_end = ("EndOfMedia" in status_str) or (str(int(status)) == "6")
        if is_end:
            # 임시 mp3 파일 삭제
            if self._current_mp3 and os.path.exists(self._current_mp3):
                try: os.remove(self._current_mp3)
                except Exception: pass
            self._current_mp3 = None

            # 상태 리셋
            self._is_busy = False
            self.speakingFinished.emit("OK")

            # 예약된 텍스트가 있으면 바로 이어서 재생
            if self._pending_text:
                t = self._pending_text; self._pending_text = None
                QTimer.singleShot(0, lambda: self.speak(t))

    # ---------------------------
    # 볼륨 제어 (0 ~ 100)
    # ---------------------------
    def set_volume(self, vol: int):
        """볼륨 설정 (0~100 정수)"""
        vol = max(0, min(100, int(vol)))
        if _PYQT == 6:
            try:
                self._audio.setVolume(vol / 100.0)   # 0.0 ~ 1.0
            except Exception:
                pass
        else:
            try:
                self._player.setVolume(vol)          # 0 ~ 100
            except Exception:
                pass

    def get_volume(self) -> int:
        """현재 볼륨 반환 (0~100)"""
        if _PYQT == 6:
            try:
                return int(round((self._audio.volume() or 0.0) * 100))
            except Exception:
                return 100
        else:
            try:
                return int(self._player.volume())
            except Exception:
                return 100
