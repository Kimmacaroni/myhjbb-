#!/usr/bin/env bash
# 새로 만든 VM(Ubuntu/Debian 계열)에 봇을 설치하는 스크립트입니다.
#
# 사용법:
#   1) 이 저장소를 VM에 clone 한 뒤, 그 디렉터리 안에서 실행하세요.
#      git clone <저장소 주소> honorary-bot && cd honorary-bot
#      bash deploy/install.sh
#   2) .env 파일에 토큰 등을 채우라는 안내가 뜨면 채운 뒤 스크립트를 다시 실행하세요.
#
# 실행마다 안전하게 다시 돌려도 되도록(idempotent) 만들었습니다.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="honorary-bot"
RUN_USER="$(id -un)"

cd "$APP_DIR"

echo "▶ 패키지 목록 갱신 및 설치 (Python, git, FFmpeg)"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip git ffmpeg curl unzip bzip2

# 최신 유튜브는 재생 URL 검증에 JavaScript 실행 환경을 요구합니다.
if ! command -v deno >/dev/null 2>&1; then
    echo "▶ 유튜브 검증용 Deno 설치"
    curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/opt/deno sh
    sudo ln -sf /opt/deno/bin/deno /usr/local/bin/deno
fi

echo "▶ 가상환경 준비: $APP_DIR/.venv"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

FAST_TTS_DIR="$APP_DIR/models/vits-mimic3-ko_KO-kss_low"
if [ ! -f "$FAST_TTS_DIR/ko_KO-kss_low.onnx" ]; then
    echo "▶ 빠른 한국어 TTS 모델 설치"
    mkdir -p "$APP_DIR/models"
    curl -fL \
        https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-mimic3-ko_KO-kss_low.tar.bz2 \
        -o "$APP_DIR/models/ko-tts.tar.bz2"
    tar -xjf "$APP_DIR/models/ko-tts.tar.bz2" -C "$APP_DIR/models"
    rm "$APP_DIR/models/ko-tts.tar.bz2"
fi

if [ ! -f ".env" ]; then
    echo
    echo "▶ .env 파일이 없어 .env.example 을 복사합니다."
    cp .env.example .env
    echo "  ⚠️  $APP_DIR/.env 를 열어 DISCORD_TOKEN 등 값을 채운 뒤"
    echo "     이 스크립트를 다시 실행하세요:  bash deploy/install.sh"
    exit 0
fi

if ! grep -q '^DISCORD_TOKEN=.\+' .env; then
    echo "⚠️  .env 의 DISCORD_TOKEN 이 비어 있습니다. 값을 채운 뒤 다시 실행하세요."
    exit 1
fi

echo "▶ systemd 서비스 등록: /etc/systemd/system/${SERVICE_NAME}.service"
sudo sed \
    -e "s#__USER__#${RUN_USER}#g" \
    -e "s#__APP_DIR__#${APP_DIR}#g" \
    deploy/honorary-bot.service \
    | sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo
echo "✅ 설치 완료. 서버가 재부팅되어도 자동으로 켜집니다."
echo
echo "상태 확인:   sudo systemctl status ${SERVICE_NAME}"
echo "로그 보기:   journalctl -u ${SERVICE_NAME} -f"
echo "재시작:      sudo systemctl restart ${SERVICE_NAME}"
echo "코드 갱신 후: git pull && ./.venv/bin/pip install -r requirements.txt && sudo systemctl restart ${SERVICE_NAME}"
