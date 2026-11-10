"""IL 栈模拟：判断一个 ldstr 最终被谁消费（渲染参数 / 字段 / 字符串比较 ...）

结论写进 context 的 sink= 字段，翻译时据此决定是否要翻：
  show  -> 一定会显示：Buttonbar.AddButton#buttonText / EventBase.Say#text / TMP_Text.set_text ...
  id    -> 代码内部标识：String.op_Equality#1 / *Button#$stateText / GetEvent#id / SetBoolFlag#flagName
  other -> 追不到明确去向（数组元素、ret 等），按字段名人工判断
"""
import re
from dncil.cil.enums import StackBehaviour as SB

from reader import field_name, method_sig

POP = {SB.Pop0: 0, SB.Pop1: 1, SB.Popi: 1, SB.Popref: 1,
       SB.Pop1_pop1: 2, SB.Popi_pop1: 2, SB.Popi_popi: 2, SB.Popi_popi8: 2, SB.Popi_popr4: 2, SB.Popi_popr8: 2,
       SB.Popref_pop1: 2, SB.Popref_popi: 2,
       SB.Popi_popi_popi: 3, SB.Popref_popi_popi: 3, SB.Popref_popi_popi8: 3, SB.Popref_popi_popr4: 3,
       SB.Popref_popi_popr8: 3, SB.Popref_popi_popref: 3, SB.Popref_popi_pop1: 3}
PUSH = {SB.Push0: 0, SB.Push1: 1, SB.Pushi: 1, SB.Pushi8: 1, SB.Pushr4: 1, SB.Pushr8: 1, SB.Pushref: 1, SB.Push1_push1: 2}

# 拼接/格式化类调用：字符串只是中间产物，继续往下追
CHAIN = {('String', 'Concat'), ('String', 'Format'), ('String', 'Replace'), ('String', 'Insert'),
         ('String', 'Trim'), ('String', 'ToUpper'), ('String', 'ToLower'), ('StringBuilder', 'Append')}

# 显示类参数名后缀 —— 命中即视为会渲染
SHOW_ARG = re.compile(r'^(newText|text|buttonText|content|header|value|valueText|body|title|'
                      r'label|logText|template|line|description|desc|tooltip|tooltipTitle|tooltipBody|'
                      r'message|msg|dialogue)$', re.I)
SHOW_METHOD = re.compile(r'(set_text|AddText|AddLog|AddReactionText|Say|SpawnNotification|SetText|'
                         r'GetPartDescription)$')

# IDE 类参数名 —— 命中即视为内部标识
ID_ARG = re.compile(r'^(state|eventState|returnState|id|ID|flagName|direction|partName|bodyPart|'
                    r'containerName|eventName|stateText|archetypeName|effectID|EffectID|'
                    r'categoryName|resultStrings|key)$')
ID_METHOD = re.compile(r'(op_Equality|op_Inequality|Contains|StartsWith|EndsWith|GetEvent|GetFlag|SetFlag|'
                       r'AlterIntFlag|PlayHeldEventAtState|IsBodyPartExposed|GetIntFlag|GetBoolFlag|'
                       r'SetIntFlag|SetBoolFlag|Debug\.)')
ID_FIELD = re.compile(r'(ID|Id)$')


def classify(sink):
    if sink.startswith('arr:'):
        return classify(sink[4:])
    if not sink or sink.startswith(('?', 'op:', 'flow', 'ret', 'local', 'array')):
        return 'other'
    if sink.startswith('fld:'):
        return 'id' if ID_FIELD.search(sink) else 'other'
    owner_name, _, rest = sink.rpartition('.')
    name, _, arg = rest.partition('#')
    if ID_METHOD.search(name) or ID_ARG.match(arg):
        return 'id'
    if SHOW_ARG.match(arg) or SHOW_METHOD.search(name):
        return 'show'
    return 'other'


def _tok(ins):
    o = ins.operand
    return int(o.value) if hasattr(o, 'value') else int(o)


def _lidx(ins):
    nm = ins.opcode.name
    tail = nm.rsplit('.', 1)[-1]
    if tail.isdigit():
        return int(tail)
    return getattr(ins.operand, 'index', ins.operand)


def resolve_sink(pe, insns, i, depth=0):
    """从 insns[i]（ldstr）出发，返回 sink 描述字符串"""
    above = 0
    for j in range(i + 1, min(i + 60, len(insns))):
        ins, op, nm = insns[j], insns[j].opcode, insns[j].opcode.name
        if nm in ('call', 'callvirt', 'newobj'):
            name, owner, n, hasthis, rvoid, pn = method_sig(pe, _tok(ins))
            has_this = hasthis and nm != 'newobj'
            pops = n + (1 if has_this else 0)
            push = 0 if (rvoid and nm != 'newobj') else 1
            if above < pops:
                argi = pops - 1 - above
                pi = argi - (1 if has_this else 0)
                label = pn[pi] if 0 <= pi < len(pn) else f'arg{pi}'
                if (owner, name) in CHAIN and push:
                    return resolve_sink(pe, insns, j, depth)
                return f"{owner}.{name}#{label}"
            above += push - pops
            continue
        if nm.startswith('stloc') and above == 0:
            if depth >= 2:
                return 'local'
            idx = _lidx(ins)
            for k in range(j + 1, min(j + 300, len(insns))):
                if insns[k].opcode.name.startswith('ldloc') and _lidx(insns[k]) == idx:
                    return resolve_sink(pe, insns, k, depth + 1)
            return 'local'
        if nm in ('stfld', 'stsfld') and above <= (1 if nm == 'stfld' else 0):
            return 'fld:' + field_name(pe, _tok(ins))
        if nm == 'stelem.ref' and above == 0:
            if depth >= 3:
                return 'array'
            r = resolve_sink(pe, insns, j, depth + 1)
            return r if r.startswith('arr:') else 'arr:' + r
        if nm == 'ret' and above == 0:
            return 'ret'
        if nm in ('br', 'br.s', 'leave', 'leave.s', 'throw'):
            return 'flow'
        if nm == 'dup':
            if above == 0:
                above = 1
                continue
            above += 1
            continue
        pops, push = POP.get(op.stack_pop, 0), PUSH.get(op.stack_push, 0)
        if above < pops:
            return f"op:{nm}"
        above += push - pops
    return '?'
