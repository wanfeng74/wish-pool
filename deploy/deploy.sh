#!/usr/bin/env bash
# 一键部署到 Linux 服务器
#   SERVER=root@1.2.3.4 PORT=22 ./deploy/deploy.sh
set -euo pipefail

SERVER="${SERVER:?请设置 SERVER，例如 SERVER=root@1.2.3.4}"
SSH_PORT="${PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-/opt/wishpool}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"

echo "==> 上传到 $SERVER:$REMOTE_DIR"
ssh -p "$SSH_PORT" "$SERVER" "mkdir -p $REMOTE_DIR/pkg $REMOTE_DIR/backups"
scp -P "$SSH_PORT" "$ROOT/server/wish_server.py" "$ROOT/server/panel.html" "$SERVER:$REMOTE_DIR/"

echo "==> 安装 systemd 单元"
scp -P "$SSH_PORT" "$HERE/wishpool.service" "$SERVER:/etc/systemd/system/wishpool.service"
ssh -p "$SSH_PORT" "$SERVER" "systemctl daemon-reload && systemctl enable --now wishpool"

echo "==> 状态"
ssh -p "$SSH_PORT" "$SERVER" "systemctl is-active wishpool; curl -s http://127.0.0.1:17613/healthz; echo"
echo
echo "完成。管理密码见服务器 $REMOTE_DIR/admin_pass.txt"
