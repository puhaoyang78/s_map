#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

trap 'echo "ERROR: line ${LINENO}: ${BASH_COMMAND}" >&2' ERR

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${APP_ROOT:-$(cd -- "$SCRIPT_DIR/.." && pwd)}"
BACKEND_DIR="$APP_ROOT/backend"
FRONT_DIR="$APP_ROOT/front"

CONDA_ENV="${CONDA_ENV:-starlink}"
PYTHON_VERSION="${PYTHON_VERSION:-3.9}"
NODE_VERSION="${NODE_VERSION:-20.19.0}"
BACKEND_PORT="${BACKEND_PORT:-5000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
USE_TUNA_APT="${USE_TUNA_APT:-1}"
FORCE_ENV="${FORCE_ENV:-0}"
CHOWN_APP_ROOT="${CHOWN_APP_ROOT:-1}"
RUN_PREFLIGHT="${RUN_PREFLIGHT:-1}"
SKIP_SERVICE_START="${SKIP_SERVICE_START:-0}"

CONDA_INSTALLER_URL="${CONDA_INSTALLER_URL:-https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"

log() {
  printf '\n==> %s\n' "$*"
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

run_privileged() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi

  command -v sudo >/dev/null 2>&1 || die "需要 root 权限或可用的 sudo"
  sudo "$@"
}

run_as_deploy_user() {
  if [[ "$(id -un)" == "$DEPLOY_USER" ]]; then
    "$@"
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo -H -u "$DEPLOY_USER" "$@"
    return
  fi

  runuser -u "$DEPLOY_USER" -- "$@"
}

detect_deploy_user() {
  if [[ -n "${DEPLOY_USER:-}" ]]; then
    return
  fi

  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    DEPLOY_USER="$SUDO_USER"
    return
  fi

  if id ubuntu >/dev/null 2>&1; then
    DEPLOY_USER="ubuntu"
    return
  fi

  DEPLOY_USER="$(id -un)"
}

detect_public_host() {
  if [[ -n "${PUBLIC_HOST:-}" ]]; then
    return
  fi

  PUBLIC_HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -z "$PUBLIC_HOST" ]]; then
    PUBLIC_HOST="127.0.0.1"
  fi
}

random_secret() {
  local bytes="${1:-32}"
  openssl rand -hex "$bytes"
}

validate_layout() {
  [[ -d "$APP_ROOT" ]] || die "APP_ROOT 不存在: $APP_ROOT"
  [[ -f "$BACKEND_DIR/requirements.txt" ]] || die "后端 requirements 不存在: $BACKEND_DIR/requirements.txt"
  [[ -f "$FRONT_DIR/package.json" ]] || die "前端 package.json 不存在: $FRONT_DIR/package.json"
  [[ -f "$APP_ROOT/scripts/preflight_check.py" ]] || die "preflight 脚本不存在: $APP_ROOT/scripts/preflight_check.py"
}

configure_apt_tuna_mirror() {
  [[ "$USE_TUNA_APT" == "1" ]] || return
  [[ -r /etc/os-release ]] || {
    warn "无法识别系统版本，跳过 apt 清华源替换"
    return
  }

  # shellcheck disable=SC1091
  . /etc/os-release
  case "${ID:-}" in
    ubuntu|debian) ;;
    *)
      warn "当前系统不是 Ubuntu/Debian，跳过 apt 清华源替换"
      return
      ;;
  esac

  log "备份并替换 apt 源为清华镜像"
  local stamp files file
  stamp="$(date +%Y%m%d%H%M%S)"
  files=()
  [[ -f /etc/apt/sources.list ]] && files+=(/etc/apt/sources.list)

  shopt -s nullglob
  files+=(/etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources)
  shopt -u nullglob

  for file in "${files[@]}"; do
    [[ -f "$file" ]] || continue
    run_privileged cp -n "$file" "${file}.bootstrap-backup-${stamp}"
    if [[ "${ID:-}" == "ubuntu" ]]; then
      run_privileged sed -i -E \
        -e 's#https?://([a-z]{2}\.)?archive\.ubuntu\.com/ubuntu/?#https://mirrors.tuna.tsinghua.edu.cn/ubuntu/#g' \
        -e 's#https?://security\.ubuntu\.com/ubuntu/?#https://mirrors.tuna.tsinghua.edu.cn/ubuntu/#g' \
        "$file"
    else
      run_privileged sed -i -E \
        -e 's#https?://deb\.debian\.org/debian/?#https://mirrors.tuna.tsinghua.edu.cn/debian/#g' \
        -e 's#https?://security\.debian\.org/debian-security/?#https://mirrors.tuna.tsinghua.edu.cn/debian-security/#g' \
        "$file"
    fi
  done
}

