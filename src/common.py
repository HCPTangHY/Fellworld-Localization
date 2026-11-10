"""公共工具：版本号、key 生成、PZ json 读写"""
import collections
import glob
import json
import os
import re

POS_RE = re.compile(r'<<POS:(\d+)>>')


def game_version(data_dir):
    """从 globalgamemanagers 的 PlayerSettings.bundleVersion 读游戏版本号（如 0.0.19）"""
    import UnityPy
    env = UnityPy.load(os.path.join(data_dir, 'globalgamemanagers'))
    for o in env.objects:
        if o.type.name == 'PlayerSettings':
            return o.read_typetree()['bundleVersion']
    raise RuntimeError('PlayerSettings not found')


def slug(text, n=40):
    return re.sub(r'[^a-zA-Z0-9]+', '_', text[:n]).strip('_')


class KeyCounter:
    """同一 base key 重复出现时追加 #2、#3 ...（# 避免和原文里的数字撞，如 leave + leave2）"""

    def __init__(self):
        self.c = collections.Counter()

    def __call__(self, base):
        self.c[base] += 1
        return base if self.c[base] == 1 else f"{base}#{self.c[base]}"


def entry(key, original, pos, extra):
    """context 统一格式：<<POS:8位>> 在最前，其余标签跟在后面"""
    return {"key": key, "original": original, "translation": "",
            "context": f"<<POS:{pos:08d}>>{extra}"}


def write_files(files, out_dir):
    """files: {相对路径(无 .json): [entry]}"""
    for rel, entries in files.items():
        p = os.path.join(out_dir, rel + '.json')
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)


def load_dir(d):
    """-> {相对路径: [entry]}"""
    out = {}
    for p in glob.glob(os.path.join(d, '**', '*.json'), recursive=True):
        with open(p, encoding='utf-8') as f:
            out[os.path.relpath(p, d)[:-5]] = json.load(f)
    return out


def tag(ctx, name):
    m = re.search(rf'<<{name}:([^>]*)>>', ctx)
    return m.group(1) if m else None
