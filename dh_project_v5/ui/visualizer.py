# -*- coding: utf-8 -*-
import cv2
import numpy as np
from PIL import ImageFont, ImageDraw, Image
from config.paths import FONT_PATH



def putText_korean(image, text, pos, font_path, font_size, color):
    """
    영상 이미지 위에 한글 텍스트 작성
    (OpenCV & Pillow 라이브러리 사용)
    """
    img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGBA))  # RGBA 모드로 변경
    draw = ImageDraw.Draw(img_pil, 'RGBA')
    font = ImageFont.truetype(FONT_PATH, font_size)

    # 텍스트 크기 계산
    try:
        text_bbox = draw.textbbox(pos, text, font=font)
    except AttributeError:
        text_width, text_height = draw.textsize(text, font=font)
        text_bbox = (pos[0], pos[1], pos[0] + text_width, pos[1] + text_height)

    padding = 10
    # 반투명한 검은색 배경 박스
    bg_color_rgba = (0, 0, 0, 100) # 100은 투명도 (0-255)
    draw.rectangle(
        [(text_bbox[0] - padding, text_bbox[1] - padding),
         (text_bbox[2] + padding, text_bbox[3] + padding)],
        fill=bg_color_rgba
    )

    # 흰색 텍스트
    text_color_rgba = (255, 255, 255, 255)
    draw.text(pos, text, font=font, fill=text_color_rgba)

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGBA2BGR)