install_system_packages() {
  configure_apt_tuna_mirror
  log "安装系统基础依赖"
  run_privileged apt-get update
  run_privileged env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates \
    curl \
    bzip2 \
    xz-utils \
    tar \
    git \
    openssl \
    build-essential
}

configure_user_mirrors() {
  log "写入 conda 与 pip 清华源配置"
  local tmp_condarc tmp_pipconf
  tmp_condarc="$(mktemp)"
  tmp_pipconf="$(mktemp)"

  cat >"$tmp_condarc" <<'EOF'
channels:
  - defaults
show_channel_urls: true
default_channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2
custom_channels:
  conda-forge: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  pytorch: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  nvidia: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
EOF

  cat >"$tmp_pipconf" <<EOF
[global]
index-url = $PIP_INDEX_URL
trusted-host = pypi.tuna.tsinghua.edu.cn
timeout = 60
EOF

  run_privileged install -d -o "$DEPLOY_USER" -g "$DEPLOY_GROUP" "$DEPLOY_HOME/.pip"
  run_privileged install -m 0644 -o "$DEPLOY_USER" -g "$DEPLOY_GROUP" "$tmp_condarc" "$DEPLOY_HOME/.condarc"
  run_privileged install -m 0644 -o "$DEPLOY_USER" -g "$DEPLOY_GROUP" "$tmp_pipconf" "$DEPLOY_HOME/.pip/pip.conf"
  rm -f "$tmp_condarc" "$tmp_pipconf"
}

install_miniconda() {
  if [[ -x "$CONDA_DIR/bin/conda" ]]; then
    CONDA_BIN="$CONDA_DIR/bin/conda"
    log "复用已有 conda: $CONDA_BIN"
    return
  fi

  log "从清华镜像安装 Miniconda 到 $CONDA_DIR"
  local installer
  installer="$(mktemp --suffix=.sh)"
  curl -fsSL --retry 3 "$CONDA_INSTALLER_URL" -o "$installer"
  chmod 0755 "$installer"
  run_as_deploy_user bash "$installer" -b -p "$CONDA_DIR"
  rm -f "$installer"

  CONDA_BIN="$CONDA_DIR/bin/conda"
  [[ -x "$CONDA_BIN" ]] || die "conda 安装失败: $CONDA_BIN"
}

ensure_conda_env() {
  log "创建或复用 conda env: $CONDA_ENV"
  if ! run_as_deploy_user "$CONDA_BIN" run -n "$CONDA_ENV" python --version >/dev/null 2>&1; then
    run_as_deploy_user "$CONDA_BIN" create -y -n "$CONDA_ENV" "python=$PYTHON_VERSION" pip
  fi

  log "安装后端 Python requirements"
  run_as_deploy_user "$CONDA_BIN" run -n "$CONDA_ENV" python -m pip config set global.index-url "$PIP_INDEX_URL" >/dev/null
  run_as_deploy_user "$CONDA_BIN" run -n "$CONDA_ENV" python -m pip install --upgrade pip
  run_as_deploy_user "$CONDA_BIN" run -n "$CONDA_ENV" python -m pip install -r "$BACKEND_DIR/requirements.txt"
}

