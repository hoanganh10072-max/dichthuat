"""Offline-only inference. Model download is an explicit, separate operation."""
import os
import logging
import re
import threading
from pathlib import Path

LANGUAGES = {
    'vi': 'Tiếng Việt', 'lo': 'ພາສາລາວ · Tiếng Lào', 'en': 'English',
    'th': 'ไทย · Tiếng Thái', 'zh': '中文 · Tiếng Trung', 'km': 'ខ្មែរ · Tiếng Khmer',
    'ja': '日本語 · Tiếng Nhật', 'ko': '한국어 · Tiếng Hàn', 'fr': 'Français',
    'de': 'Deutsch', 'es': 'Español', 'ru': 'Русский', 'id': 'Bahasa Indonesia',
    'ms': 'Bahasa Melayu', 'my': 'မြန်မာ · Tiếng Myanmar', 'hi': 'हिन्दी',
    'it': 'Italiano · Tiếng Ý', 'pt': 'Português · Tiếng Bồ Đào Nha',
    'nl': 'Nederlands · Tiếng Hà Lan', 'ar': 'العربية · Tiếng Ả Rập',
}


class TranslationTooLong(RuntimeError):
    pass


class LocalEngine:
    def __init__(self):
        self.state = 'loading'
        self.error = None
        self.lock = threading.Lock()
        self.tokenizer = None
        self.translator = None

    def load(self):
        try:
            import ctranslate2
            from transformers import M2M100Tokenizer
            root = Path(os.getenv('MODEL_DIR', '/models/m2m100'))
            if not ctranslate2.contains_model(str(root / 'ct2')):
                raise FileNotFoundError('Chưa có mô hình CTranslate2. Chạy lệnh chuẩn bị mô hình trong README.')
            self.tokenizer = M2M100Tokenizer.from_pretrained(str(root / 'tokenizer'), local_files_only=True)
            self.translator = ctranslate2.Translator(
                str(root / 'ct2'), device='cpu', compute_type='int8',
                inter_threads=1, intra_threads=int(os.getenv('MODEL_THREADS', '4')),
            )
            self.state = 'ready'
        except Exception as exc:
            logging.exception('Model load failed; run prepare_model.py and verify MODEL_DIR')
            self.error = str(exc)
            self.state = 'unavailable'

    def chunks(self, text):
        # Use token IDs, never silently truncate input. Preserve paragraph breaks.
        for paragraph in re.split(r'(\n+)', text):
            if not paragraph:
                continue
            if paragraph.isspace():
                yield paragraph, None
                continue
            ids = self.tokenizer.encode(paragraph, add_special_tokens=False)
            for start in range(0, len(ids), 180):
                yield None, ids[start:start + 180]

    def translate(self, text, source, target, *, document=False):
        if self.state != 'ready':
            raise RuntimeError('Mô hình chưa sẵn sàng.')
        # Tokenizer src_lang is mutable; serialize the whole inference operation.
        if not self.lock.acquire(blocking=False):
            raise BlockingIOError('Máy chủ đang dịch một yêu cầu khác. Vui lòng thử lại.')
        try:
            self.tokenizer.src_lang = source
            output = []
            count = 0
            for whitespace, ids in self.chunks(text):
                if whitespace is not None:
                    output.append(whitespace)
                    continue
                tokens = self.tokenizer.convert_ids_to_tokens(
                    self.tokenizer.build_inputs_with_special_tokens(ids)
                )
                prefix = self.tokenizer.lang_code_to_token[target]
                result = self.translator.translate_batch(
                    [tokens], target_prefix=[[prefix]], beam_size=4,
                    max_input_length=0, max_decoding_length=512,
                    no_repeat_ngram_size=4 if document else 0,
                    repetition_penalty=1.1 if document else 1,
                )[0].hypotheses[0]
                if len(result) >= 512:
                    raise TranslationTooLong('Bản dịch vượt giới hạn sinh; hãy chia nội dung ngắn hơn.')
                if result and result[0] == prefix:
                    result = result[1:]
                decoded = self.tokenizer.decode(self.tokenizer.convert_tokens_to_ids(result), skip_special_tokens=True)
                if output and not output[-1].endswith('\n'):
                    output.append(' ')
                output.append(decoded)
                count += 1
            return ''.join(output), count
        finally:
            self.lock.release()


# Retain the old implementation only for historical local-model fixtures.
# The production app exclusively uses OpenAI; it never silently falls back.
from .api_engine import APIEngine as Engine
