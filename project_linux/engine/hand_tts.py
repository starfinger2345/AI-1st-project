# # hand_tts.py
# # -*- coding: utf-8 -*-
# import os, uuid, tempfile
# from typing import Optional

# # ===========================
# # PyQt5 / PyQt6 호환 처리
# # ===========================
# try:
#     from PyQt6.QtCore import QObject, QThread, pyqtSignal, QUrl, QTimer
#     from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
#     _PYQT = 6
# except Exception:
#     from PyQt5.QtCore import QObject, QThread, pyqtSignal, QUrl, QTimer
#     from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
#     _PYQT = 5

# from gtts import gTTS

# import os, subprocess
# from gtts import gTTS
# from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QSoundEffect
# from PyQt5.QtCore import QUrl, QTimer

# # ===========================
# # 실제 TTS 변환을 백그라운드에서 처리하는 워커 스레드
# # ===========================
# class _TTSWorker(QThread):
#     done = pyqtSignal(str)   # 변환 완료 → mp3 파일 경로 반환
#     error = pyqtSignal(str)  # 변환 실패 → 에러 메시지 반환

#     def __init__(self, text:str, lang='ko', out_dir:Optional[str]=None):
#         super().__init__()
#         self.text = text
#         self.lang = lang
#         # 결과 mp3 파일을 저장할 폴더 (기본: 시스템 임시폴더)
#         self.out_dir = out_dir or tempfile.gettempdir()

#     def run(self):
#         try:
#             # 텍스트가 비어있으면 에러 처리
#             if not self.text or not self.text.strip():
#                 self.error.emit("EMPTY_TEXT"); return

#             # 임시 mp3 파일 경로 생성
#             fpath = os.path.join(self.out_dir, f"tts_{uuid.uuid4().hex}.mp3")

#             # gTTS로 음성 합성 후 mp3 저장
#             gTTS(text=self.text, lang=self.lang).save(fpath)

#             # 성공 시 mp3 경로 시그널 송출
#             self.done.emit(fpath)
#         except Exception as e:
#             # 에러 발생 시 에러 메시지 송출
#             self.error.emit(str(e))


# # ===========================
# # TTS 전체 제어 클래스
# # ===========================
# class HandTTS(QObject):
#     # 이벤트 시그널 정의
#     speakingStarted = pyqtSignal(str)   # 음성 시작 (텍스트 함께 전달)
#     speakingFinished = pyqtSignal(str)  # 음성 끝남 ("OK" 반환)
#     speakingError = pyqtSignal(str)     # 에러 발생 (에러 메시지 반환)

#     def __init__(self, parent=None, lang='ko'):
#         super().__init__(parent)
#         self._lang = lang
#         self._player = None    # QMediaPlayer 객체
#         self._audio = None     # PyQt6의 경우 QAudioOutput 필요
#         self._current_mp3 = None
#         self._init_player()    # 오디오 플레이어 초기화
#         self._is_busy = False  # 현재 재생 중인지 여부
#         self._pending_text: Optional[str] = None  # 재생 중일 때 예약된 텍스트

#     # ---------------------------
#     # 오디오 플레이어 초기화
#     # ---------------------------
#     def _init_player(self):
#         if _PYQT == 6:
#             self._player = QMediaPlayer(self)

#             # PyQt6는 AudioOutput 객체 필수
#             try:
#                 self._audio = QAudioOutput(self)
#             except Exception:
#                 self._audio = QAudioOutput()

#             self._player.setAudioOutput(self._audio)

#             # 기본 볼륨 (0.0 ~ 1.0)
#             try: 
#                 self._audio.setVolume(1.0)
#             except Exception: 
#                 pass

#             # 상태 변화 시그널 연결
#             self._player.mediaStatusChanged.connect(self._on_media_status_changed)
#             self._player.playbackStateChanged.connect(self._on_state_changed)
#         else:
#             # PyQt5는 QMediaPlayer만 사용
#             self._player = QMediaPlayer(self)

