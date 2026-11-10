"""Unity 资源（MonoBehaviour 字符串字段）提取

资源里不带 typetree，用 TypeTreeGenerator 从 Managed/*.dll 现生成（需 glibc>=2.34，旧服务器用 docker）
key     : asset|<文件>|<脚本类>|<字段路径>|<原文摘要>[n]
context : <<POS:PathID>><<FIELD:字段路径>><<FILE:文件>> 类名
文件    : <out>/assets/<文件>/<脚本类>.json
"""
import collections
import os
import re
import struct

from common import KeyCounter, entry, slug

ASSET_FILES = ("resources.assets", "sharedassets0.assets", "level0")
DEP_FILES = ("globalgamemanagers", "globalgamemanagers.assets")

# 字段名命中 -> 跳过；子树命中 -> 整棵跳过
SKIP_FIELD = re.compile(r'(^|\.)(m_Name|guid|\w*ID|\w*Id|path|Path|key|Key|gate|prefabs|eventState|eventName|'
                        r'archetypeName|m_StyleName|m_FamilyName|type)(\[\d+\])?$')
SKIP_TREE = re.compile(r'^(m_Script|m_GameObject)|m_AnimationTriggers|m_PersistentCalls|m_StyleList|m_FaceInfo|'
                       r'm_FontData|m_fontAsset')


def _walk(v, path, out):
    if isinstance(v, str):
        if re.search(r'[A-Za-z]{2,}', v) and not SKIP_FIELD.search(path) and not SKIP_TREE.search(path):
            out.append((path, v))
    elif isinstance(v, dict):
        for k, x in v.items():
            _walk(x, f"{path}.{k}" if path else k, out)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            _walk(x, f"{path}[{i}]", out)


def load_env(data_dir, unity_version):
    import UnityPy
    from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
    gen = TypeTreeGenerator(unity_version)
    gen.load_local_game(os.path.dirname(os.path.abspath(data_dir)))
    env = UnityPy.load(*[os.path.join(data_dir, f) for f in DEP_FILES + ASSET_FILES])
    env.typetree_generator = gen
    return env


def _script_index(env):
    return {(os.path.basename(o.assets_file.name), o.path_id): o.read().m_ClassName
            for o in env.objects if o.type.name == "MonoScript"}


def _script_of(o, scripts):
    # MonoBehaviour 头部固定布局：m_GameObject(PPtr 12B) + m_Enabled(1B 对齐到 4B) + m_Script(PPtr)
    try:
        raw = o.get_raw_data()
        fid, pid = struct.unpack_from('<iq', raw, 16)
        f = os.path.basename(o.assets_file.name) if fid == 0 else os.path.basename(o.assets_file.externals[fid - 1].path)
        return scripts.get((f, pid), 'Unknown')
    except Exception:
        return 'Unknown'


def extract(data_dir, unity_version):
    env = load_env(data_dir, unity_version)
    scripts = _script_index(env)
    files = collections.defaultdict(list)
    counters = collections.defaultdict(KeyCounter)
    stat = collections.Counter()
    for o in env.objects:
        fn = os.path.basename(o.assets_file.name)
        if o.type.name != "MonoBehaviour" or fn not in ASSET_FILES:
            continue
        try:
            tree = o.read_typetree()
        except Exception:
            stat['err'] += 1
            continue
        cls = _script_of(o, scripts)
        found = []
        _walk(tree, "", found)
        for path, s in found:
            field = re.sub(r'\[\d+\]', '', path)
            base = f"asset|{fn}|{cls}|{field}|{slug(s)}"
            files[f"assets/{fn}/{cls}"].append(entry(
                counters[f"{fn}/{cls}"](base), s, o.path_id, f"<<FIELD:{path}>><<FILE:{fn}>> {cls}"))
            stat['kept'] += 1
    return files, stat


