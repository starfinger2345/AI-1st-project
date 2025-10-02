"""한글 조합 규칙"""
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np

from data.dictionary_kr import (
                    first_spelling, second_spelling, last_spelling,
                    start_kr, end_kr,
                    consonant_labels, vowel_labels, command_labels
)


def is_hangul(char):
    return start_kr <= ord(char) <= end_kr

def decompose(char):
    if not is_hangul(char): return None, None, None
    code = ord(char) - start_kr
    last_index = code % 28
    code //= 28
    second_index = code % 21
    first_index = code // 21
    return first_spelling[first_index], second_spelling[second_index], last_spelling[last_index]

def compose(first, second, last=' '):
    try:
        first_index = first_spelling.index(first)
        second_index = second_spelling.index(second)
        last_index = last_spelling.index(last)
        code = start_kr + (first_index * 588) + (second_index * 28) + last_index
        return chr(code)
    except (ValueError, IndexError):
        return None

# ---한글 폰트 설정---
def putText_korean(image, text, pos, font_path, font_size, color):
    img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font = ImageFont.truetype(font_path, font_size)
    draw.text(pos, text, font=font, fill=tuple(color[::-1]))
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


class HangulAssembler:
    def __init__(self):
        self.full_text = ""
        self.command_shift = False

        # 각 조합 규칙에 대한 매핑 테이블
        self.double_consonant_map = {'ㄱ': 'ㄲ', 'ㄷ': 'ㄸ', 'ㅂ': 'ㅃ', 'ㅅ': 'ㅆ', 'ㅈ': 'ㅉ'}
        self.complex_last_map = {('ㄱ', 'ㅅ'): 'ㄳ', ('ㄴ', 'ㅈ'): 'ㄵ', ('ㄴ', 'ㅎ'): 'ㄶ', ('ㄹ', 'ㄱ'): 'ㄺ', ('ㄹ', 'ㅁ'): 'ㄻ', ('ㄹ', 'ㅂ'): 'ㄼ', ('ㄹ', 'ㅅ'): 'ㄽ', ('ㄹ', 'ㅌ'): 'ㄾ', ('ㄹ', 'ㅍ'): 'ㄿ', ('ㄹ', 'ㅎ'): 'ㅀ', ('ㅂ', 'ㅅ'): 'ㅄ'}
        self.dipthong_map = {('ㅗ', 'ㅏ'): 'ㅘ', ('ㅗ', 'ㅐ'): 'ㅙ', ('ㅗ', 'ㅣ'): 'ㅚ', ('ㅜ', 'ㅓ'): 'ㅝ', ('ㅜ', 'ㅔ'): 'ㅞ', ('ㅜ', 'ㅣ'): 'ㅟ', ('ㅡ', 'ㅣ'): 'ㅢ'}
        
        # 연음 법칙을 위한 겹받침 분해 맵
        self.last_decompose_map = {v: k for k, v in self.complex_last_map.items()}

    def add_char(self, char):
        if char in command_labels:
            self._process_command(char)
        elif char in consonant_labels:
            self._process_consonant(char)
        elif char in vowel_labels:
            self._process_vowel(char)
        return self.full_text
            

    def _process_command(self, char):
        if char == 'shift':
            self.command_shift = True
        elif char == 'space':
            self.full_text += " "
        elif char == 'b_space':
            self._process_backspace()
        elif char == 'end':
            pass

    def _process_backspace(self):
        if not self.full_text:
            return
        last_char = self.full_text[-1]

        # 1. 마지막 글자가 한글이 아닌 경우 (공백, 새 줄)
        if not is_hangul(last_char):
            self.full_text = self.full_text[:-1]
            return

        # 2. 마지막 글자가 한글인 경우
        first, second, last = decompose(last_char)
        # 2-1. 받침이 있는 경우 -> 받침 제거
        if last != ' ':
            # 겹받침인 경우 -> 홑받침으로 변경
            if last in self.last_decompose_map:
                new_last = self.last_decompose_map[last][0]
                new_char = compose(first,second, new_last)
            # 홑받침인 경우 -> 받침 제거
            else:
                new_char = compose(first, second)
            self.full_text = self.full_text[:-1] + new_char
        # 2-2. 받침 없이 모음만 있는 경우 -> 모음 제거 (초성만 남음)
        elif second:
            self.full_text = self.full_text[:-1] + first
        # 2-3. 초성만 있는 경우 -> 남아 있지 않음
        else:
            self.full_text = self.full_text[:-1]


    def _process_consonant(self, char):
        # 1. 쌍자음 처리
        if self.command_shift and char in self.double_consonant_map:
            char = self.double_consonant_map[char]
        self.command_shift = False

        last_char = self.full_text[-1] if self.full_text else None
        
        # 2. 받침(종성) 추가 또는 겹받침 처리
        if last_char and is_hangul(last_char):
            first, second, last = decompose(last_char)
            # 2-1. 기존에 받침이 없는 경우 -> 새 받침 추가
            if last == ' ' and char in last_spelling:
                self.full_text = self.full_text[:-1] + compose(first, second, char)
                return
            # 2-2. 기존에 받침이 있는 경우 -> 겹받침 시도
            elif last in last_spelling and (last, char) in self.complex_last_map:
                complex_last = self.complex_last_map[(last, char)]
                self.full_text = self.full_text[:-1] + compose(first, second, complex_last)
                return
        
        # 3. 위 조건에 해당 없으면 새 글자로 추가
        self.full_text += char

    def _process_vowel(self, char):
        self.command_shift = False
        last_char = self.full_text[-1] if self.full_text else None

        if not last_char:
            self.full_text += char
            return

        # 1. 마지막 글자가 자음인 경우 -> 자음+모음 조합
        if last_char in first_spelling:
            self.full_text = self.full_text[:-1] + compose(last_char, char)
            return

        if is_hangul(last_char):
            first, second, last = decompose(last_char)
            # 2. 연음 법칙 처리 (받침이 있는 경우)
            if last != ' ':
                # 2-1. 겹받침인 경우 -> 분리 후 연음
                if last in self.last_decompose_map:
                    last_1, last_2 = self.last_decompose_map[last]
                    syllable_1 = compose(first, second, last_1)
                    syllable_2 = compose(last_2, char)
                    self.full_text = self.full_text[:-1] + syllable_1 + syllable_2
                # 2-2. 홑받침인 경우 -> 받침을 다음 글자 초성으로
                else:
                    syllable_1 = compose(first, second) # 받침 없는 글자
                    syllable_2 = compose(last, char) # 받침이 초성이 된 새 글자
                    self.full_text = self.full_text[:-1] + syllable_1 + syllable_2
                return
            # 3. 이중모음 처리 (받침이 없는 경우)
            else:
                if (second, char) in self.dipthong_map:
                    diphthong = self.dipthong_map[(second, char)]
                    self.full_text = self.full_text[:-1] + compose(first, diphthong)
                    return
        
        # 4. 위 조건에 해당 없으면 새 글자로 추가
        self.full_text += char