#             # 기본 볼륨 (0 ~ 100)
#             try: 
#                 self._player.setVolume(100)
#             except Exception: 
#                 pass

#             # 상태 변화 시그널 연결
#             self._player.mediaStatusChanged.connect(self._on_media_status_changed)

#     # 언어 설정 (기본: 한국어 'ko')
#     def set_lang(self, lang='ko'):
#         self._lang = lang

#     # ---------------------------
#     # 텍스트를 받아서 음성 출력
#     # ---------------------------
#     def speak(self, text:str):
#         if self._is_busy:
#             # 현재 재생 중이면 대기열에 넣음
#             self._pending_text = text
#             return
#         self._is_busy = True
#         self.speakingStarted.emit(text)

#         # 백그라운드 워커 실행 (gTTS → mp3 생성)
#         self._worker = _TTSWorker(text, self._lang)
#         self._worker.done.connect(self._on_synth_ready)
#         self._worker.error.connect(self._on_synth_error)
#         self._worker.start()
    
#     def _on_synth_ready(self, mp3_path: str):
#         """워커가 MP3 생성 완료 후 호출됨 → MP3 재생 시도, 실패 시 WAV 폴백"""
#         try:
#             self._play_mp3(mp3_path)
#         except Exception as e:
#             self._play_wav_fallback(mp3_path, reason=f"exception: {e}")

#     def _on_synth_error(self, message: str):
#         # 기존 로직 유지 + 상태 복구
#         try:
#             print("[TTS] synth error:", message)
#         finally:
#             self._is_busy = False
#             self.speakingFinished.emit(False, message)  # 필요 시 시그널 인자 형식 맞춰주세요
#             if getattr(self, "_pending_text", None):
#                 text = self._pending_text; self._pending_text = None
#                 self.speak(text)

#     def _play_mp3(self, mp3_path: str):
#         """QMediaPlayer로 MP3 재생 시도"""
#         url = QUrl.fromLocalFile(mp3_path)
#         self._player = QMediaPlayer(self)
#         self._player.setMedia(QMediaContent(url))
#         # 볼륨 필드가 0~100 정수라고 가정
#         self._player.setVolume(getattr(self, "_volume", 100))

#         def on_err(err):
#             # QMediaPlayer 오류 시 WAV 폴백
#             self._player.error.disconnect(on_err)
#             self._player.stateChanged.disconnect(on_state)
#             self._play_wav_fallback(mp3_path, reason=f"QMediaPlayer error={err}")

#         def on_state(state):
#             from PyQt5.QtMultimedia import QMediaPlayer as _QMP
#             if state == _QMP.StoppedState:
#                 self._finish_and_drain_queue()

#         self._player.error.connect(on_err)
#         self._player.stateChanged.connect(on_state)
#         self._player.play()
#         # 여기까지 예외 없이 오면 일단 MP3 재생 시도는 성공 경로

#     def _play_wav_fallback(self, mp3_path: str, reason: str = ""):
#         """ffmpeg으로 WAV 변환 후 QSoundEffect로 재생 (MP3 디코더 미탑재 환경용)"""
#         wav_path = str(Path(mp3_path).with_suffix(".wav"))
#         try:
#             subprocess.run(
#                 ["ffmpeg", "-y", "-i", mp3_path, wav_path],
#                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
#             )
#         except Exception as e:
#             return self._on_synth_error(f"WAV fallback convert failed: {e} (reason: {reason})")

#         self._se = QSoundEffect(self)
#         self._se.setSource(QUrl.fromLocalFile(wav_path))
#         # QSoundEffect 볼륨은 0.0~1.0
#         self._se.setVolume(max(0.0, min(1.0, (getattr(self, "_volume", 100) / 100.0))))
#         self._se.play()

#         # 재생 종료 감지 후 큐 처리
#         def on_playing_changed():
#             if not self._se.isPlaying():
#                 try:
#                     self._se.playingChanged.disconnect(on_playing_changed)
#                 except Exception:
#                     pass
#                 self._finish_and_drain_queue()

