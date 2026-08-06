#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path
from typing import Optional
from celery import Celery
from celery.signals import worker_init

from utils.env_loader import load_backend_dotenv
from utils.logger import setup_logging
from utils.startup_validation import assert_backend_startup_config

load_backend_dotenv()
assert_backend_startup_config()


@worker_init.connect
def _setup_worker_logging(**_kwargs):
    # worker 进程不经过 backend/app.py 的 create_app()，需在此初始化项目日志；
    # 不在模块顶层直接调用，避免 Flask 进程 import 本模块后与
    # create_app() 里的 setup_logging(app) 叠加出重复的文件 handler。
    setup_logging()


_CELERY_APP: Optional[Celery] = None


def create_celery() -> Celery:
    broker_url = (os.environ.get('CELERY_BROKER_URL') or 'filesystem://').strip()
    result_backend = (os.environ.get('CELERY_RESULT_BACKEND') or '').strip()

    backend_root = Path(__file__).resolve().parent.parent
    queue_root_raw = (os.environ.get('CELERY_FS_QUEUE_ROOT') or '').strip()
    if queue_root_raw:
        queue_root_path = Path(queue_root_raw)
        if not queue_root_path.is_absolute():
            queue_root_path = backend_root / queue_root_path
        queue_root = queue_root_path.resolve()
    else:
        queue_root = (backend_root / 'data' / 'celery').resolve()
    # For single-machine development with filesystem transport, use one shared
    # folder for both incoming/outgoing messages to avoid producer/consumer
    # directory mismatch causing queued tasks to never be consumed.
    msg_dir = queue_root / 'messages'
    processed_dir = queue_root / 'processed'
    msg_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    app = Celery('my_map_app_detection', broker=broker_url, backend=(result_backend or None))
    app.conf.update(
        task_track_started=True,
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        timezone='Asia/Shanghai',
        enable_utc=False,
        broker_connection_retry_on_startup=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        task_ignore_result=True,
        broker_transport_options={
            'data_folder_in': str(msg_dir),
            'data_folder_out': str(msg_dir),
            'data_folder_processed': str(processed_dir),
        },
        imports=('tasks.detection_task',),
    )
    # tasks 包内只有 detection_task 一个任务模块，已由 imports 显式加载；
    # autodiscover 只会去查找不存在的 tasks.tasks，故移除。
    return app


def get_celery_app() -> Celery:
    global _CELERY_APP
    if _CELERY_APP is None:
        _CELERY_APP = create_celery()
    return _CELERY_APP


def init_celery() -> Celery:
    return get_celery_app()


def enqueue_detection_job(job_id: str) -> str:
    from tasks.detection_task import run_detection_job_task

    async_result = run_detection_job_task.delay(job_id)
    return async_result.id


celery_app = get_celery_app()

# worker 启动命令：celery -A tasks.celery_app:celery_app worker -l info
