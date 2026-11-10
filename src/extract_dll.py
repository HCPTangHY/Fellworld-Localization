"""Assembly-CSharp.dll 字符串提取

key     : dll|类::方法|去向_原文摘要[n]
context : <<POS:IL偏移>><<TOKEN:MethodDef>><<SINK:sink>><<KIND:show|id|other>> 
文件    : 按顶层类型拆分，<out>/dll/<类型>.json
"""
import collections
import re

from common import KeyCounter, entry, slug
from reader import TYPE_OWNER, iter_ldstr, load_pe, read_method
from sinks import classify, resolve_sink

# 这些 sink 的字符串不进 PZ（调试输出 / 异常信息）
DROP = re.compile(r'^(Debug\.Log\w*|Exception\.\.ctor|\w*Exception\.\.ctor|Debug\.Assert)#')


def _short_sink(sink):
    """key 里的去向前缀：方法名或字段名"""
    s = sink[4:] if sink.startswith('arr:') else sink
    if s.startswith('fld:'):
        return s[4:]
    if '#' in s:
        name = s.split('#')[0].rsplit('.', 1)[-1]
        return '' if name in ('op_Equality', 'op_Inequality', 'Add', 'ctor', '.ctor') else name.replace('set_', '')
    return ''


def extract(dll_path):
    pe = load_pe(dll_path)
    files = collections.defaultdict(list)
    stat = collections.Counter()
    for rid in range(1, len(pe.net.mdtables.MethodDef) + 1):
        body, il0 = read_method(pe, rid)
        if body is None:
            continue
        insns = list(body.instructions)
        owner = TYPE_OWNER.get(rid, '?')
        mname = str(pe.net.mdtables.MethodDef[rid - 1].Name)
        kc = KeyCounter()
        for i, off, s in iter_ldstr(pe, insns):
            if not re.search(r'[A-Za-z]{2,}', s):
                continue
            sink = resolve_sink(pe, insns, i)
            if DROP.match(sink):
                stat['drop'] += 1
                continue
            kind = classify(sink)
            stat[kind] += 1
            pre = _short_sink(sink)
            base = f"dll|{owner}::{mname}|" + (slug(pre) + '_' if pre else '') + slug(s)
            top = owner.split('.')[-1].split('/')[0].strip('<>') or 'misc'
            files['dll/' + top].append(entry(
                kc(base), s, off - il0,
                f"<<TOKEN:{0x06000000 | rid:#010x}>><<SINK:{sink}>><<KIND:{kind}>> {owner}::{mname}"))
    return files, stat
