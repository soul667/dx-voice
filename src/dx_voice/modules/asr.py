"""Provider boundary; audio capture/format and transcription stay paired per backend."""
from importlib.metadata import entry_points
from ..realtime import Realtime, Capture


class OpenAIBackend:
    id = 'openai'

    @staticmethod
    def settings(cfg):
        values = dict(cfg)
        for name in ('api_key', 'base_url'):
            if cfg.get('asr_' + name):
                values[name] = cfg['asr_' + name]
        return values

    def create_realtime(self, callback):
        return Realtime(callback)

    def create_capture(self, path, source, chunk, done):
        return Capture(path, source, chunk, done)

    def transcribe_file(self, path, cfg):
        from ..app import transcription
        return transcription(path, self.settings(cfg))


def providers():
    return ['openai', *sorted(p.name for p in entry_points(group='dx_voice.asr'))]


def load_backend(name):
    if name == 'openai':
        return OpenAIBackend()
    for point in entry_points(group='dx_voice.asr'):
        if point.name == name:
            backend = point.load()()
            if all(callable(getattr(backend, field, None)) for field in
                   ('settings', 'create_realtime', 'create_capture', 'transcribe_file')):
                return backend
            raise RuntimeError('语音后端接口不完整。')
    raise RuntimeError('语音后端未安装；当前内置 OpenAI，千问等后端可通过独立适配器接入。')
