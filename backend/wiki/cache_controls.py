from django.core.cache import cache


def atomic_cache_increment(key: str, amount: int = 1, *, timeout: int) -> int:
    """Atomically add to a shared-cache counter and preserve its first-write TTL."""
    amount = int(amount)
    if cache.add(key, amount, timeout=timeout):
        return amount
    try:
        return int(cache.incr(key, amount))
    except ValueError:
        # The key may have expired between add and incr. Retry the create once.
        if cache.add(key, amount, timeout=timeout):
            return amount
        return int(cache.incr(key, amount))
