import threading
from .config import Config
from .utils import log, GLOBAL_DEBUG
from .synth import SynthModule
from .midi import MidiBridge
from .webui import create_app
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


def reload_configs(cfg, synth, midi):
    try:
        cfg.load()
        synth.reload(cfg.data)
        midi.cc_map = cfg.midi_map.get('cc', {})
        midi.actions = cfg.midi_map.get('actions', {})
        log('[reload] configs reloaded from config.yaml')
    except Exception as e:
        log(f'[reload] error: {e}')


class ConfigWatcher(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        self.callback()


def run():
    cfg = Config()
    from . import utils
    utils.GLOBAL_DEBUG = cfg.debug

    synth = SynthModule(cfg)
    midi = MidiBridge(cfg, synth)

    if cfg.data.get('auto_reload', True):
        watcher = ConfigWatcher(lambda: reload_configs(cfg, synth, midi))
        obs = Observer()
        obs.schedule(watcher, '.', recursive=False)
        obs.start()

    http_cfg = cfg.data.get('http', {})
    if http_cfg.get('enabled', False):
        app = create_app(synth)
        t = threading.Thread(
            target=app.run,
            kwargs={
                'host': http_cfg.get('host', '0.0.0.0'),
                'port': http_cfg.get('port', 5000),
                'debug': False,
                'use_reloader': False,
            },
            daemon=True
        )
        t.start()
        log('[http] UI running')

    try:
        midi.process()
    except KeyboardInterrupt:
        log('Exiting...')


if __name__ == "__main__":
    run()
