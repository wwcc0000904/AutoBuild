"""macOS NSVisualEffectView 毛玻璃效果。"""
import ctypes
import logging

from config.logging_setup import get_logger

_logger: logging.Logger = get_logger()
import ctypes.util

_objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))

_objc.sel_registerName.restype = ctypes.c_void_p
_objc.sel_registerName.argtypes = [ctypes.c_char_p]
_objc.objc_getClass.restype = ctypes.c_void_p
_objc.objc_getClass.argtypes = [ctypes.c_char_p]


def _msg(obj, sel_name, *cargs):
    """通用 objc_msgSend。"""
    sel = _objc.sel_registerName(sel_name.encode())
    nargs = [ctypes.c_void_p(a) if isinstance(a, int) else a for a in cargs]
    _objc.objc_msgSend.restype = ctypes.c_void_p
    _objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p] * 1  # 先设基础
    # 动态构造
    atypes = [ctypes.c_void_p, ctypes.c_void_p]
    for a in nargs:
        atypes.append(type(a))
    _objc.objc_msgSend.argtypes = atypes
    return _objc.objc_msgSend(obj, sel, *nargs)


def add_frosted_effect(qwindow, material=9):
    """给窗口添加毛玻璃。material=9 是 sidebar（白色毛玻璃）。"""
    try:
        ns_view = ctypes.c_void_p(int(qwindow.winId()))
        ns_window = _msg(ns_view, "window")
        if not ns_window:
            return False

        content_view = _msg(ns_window, "contentView")

        # NSVisualEffectView.alloc().init()
        NSVEV = _objc.objc_getClass(b"NSVisualEffectView")
        ev = _msg(NSVEV, "alloc")
        ev = _msg(ev, "init")

        _msg(ev, "setMaterial:", material)
        _msg(ev, "setBlendingMode:", 0)   # behindWindow
        _msg(ev, "setState:", 1)           # active

        # 用 autoresizingMask 自适应，不需要手动设 frame
        _msg(ev, "setAutoresizingMask:", 18)  # width|height sizable

        # addSubview:positioned:relativeTo:  (-1 = NSWindowBelow)
        sel_add = _objc.sel_registerName(b"addSubview:positioned:relativeTo:")
        _objc.objc_msgSend.restype = ctypes.c_void_p
        _objc.objc_msgSend.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        ]
        _objc.objc_msgSend(content_view, sel_add, ev,
                          ctypes.c_void_p(-1), ctypes.c_void_p(0))

        _logger.debug("mac_blur: 成功添加毛玻璃效果")
        return True
    except Exception as e:
        _logger.exception("mac_blur: 添加毛玻璃效果失败: %s", e)
        return False
