import json
import logging
from pathlib import Path
from configparser import ConfigParser

logger = logging.getLogger(__name__)


class Translator:
    def __init__(self, builtin_dir: Path, user_dir: Path = None):
        self.builtin_dir = builtin_dir
        self.user_dir = user_dir
        self.current_lang = 'en'
        self._data = {}
        self._load('en')

    def _load(self, lang: str):
        self._data = {}

        sources = []
        if self.user_dir:
            sources.append(self.user_dir / f'{lang}.json')
        sources.append(self.builtin_dir / f'{lang}.json')
        sources.append(self.builtin_dir / f'{lang}.ini')

        loaded = False
        for path in sources:
            if path.suffix == '.json' and path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                self._data = self._flatten(raw)
                loaded = True
                break
            elif path.suffix == '.ini' and path.exists():
                parser = ConfigParser()
                parser.optionxform = str
                parser.read(path, encoding='utf-8')
                for section in parser.sections():
                    for key, val in parser.items(section):
                        self._data[f'{section}.{key}'] = val
                loaded = True
                break

        if not loaded:
            logger.warning(f"No language file found for '{lang}'")

    def _flatten(self, d: dict, prefix: str = '') -> dict:
        result = {}
        for k, v in d.items():
            key = f'{prefix}.{k}' if prefix else k
            if isinstance(v, dict):
                result.update(self._flatten(v, key))
            else:
                result[key] = v
        return result

    def set_language(self, lang: str):
        self._load(lang)
        self.current_lang = lang

    def tr(self, key: str, default: str = None) -> str:
        return self._data.get(key, default if default is not None else key)

    def available_languages(self) -> list[tuple[str, str]]:
        seen = set()
        langs = []

        for base_dir in [self.user_dir, self.builtin_dir]:
            if not base_dir or not base_dir.exists():
                continue
            for f in sorted(base_dir.glob('*.json')):
                if f.stem == 'languages' or f.stem in seen:
                    continue
                code = f.stem
                with open(f, 'r', encoding='utf-8') as fh:
                    raw = json.load(fh)
                label = raw.get('lang', {}).get('self_name', code)
                langs.append((code, label))
                seen.add(code)
            if not langs:
                for f in sorted(base_dir.glob('*.ini')):
                    if f.stem in seen:
                        continue
                    code = f.stem
                    p = ConfigParser()
                    p.optionxform = str
                    p.read(f, encoding='utf-8')
                    label = p.get('lang', 'self_name', fallback=code)
                    langs.append((code, label))
                    seen.add(code)

        return langs
