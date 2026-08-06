#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from pathlib import Path
from unittest.mock import patch

from services.import_pipeline_service import _resolve_snapshot_key


class ImportPipelineSnapshotKeyTests(unittest.TestCase):
    def test_prefers_artifact_timestamp_after_job_id_prefix(self):
        key = _resolve_snapshot_key(
            '8c4ba27a569042f889494111730ec8a6_20260611-120541_enc.7z',
            Path('20260611-120541.db'),
        )

        self.assertEqual(key, '20260611')

    def test_skips_invalid_eight_digits_from_artifact_name(self):
        key = _resolve_snapshot_key(
            '8c4ba27a569042f889494111730ec8a6_artifact.7z',
            Path('20260611-120541.db'),
        )

        self.assertEqual(key, '20260611')

    def test_keeps_legacy_global_device_name(self):
        key = _resolve_snapshot_key(
            'artifact-without-date.7z',
            Path('global_device_20250728.db'),
        )

        self.assertEqual(key, '20250728')

    def test_falls_back_to_today_when_no_date_is_available(self):
        with patch('services.import_pipeline_service.datetime') as fake_datetime:
            fake_datetime.now.return_value.strftime.return_value = '20260611'
            key = _resolve_snapshot_key(
                'artifact-without-date.7z',
                Path('result.db'),
            )

        self.assertEqual(key, '20260611')


if __name__ == '__main__':
    unittest.main()
