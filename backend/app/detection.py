"""Local language detection: distinctive scripts + bundled statistical model."""
import re
import threading
from functools import lru_cache

SCRIPTS = {'lo': r'[\u0e80-\u0eff]', 'th': r'[\u0e00-\u0e7f]', 'ko': r'[\uac00-\ud7af\u1100-\u11ff]',
           'ja': r'[\u3040-\u30ff]', 'km': r'[\u1780-\u17ff]', 'my': r'[\u1000-\u109f]',
           'hi': r'[\u0900-\u097f]', 'ru': r'[\u0400-\u04ff]', 'ar':r'[\u0600-\u06ff]'}
DETECT_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def detector():
    from langid.langid import LanguageIdentifier, model
    classifier = LanguageIdentifier.from_modelstring(model, norm_probs=True)
    # Keep the full model so unsupported languages do not become false positives.
    return classifier


def detect_language(text):
    from .engine import LANGUAGES
    letters = ''.join(c for c in text if c.isalpha())
    if len(letters) < 3:
        raise ValueError('Chưa đủ chữ để phát hiện ngôn ngữ. Nhập thêm nội dung hoặc chọn nguồn thủ công.')
    counts = {code: len(re.findall(pattern, text)) for code, pattern in SCRIPTS.items()}
    code, count = max(counts.items(), key=lambda item: item[1])
    # Kana/Hangul take precedence over Han characters in Japanese/Korean.
    if count >= 2 and count / len(letters) >= .15:
        return {'code': code, 'method': 'script', 'uncertain': code in {'ru', 'hi','ar'}}
    if len(re.findall(r'[\u3400-\u9fff]', text)) / len(letters) > .4:
        return {'code': 'zh', 'method': 'script', 'uncertain': True}
    with DETECT_LOCK:
        code, probability = detector().classify(text[:6000])
    if code not in LANGUAGES:
        raise ValueError('Ngôn ngữ nhận diện nằm ngoài danh sách hỗ trợ. Hãy chọn nguồn thủ công.')
    return {'code': code, 'method': 'langid', 'uncertain': bool(probability < .8 or len(letters) < 20)}
