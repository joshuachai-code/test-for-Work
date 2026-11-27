from contextlib import ExitStack
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cosec-desk-actions/scripts'))
import hi2_assignment as flow


def ticket():
    return {'request_id': str(uuid.uuid4()), 'ticket': 'c' * 64}


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.user = {'id': 'live-leader-27', 'name': 'Current Caller', 'role': 'Team Leader', 'team_id': 'east',
                     'allowed_sections': ['tasks']}
        self.people = [{'id': 'worker', 'name': 'Aisha Rahman', 'role': 'Team Member', 'team_id': 'east'},
                       {'id': 'other', 'name': 'Aisha Noor', 'team_id': 'west'}]
        self.workspace = {'revision': 23, 'data': {'entities': [{'c': 'FA', 'name': 'Fast AI Sdn Bhd'}],
                         'progress': {'FA': {'teamId': 'east'}},
                         'rates': [{'id': 'svc', 'name': 'Certified true copies'}]}}
        self.business = {'company': 'Fast AI Sdn Bhd', 'assignee': 'Aisha', 'service': 'CTC',
                         'quantity': 5, 'due_date': '2026-11-30'}
        self.row = {'database_login': 'provisioned_actor_27', 'employee_id': self.user['id'],
                    'staff_role': self.user['role'], 'tasks_enabled': True, 'identity_ticket': ticket(), 'workspace_ticket': ticket()}
        self.document = {'request': self.business, 'hi2': [{'text': json.dumps([self.row])}]}

    def plan(self):
        identity = {'people': self.people, 'user': self.user}
        with patch.object(flow, 'fetch', side_effect=[identity, self.workspace]) as fetch:
            saved = flow.plan(self.document)
        self.assertEqual([c.args[0]['request_id'] for c in fetch.call_args_list],
                         [self.row[k]['request_id'] for k in ('identity_ticket', 'workspace_ticket')])
        return saved

    def eligibility_request(self):
        return {**self.document, 'request': {'company': 'FA', 'assignee': 'Aisha'}}

    def test_check_cli_returns_scoped_result_and_two_read_timings(self):
        identity = {'user': self.user, 'people': self.people}
        output = StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'argv', ['hi2_assignment.py', 'check']))
            stack.enter_context(patch.object(sys, 'stdin', StringIO(json.dumps(self.eligibility_request()))))
            stack.enter_context(patch.object(sys, 'stdout', output))
            stack.enter_context(patch.object(flow, 'perf_counter_ns', side_effect=[0, 3_000_000, 4_000_000, 9_000_000]))
            for forbidden in ('plan', 'write_call', 'finish'):
                stack.enter_context(patch.object(flow, forbidden, side_effect=AssertionError(forbidden)))
            reads = stack.enter_context(patch.object(flow, 'fetch', side_effect=[identity, self.workspace]))
            flow.main()
        self.assertEqual([call.args[0] for call in reads.call_args_list],
                         [self.row['identity_ticket'], self.row['workspace_ticket']])
        result = json.loads(output.getvalue())
        self.assertTrue(result['eligible'])
        self.assertEqual(result['caller']['id'], self.user['id'])
        self.assertEqual(result['assignee']['id'], 'worker')
        self.assertEqual(result['company'], {'code': 'FA', 'name': 'Fast AI Sdn Bhd'})
        self.assertEqual(result['timings_ms'], {'identity_read': 3, 'workspace_read': 5})
        self.assertNotIn('ticket', output.getvalue())
        self.assertNotIn('Aisha Noor', output.getvalue())

    def test_check_refuses_ambiguous_recipient_and_denied_workspace(self):
        identity = {'user': self.user, 'people': self.people + [dict(self.people[0], id='another')]}
        with patch.object(flow, 'fetch', side_effect=[identity, self.workspace]):
            with self.assertRaisesRegex(flow.AssignmentError, 'No unique eligible assignee'):
                flow.check(self.eligibility_request())
        with patch.object(flow, 'fetch', side_effect=[identity, flow.AssignmentError('Workspace denied')]):
            with self.assertRaisesRegex(flow.AssignmentError, 'Workspace denied'):
                flow.check(self.eligibility_request())

    def test_check_refuses_write_inputs_before_any_fetch(self):
        with patch.object(flow, 'fetch') as fetch:
            with self.assertRaisesRegex(flow.AssignmentError, 'only company and assignee'):
                flow.check(self.document)
        fetch.assert_not_called()

    def test_caller_request_recipient_write_readback(self):
        saved = self.plan()
        self.assertEqual(saved['employee_id'], self.user['id'])
        self.assertEqual(saved['arguments'], {'revision': 23, 'company': 'FA', 'ownerId': 'worker',
                         'serviceId': 'svc', 'quantity': 5, 'dueDate': '2026-11-30'})
        args = flow.write_call(saved)
        self.assertNotIn('role_name', args)
        self.assertIn(flow.sql_text(self.user['id']), args['sql'])
        self.assertIn(flow.sql_text(self.row['database_login']), args['sql'])
        self.assertEqual(args, flow.write_call(json.loads(json.dumps(saved))))
        write = {**ticket(), 'request_id': saved['request_id']}
        verify = ticket()
        row = {'id': 't-45', 'ownerId': 'worker', 'company_code': 'FA', 'serviceId': 'svc',
               'status': 'open', 'quantity': 5, 'dueDate': '2026-11-30'}
        with patch.object(flow, 'fetch', side_effect=[{'ok': True, 'operation':'create_task', 'task_id':'t-45'},
                                                      {'tasks': [{'id': 't-44'}, row]}]) as fetch:
            out = flow.finish(saved, [{'create_ticket': write, 'verify_ticket': verify}])
            self.assertTrue(out['verified'])
            self.assertEqual(out['task']['ownerId'], 'worker')
            self.assertEqual([c.args[0] for c in fetch.call_args_list], [write, verify])

    def test_same_first_name_in_company_team_or_unknown_or_inactive_stops(self):
        for people in [self.people + [dict(self.people[0], id='third')],
                       self.people[1:], [dict(self.people[0], active=False)]]:
            with self.subTest(people=people), self.assertRaises(flow.AssignmentError):
                flow.resolve(self.business, self.user, people, self.workspace)

    def test_member_may_only_assign_self_and_director_can_assign_across_teams(self):
        member = dict(self.user, role='Team Member')
        with self.assertRaises(flow.AssignmentError):
            flow.resolve(self.business, member, self.people, self.workspace)
        own = flow.resolve(self.business, dict(member, id='worker'), self.people, self.workspace)
        self.assertEqual(own['ownerId'], 'worker')
        director = dict(self.user, team_id='west', role='Director')
        self.assertEqual(flow.resolve(self.business, director, self.people, self.workspace)['ownerId'], 'worker')
        with self.assertRaises(flow.AssignmentError):
            flow.resolve(self.business, dict(self.user, team_id='west'), self.people, self.workspace)

    def test_missing_link_or_disabled_or_changed_actor_never_plans_a_write(self):
        with patch.object(flow, 'fetch') as fetch, self.assertRaises(flow.AssignmentError):
            flow.plan({'hi2': [], 'request': self.business})
        fetch.assert_not_called()
        with patch.object(flow, 'fetch') as fetch, self.assertRaises(flow.AssignmentError):
            flow.plan({'hi2': {**self.row, 'tasks_enabled':False, 'identity_ticket':None, 'workspace_ticket':None},
                       'request': self.business})
        fetch.assert_not_called()
        for user in [dict(self.user, allowed_sections=[]), dict(self.user, id='different')]:
            with patch.object(flow, 'fetch', return_value={'user': user, 'people': self.people}) as fetch:
                with self.assertRaises(flow.AssignmentError):
                    flow.plan(self.document)
                self.assertEqual(fetch.call_count, 1)

    def test_commit_before_failed_or_mismatched_readback_never_recreates(self):
        saved = self.plan()
        response = {'create_ticket': {**ticket(), 'request_id': saved['request_id']}, 'verify_ticket': ticket()}
        receipt = {'ok':True,'operation':'create_task','task_id':'new'}
        for read in [flow.AssignmentError('Read denied'), {'tasks':[{'id':'new','quantity':2}]}]:
            with patch.object(flow, 'fetch', side_effect=[receipt, read]) as fetch:
                result = flow.finish(saved, response)
                self.assertTrue(result['committed'])
                self.assertFalse(result['verified'])
                self.assertEqual(fetch.call_count, 2)
        with patch.object(flow, 'fetch', return_value={'ok':True, 'operation':'create_task',
                                                     'already_completed':True}) as fetch:
            result = flow.finish(saved, response)
            self.assertTrue(result['committed'])
            self.assertEqual(fetch.call_count, 1)
        response['create_ticket'] = ticket()
        with patch.object(flow, 'fetch') as fetch, self.assertRaises(flow.AssignmentError):
            flow.finish(saved, response)
        fetch.assert_not_called()

    def test_shipping_assignment_guide_derives_caller_and_packages_helper(self):
        with ZipFile(ROOT / 'cosec-desk-actions.skill') as pkg:
            self.assertEqual(pkg.read('scripts/hi2_assignment.py'),
                             (ROOT / 'cosec-desk-actions/scripts/hi2_assignment.py').read_bytes())
            guide = pkg.read('SKILL.md').decode()
        self.assertIn("WHERE links = 1 AND database_role = current_user AND tasks_enabled", guide)
        self.assertNotIn('gwork_daniel', guide)
        self.assertNotIn('gwork_member_a', guide)


if __name__ == '__main__':
    unittest.main()
