import threading
import time
import unittest

from heavy_job_queue import HeavyJobCoordinator


class HeavyJobCoordinatorTests(unittest.TestCase):
    def test_exclusive_backup_waits_then_blocks_later_work(self):
        coordinator = HeavyJobCoordinator(max_parallel=2)
        video_started = threading.Event()
        release_video = threading.Event()
        backup_started = threading.Event()
        release_backup = threading.Event()
        download_started = threading.Event()

        def video():
            with coordinator.acquire("video"):
                video_started.set()
                release_video.wait(timeout=2)

        def backup():
            with coordinator.acquire("backup", exclusive=True):
                backup_started.set()
                release_backup.wait(timeout=2)

        def download():
            with coordinator.acquire("download"):
                download_started.set()

        threads = [threading.Thread(target=video), threading.Thread(target=backup), threading.Thread(target=download)]
        threads[0].start()
        self.assertTrue(video_started.wait(timeout=1))
        threads[1].start()
        time.sleep(0.03)
        threads[2].start()
        time.sleep(0.05)

        self.assertFalse(backup_started.is_set())
        self.assertFalse(download_started.is_set())
        snapshot = coordinator.snapshot()
        self.assertEqual(snapshot["active"], 1)
        self.assertEqual(snapshot["waiting"], 2)

        release_video.set()
        self.assertTrue(backup_started.wait(timeout=1))
        self.assertFalse(download_started.is_set())
        self.assertTrue(coordinator.snapshot()["exclusive_active"])

        release_backup.set()
        self.assertTrue(download_started.wait(timeout=1))
        for thread in threads:
            thread.join(timeout=1)

    def test_parallel_limit_is_enforced(self):
        coordinator = HeavyJobCoordinator(max_parallel=2)
        release = threading.Event()
        started = []
        lock = threading.Lock()

        def worker(number):
            with coordinator.acquire("video"):
                with lock:
                    started.append(number)
                release.wait(timeout=10)

        threads = [threading.Thread(target=worker, args=(number,)) for number in range(3)]
        for thread in threads:
            thread.start()
        try:
            # Containerised production hosts can be busy immediately after an
            # image build. Wait for both the active and queued states instead
            # of assuming all three threads are scheduled within one second.
            deadline = time.monotonic() + 5
            started_count = 0
            snapshot = coordinator.snapshot()
            while time.monotonic() < deadline:
                with lock:
                    started_count = len(started)
                snapshot = coordinator.snapshot()
                if started_count == 2 and snapshot["waiting"] == 1:
                    break
                time.sleep(0.01)

            self.assertEqual(started_count, 2)
            self.assertEqual(snapshot["waiting"], 1)
        finally:
            release.set()
            for thread in threads:
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