detect_node_arch() {
  case "$(uname -m)" in
    x86_64|amd64) NODE_ARCH="x64" ;;
    aarch64|arm64) NODE_ARCH="arm64" ;;
    *) die "暂不支持当前 Node.js 架构: $(uname -m)" ;;
  esac
}

install_nodejs() {
  detect_node_arch
  NODE_DIST="node-v${NODE_VERSION}-linux-${NODE_ARCH}"
  NODE_PREFIX="/opt/${NODE_DIST}"
  NODE_CURRENT="/opt/node-current"

  if [[ ! -x "$NODE_PREFIX/bin/node" ]]; then
    log "从清华镜像安装 Node.js $NODE_VERSION"
    local archive url
    archive="$(mktemp --suffix=.tar.xz)"
    url="${NODE_DOWNLOAD_BASE:-https://mirrors.tuna.tsinghua.edu.cn/nodejs-release/v${NODE_VERSION}}/${NODE_DIST}.tar.xz"
    curl -fsSL --retry 3 "$url" -o "$archive"
    run_privileged tar -C /opt -xJf "$archive"
    rm -f "$archive"
  else
    log "复用已有 Node.js: $NODE_PREFIX"
  fi

  run_privileged ln -sfn "$NODE_PREFIX" "$NODE_CURRENT"
  run_privileged ln -sfn "$NODE_CURRENT/bin/node" /usr/local/bin/node
  run_privileged ln -sfn "$NODE_CURRENT/bin/npm" /usr/local/bin/npm
  run_privileged ln -sfn "$NODE_CURRENT/bin/npx" /usr/local/bin/npx

  NODE_BIN="$NODE_CURRENT/bin/node"
  NPM_BIN="$NODE_CURRENT/bin/npm"
  run_as_deploy_user "$NPM_BIN" config set registry "$NPM_REGISTRY" >/dev/null
}

prepare_runtime_dirs() {
  log "准备运行时目录"
  run_privileged install -d -o "$DEPLOY_USER" -g "$DEPLOY_GROUP" \
    "$BACKEND_DIR/data" \
    "$BACKEND_DIR/data/artifacts" \
    "$BACKEND_DIR/data/celery" \
    "$BACKEND_DIR/logs" \
    "$BACKEND_DIR/control" \
    "$BACKEND_DIR/db_backups"

  if [[ "$CHOWN_APP_ROOT" == "1" ]]; then
    run_privileged chown -R "$DEPLOY_USER:$DEPLOY_GROUP" "$APP_ROOT"
  fi
}

ensure_backend_cors_origins() {
  [[ -f "$BACKEND_ENV" ]] || return

  log "确保后端 CORS_ORIGINS 包含当前前端地址"
  local tmp_env
  tmp_env="$(mktemp)"

  run_privileged "$CONDA_BIN" run -n "$CONDA_ENV" python - "$BACKEND_ENV" "$CORS_ORIGINS" >"$tmp_env" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
desired = [item.strip() for item in sys.argv[2].split(',') if item.strip()]
lines = path.read_text(encoding='utf-8').splitlines()

existing = []
for line in lines:
    if line.startswith('CORS_ORIGINS='):
        existing = [item.strip() for item in line.split('=', 1)[1].split(',') if item.strip()]
        break

merged = []
for item in existing + desired:
    if item not in merged:
        merged.append(item)

cors_line = 'CORS_ORIGINS=' + ','.join(merged)
for index, line in enumerate(lines):
    if line.startswith('CORS_ORIGINS='):
        lines[index] = cors_line
        break
else:
    lines.append(cors_line)

print('\n'.join(lines) + '\n', end='')
PY

  run_privileged install -m 0600 -o "$DEPLOY_USER" -g "$DEPLOY_GROUP" "$tmp_env" "$BACKEND_ENV"
  rm -f "$tmp_env"
}

