"""Server-only account provisioning. Secrets arrive on stdin, never in argv."""
import json
import sys

from .accounts import store


if __name__ == '__main__':
    store.init()
    body = json.load(sys.stdin)
    users = body if isinstance(body, list) else [body]
    result = [store.create_user(item['username'], item['password'], item.get('role', 'user')) for item in users]
    print(json.dumps(result))
