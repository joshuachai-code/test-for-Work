import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('installer', Path(__file__).with_name('install-morning-briefing.py'))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class FakeGWork:
    def __init__(self, tasks=None, corrupt=False):
        self.tasks = tasks or []
        self.writes = []
        self.corrupt = corrupt

    def open(self, request, timeout):
        method = request.get_method()
        if method == 'GET':
            tasks = json.loads(json.dumps(self.tasks))
            if self.corrupt and self.writes:
                tasks[0]['schedule']['expression'] = '0 2 * * *'
            result = {'success': True, 'tasks': tasks}
        else:
            payload = json.loads(request.data)
            self.writes.append(method)
            if method == 'POST':
                saved = dict(payload, id='reminder-1')
                self.tasks.append(saved)
            else:
                saved = self.tasks[0]
                saved.update(payload)
            result = {'success': True, 'task': saved}
        return io.BytesIO(json.dumps(result).encode())


class MorningBriefingTests(unittest.TestCase):
    def run_installer(self, fake, base='http://127.0.0.1:12345', offset=8):
        with patch.dict(installer.os.environ, {'LOBSTERAI_API_BASE_URL': base}), \
             patch('sys.argv', ['install', '--staff-id', 'member-demo', '--staff-name', 'Aisha Rahman']), \
             patch.object(installer.dt, 'datetime') as clock, \
             patch.object(installer.urllib.request, 'build_opener', return_value=fake), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            clock.now.return_value.astimezone.return_value.utcoffset.return_value = installer.dt.timedelta(hours=offset)
            installer.main()
            return json.loads(output.getvalue())

    def test_bound_read_only_prompt_and_times(self):
        payload = installer.make_payload('member-demo', 'Aisha Rahman', '09:00')
        self.assertNotIn('__STAFF_', payload['prompt'])
        self.assertIn('employee_id` equal to member-demo', payload['prompt'])
        self.assertIn('This is a read-only briefing.', payload['prompt'])
        self.assertEqual(payload['schedule']['expression'], '0 9 * * *')
        self.assertEqual(installer.make_payload('member-demo', 'Aisha', '09:30')['schedule']['expression'], '30 9 * * *')
        self.assertEqual(payload['notifyPlatforms'], [])

    def test_create_and_read_back(self):
        fake = FakeGWork()
        result = self.run_installer(fake)
        self.assertTrue(result['saved_and_checked'])
        self.assertEqual(fake.writes, ['POST'])
        self.assertEqual(len(fake.tasks), 1)

    def test_reinstall_updates_same_reminder(self):
        fake = FakeGWork()
        self.run_installer(fake)
        self.run_installer(fake)
        self.assertEqual(fake.writes, ['POST', 'PUT'])
        self.assertEqual(len(fake.tasks), 1)
        self.assertEqual(fake.tasks[0]['id'], 'reminder-1')

    def test_missing_session_creates_nothing(self):
        fake = FakeGWork()
        with self.assertRaisesRegex(ValueError, 'No schedule was created'):
            self.run_installer(fake, base='')
        self.assertEqual(fake.writes, [])

    def test_refuses_remote_api_destination(self):
        fake = FakeGWork()
        with self.assertRaisesRegex(ValueError, 'refusing another destination'):
            self.run_installer(fake, base='https://example.invalid')
        self.assertEqual(fake.writes, [])

    def test_wrong_device_time_creates_nothing(self):
        fake = FakeGWork()
        with self.assertRaisesRegex(ValueError, 'timezone'):
            self.run_installer(fake, offset=0)
        self.assertEqual(fake.writes, [])

    def test_failed_readback_is_not_success(self):
        fake = FakeGWork(corrupt=True)
        with self.assertRaisesRegex(ValueError, 'saved schedule differs'):
            self.run_installer(fake)
        self.assertEqual(fake.writes, ['POST'])

    def test_existing_duplicates_are_not_multiplied(self):
        payload = installer.make_payload('member-demo', 'Aisha Rahman', '09:00')
        fake = FakeGWork([dict(payload, id='one'), dict(payload, id='two')])
        with self.assertRaisesRegex(ValueError, 'Multiple matching reminders'):
            self.run_installer(fake)
        self.assertEqual(fake.writes, [])


if __name__ == '__main__':
    unittest.main()
