from gtts import gTTS

# 변환할 텍스트
text = "안녕하세요. 구글 TTS 테스트입니다."

# 음성 변환 (한국어)
tts = gTTS(text=text, lang='ko')

# mp3 파일로 저장
tts.save("test_tts.mp3")

print("✅ test_tts.mp3 파일 생성 완료!")