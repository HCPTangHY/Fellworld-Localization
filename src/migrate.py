"""版本迁移：把旧版本 PZ 导出的译文搬到新版本 pz_origin

匹配顺序：
  1. key 完全一致
  2. 同一文件内 original 完全一致且旧侧唯一（处理 key 因方法改名 / 去向变化而变动）
  3. 全局 original 完全一致且旧侧唯一
未命中的条目留空，报告里列出新增 / 删除 / 原文变动
"""
import collections

from common import load_dir


def _index(old):
    by_key, by_file_orig, by_orig = {}, collections.defaultdict(list), collections.defaultdict(list)
    for rel, es in old.items():
        for e in es:
            if not (e.get('translation') or '').strip():
                continue
            by_key[e['key']] = e
            by_file_orig[(rel, e['original'])].append(e)
            by_orig[e['original']].append(e)
    return by_key, by_file_orig, by_orig


def migrate(new_dir, old_trans_dir):
    new, old = load_dir(new_dir), load_dir(old_trans_dir)
    by_key, by_file_orig, by_orig = _index(old)
    old_keys = {e['key']: e['original'] for es in old.values() for e in es}
    stat, changed = collections.Counter(), []
    for rel, es in new.items():
        for e in es:
            hit = by_key.get(e['key'])
            how = 'key'
            if hit and hit['original'] != e['original']:
                changed.append((e['key'], hit['original'], e['original']))
                hit, how = None, None
            if not hit:
                c = by_file_orig.get((rel, e['original']), [])
                hit, how = (c[0], 'file') if len(c) == 1 else (None, None)
            if not hit:
                c = by_orig.get(e['original'], [])
                hit, how = (c[0], 'global') if len(set(x['translation'] for x in c)) == 1 and c else (None, None)
            if hit:
                e['translation'] = hit['translation']
                if 'stage' in hit:
                    e['stage'] = hit['stage']
                stat[how] += 1
            else:
                stat['untranslated'] += 1
    new_keys = {e['key'] for es in new.values() for e in es}
    report = {
        'stat': dict(stat),
        'added': sorted(new_keys - set(old_keys)),
        'removed': sorted(set(old_keys) - new_keys),
        'original_changed': changed,
    }
    return new, report
