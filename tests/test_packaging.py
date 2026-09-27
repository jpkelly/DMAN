"""Packaging checks runnable without a Windows host or USB hardware."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dsan_display.packaging_check import self_test
from dsan_display.windows import default_data_directory, main


class PackagingTests(unittest.TestCase):
    def test_frozen_settings_use_user_data_not_extraction_or_working_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('sys.frozen', True, create=True), patch.dict('os.environ', {'LOCALAPPDATA': folder}):
                self.assertEqual(default_data_directory(), Path(folder) / 'DSANDisplay')

    def test_source_launcher_preserves_workspace_default(self):
        with patch('sys.frozen', False, create=True):
            self.assertEqual(default_data_directory(), Path.cwd())

    def test_smoke_check_does_not_enumerate_or_open_hardware(self):
        output = io.StringIO()
        with patch('hid.enumerate') as enumerate_hid, patch('hid.device') as open_hid, \
                patch('serial.tools.list_ports.comports') as serial_ports, \
                patch('usb.core.find') as find_usb, contextlib.redirect_stdout(output):
            self_test()
        for operation in (enumerate_hid, open_hid, serial_ports, find_usb):
            operation.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['self_test'], 'passed')

    def test_self_test_does_not_create_config_or_log_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'unused'
            with patch('dsan_display.packaging_check.self_test') as check:
                main(['--self-test', '--data-dir', str(destination)])
            check.assert_called_once_with()
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
