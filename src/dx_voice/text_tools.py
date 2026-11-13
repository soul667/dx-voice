"""Thin adapters around the official OpenAI SDK; generated commands are never run."""
from dataclasses import dataclass
import os
import re
import shutil
import subprocess

import httpx
from openai import OpenAI
from pydantic import BaseModel


class TextResult(BaseModel):
    text: str


def text_settings(cfg):
    result = dict(cfg)
    for key in ('api_key', 'base_url'):
        if cfg.get('text_' + key):
            result[key] = cfg['text_' + key]
    return result


@dataclass
class Outcome:
    text: str
    processing: str


class TextTools:
    def __init__(self):
        self._client = None
        self._signature = None

    def client(self, cfg):
        signature = tuple(cfg.get(k, '') for k in ('api_key', 'base_url', 'proxy_url'))
        if signature != self._signature:
            if self._client:
                self._client.close()
            self._client = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'], max_retries=0,
                                  http_client=httpx.Client(proxy=cfg.get('proxy_url') or None))
            self._signature = signature
        return self._client

    def request(self, cfg, model, instructions, text, timeout, effort, image=None):
        content = text
        if image:
            content = [{'role': 'user', 'content': [{'type': 'input_text', 'text': text},
                        {'type': 'input_image', 'image_url': image, 'detail': cfg.get('rewrite_image_detail', 'low')}]}]
        options = dict(model=model, instructions=instructions, input=content, text_format=TextResult,
                       tools=[], store=False, max_output_tokens=1800)
        if model.startswith(('gpt-5', 'gpt-6', 'o1', 'o3', 'o4')):
            options['reasoning'] = {'effort': effort}
        response = self.client(cfg).with_options(timeout=timeout, max_retries=0).responses.parse(**options)
        if response.output_parsed is None or not response.output_parsed.text.strip():
            raise RuntimeError('模型未返回可用结果。')
        return response.output_parsed.text.strip()

    def process(self, mode, raw, cfg, image=None):
        if mode == 'command':
            from .modules.command import generate
            return generate(self, raw, cfg)
        from .modules.rewrite import process
        return process(self, raw, cfg, image)

    def close(self):
        if self._client:
            self._client.close()


def validate_command(command, shell):
    if not command.strip() or '```' in command or any(ord(char) < 32 or ord(char) == 127 for char in command):
        raise RuntimeError('模型返回的不是纯命令，结果没有被粘贴。')
    executable = shutil.which(shell)
    if not executable:
        raise RuntimeError('目标 shell 未安装，命令保留在历史前请先选择本机 shell。')
    # -n parses syntax only; it never runs the generated command.
    env = {key: value for key, value in os.environ.items() if key not in ('BASH_ENV', 'ENV')}
    flags = ['--no-config', '--no-execute'] if shell == 'fish' else ['--noprofile', '--norc', '-n'] if shell == 'bash' else ['-f', '-n'] if shell == 'zsh' else ['-n']
    parsed = subprocess.run([executable, *flags], input=command, text=True, capture_output=True, timeout=2, env=env)
    if parsed.returncode:
        raise RuntimeError('命令语法不完整，结果没有被粘贴。')
