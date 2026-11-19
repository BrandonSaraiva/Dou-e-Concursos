[app]
title = Radar DOU
package.name = monitor
package.domain = org.radardou
source.dir = .
source.include_exts = py,kv,png,jpg,atlas,md
source.exclude_dirs = .git,.github,.venv,tests,assets,__pycache__,.pytest_cache,dist,build,bin
version = 1.2.1
requirements = python3,kivy==2.3.1,pyjnius,requests,beautifulsoup4,python-telegram-bot,apscheduler
orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.minapi = 26
android.api = 35
android.ndk = 28c
p4a.branch = v2026.05.09
android.accept_sdk_license = True
android.permissions = INTERNET,FOREGROUND_SERVICE,FOREGROUND_SERVICE_SPECIAL_USE,POST_NOTIFICATIONS,WAKE_LOCK
android.allow_backup = False
services = Radar:android_service.py:foreground:sticky:foregroundServiceType=specialUse
# O serviço monitora publicações continuamente a pedido do usuário. Para
# distribuição na Play Store, acrescente a declaração documentada de subtipo
# de serviço e realize revisão de conformidade com a política Google Play.
[buildozer]
log_level = 2
warn_on_root = 1
