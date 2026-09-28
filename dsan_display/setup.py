"""Browser adapter for the same guided pairing routine used by the console."""
import copy
import hashlib
import json
import logging
import threading
import uuid

from .model import Source
from .workers import Worker


class SetupCancelled(Exception):
    pass


class Setup:
    def __init__(self, server, config_path, enumerate_devices, make_worker=None, target='This computer'):
        self.server, self.config_path = server, config_path
        self.enumerate_devices = enumerate_devices
        self.make_worker = make_worker or native_worker
        self.target = target
        self.condition = threading.Condition()
        self.thread = None
        self.cancelled = False
        self.answer = None
        self.notice = ''
        self.state = {'status': 'idle', 'session': '', 'prompt': None, 'messages': [],
                      'config': None, 'error': '', 'target': target}

    def snapshot(self):
        with self.condition:
            return {**copy.deepcopy(self.state), 'has_saved': self.config_path.exists()}

    def notify(self, message):
        with self.condition:
            self.state['messages'] = (self.state['messages'] + [message])[-8:]
            self.notice = message

    def prompt(self, prompt):
        with self.condition:
            if self.cancelled:
                raise SetupCancelled()
            self.answer = None
            self.state.update(status='waiting', prompt={**prompt, 'id': uuid.uuid4().hex, 'note': self.notice})
            self.notice = ''
            self.condition.wait_for(lambda: self.cancelled or self.answer is not None)
            if self.cancelled:
                raise SetupCancelled()
            answer = self.answer
            self.state.update(status='working', prompt=None)
            return answer

    def start(self):
        with self.condition:
            if self.server.quitting.is_set():
                raise ValueError('Application is shutting down')
            if self.thread and self.thread.is_alive():
                raise ValueError('Setup is already in progress')
            self.cancelled = False
            self.state.update(status='working', session=uuid.uuid4().hex, prompt=None,
                              messages=[], config=None, error='')
            self.thread = threading.Thread(target=self._pair, daemon=True, name='dsan-setup')
            self.thread.start()

    def _pair(self):
        from .windows import guided_configure
        try:
            config = guided_configure(enumerate_devices=self.enumerate_devices,
                                      prompt_callback=self.prompt, notify=self.notify)
            with self.condition:
                if self.cancelled:
                    raise SetupCancelled()
                self.state.update(status='review', config=config, prompt=None)
        except SetupCancelled:
            pass
        except Exception as exc:
            logging.exception('Device setup failed')
            with self.condition:
                if not self.cancelled:
                    self.state.update(status='error', error=str(exc), prompt=None)

    def cancel(self):
        with self.condition:
            if self.state['status'] in ('applying', 'restoring'):
                raise ValueError('Please wait for the inputs to start')
            self.cancelled = True
            self.state.update(status='idle', prompt=None, config=None, error='')
            self.condition.notify_all()

    def close(self):
        with self.condition:
            self.cancelled = True
            self.condition.notify_all()

    def respond(self, data):
        with self.condition:
            prompt = self.state['prompt']
            if (self.state['status'] != 'waiting' or not prompt or
                    data.get('prompt') != prompt['id'] or data.get('session') != self.state['session'] or
                    self.answer is not None):
                raise ValueError('This step has changed. Refresh the setup page.')
            answer = data.get('answer')
            if not isinstance(answer, str) or len(answer) > 120:
                raise ValueError('Enter an answer of at most 120 characters')
            if prompt['kind'] == 'role' and answer not in ('1', '2', ''):
                raise ValueError('Choose Limitimer, PerfectCue, or Review')
            if prompt['kind'] == 'continue' and answer != '':
                raise ValueError('Use Check connection to continue')
            self.answer = answer
            self.condition.notify_all()

    def apply(self, session):
        with self.condition:
            if self.state['status'] != 'review' or session != self.state['session']:
                raise ValueError('Review the current setup before saving')
            config = copy.deepcopy(self.state['config'])
            self.state.update(status='applying', error='')
            self.thread = threading.Thread(target=self._apply, args=(config,), daemon=True, name='dsan-setup-save')
            self.thread.start()

    def _activate(self, config, save):
        from .windows import launch_arguments
        # Fresh enumeration immediately before saving/opening: never substitute a peer.
        devices = self.enumerate_devices()
        launch_arguments(config, devices)
        if save and {d['path_hex'] for d in devices} != {s['path_hex'] for s in config['sources']}:
            raise ValueError('Connections changed since review. Run setup again before saving.')
        workers = dict(self.make_worker(source) for source in config['sources'])
        with self.server.control_lock:
            if self.server.quitting.is_set() or self.cancelled:
                raise ValueError('Application is shutting down')
            if save:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.config_path.with_suffix('.tmp')
                temporary.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
                temporary.replace(self.config_path)
            for worker in self.server.workers.values():
                worker.stop()
                if worker.thread and worker.thread.is_alive():
                    raise RuntimeError('An old input has not stopped; new inputs were not opened')
            self.server.workers = workers
            for worker in workers.values():
                worker.start()

    def _apply(self, config):
        try:
            self._activate(config, save=True)
            with self.condition:
                self.state.update(status='complete', prompt=None)
        except Exception as exc:
            logging.exception('Could not activate device setup')
            with self.condition:
                self.state.update(status='error', error=str(exc), prompt=None)

    def restore(self):
        """Keep the browser responsive while loading and checking saved bindings."""
        def run():
            try:
                config = json.loads(self.config_path.read_text(encoding='utf-8'))
                self._activate(config, save=False)
                with self.condition:
                    self.state.update(status='complete', config=config)
            except Exception as exc:
                with self.condition:
                    self.state.update(status='error', error=str(exc))
        with self.condition:
            if self.thread and self.thread.is_alive():
                raise ValueError('Setup is already in progress')
            self.cancelled = False
            self.state.update(status='restoring', error='', prompt=None)
            self.thread = threading.Thread(target=run, daemon=True, name='dsan-setup-restore')
            self.thread.start()


def native_worker(source):
    identity = hashlib.sha256(('hid:' + source['path_hex']).encode()).hexdigest()[:12]
    return identity, Worker(Source(identity, source['label'], 'hid', source['path_hex'], role=source['role']),
                            initialize_hid=source['initialize'])


def launch_gui(args, enumerate_devices):
    import webbrowser
    from .__main__ import create_server
    from .video_settings import VideoSettings
    server = create_server(args.host, args.port)
    server.video_settings = VideoSettings(args.data_dir / 'video-settings.json')
    setup = server.setup = Setup(server, args.config, enumerate_devices)
    if args.config.exists() and not args.configure:
        setup.restore()
    host = '127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host
    if ':' in host:
        host = '[' + host + ']'
    url = f'http://{host}:{server.server_port}/setup'
    print('DSAN device setup: ' + url, flush=True)
    print('Keep this console open. Use Quit application in the browser to stop.', flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop_workers()
        server.server_close()