write_backend_env() {
  BACKEND_ENV="$BACKEND_DIR/.env.local"
  if [[ -f "$BACKEND_ENV" && "$FORCE_ENV" != "1" ]]; then
    log "保留已有后端环境文件: $BACKEND_ENV"
    ensure_backend_cors_origins
    return
  fi

  log "生成后端环境文件: $BACKEND_ENV"
  GENERATED_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-$(random_secret 16)}"
  local auth_secret agent_token webhook_token artifact_password artifact_path agent_base_url
  auth_secret="${AUTH_SECRET:-$(random_secret 32)}"
  agent_token="${DETECTION_AGENT_TOKEN:-$(random_secret 32)}"
  webhook_token="${DETECTION_WEBHOOK_TOKEN:-$(random_secret 32)}"
  artifact_password="${DETECTION_ARTIFACT_PASSWORD:-$(random_secret 24)}"
  # 默认留空：走 REMOTE 模式（由 agent 提供制品）；仅当操作员显式传入
  # DETECTION_LOCAL_ARTIFACT_PATH 时才写入本地制品文件路径（preflight 要求它指向文件）。
  artifact_path="${DETECTION_LOCAL_ARTIFACT_PATH:-}"
  agent_base_url="${DETECTION_AGENT_BASE_URL:-https://${PUBLIC_HOST}:18080/}"

  cat >"$BACKEND_ENV" <<EOF
FLASK_HOST=0.0.0.0
FLASK_PORT=$BACKEND_PORT
FLASK_DEBUG=false
LOG_LEVEL=${LOG_LEVEL:-INFO}
CORS_ORIGINS=$CORS_ORIGINS

AUTH_COOKIE_NAME=auth_token
AUTH_COOKIE_MAX_AGE=604800
AUTH_COOKIE_SECURE=${AUTH_COOKIE_SECURE:-false}
AUTH_COOKIE_SAMESITE=Lax
AUTH_SECRET=$auth_secret

DEFAULT_ADMIN_USERNAME=${DEFAULT_ADMIN_USERNAME:-admin}
DEFAULT_ADMIN_PASSWORD=$GENERATED_ADMIN_PASSWORD
ALLOW_INSECURE_DEFAULT_ADMIN=false

SSH_STRICT_HOST_KEY=true
SELF_RESTART_ENABLED=false
AUTH_LOGIN_WINDOW_SECONDS=300
AUTH_LOGIN_MAX_ATTEMPTS=5
AUTH_LOGIN_LOCK_SECONDS=600
AUTH_EXPOSE_RESET_TOKEN=false
AUTH_RESET_TOKEN_TTL_SECONDS=600

DETECTION_LOCAL_ARTIFACT_PATH=$artifact_path
DETECTION_AGENT_BASE_URL=$agent_base_url
DETECTION_AGENT_TOKEN=$agent_token
DETECTION_AGENT_VERIFY_TLS=${DETECTION_AGENT_VERIFY_TLS:-true}
DETECTION_AGENT_CA_CERT_PATH=${DETECTION_AGENT_CA_CERT_PATH:-}
DETECTION_AGENT_ALLOW_INSECURE_HTTP=${DETECTION_AGENT_ALLOW_INSECURE_HTTP:-false}

DETECTION_AGENT_START_TIMEOUT_SECONDS=30
DETECTION_AGENT_STATUS_TIMEOUT_SECONDS=30
DETECTION_AGENT_CANCEL_TIMEOUT_SECONDS=30
DETECTION_AGENT_ARTIFACT_TIMEOUT_SECONDS=300
DETECTION_AGENT_POLL_INTERVAL_SECONDS=30
DETECTION_AGENT_HTTP_RETRIES=2
DETECTION_AGENT_HTTP_RETRY_BACKOFF_SECONDS=1.5
DETECTION_AGENT_MAX_POLL_FAILURES=5
DETECTION_JOB_MAX_RUNTIME_SECONDS=7200

