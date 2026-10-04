"""Verify periodic router recovery and orderly shutdown without network access."""

import subprocess
from threading import Event
import unittest
from unittest.mock import Mock, patch

from mycount.activity.MaintainRouterMappings import MaintainRouterMappings
from mycount.constants.DRouterMappings import DRouterMappings
from mycount.server.RouterWorker import main


class RouterWorkerTests(unittest.TestCase):
    def test_failure_retries_and_reports_repair(self):
        router = Mock()
        router.forward.side_effect = [subprocess.TimeoutExpired('upnpc', 30), (443,)]
        stopping = Mock()
        stopping.is_set.side_effect = [False, False, True]
        with self.assertLogs('mycount.activity.MaintainRouterMappings', level='INFO') as logs:
            MaintainRouterMappings(router).run(stopping)
        self.assertEqual(router.forward.call_count, 2)
        router.forward.assert_called_with((80, 443))
        self.assertEqual(stopping.wait.call_count, 2)
        stopping.wait.assert_called_with(DRouterMappings.CHECK_INTERVAL)
        self.assertIn('check failed', logs.output[0])
        self.assertIn('Restored', logs.output[1])

    def test_correct_mappings_are_quiet_and_shutdown_interrupts_wait(self):
        router = Mock()
        router.forward.return_value = ()
        stopping = Event()
        with patch.object(stopping, 'wait', side_effect=lambda _: stopping.set()):
            with patch('mycount.activity.MaintainRouterMappings.logging.getLogger') as logger:
                MaintainRouterMappings(router).run(stopping)
        router.forward.assert_called_once_with((80, 443))
        logger.return_value.info.assert_not_called()
        logger.return_value.warning.assert_not_called()

    def test_programming_errors_propagate(self):
        router = Mock()
        router.forward.side_effect = TypeError('broken contract')
        with self.assertRaises(TypeError):
            MaintainRouterMappings(router).run(Event())

    def test_entry_point_signals_stop_the_worker(self):
        with patch('mycount.server.RouterWorker.signal.signal') as register:
            with patch('mycount.server.RouterWorker.MaintainRouterMappings') as worker:
                main()
        stopping = worker.return_value.run.call_args.args[0]
        self.assertFalse(stopping.is_set())
        register.call_args_list[0].args[1](15, None)
        self.assertTrue(stopping.is_set())
