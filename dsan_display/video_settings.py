"""Shared video presentation settings, independent of confidence rendering."""
import json
import threading
from pathlib import Path

DEFAULTS = {'displayMode': 'both', 'minimal': True, 'timerSize': 100,
            'cueSize': 100, 'warning': 30, 'overtime': False}


def validate_changes(changes):
    if not isinstance(changes, dict) or not changes or set(changes) - DEFAULTS.keys():
        raise ValueError('Expected known video presentation settings')
    for key, value in changes.items():
        if key == 'displayMode':
            if value not in ('timer', 'cue', 'both'):
                raise ValueError('Invalid video layout')
        elif key in ('minimal', 'overtime'):
            if type(value) is not bool:
                raise ValueError(f'{key} must be true or false')
        else:
            low, high = (0, 3600) if key == 'warning' else (50, 150)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{key} must be an integer from {low} to {high}')
    return dict(changes)


class VideoSettings:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.lock = threading.Lock()
        self.settings, self.revision = dict(DEFAULTS), 0
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('schema') != 1 or type(data.get('revision')) is not int or data['revision'] < 0:
                raise ValueError('Invalid video settings file')
            self.settings.update(validate_changes(data['settings']))
            self.revision = data['revision']

    def snapshot(self):
        with self.lock:
            return {'settings': dict(self.settings), 'revision': self.revision}

    def update(self, changes):
        changes = validate_changes(changes)
        with self.lock:
            updated = {**self.settings, **changes}
            revision = self.revision + 1
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix('.tmp')
                temporary.write_text(json.dumps({'schema': 1, 'settings': updated, 'revision': revision}, indent=2) + '\n', encoding='utf-8')
                temporary.replace(self.path)
            self.settings, self.revision = updated, revision
            return {'settings': dict(updated), 'revision': revision}
