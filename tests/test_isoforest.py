"""IsoForest feature, filter, scheduling, and request-boundary contracts."""

from dataclasses import replace
from datetime import datetime, timedelta
from email.message import Message
from io import BytesIO
import json
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import numpy as np

from mycount.activity.BuildIsoForestFeatures import BuildIsoForestFeatures
from mycount.activity.RunIsoForest import RunIsoForest
from mycount.constants.DIsoForest import DIsoForest
from mycount.constants.DTrafficFilters import DTrafficFilters
from mycount.entity.IsoForestVisit import IsoForestVisit
from mycount.entity.Report import Report
from mycount.interface.IsoForestModel import IsoForestModel
from mycount.interface.IsoForestSchedule import IsoForestSchedule
from mycount.interface.ReportQuery import ReportQuery
from mycount.interface.VisitorsQuery import VisitorsQuery
from mycount.server.ControlHandler import ControlHandler
from mycount.server.ControlPages import ControlPages


def visit(identifier=1, *, address='10.1.2.3', stamp=datetime(2026, 11, 10, 12), site='blog'):
    return IsoForestVisit(identifier, stamp, site, f'https://{site}.example/page/{identifier}',
                          address, 'Example browser', (('platform', 'Win32'),))


class IsoForestTests(unittest.TestCase):
    def test_rotating_addresses_group_without_losing_any_visit(self):
        rows = [visit(i, address=f'10.1.{i}.1', stamp=datetime(2026, 11, 10, 12) + timedelta(minutes=6*i))
                for i in range(1, 15)]
        rows.append(visit(15, address='10.2.1.1'))
        observations = BuildIsoForestFeatures().build(list(reversed(rows)))
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0].network_block, '10.1.0.0/16')
        self.assertEqual(observations[0].distinct_ips, 14)
        self.assertEqual(set(i for observation in observations for i in observation.page_view_ids), set(range(1, 16)))
        features = dict(zip(DIsoForest.FEATURES, observations[0].features))
        self.assertAlmostEqual(features['inter_ip_median_gap_log'], np.log1p(360))
        self.assertEqual(features['inter_ip_gap_cv'], 0)
        self.assertEqual(observations, BuildIsoForestFeatures().build(rows))

    def test_long_session_from_one_ip_has_same_network_features_as_one_view(self):
        first = visit()
        multiple = [replace(first, page_view_id=i, url=f'https://blog.example/{i}',
                            received_at=first.received_at + timedelta(minutes=i)) for i in range(1, 21)]
        builder = BuildIsoForestFeatures()
        one = builder.build([first])[0]
        many = builder.build(multiple)[0]
        self.assertEqual(one.features, many.features)
        self.assertEqual(len(many.page_view_ids), 20)

    def test_missing_ips_ipv6_sites_and_utc_window_boundaries(self):
        rows = [visit(1, address=None), visit(2, address=None),
                visit(3, address='2001:db8:1234:1::1'), visit(4, address='2001:db8:1234:2::1'),
                visit(5, stamp=datetime(2026, 11, 11)), visit(6, site='other')]
        observations = BuildIsoForestFeatures().build(rows)
        self.assertEqual(len(observations), 5)
        missing = [o for o in observations if o.network_block.startswith('missing-ip:')]
        self.assertEqual(len(missing), 2)
        self.assertTrue(all(o.distinct_ips == 0 and len(o.page_view_ids) == 1 for o in missing))
        ipv6 = next(o for o in observations if o.network_block == '2001:db8:1234::/48')
        self.assertEqual(ipv6.distinct_ips, 2)
        self.assertEqual(ipv6.page_view_ids, (3, 4))
        self.assertTrue(all(np.isfinite(o.features).all() for o in observations))

    def test_model_reproducibility_automatic_cutoff_and_empty_source(self):
        builder = BuildIsoForestFeatures()
        rows = [visit(i, address=f'10.{i % 4}.{i}.1') for i in range(1, 50)]
        observations = builder.build(rows)
        first = IsoForestModel().fit(observations)
        second = IsoForestModel().fit(observations)
        self.assertEqual(first.decisions, second.decisions)
        self.assertEqual(first.manifest['parameters']['contamination'], 'auto')
        self.assertEqual(first.manifest['feature_version'], 'browser-context-v3')
        self.assertEqual(first.manifest['template_fields'], DIsoForest.TEMPLATE_FIELDS)
        model = pickle.loads(first.model)
        matrix = np.asarray([o.features for o in observations], dtype=np.float32)
        np.testing.assert_array_equal(model.predict(matrix) == -1, np.array(first.decisions) < 0)
        empty = IsoForestModel().fit(())
        self.assertEqual((empty.observations, empty.decisions, empty.model), ((), (), None))

    def test_legacy_run_inspection_uses_its_recorded_feature_names(self):
        selected = dict(run_id=1, status='complete', feature_version='network-rotation-v2',
                        ipv4_prefix=16, ipv6_prefix=48, window_hours=24, source_views=1,
                        observation_count=1, anomaly_views=0, anomaly_observations=0,
                        started_at=datetime(2026, 11, 13), completed_at=datetime(2026, 11, 13),
                        elapsed_seconds=.1, error=None, manifest={'features': DIsoForest.NETWORK_FEATURES})
        row = dict.fromkeys(DIsoForest.BROWSER_FEATURES)
        row.update(dict.fromkeys(DIsoForest.NETWORK_FEATURES, 0.))
        row.update(window_start=datetime(2026, 11, 13), site='blog', network_block='10.1.0.0/16',
                   page_views=1, distinct_ips=1, decision_score=.1, is_anomaly=False)
        body = ControlPages().isoforest(dict(selected=selected, runs=[selected], observations=[row],
                                              first_visit_at=None)).decode()
        self.assertIn('<dt>distinct_ips_log</dt>', body)
        self.assertNotIn('<dt>timezone_gap_hours</dt>', body)

    def test_filter_selection_round_trips_and_preserves_legacy_bookmarks(self):
        for mode, label in DTrafficFilters.OPTIONS:
            options = ReportQuery.resolve({'filter': [mode]})
            self.assertEqual(ReportQuery.resolve(parse_qs(urlsplit(ReportQuery.link('/metrics', options)).query)), options)
            link = VisitorsQuery.link({'languages': 'en'}, filter_mode=mode)
            self.assertEqual(ReportQuery.resolve(parse_qs(urlsplit(link).query)).filter_mode, mode)
            report = Report(options, [], None)
            pages = ControlPages()
            for render in (pages.render, pages.visitor_map, pages.marketing, lambda r: pages.visitors(r, {})):
                body = render(report).decode()
                self.assertIn(f'<option value="{mode}" selected>{label}</option>', body)
                self.assertNotIn('Exclude bots</label>', body)
        self.assertEqual(ReportQuery.resolve({'exclude_bots': ['0', '1']}).filter_mode, 'basic')
        self.assertEqual(ReportQuery.resolve({'exclude_bots': ['0']}).filter_mode, 'none')
        for values in (['bad'], ['basic', 'none'], [''], []):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ReportQuery.resolve({'filter': values})

    def test_schedule_retention_worker_lock_and_queued_run(self):
        with TemporaryDirectory() as directory:
            schedule = IsoForestSchedule(Path(directory))
            self.assertEqual(schedule.install(), {'enabled': True, 'expression': '0 * * * *'})
            schedule.update(False, '*/15 * * * *')
            self.assertEqual(schedule.install(), {'enabled': False, 'expression': '*/15 * * * *'})
            schedule.request_run()
            schedule.request_run()
            self.assertTrue(schedule.requested())
            with schedule.worker_lock() as first:
                with IsoForestSchedule(Path(directory)).worker_lock() as second:
                    self.assertTrue(first)
                    self.assertFalse(second)
            schedule.claim_request()
            self.assertFalse(schedule.requested())

    def request(self, schedule, *, path='/api/isoforest-schedule', method='GET', body=b'', headers=None):
        handler = object.__new__(ControlHandler)
        handler.path = path
        handler.headers = Message()
        for name, value in {'Host': 'localhost', 'Content-Type': 'application/json',
                            'Content-Length': str(len(body)), **(headers or {})}.items():
            handler.headers[name] = value
        handler.rfile = BytesIO(body)
        handler.respond = Mock()
        handler.send_error = Mock()
        with patch('mycount.server.ControlHandler.IsoForestSchedule', return_value=schedule):
            getattr(handler, 'do_' + method)()
        if handler.send_error.called:
            return handler.send_error.call_args.args[0], {}
        status, response, _ = handler.respond.call_args.args
        return status, json.loads(response)

    def test_schedule_and_queue_api_validate_writes_and_refuse_cross_site_requests(self):
        with TemporaryDirectory() as directory:
            schedule = IsoForestSchedule(Path(directory))
            self.assertEqual(self.request(schedule)[1]['schedule']['expression'], '0 * * * *')
            values = {'enabled': False, 'expression': '*/10 * * * *'}
            self.assertEqual(self.request(schedule, method='POST', body=json.dumps(values).encode())[0], 200)
            self.assertEqual(schedule.read(), values)
            self.assertEqual(self.request(schedule, path='/api/isoforest-run', method='POST', body=b'{}'),
                             (202, {'schedule': values, 'queued': True}))
            for body in (b'{', b'[]', b'{}', b'{"enabled":true,"expression":"@daily"}'):
                self.assertEqual(self.request(schedule, method='POST', body=body)[0], 400)
            for headers, expected in (({'Origin': 'https://other.example'}, 403),
                                      ({'Sec-Fetch-Site': 'cross-site'}, 403),
                                      ({'Content-Type': 'text/plain'}, 415),
                                      ({'Transfer-Encoding': 'chunked'}, 400)):
                self.assertEqual(self.request(schedule, path='/api/isoforest-run', method='POST',
                                              body=b'{}', headers=headers)[0], expected)

    @patch('mycount.activity.RunIsoForest.DbMgr')
    def test_disabled_and_busy_workers_do_not_open_database(self, factory):
        with TemporaryDirectory() as directory:
            schedule = IsoForestSchedule(Path(directory))
            schedule.update(False, '0 * * * *')
            self.assertIsNone(RunIsoForest(schedule).run(scheduled=True))
            with schedule.worker_lock():
                self.assertIsNone(RunIsoForest(schedule).run())
            factory.assert_not_called()

    @patch('mycount.activity.RunIsoForest.DbMgr')
    @patch('mycount.activity.RunIsoForest.IsoForestDb')
    @patch('mycount.interface.IsoForestModel.IsoForestModel')
    def test_manual_queue_runs_when_schedule_disabled_and_failures_are_recorded(self, model, store, factory):
        with TemporaryDirectory() as directory:
            schedule = IsoForestSchedule(Path(directory))
            schedule.update(False, '0 * * * *')
            schedule.request_run()
            store.return_value.start_run.return_value = 4
            store.return_value.raw_visits.return_value = []
            model.return_value.fit.side_effect = ValueError('model failed')
            with self.assertRaisesRegex(ValueError, 'model failed'):
                RunIsoForest(schedule).run(scheduled=True)
            store.return_value.fail_run.assert_called_once()
            store.return_value.publish.assert_not_called()
            self.assertFalse(schedule.requested())
            factory.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