DETECTION_ARTIFACT_ALLOWED_HOSTS=${DETECTION_ARTIFACT_ALLOWED_HOSTS:-$PUBLIC_HOST}
DETECTION_ARTIFACT_ALLOWED_PORTS=${DETECTION_ARTIFACT_ALLOWED_PORTS:-}
DETECTION_ARTIFACT_ALLOW_PRIVATE_HOSTS=${DETECTION_ARTIFACT_ALLOW_PRIVATE_HOSTS:-false}
DETECTION_WEBHOOK_BASE_URL=${DETECTION_WEBHOOK_BASE_URL:-}
DETECTION_WEBHOOK_TOKEN=$webhook_token
DETECTION_WEBHOOK_ALLOW_INSECURE_HTTP=${DETECTION_WEBHOOK_ALLOW_INSECURE_HTTP:-false}
DETECTION_WEBHOOK_REQUIRE_SIGNATURE=true
DETECTION_WEBHOOK_SIGNATURE_TTL_SECONDS=300

CELERY_BROKER_URL=filesystem://
CELERY_RESULT_BACKEND=
CELERY_FS_QUEUE_ROOT=$BACKEND_DIR/data/celery

DETECTION_ARTIFACT_PASSWORD=$artifact_password

STARLINK_CELESTRAK_URL=https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle
STARLINK_SPACEX_URL=https://api.spacexdata.com/v4/starlink/
STARLINK_CACHE_TTL_SECONDS=300
STARLINK_HTTP_TIMEOUT_SECONDS=20
STARLINK_MAX_ITEMS=2500
EOF

  run_privileged chown "$DEPLOY_USER:$DEPLOY_GROUP" "$BACKEND_ENV"
  run_privileged chmod 0600 "$BACKEND_ENV"
  ensure_backend_cors_origins
}

write_frontend_env() {
  FRONT_ENV="$FRONT_DIR/.env.production.local"
  if [[ -f "$FRONT_ENV" && "$FORCE_ENV" != "1" ]]; then
    log "保留已有前端生产环境覆盖文件: $FRONT_ENV"
    return
  fi

  log "生成前端生产环境覆盖文件: $FRONT_ENV"
  cat >"$FRONT_ENV" <<EOF
VITE_API_BASE_URL=$BACKEND_API_BASE_URL
EOF

  run_privileged chown "$DEPLOY_USER:$DEPLOY_GROUP" "$FRONT_ENV"
  run_privileged chmod 0600 "$FRONT_ENV"
}

install_frontend_dependencies() {
  log "安装前端依赖并构建"
  if [[ -f "$FRONT_DIR/package-lock.json" ]]; then
    run_as_deploy_user bash -lc "cd '$FRONT_DIR' && '$NPM_BIN' ci"
  else
    run_as_deploy_user bash -lc "cd '$FRONT_DIR' && '$NPM_BIN' install"
  fi
  run_as_deploy_user bash -lc "cd '$FRONT_DIR' && '$NPM_BIN' run build"
}

run_preflight() {
  [[ "$RUN_PREFLIGHT" == "1" ]] || return
  log "运行部署 preflight 检查"
  run_as_deploy_user "$CONDA_BIN" run -n "$CONDA_ENV" python "$APP_ROOT/scripts/preflight_check.py"
}

write_systemd_units() {
  log "写入 systemd 服务"
  local backend_unit frontend_unit node_path
  backend_unit="$(mktemp)"
  frontend_unit="$(mktemp)"
  node_path="$NODE_CURRENT/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin"

  cat >"$backend_unit" <<EOF
[Unit]
Description=My Map App Backend (Flask, conda env: $CONDA_ENV)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$DEPLOY_USER
Group=$DEPLOY_GROUP
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=$BACKEND_ENV
Environment=PYTHONUNBUFFERED=1
Environment=PATH=$CONDA_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin
ExecStart=$CONDA_BIN run --no-capture-output -n $CONDA_ENV python app.py
Restart=always
RestartSec=5
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
EOF

  cat >"$frontend_unit" <<EOF
[Unit]
Description=My Map App Frontend (Vite Preview)
After=network-online.target my-map-backend.service
Wants=network-online.target

[Service]
Type=simple
User=$DEPLOY_USER
Group=$DEPLOY_GROUP
WorkingDirectory=$FRONT_DIR
Environment=HOME=$DEPLOY_HOME
Environment=NODE_ENV=production
Environment=PATH=$node_path
EnvironmentFile=-$FRONT_ENV
ExecStartPre=/usr/bin/test -f $FRONT_DIR/dist/index.html
ExecStart=$NPM_BIN run preview -- --host 0.0.0.0 --port $FRONTEND_PORT
Restart=always
RestartSec=5
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
EOF

  run_privileged install -m 0644 "$backend_unit" /etc/systemd/system/my-map-backend.service
  run_privileged install -m 0644 "$frontend_unit" /etc/systemd/system/my-map-frontend.service
  rm -f "$backend_unit" "$frontend_unit"
}

