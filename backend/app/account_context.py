from contextvars import ContextVar

# Middleware establishes this context before FastAPI copies it into worker threads.
current_account = ContextVar('current_account', default=None)
