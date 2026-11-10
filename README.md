# Fellworld-Localization

Fellworld（Unity 2021.3.18f1 / Mono）汉化工具链。

## 目录

```
src/
  main.py            入口：extract / migrate / stat
  reader.py          dnfile/dncil 读 DLL：字符串堆、方法签名、类型归属
  sinks.py           IL 栈模拟：追踪每个字符串最终流向（sink），并分类 show / id / other
  extract_dll.py     Assembly-CSharp.dll 字符串提取
  extract_assets.py  MonoBehaviour 字符串字段提取（UnityPy + TypeTreeGenerator）
  migrate.py         版本迁移：旧版本译文 -> 新版本 pz_origin
  common.py          版本号读取、key 计数、PZ json 读写
pz_origin/<版本>/
  dll/<类型>.json
  assets/<资源文件>/<脚本类>.json
```

版本号读自 `globalgamemanagers` 的 `PlayerSettings.bundleVersion`（当前 `0.0.19`）。

## 用法

```bash
pip install -r requirements.txt
python src/main.py extract <Fellworld_Data>          # -> pz_origin/<版本>/
python src/main.py stat 0.0.19                       # 按 KIND / SINK 统计
python src/main.py migrate 0.0.20 <旧版本PZ导出目录>   # -> pz_trans/0.0.20/ + _migrate_report.json
```

> TypeTreeGeneratorAPI 需要 glibc ≥ 2.34；老系统用 `docker run -v ...:/w python:3.11-slim` 跑。

## 词条格式

### DLL

```json
{
  "key": "dll|EventCronosReturn::EventProgress|AddButton_Inquire",
  "original": "Inquire",
  "context": "<<POS:00000187>><<TOKEN:0x060002ff>><<SINK:Buttonbar.AddButton#buttonText>><<KIND:show>> EventCronosReturn::EventProgress"
}
```

- key：`dll|类::方法|去向_原文摘要`，同方法内重复时追加 `#2`、`#3`…（CoT 风格，不含上下文 hash）
- POS：该 `ldstr` 在方法体内的 IL 偏移（8 位补零），TOKEN：MethodDef token。回写按 TOKEN+POS 定位
- SINK：字符串最终被谁消费
  - `类.方法#参数名`：作为参数传入（参数名来自元数据）
  - `fld:字段名`：写入字段；`arr:...`：作为数组元素，后接数组的去向
  - `ret` / `flow` / `local` / `?`：追踪不到
- KIND：
  - `show` 会渲染（AddText / Say / buttonText / content / header / set_text …）
  - `id` 内部标识，**不要翻**（op_Equality、stateText、GetEvent#id、flagName …）
  - `other` 无法判定，按 SINK 人工看

Debug.Log* / Exception 构造参数不提取。

### Assets

```json
{
  "key": "asset|sharedassets0.assets|Point|pointDescription|A_narrow_cracked_road",
  "context": "<<POS:00009078>><<FIELD:pointDescription>><<FILE:sharedassets0.assets>> Point"
}
```

- POS：对象 PathID，FIELD：typetree 字段路径（含数组下标）

## 版本迁移

作者更新后：

1. `extract` 新版本 → `pz_origin/<新版本>/`
2. 从 PZ 导出旧版本译文
3. `migrate <新版本> <导出目录>`：按 key → 同文件同原文 → 全局唯一同原文 依次匹配
4. 看 `_migrate_report.json`（added / removed / original_changed），上传 PZ

key 只依赖 类名、方法名、去向、原文，Mono 没混淆，作者不改名就稳定；
编译器生成的 `<>c__DisplayClassN_0` 之类编号可能漂移，迁移第 2、3 步兜底。
