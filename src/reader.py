"""dnfile / dncil 读写辅助：字符串堆、成员名、方法签名、类型归属"""
import dnfile
from dncil.cil.body import CilMethodBody
from dncil.cil.body.reader import CilMethodBodyReaderBase
from dncil.cil.error import MethodBodyFormatError

TYPE_OWNER = {}   # MethodDef rid -> 类型名（含嵌套类型外层路径）
FIELD_OWNER = {}  # Field rid  -> 类型名


class Reader(CilMethodBodyReaderBase):
    def __init__(self, pe, rva):
        self.pe, self.off = pe, pe.get_offset_from_rva(rva)

    def read(self, n):
        d = self.pe.get_data(self.pe.get_rva_from_offset(self.off), n)
        self.off += n
        return d

    def tell(self):
        return self.off

    def seek(self, o):
        self.off = o
        return o


def init(pe):
    mt = pe.net.mdtables
    parent = {n.NestedClass.row_index: n.EnclosingClass.row_index for n in mt.NestedClass}
    TYPE_OWNER.clear()
    FIELD_OWNER.clear()
    for rid, td in enumerate(mt.TypeDef, 1):
        names, r = [str(td.TypeName)], rid
        while r in parent and len(names) < 8:  # 嵌套类型 -> Outer/Inner
            r = parent[r]
            names.insert(0, str(mt.TypeDef[r - 1].TypeName))
        name = '/'.join(names)
        ns = str(mt.TypeDef[r - 1].TypeNamespace or '')
        full = f"{ns}.{name}" if ns else name
        for m in td.MethodList:
            TYPE_OWNER[m.row_index] = full
        for f in td.FieldList:
            FIELD_OWNER[f.row_index] = full


def user_string(pe, tok):
    r = pe.net.user_strings.get(tok & 0xFFFFFF)
    return (r.value if hasattr(r, 'value') else r) or ''


def _row(pe, tok):
    t, rid = tok >> 24, tok & 0xFFFFFF
    mt = pe.net.mdtables
    tbl = {0x04: 'Field', 0x06: 'MethodDef', 0x0A: 'MemberRef', 0x2B: 'MethodSpec', 0x1B: 'TypeSpec'}.get(t)
    if not tbl:
        return None, None, 0
    return getattr(mt, tbl)[rid - 1], tbl, rid


def member_name(pe, tok):
    """'Owner::Name' 形式；失败返回 ''"""
    row, kind, rid = _row(pe, tok)
    if row is None:
        return ''
    try:
        if kind in ('MethodDef', 'Field'):
            return (TYPE_OWNER if kind == 'MethodDef' else FIELD_OWNER).get(rid, '') + '::' + str(row.Name)
        if kind == 'MemberRef':
            c = row.Class
            owner = str(getattr(c.row, 'TypeName', '')) or str(c.table.name)
            return owner + '::' + str(row.Name)
    except Exception:
        pass
    return ''


def method_sig(pe, tok):
    """-> (name, owner, nparams, hasthis, ret_void, paramnames)
    MethodSpec 不支持时退化为通用调用（按调用方自行处理）"""
    row, kind, rid = _row(pe, tok)
    if kind == 'MethodSpec':
        m = row.Method
        return method_sig(pe, m.row_index | (0x06000000 if m.table.name == 'MethodDef' else 0x0A000000))
    if row is None:
        return '?', '?', 0, False, True, []
    try:
        blob = bytes(row.Signature.value if hasattr(row.Signature, 'value') else row.Signature)
        cc, k = blob[0], 1
        if cc & 0x10:
            k += 1
        n, ret = blob[k], blob[k + 1]
        hasthis = bool(cc & 0x20)
        if kind == 'MethodDef':
            owner = TYPE_OWNER.get(rid, '?')
            pn = [str(p.row.Name) for p in row.ParamList if p.row.Sequence > 0]
        else:
            owner = str(getattr(row.Class.row, 'TypeName', '?'))
            pn = []
        return str(row.Name), owner, n, hasthis, ret == 0x01, pn
    except Exception:
        return '?', '?', 0, False, True, []


def field_name(pe, tok):
    row, kind, _ = _row(pe, tok)
    if kind == 'Field':
        return str(row.Name)
    if kind == 'MemberRef':
        return str(row.Name)
    return '?'


def read_method(pe, rid):
    """MethodDef rid -> (CilMethodBody, il0) ；il0 是方法体指令区起点"""
    try:
        md = pe.net.mdtables.MethodDef[rid - 1]
        if not md.Rva:
            return None, None
        b = CilMethodBody(Reader(pe, md.Rva))
        return b, b.offset + b.header_size
    except MethodBodyFormatError:
        return None, None


def iter_ldstr(pe, insns):
    """-> [(指令下标, IL偏移, 字符串)]"""
    return [(i, ins.offset, user_string(pe, ins.operand.value if hasattr(ins.operand, 'value') else int(ins.operand)))
            for i, ins in enumerate(insns) if ins.opcode.name == 'ldstr']


def load_pe(dll_path):
    pe = dnfile.dnPE(dll_path)
    init(pe)
    return pe
