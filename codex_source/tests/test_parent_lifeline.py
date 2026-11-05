import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'payload/game/red4ext/plugins/AiNpcCodexBridge'))
import bridge


class FakeServer:
    def __init__(self):
        self.stopping = threading.Event()
        self.shutdowns = 0

    def shutdown(self):
        self.shutdowns += 1


class ParentTests(unittest.TestCase):
    def test_parent_exit_stops_owned_server(self):
        server = FakeServer()
        class Parent:
            def wait(self, timeout):
                return True
        bridge.watch_parent(server, Parent())
        self.assertTrue(server.stopping.is_set())
        self.assertEqual(server.shutdowns, 1)

    def test_wait_failure_does_not_leave_an_orphan(self):
        server = FakeServer()
        class Parent:
            def wait(self, timeout):
                raise OSError('parent no longer available')
        bridge.watch_parent(server, Parent())
        self.assertEqual(server.shutdowns, 1)

    def test_existing_shutdown_stops_watching_without_an_extra_shutdown(self):
        server = FakeServer()
        server.stopping.set()
        bridge.watch_parent(server, None)
        self.assertEqual(server.shutdowns, 0)

    @unittest.skipUnless(os.name == 'nt', 'Windows process-handle lifecycle')
    def test_real_process_handle_distinguishes_running_and_exited_parent(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(0.3)'])
        parent = bridge.WindowsParentLifeline(process.pid)
        try:
            self.assertFalse(parent.wait(0))
            process.wait(timeout=5)
            self.assertTrue(parent.wait(1000))
        finally:
            parent.close()
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
