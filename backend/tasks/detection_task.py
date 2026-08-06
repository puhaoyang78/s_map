#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from tasks.celery_app import celery_app
from services.detection_orchestrator_service import run_detection_job


@celery_app.task(name='detection.run_job', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def run_detection_job_task(self, job_id: str):
    run_detection_job(job_id)
    return {'job_id': job_id, 'status': 'done'}
