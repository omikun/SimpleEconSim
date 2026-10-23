"""Stable fingerprints of Python callback code, independent of marshal intern flags.

Defaults, closures and mutable function attributes belong to the state graph.
Source files and runtime versions are checked separately by checkpoint manifests.
"""
import hashlib
import json
import types


def code_signature(code):
    def constant(value):
        if isinstance(value, types.CodeType):
            return describe(value)
        if value is None or value is Ellipsis:
            return {'singleton': str(value)}
        if isinstance(value, bool):
            return {'bool': value}
        if isinstance(value, int):
            return {'int': str(value)}
        if isinstance(value, float):
            return {'float': value.hex()}
        if isinstance(value, complex):
            return {'complex': [value.real.hex(), value.imag.hex()]}
        if isinstance(value, (str, bytes)):
            return {type(value).__name__: value.hex() if isinstance(value, bytes) else value}
        if isinstance(value, (tuple, frozenset)):
            items = [constant(item) for item in value]
            if isinstance(value, frozenset):
                items.sort(key=lambda item: json.dumps(item, sort_keys=True))
            return {type(value).__name__: items}
        raise TypeError('unsupported Python code constant: ' + type(value).__name__)

    def describe(value):
        fields = ('co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount',
                  'co_nlocals', 'co_stacksize', 'co_flags', 'co_names',
                  'co_varnames', 'co_freevars', 'co_cellvars', 'co_name', 'co_qualname')
        result = {name: getattr(value, name) for name in fields}
        result.update(bytecode=value.co_code.hex(),
                      exception_table=value.co_exceptiontable.hex(),
                      constants=[constant(item) for item in value.co_consts])
        return result

    data = json.dumps(describe(code), sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(data.encode()).hexdigest()
