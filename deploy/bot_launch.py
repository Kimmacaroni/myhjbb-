#!/usr/bin/python3 -I
"""Run as the unprivileged service user; systemd supplies existing credentials."""
import os

os.environ['DB_PATH'] = '/var/lib/honorary-bot/bot.db'
os.environ['YTDLP_COOKIE_FILE'] = '/var/lib/honorary-bot/youtube-cookies.txt'
os.environ['BOT_UPDATE_STATUS'] = '/var/lib/honorary-bot/.update-status'
os.environ['HOME'] = '/var/lib/honorary-bot'
os.environ['HF_HOME'] = '/var/lib/honorary-bot/huggingface'
os.chdir('/opt/honorary-bot')
os.execv('/opt/honorary-bot/.venv/bin/python',
         ['/opt/honorary-bot/.venv/bin/python', 'bot.py'])