#         self._se.playingChanged.connect(on_playing_changed)

#     def _finish_and_drain_queue(self):
#         """현재 발화 종료 처리 + 대기열 비우기"""
#         self._is_busy = False
#         self.speakingFinished.emit(True, "")  # 시그널 인자 형식 프로젝트에 맞춰 조정
#         if getattr(self, "_pending_text", None):
#             text = self._pending_text; self._pending_text = None
#             self.speak(text)


    

#     # 재생 중지
#     def stop(self):
#         try: self._player.stop()
#         except Exception: pass

#     # ---------------------------
#     # 워커에서 음성 합성 완료 시 호출
#     # ---------------------------
#     def _on_synth_ready(self, mp3_path:str):
#         self._current_mp3 = mp3_path
#         if _PYQT == 6:
#             # PyQt6: setSource 방식
#             self._player.setSource(QUrl.fromLocalFile(mp3_path))
#         else:
#             # PyQt5: setMedia + QMediaContent 방식
#             self._player.setMedia(QMediaContent(QUrl.fromLocalFile(mp3_path)))

#         # 음성 재생 시작
#         self._player.play()

#     # 워커에서 에러 발생 시 호출
#     def _on_synth_error(self, msg:str):
#         self._is_busy = False
#         self.speakingError.emit(msg)

#         # 대기열에 텍스트가 있으면 이어서 실행
#         if self._pending_text:
#             t = self._pending_text; self._pending_text = None
#             QTimer.singleShot(0, lambda: self.speak(t))

#     def _on_state_changed(self, s):  # PyQt6 전용
#         # 디버깅 용도로 사용 가능 (현재 재생 상태)
#         # print("player state:", s)
#         pass

#     # ---------------------------
#     # 미디어 상태 변경 시 호출
#     # ---------------------------
#     def _on_media_status_changed(self, status):
#         # status는 숫자 또는 Enum 이름으로 전달됨
#         status_str = str(status)

#         # EndOfMedia (6번 상태) → 재생 종료
#         is_end = ("EndOfMedia" in status_str) or (str(int(status)) == "6")
#         if is_end:
#             # 임시 mp3 파일 삭제
#             if self._current_mp3 and os.path.exists(self._current_mp3):
#                 try: os.remove(self._current_mp3)
#                 except Exception: pass
#             self._current_mp3 = None

#             # 상태 리셋
#             self._is_busy = False
#             self.speakingFinished.emit("OK")

#             # 예약된 텍스트가 있으면 바로 이어서 재생
#             if self._pending_text:
#                 t = self._pending_text; self._pending_text = None
#                 QTimer.singleShot(0, lambda: self.speak(t))

#     # ---------------------------
#     # 볼륨 제어 (0 ~ 100)
#     # ---------------------------
#     def set_volume(self, vol: int):
#         """볼륨 설정 (0~100 정수)"""
#         vol = max(0, min(100, int(vol)))
#         if _PYQT == 6:
#             try:
#                 self._audio.setVolume(vol / 100.0)   # 0.0 ~ 1.0
#             except Exception:
#                 pass
#         else:
#             try:
#                 self._player.setVolume(vol)          # 0 ~ 100
#             except Exception:
#                 pass

#     def get_volume(self) -> int:
#         """현재 볼륨 반환 (0~100)"""
#         if _PYQT == 6:
#             try:
#                 return int(round((self._audio.volume() or 0.0) * 100))
#             except Exception:
#                 return 100
#         else:
#             try:
#                 return int(self._player.volume())
#             except Exception:
#                 return 100

# hand_tts.py
# -*- coding: utf-8 -*-
import os, uuid, tempfile, subprocess
from pathlib import Path
from typing import Optional

# ===========================
# PyQt5 / PyQt6 호환 처리
# ===========================
try:
    from PyQt6.QtCore import QObject, QThread, pyqtSignal, QUrl, QTimer
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QSoundEffect
    _PYQT = 6
