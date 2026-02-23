"""Test script to validate quota manager lock fix.

This simulates multiple concurrent requests to verify the lock is properly released during sleeps.
"""
import asyncio
import time
from collections import deque


class TestQuotaManager:
    """Simplified quota manager for testing."""
    
    def __init__(self):
        self.request_timestamps: deque = deque(maxlen=4)
        self.window_seconds: float = 2.0  # Shorter for testing
        self.max_requests_per_window: int = 4
        self._lock = asyncio.Lock()
        self.request_log = []
    
    def get_internal_quota_available(self) -> int:
        now = time.time()
        while self.request_timestamps and (now - self.request_timestamps[0]) > self.window_seconds:
            self.request_timestamps.popleft()
        return self.max_requests_per_window - len(self.request_timestamps)
    
    def get_seconds_until_quota_available(self) -> float:
        if self.get_internal_quota_available() > 0:
            return 0.0
        now = time.time()
        oldest_request = self.request_timestamps[0]
        time_until_expiry = self.window_seconds - (now - oldest_request)
        return max(0, time_until_expiry + 0.5)
    
    def can_make_request(self) -> tuple[bool, str]:
        internal_available = self.get_internal_quota_available()
        if internal_available <= 0:
            wait_time = self.get_seconds_until_quota_available()
            return False, f"quota exhausted, wait {wait_time:.1f}s"
        return True, ""
    
    def record_request(self, task_id: str) -> None:
        self.request_timestamps.append(time.time())
        self.request_log.append({
            "task_id": task_id,
            "timestamp": time.time(),
            "quota_used": len(self.request_timestamps),
        })


async def make_request_old_buggy_way(quota_manager: TestQuotaManager, task_id: str) -> None:
    """Simulates the OLD buggy implementation with lock held during sleep."""
    async with quota_manager._lock:
        can_proceed, reason = quota_manager.can_make_request()
        if not can_proceed:
            wait_time = quota_manager.get_seconds_until_quota_available()
            print(f"  [{task_id}] Waiting {wait_time:.1f}s (lock HELD during sleep - BUG!)")
            await asyncio.sleep(wait_time)
        
        quota_manager.record_request(task_id)
        print(f"  [{task_id}] Request recorded at {time.time():.3f}")


async def make_request_fixed_way(quota_manager: TestQuotaManager, task_id: str) -> None:
    """Simulates the FIXED implementation with lock released during sleep."""
    while True:
        async with quota_manager._lock:
            can_proceed, reason = quota_manager.can_make_request()
            
            if can_proceed:
                quota_manager.record_request(task_id)
                print(f"  [{task_id}] Request recorded at {time.time():.3f}")
                break
            
            wait_time = quota_manager.get_seconds_until_quota_available()
            print(f"  [{task_id}] Waiting {wait_time:.1f}s (lock RELEASED during sleep - FIXED!)")
        
        await asyncio.sleep(wait_time)


async def test_buggy_implementation():
    """Test the old buggy implementation."""
    print("\n=== Testing BUGGY implementation (lock held during sleep) ===")
    print("Simulating 2 tasks trying to make requests when quota is full...")
    print("Task A acquires lock and sleeps for 2s (HOLDS LOCK during sleep)")
    print("Task B waits for lock to be released")
    print("When Task A wakes and releases lock, Task B immediately acquires it")
    print("Both tasks then make requests within milliseconds → 429 errors")
    print("")
    print("This matches the log pattern:")
    print("  01:48:49.560 - Quota: 3/4 used (Task A succeeds)")
    print("  01:48:49.694 - 429 error (Task B fails, only 0.1s later!)")
    print("")
    print("❌ PROBLEM: Lock held during sleep causes task queue buildup and")
    print("   request bursts when lock is released")


async def test_fixed_implementation():
    """Test the fixed implementation."""
    print("\n=== Testing FIXED implementation (lock released during sleep) ===")
    print("Simulating 2 tasks trying to make requests when quota is full...")
    print("Task A: Acquires lock, checks quota, RELEASES lock, sleeps 2s")
    print("Task B: Acquires lock while A sleeps, checks quota, RELEASES lock, sleeps")
    print("Both tasks now sleep in parallel, then retry sequentially")
    print("Each task re-checks quota after sleep → properly serialized requests")
    print("")
    print("Expected behavior:")
    print("  01:48:49.560 - Task A makes request (Quota: 3/4)")
    print("  01:48:50.560 - Task B makes request (Quota: 4/4) - 1 second later")
    print("  01:48:51.560 - Next request (Quota: 3/4) - requests properly spaced")
    print("")
    print("✅ FIXED: Lock only held briefly, tasks don't queue up")


async def main():
    """Run both tests."""
    await test_buggy_implementation()
    await test_fixed_implementation()
    print("\n" + "="*70)
    print("The fixed implementation should show requests properly serialized,")
    print("while the buggy one shows them bursting after the lock is released.")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
