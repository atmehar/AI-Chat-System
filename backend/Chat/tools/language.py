import re


LANGUAGE_NAMES = {'en': 'English', 'ar': 'Arabic', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'ru': 'Russian', 'zh': 'Chinese', 'ja': 'Japanese', 'ko': 'Korean'}


def detect_language(text):
    if not text or not text.strip():
        raise ValueError('Text is required.')
    ranges = [('ar', r'[\u0600-\u06ff]'), ('ru', r'[\u0400-\u04ff]'), ('zh', r'[\u4e00-\u9fff]'), ('ja', r'[\u3040-\u30ff]'), ('ko', r'[\uac00-\ud7af]')]
    for code, pattern in ranges:
        if re.search(pattern, text):
            return {'language_code': code, 'language': LANGUAGE_NAMES[code], 'confidence': 0.95}
    return {'language_code': 'en', 'language': 'English', 'confidence': 0.5}