start_services() {
  [[ "$SKIP_SERVICE_START" == "0" ]] || {
    warn "SKIP_SERVICE_START=1，已跳过 systemd 启动"
    return
  }

  log "启用并启动 systemd 服务"
  run_privileged systemctl daemon-reload
  run_privileged systemctl enable my-map-backend.service my-map-frontend.service
  run_privileged systemctl restart my-map-backend.service
  run_privileged systemctl restart my-map-frontend.service
  sleep 3

  for service in my-map-backend.service my-map-frontend.service; do
    if ! run_privileged systemctl is-active --quiet "$service"; then
      run_privileged journalctl -u "$service" -n 80 --no-pager || true
      die "$service 启动失败"
    fi
  done
}

smoke_check() {
  [[ "$SKIP_SERVICE_START" == "0" ]] || return
  log "执行最小健康检查"
  curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/health" >/dev/null || die "后端健康检查失败"
  curl -fsS "http://127.0.0.1:${FRONTEND_PORT}/" >/dev/null || die "前端健康检查失败"
}

print_summary() {
  log "部署完成"
  echo "应用目录: $APP_ROOT"
  echo "运行用户: $DEPLOY_USER"
  echo "conda: $CONDA_BIN"
  echo "conda env: $CONDA_ENV"
  echo "node: $NODE_BIN"
  echo "npm: $NPM_BIN"
  echo "后端: http://${PUBLIC_HOST}:${BACKEND_PORT}/api/health"
  echo "前端: http://${PUBLIC_HOST}:${FRONTEND_PORT}/"
  if [[ -n "${GENERATED_ADMIN_PASSWORD:-}" ]]; then
    echo "默认管理员账号: ${DEFAULT_ADMIN_USERNAME:-admin}"
    echo "默认管理员密码: $GENERATED_ADMIN_PASSWORD"
    echo "请妥善保存该密码，并在首次登录后立即修改。"
  fi
}

main() {
  detect_deploy_user
  id "$DEPLOY_USER" >/dev/null 2>&1 || die "部署用户不存在: $DEPLOY_USER"
  DEPLOY_GROUP="${DEPLOY_GROUP:-$(id -gn "$DEPLOY_USER")}"
  DEPLOY_HOME="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)"
  [[ -n "$DEPLOY_HOME" ]] || die "无法获取部署用户 Home: $DEPLOY_USER"

  CONDA_DIR="${CONDA_DIR:-$DEPLOY_HOME/miniconda3}"
  detect_public_host
  BACKEND_API_BASE_URL="${BACKEND_API_BASE_URL:-http://${PUBLIC_HOST}:${BACKEND_PORT}}"
  FRONTEND_PUBLIC_URL="${FRONTEND_PUBLIC_URL:-http://${PUBLIC_HOST}:${FRONTEND_PORT}}"
  CORS_ORIGINS="${CORS_ORIGINS:-$FRONTEND_PUBLIC_URL,http://127.0.0.1:${FRONTEND_PORT},http://localhost:${FRONTEND_PORT}}"

  validate_layout
  install_system_packages
  prepare_runtime_dirs
  configure_user_mirrors
  install_miniconda
  ensure_conda_env
  install_nodejs
  write_backend_env
  write_frontend_env
  install_frontend_dependencies
  run_preflight
  write_systemd_units
  start_services
  smoke_check
  print_summary
}

main "$@"
