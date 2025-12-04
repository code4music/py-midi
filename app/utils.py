import time

GLOBAL_DEBUG = True


def log(msg):
    if GLOBAL_DEBUG:
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{ts}] {msg}")
