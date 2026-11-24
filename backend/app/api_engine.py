"""Shared admin-configured API credentials, with the existing translation workflow."""
from . import accounts
from .chatgpt_engine import ChatGPTEngine
from .openai_engine import ProviderError


class APIEngine(ChatGPTEngine):
    provider = 'openai'

    @property
    def state(self):
        return 'ready' if accounts.store.provider()['key'] else 'unconfigured'

    def credentials(self, user_id):
        config = accounts.store.provider()
        if not config['key']:
            raise ProviderError('Admin cần cấu hình khóa OpenAI API trong Quản trị → OpenAI API.', 503)
        return {'model': config['model'], 'tokens': {'access_token': config['key']}}

    def _response(self, body, access_token):
        try:
            return super()._response(body, access_token)
        except ProviderError as exc:
            if exc.status_code == 409:
                raise ProviderError('Khóa API không hợp lệ hoặc chưa có quyền truy cập mô hình. Admin cần kiểm tra OpenAI API.', 503) from None
            if exc.status_code == 429:
                raise ProviderError('OpenAI API hết hạn mức hoặc đang giới hạn lượt gọi. Admin cần kiểm tra API billing.', 429) from None
            message = str(exc).replace('ChatGPT', 'OpenAI API')
            message = message.replace('Chọn lại mô hình trong OpenAI API của tôi.', 'Kiểm tra tên mô hình trong Quản trị → OpenAI API.')
            raise ProviderError(message, exc.status_code) from None
