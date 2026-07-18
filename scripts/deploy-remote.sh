#!/usr/bin/env bash
# 在服务器上执行（由 .github/workflows/deploy.yml 经 SSH `bash -s` 灌入，也可手动跑）。
#
# 作用：把 /root/ChaYu-BAMA 同步到 origin/main 最新，然后 docker compose up -d --build。
# 幂等：可重复执行，不会动 backend/.env（被 gitignore，仅服务器上一次性放置），
#      也不碰其他 compose 项目（如 my-blog）。
#
# 前置（一次性，已做好）：
#   - 服务器装好 docker + compose（已确认 v5.3.1）
#   - /root/ChaYu-BAMA/backend/.env 已放置（含 LLM_API_KEY / IMAGE_API_KEY 等）
#   - GitHub 仓库 Secret：SSH_PRIVATE_KEY（对应服务器 authorized_keys 里的公钥）、SSH_HOST

set -euo pipefail

DEPLOY_DIR=/root/ChaYu-BAMA
REPO=https://github.com/Littlebanbrick/ChaYu-BAMA.git
BRANCH=main

echo "[deploy] $(date -u +%FT%TZ) start on $(hostname)"

# 首次部署：仓库不存在则 clone
if [ ! -d "$DEPLOY_DIR/.git" ]; then
  echo "[deploy] first deploy: cloning $REPO"
  git clone --branch "$BRANCH" "$REPO" "$DEPLOY_DIR"
else
  echo "[deploy] repo present, syncing"
fi

cd "$DEPLOY_DIR"
git fetch --all --prune
git reset --hard "origin/$BRANCH"
# 注意：不跑 git clean -fdx，那会删掉被 gitignore 的 backend/.env。reset --hard 已足够。

# 守卫：.env 必须存在（gitignored，需在服务器上手动放一次）
if [ ! -f backend/.env ]; then
  echo "[deploy] ERROR: backend/.env 不存在。请在服务器放置后再部署。" >&2
  exit 1
fi

echo "[deploy] building & starting containers (8080)..."
docker compose up -d --build
docker image prune -f

echo "[deploy] containers:"
docker compose ps
echo "[deploy] done $(date -u +%FT%TZ)"
