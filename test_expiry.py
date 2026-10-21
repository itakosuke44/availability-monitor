import unittest
from datetime import datetime
from unittest.mock import patch
from expiry import is_active, main
from zoneinfo import ZoneInfo
import tempfile
import os

class ExpiryTests(unittest.TestCase):
    def test_last_day_in_japan(self):
        self.assertTrue(is_active(datetime(2026,11,19,23,59,59,tzinfo=ZoneInfo('Asia/Tokyo'))))
        self.assertFalse(is_active(datetime(2026,11,20,0,0,0,tzinfo=ZoneInfo('Asia/Tokyo'))))
        self.assertFalse(is_active(datetime(2026,11,19,15,0,0,tzinfo=ZoneInfo('UTC'))))

    def test_expiry_disables_only_this_workflow(self):
        with tempfile.TemporaryDirectory() as folder:
            output = os.path.join(folder, 'output')
            with patch.dict(os.environ, {'GITHUB_OUTPUT': output, 'GITHUB_REPOSITORY': 'example/monitor', 'GH_TOKEN': 'test-token'}):
                with patch('expiry.is_active', return_value=False), patch('expiry.urlopen') as opened:
                    opened.return_value.__enter__.return_value.status = 204
                    main()
                    request = opened.call_args.args[0]
                    self.assertEqual(request.method, 'PUT')
                    self.assertEqual(request.full_url, 'https://api.github.com/repos/example/monitor/actions/workflows/monitor.yml/disable')
                with open(output) as f:
                    self.assertEqual(f.read(), 'active=false\n')

if __name__ == '__main__':
    unittest.main()
