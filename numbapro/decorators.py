from numbapro import translate
from numba import double
import llvm.core as _lc

default_module = _lc.Module.new('default')

def export(ret_type=double, arg_types=[double], backend='bytecode', **kws):
    def _export(func):
        # XXX: need to implement ast backend.
        t = translate.Translate(func, ret_type=ret_type,
                                arg_types=arg_types,
                                module=default_module, **kws)
        t.translate()
    return _export
