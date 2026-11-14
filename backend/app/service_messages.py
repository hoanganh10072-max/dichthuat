"""Keep connection troubleshooting in admin; give users an actionable message."""
from .account_context import current_account

CONTACT_ADMIN = 'Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng.'


def is_admin():
    account = current_account.get()
    return bool(account and account['role'] == 'admin')


def access_message():
    return 'Hãy mở ChatGPT của tôi để kết nối tài khoản và chọn mô hình trước khi dịch.' if is_admin() else CONTACT_ADMIN


def provider_message(error):
    if is_admin():
        return str(error)
    if error.status_code in (401, 403, 409):
        return CONTACT_ADMIN
    if error.status_code == 429:
        return 'Đã đạt hạn mức sử dụng. Vui lòng liên hệ admin để được trợ giúp.'
    return 'Dịch vụ dịch đang tạm gián đoạn. Vui lòng thử lại hoặc liên hệ admin để được trợ giúp.'
