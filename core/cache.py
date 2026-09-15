import time
from typing import Any, Optional
from functools import wraps


class Cache:
    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any):
        self.cache[key] = (value, time.time())

    def clear(self):
        self.cache.clear()

    def cleanup(self):
        current_time = time.time()
        expired = [k for k, (_, t) in self.cache.items() if current_time - t >= self.ttl]
        for k in expired:
            del self.cache[k]


stock_cache = Cache(ttl_seconds=300)
indicator_cache = Cache(ttl_seconds=600)
price_cache = Cache(ttl_seconds=30)


def cached(cache_instance):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            result = cache_instance.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            if result is not None:
                cache_instance.set(key, result)
            return result
        return wrapper
    return decorator
