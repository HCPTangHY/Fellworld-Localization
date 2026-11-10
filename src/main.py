"""Fellworld 汉化工具入口

  python src/main.py extract  <Fellworld_Data>                 -> pz_origin/<版本>/{dll,assets}/...
  python src/main.py migrate  <新版本> <旧版本PZ导出目录>        -> pz_trans/<新版本>/... + 迁移报告
  python src/main.py stat     <版本>                            -> 按 KIND / SINK 统计
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import game_version, load_dir, tag, write_files  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cmd_extract(a):
    import extract_assets
    import extract_dll
    ver = a.version or game_version(a.data)
    out = os.path.join(ROOT, 'pz_origin', ver)
    files, stat = extract_dll.extract(os.path.join(a.data, 'Managed', 'Assembly-CSharp.dll'))
    print('dll', dict(stat))
    if not a.skip_assets:
        af, ast = extract_assets.extract(a.data, a.unity)
        files.update(af)
        print('assets', dict(ast))
    write_files(files, out)
    print('version', ver, '->', out, 'files', len(files))


def cmd_migrate(a):
    import migrate
    new, report = migrate.migrate(os.path.join(ROOT, 'pz_origin', a.version), a.old)
    out = os.path.join(ROOT, 'pz_trans', a.version)
    write_files(new, out)
    with open(os.path.join(out, '_migrate_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(report['stat'], 'added', len(report['added']), 'removed', len(report['removed']),
          'changed', len(report['original_changed']))


def cmd_stat(a):
    data = load_dir(os.path.join(ROOT, 'pz_origin', a.version))
    kind, sink = collections.Counter(), collections.Counter()
    for es in data.values():
        for e in es:
            kind[tag(e['context'], 'KIND') or 'asset'] += 1
            sink[tag(e['context'], 'SINK') or 'asset'] += 1
    print(dict(kind))
    for k, v in sink.most_common(a.top):
        print(v, k)


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest='cmd', required=True)
    e = sp.add_parser('extract')
    e.add_argument('data', help='Fellworld_Data 目录')
    e.add_argument('--version', help='默认读 PlayerSettings.bundleVersion')
    e.add_argument('--unity', default='2021.3.18f1')
    e.add_argument('--skip-assets', action='store_true')
    m = sp.add_parser('migrate')
    m.add_argument('version')
    m.add_argument('old', help='旧版本 PZ 导出（含译文）目录')
    s = sp.add_parser('stat')
    s.add_argument('version')
    s.add_argument('--top', type=int, default=40)
    a = p.parse_args()
    {'extract': cmd_extract, 'migrate': cmd_migrate, 'stat': cmd_stat}[a.cmd](a)


if __name__ == '__main__':
    main()