except Exception:
    from PyQt5.QtCore import QObject, QThread, pyqtSignal, QUrl, QTimer
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QSoundEffect
    _PYQT = 5

from gtts import gTTS


# ===========================
# gTTS 백그라운드 워커
# ===========================
class _TTSWorker(QThread):
    done = pyqtSignal(str)   # mp3 파일 경로
    error = pyqtSignal(str)  # 에러 메시지

    def __init__(self, text: str, lang='ko', out_dir: Optional[str] = None):
        super().__init__()
        self.text = text
        self.lang = lang
        self.out_dir = out_dir or tempfile.gettempdir()

    def run(self):
        try:
            if not self.text or not self.text.strip():
                self.error.emit("EMPTY_TEXT")
                return
            fpath = os.path.join(self.out_dir, f"tts_{uuid.uuid4().hex}.mp3")
            gTTS(text=self.text, lang=self.lang).save(fpath)
            self.done.emit(fpath)
        except Exception as e:
            self.error.emit(str(e))


# ===========================
# TTS 제어 클래스 (MP3 → 실패 시 WAV)
# ===========================
class HandTTS(QObject):
    speakingStarted = pyqtSignal(str)    # 시작: 원문 텍스트
    speakingFinished = pyqtSignal(str)   # 종료: "OK" 또는 메시지
    speakingError = pyqtSignal(str)      # 에러: 메시지

    def __init__(self, parent=None, lang='ko'):
        super().__init__(parent)
        self._lang = lang
        self._player = None
        self._audio = None      # PyQt6 전용
        self._se = None         # QSoundEffect
        self._current_mp3 = None
        self._is_busy = False
        self._pending_text: Optional[str] = None
        self._volume = 100      # 0~100
        self._init_player()

    # ---------- 초기화 ----------
    def _init_player(self):
        if _PYQT == 6:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)
            self._audio.setVolume(1.0)  # 0.0~1.0

            # 상태/에러 감시
            self._player.mediaStatusChanged.connect(self._on_media_status_changed_qt6)
            self._player.playbackStateChanged.connect(self._on_playback_state_changed_qt6)
            # 일부 버전에선 errorOccurred가 있음
            if hasattr(self._player, "errorOccurred"):
                self._player.errorOccurred.connect(self._on_error_qt6)
        else:
            self._player = QMediaPlayer(self)
            self._player.setVolume(self._volume)  # 0~100

            # 상태/에러 감시
            self._player.mediaStatusChanged.connect(self._on_media_status_changed_qt5)
            if hasattr(self._player, "error"):
                self._player.error.connect(self._on_error_qt5)

    # ---------- 외부 API ----------
    def set_lang(self, lang='ko'):
        self._lang = lang

    def set_volume(self, vol: int):
        vol = max(0, min(100, int(vol)))
        self._volume = vol
        if _PYQT == 6:
            try:
                if self._audio:
                    self._audio.setVolume(vol / 100.0)
            except Exception:
                pass
        else:
            try:
                if self._player:
                    self._player.setVolume(vol)
            except Exception:
                pass

    def get_volume(self) -> int:
        if _PYQT == 6:
            try:
                return int(round((self._audio.volume() or 1.0) * 100))
            except Exception:
                return self._volume
        else:
            try:
                return int(self._player.volume())
            except Exception:
                return self._volume

    def stop(self):
        try:
            if self._player:
                self._player.stop()
            if self._se and self._se.isPlaying():
                self._se.stop()
        except Exception:
            pass
        # 상태 복구
        self._is_busy = False

    # ---------- 메인: speak ----------
    def speak(self, text: str):
        if self._is_busy:
            self._pending_text = text
            return
        self._is_busy = True
        self.speakingStarted.emit(text)

        self._worker = _TTSWorker(text, self._lang)
        self._worker.done.connect(self._on_synth_ready_mp3)
        self._worker.error.connect(self._on_synth_error)
        self._worker.start()

    # ---------- 워커 콜백 ----------
    def _on_synth_ready_mp3(self, mp3_path: str):
        """MP3 생성 완료 → MP3 재생 시도 (실패하면 WAV 폴백)"""
        self._current_mp3 = mp3_path
        try:
            if _PYQT == 6:
                self._player.setSource(QUrl.fromLocalFile(mp3_path))
            else:
                self._player.setMedia(QMediaContent(QUrl.fromLocalFile(mp3_path)))
            self._player.play()
        except Exception as e:
            # setSource/setMedia 단계에서 바로 실패
            self._play_wav_fallback(mp3_path, reason=f"setMedia error: {e}")

    def _on_synth_error(self, msg: str):
        self._finish_with_error(msg)

    # ---------- PyQt5 상태/에러 ----------
    def _on_media_status_changed_qt5(self, status):
        # 6=EndOfMedia, 7=InvalidMedia
        s = int(status) if isinstance(status, int) else -1
        if s == 7:  # InvalidMedia → 디코더 없음 등
            self._play_wav_fallback(self._current_mp3, reason="InvalidMedia (Qt5)")
        elif s == 6:  # EndOfMedia
            self._on_playback_finished_ok()

    def _on_error_qt5(self, err):
        # QMediaPlayer.Error 값 → 디코더 문제 포함
        self._play_wav_fallback(self._current_mp3, reason=f"QMediaPlayer(Qt5) error={err}")

    # ---------- PyQt6 상태/에러 ----------
    def _on_media_status_changed_qt6(self, status):
        # Qt6 Enum 문자열/값 모두 대응
        name = str(status)
        if "InvalidMedia" in name:
            self._play_wav_fallback(self._current_mp3, reason="InvalidMedia (Qt6)")
        elif "EndOfMedia" in name:
            self._on_playback_finished_ok()

    def _on_playback_state_changed_qt6(self, state):
        # 필요 시 디버깅용
        pass

    def _on_error_qt6(self, err):
        self._play_wav_fallback(self._current_mp3, reason=f"QMediaPlayer(Qt6) error={err}")

    # ---------- WAV 폴백 ----------
    def _play_wav_fallback(self, mp3_path: Optional[str], reason: str = ""):
        if not mp3_path:
            return self._finish_with_error("No MP3 path for WAV fallback")

        wav_path = str(Path(mp3_path).with_suffix(".wav"))
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", mp3_path, wav_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
        except Exception as e:
            return self._finish_with_error(f"WAV fallback convert failed: {e} (reason: {reason})")

        # QSoundEffect로 WAV 재생
        self._se = QSoundEffect(self)
        self._se.setSource(QUrl.fromLocalFile(wav_path))
        self._se.setVolume(max(0.0, min(1.0, self._volume / 100.0)))
        self._se.play()

        # 종료 감지
        def _watch_done():
            if not self._se.isPlaying():
                try: self._se.playingChanged.disconnect(_watch_done)
                except Exception: pass
                self._on_playback_finished_ok()

        self._se.playingChanged.connect(_watch_done)

    # ---------- 종료 처리 ----------
    def _on_playback_finished_ok(self):
        # 임시 MP3 파일 삭제(선택)
        try:
            if self._current_mp3 and os.path.exists(self._current_mp3):
                os.remove(self._current_mp3)
        except Exception:
            pass
        self._current_mp3 = None

        self._is_busy = False
        self.speakingFinished.emit("OK")

        # 대기열 처리
        if self._pending_text:
            t = self._pending_text
            self._pending_text = None
            QTimer.singleShot(0, lambda: self.speak(t))

    def _finish_with_error(self, msg: str):
        self._is_busy = False
        self.speakingError.emit(msg)
        # 대기열 처리
        if self._pending_text:
            t = self._pending_text
            self._pending_text = None
            QTimer.singleShot(0, lambda: self.speak(t))
