#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import sys
import os
import getpass
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
	sys.path.insert(0, str(BASE_DIR))

from utils.auth import hash_password, verify_password
from utils.password_policy import validate_password_strength

DB_PATH = BASE_DIR / 'user' / 'users.db'


def now_iso() -> str:
	return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def restore_admin(username: str, password: str):
	ok, msg = validate_password_strength(password)
	if not ok:
		raise ValueError(f'管理员密码不符合安全策略: {msg}')

	conn = sqlite3.connect(DB_PATH)
	try:
		cur = conn.execute('SELECT id FROM users WHERE username = ?', (username,))
		row = cur.fetchone()

		if row:
			conn.execute(
				'''
				UPDATE users
				SET role = 'admin',
					status = 'active',
					password_hash = ?,
					force_password_change = 1,
					password_reset_token_hash = NULL,
					password_reset_expires_at = NULL,
					session_version = session_version + 1,
					updated_at = ?
				WHERE username = ?
				''',
				(hash_password(password), now_iso(), username),
			)
			conn.commit()
			updated = conn.execute('SELECT username, password_hash FROM users WHERE username = ?', (username,)).fetchone()
			if not updated or not verify_password(password, updated[1]):
				raise RuntimeError(f'管理员密码校验失败，请确认命令行传入的密码未被 shell 改写。db={DB_PATH}')
			print(f'admin restored: username={username}, db={DB_PATH}')
			return

		# 账号不存在时补建一个管理员
		conn.execute(
			'''
			INSERT INTO users (username, password_hash, role, status, session_version, force_password_change, created_at, updated_at)
			VALUES (?, ?, 'admin', 'active', 1, 1, ?, ?)
			''',
			(username, hash_password(password), now_iso(), now_iso()),
		)
		conn.commit()
		created = conn.execute('SELECT username, password_hash FROM users WHERE username = ?', (username,)).fetchone()
		if not created or not verify_password(password, created[1]):
			raise RuntimeError(f'管理员密码校验失败，请确认命令行传入的密码未被 shell 改写。db={DB_PATH}')
		print(f'admin created: username={username}, db={DB_PATH}')
	finally:
		conn.close()


if __name__ == '__main__':
	username = 'admin'
	password = (os.environ.get('RESTORE_ADMIN_PASSWORD') or '').strip()
	if len(sys.argv) >= 2 and sys.argv[1].strip():
		username = sys.argv[1].strip()
	if len(sys.argv) >= 3 and sys.argv[2]:
		password = sys.argv[2]
	if not password:
		try:
			password = getpass.getpass('请输入新的管理员密码（输入时不回显）: ').strip()
		except (EOFError, KeyboardInterrupt):
			password = ''
	if not password:
		print('错误: 请通过参数、RESTORE_ADMIN_PASSWORD 或交互输入提供管理员密码')
		print('用法: python backend/scripts/restore_admin.py <username> <password>')
		sys.exit(2)
	restore_admin(username, password)
