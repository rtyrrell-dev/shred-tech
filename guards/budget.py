"""The shared daily budget of Gemini requests.

One counter for the whole demo, in units of real Gemini requests (not chat turns). Before every model
call the counter is advanced with a single atomic, conditional operation: "add one only if the
count is still below the cap". Because the check and the increment happen together in the store, a
rejected call never inflates the counter that concurrent calls see, and the number of admitted
requests can never exceed the cap, however many callers race.

The counter is keyed by the Pacific-time date, because Google's daily request quota resets at
midnight Pacific time. A new day therefore starts a new key, and the old key expires shortly after.
"""

import time
from collections.abc import Callable

from guards.quota import quota_date_key, quota_day_window
from guards.ratelimit import Store, store_call

# The key outlives its day by this long, so a request just after the reset can never find a
# half-expired counter, and the key still cleans itself up.
KEY_GRACE_SECONDS = 60 * 60


class BudgetExhausted(Exception):
    """The shared daily budget is used up. `retry_after` is the seconds until the Pacific-time reset."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("daily request budget exhausted")
        self.retry_after = retry_after


class RequestBudget:
    def __init__(self, store: Store, cap: int, clock: Callable[[], float] = time.time) -> None:
        self.store = store
        self.cap = cap
        self.clock = clock

    def _today(self) -> tuple[str, int]:
        """(store key for today's counter, seconds until the reset)."""
        now = self.clock()
        return f"budget:{quota_date_key(now)}", quota_day_window(now)[1]

    async def take(self) -> int:
        """Spend one request. Returns the new count, or raises BudgetExhausted if the cap is reached.

        Raises GuardUnavailable if the store cannot be reached (callers fail closed).
        """
        key, seconds_left = self._today()
        used = await store_call(self.store.incr_if_below(key, self.cap, seconds_left + KEY_GRACE_SECONDS))
        if used is None:
            raise BudgetExhausted(seconds_left)
        return used

    async def used(self) -> int:
        key, _ = self._today()
        return await store_call(self.store.get_count(key))

    async def require_available(self) -> None:
        """Cheap admission check: raise BudgetExhausted if nothing is left, without spending anything."""
        key, seconds_left = self._today()
        if await store_call(self.store.get_count(key)) >= self.cap:
            raise BudgetExhausted(seconds_left)
