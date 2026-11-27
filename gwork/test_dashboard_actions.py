import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('actions',ROOT/'cosec-desk-actions/scripts/dashboard_action.py')
actions=importlib.util.module_from_spec(spec);spec.loader.exec_module(actions)

class DashboardActionsTests(unittest.TestCase):
    def test_status_route_is_available_in_each_standalone_import(self):
        packages = ['cosec-desk-actions', 'morning-brief', 'ctc-billing', 'ssm-form-filling']
        routes = []
        for name in packages:
            with self.subTest(package=name), ZipFile(ROOT / (name + '.skill')) as archive:
                prefix = name + '/' if name == 'ssm-form-filling' else ''
                for filename in archive.namelist():
                    local = ROOT / name / filename[len(prefix):]
                    self.assertEqual(archive.read(filename), local.read_bytes(), filename)
                guide = archive.read(prefix + 'SKILL.md').decode()
                route = guide.split('## Task status and recent updates\n', 1)[1].split('\n## ', 1)[0]
                routes.append(route)
        # Specialist packages still share their existing standalone lookup.
        self.assertEqual(len(set(routes[1:])), 1)
        reporting = [route.split('Filter by any requested task ID', 1)[1] for route in routes]
        self.assertEqual(len(set(reporting)), 1)
        self.assertIn('database_role = current_user AND tasks_enabled', routes[0])
        self.assertNotIn('gwork_daniel', routes[0])
        self.assertNotIn('gwork_member_a', routes[0])

    def test_sql_contains_encoded_data_and_preserves_request_identity(self):
        request={'request_id':str(uuid.uuid4()),'operation':'create_task',
                 'arguments':{'company':'FASB','title':"x'); DROP TABLE app_users; -- 😀",'revision':3}}
        first=actions.prepare(request)
        self.assertEqual(first,actions.prepare(request))
        self.assertNotIn('DROP TABLE',first['sql'])
        self.assertIn(request['request_id'],first['sql'])
        self.assertNotIn('role_name',first)
        self.assertEqual(first['project_id'],'lingering-base-89796182')
        # Hi2 forwards this value as Neon endpoint_id; blank values fail before SQL.
        self.assertEqual(first['compute_id'],'ep-fragrant-dust-az3a8wul')
        self.assertRegex(first['compute_id'],r'^ep-[a-z0-9-]+$')

    def test_ticket_wrappers_and_fixed_destination(self):
        ticket={'request_id':str(uuid.uuid4()),'ticket':'a'*64,'endpoint':actions.ENDPOINT}
        for wrapper in [ticket,[{'request':ticket}],{'content':[{'type':'text','text':json.dumps([{'request':ticket}])}]}]:
            self.assertEqual(actions.extract_ticket(wrapper),{k:ticket[k] for k in ['request_id','ticket']})
        for value in [{**ticket,'endpoint':'https://example.invalid'},[ticket,ticket],{}, {**ticket,'ticket':'short'}]:
            with self.assertRaises(ValueError):actions.extract_ticket(value)

    def test_private_receipts_and_bundled_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receipt.json';actions.private_write(path,{'ok':True})
            self.assertEqual(path.stat().st_mode&0o777,0o600)
        for folder in ['morning-brief','ctc-billing','ssm-form-filling']:
            for resource in ['scripts/dashboard_action.py','references/dashboard-actions.md']:
                self.assertEqual((ROOT/folder/resource).read_bytes(),(ROOT/'cosec-desk-actions'/resource).read_bytes())

if __name__=='__main__':unittest.main()
