#!/bin/bash
# publisher_private.sh — отправка превью в личку @kednet для модерации
# Запускать с VPS, чтобы pending-файлы жили в /opt/publisher/tmp/
#
# Использование:
#   ./publisher_private.sh                  # дефолт detector
#   ./publisher_private.sh my_content       # кастомный JSON
set -e
cd /opt/publisher
exec proxychains4 -q /opt/wl/.venv/bin/python scripts/post_channels.py \
    --content "${1:-detector}" \
    --channels private
