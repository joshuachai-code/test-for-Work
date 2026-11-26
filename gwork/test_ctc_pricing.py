from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ctc-billing' / 'scripts'))
from records import record_confirmed


class NewRunPricing(unittest.TestCase):
    def setUp(self):
        self.job = dict(job_id='A', run_id='A-01', subcategory='CTC', work_status='pending',
                        general_agent='agent', cosec_agent='agent', created_date='2026-11-26',
                        company_name='Example', company_id='A', billing_unit='page', quantity=3)

    def test_missing_either_price_never_opens_books(self):
        with patch('excel_source.paths', side_effect=AssertionError('opened books')):
            for prices in ({}, {'rate_rm': 5}, {'printing_rm': 0}, {'rate_rm': 5, 'printing_rm': ''}):
                with self.subTest(prices=prices), self.assertRaisesRegex(ValueError,'printing charge'):
                    record_confirmed({**self.job, **prices})

    def test_validates_printing_as_a_job_total(self):
        with self.assertRaisesRegex(ValueError, 'differs'):
            record_confirmed({**self.job, 'rate_rm': 7.50, 'printing_rm': 2, 'charge_sen': 2850})


if __name__ == '__main__':
    unittest.main()
