# -*- coding: utf-8 -*-
from typing import Tuple, Optional
from config.dictionary_kr import (first_spelling, second_spelling, last_spelling,
                    start_kr, end_kr, command_labels, consonant_labels, vowel_labels)

def is_hangul(char: str) -> bool:
    return start_kr <= ord(char) <= end_kr

def decompose(char: str):
    if not is_hangul(char): return None, None, None
    code = ord(char) - start_kr
    last_index = code % 28
    code //= 28
    second_index = code % 21
    first_index = code // 21
    return first_spelling[first_index], second_spelling[second_index], last_spelling[last_index]

def compose(first: str, second: str, last: str = ' ') -> Optional[str]:
    try:
        first_index = first_spelling.index(first)
        second_index = second_spelling.index(second)
        last_index = last_spelling.index(last)
        return chr(start_kr + (first_index * 588) + (second_index * 28) + last_index)
    except (ValueError, IndexError):
        return None

class HangulAssembler:
    def __init__(self):
        self.full_text = ""
        self.command_shift = False
        self.double_consonant_map = {'ㄱ': 'ㄲ', 'ㄷ': 'ㄸ', 'ㅂ': 'ㅃ', 'ㅅ': 'ㅆ', 'ㅈ': 'ㅉ'}
        self.complex_last_map = {
            ('ㄱ', 'ㅅ'): 'ㄳ', ('ㄴ', 'ㅈ'): 'ㄵ', ('ㄴ', 'ㅎ'): 'ㄶ',
            ('ㄹ', 'ㄱ'): 'ㄺ', ('ㄹ', 'ㅁ'): 'ㄻ', ('ㄹ', 'ㅂ'): 'ㄼ',
            ('ㄹ', 'ㅅ'): 'ㄽ', ('ㄹ', 'ㅌ'): 'ㄾ', ('ㄹ', 'ㅍ'): 'ㄿ',
            ('ㄹ', 'ㅎ'): 'ㅀ', ('ㅂ', 'ㅅ'): 'ㅄ'
        }
        self.dipthong_map = {
            ('ㅗ', 'ㅏ'): 'ㅘ', ('ㅗ', 'ㅐ'): 'ㅙ', ('ㅗ', 'ㅣ'): 'ㅚ',
            ('ㅜ', 'ㅓ'): 'ㅝ', ('ㅜ', 'ㅔ'): 'ㅞ', ('ㅜ', 'ㅣ'): 'ㅟ',
            ('ㅡ', 'ㅣ'): 'ㅢ'
        }
        self.last_decompose_map = {v: k for k, v in self.complex_last_map.items()}

    def add_char(self, char: str) -> str:
        if char in command_labels:
            self._process_command(char)
        elif char in consonant_labels:
            self._process_consonant(char)
        elif char in vowel_labels:
            self._process_vowel(char)
        return self.full_text

    def _process_command(self, char: str):
        if char == 'shift':
            self.command_shift = True
        elif char == 'space':
            self.full_text += " "
        elif char == 'b_space':
            self._process_backspace()
        elif char == 'end':
            pass

    def get_current_text_and_reset(self) -> str:
        text_to_send = self.full_text
        self.full_text = ""
        self.command_shift = False
        return text_to_send

    def _process_backspace(self):
        if not self.full_text: return
        last_char = self.full_text[-1]
        if not is_hangul(last_char):
            self.full_text = self.full_text[:-1]; return
        first, second, last = decompose(last_char)
        if last != ' ':
            if last in self.last_decompose_map:
                new_char = compose(first, second, self.last_decompose_map[last][0])
            else:
                new_char = compose(first, second)
            self.full_text = self.full_text[:-1] + new_char
        elif second:
            self.full_text = self.full_text[:-1] + first
        else:
            self.full_text = self.full_text[:-1]

    def _process_consonant(self, char: str):
        if self.command_shift and char in self.double_consonant_map:
            char = self.double_consonant_map[char]
        self.command_shift = False

        last_char = self.full_text[-1] if self.full_text else None
        if last_char and is_hangul(last_char):
            first, second, last = decompose(last_char)
            if last == ' ' and char in last_spelling:
                self.full_text = self.full_text[:-1] + compose(first, second, char)
                return
            elif last in last_spelling and (last, char) in self.complex_last_map:
                self.full_text = self.full_text[:-1] + compose(first, second, self.complex_last_map[(last, char)])
                return
        self.full_text += char

    def _process_vowel(self, char: str):
        self.command_shift = False
        last_char = self.full_text[-1] if self.full_text else None
        if not last_char:
            self.full_text += char; return
        if last_char in first_spelling:
            self.full_text = self.full_text[:-1] + compose(last_char, char); return
        if is_hangul(last_char):
            first, second, last = decompose(last_char)
            if last != ' ':
                if last in self.last_decompose_map:
                    last_1, last_2 = self.last_decompose_map[last]
                    syllable_1 = compose(first, second, last_1)
                    syllable_2 = compose(last_2, char)
                    self.full_text = self.full_text[:-1] + syllable_1 + syllable_2
                else:
                    syllable_1 = compose(first, second)
                    syllable_2 = compose(last, char)
                    self.full_text = self.full_text[:-1] + syllable_1 + syllable_2
                return
            else:
                if (second, char) in self.dipthong_map:
                    self.full_text = self.full_text[:-1] + compose(first, self.dipthong_map[(second, char)])
                    return
        self.full_text += char
