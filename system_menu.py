"""
system_menu.py — Native OS System Menu Bar Integration for REGNUM.

Provides native macOS menu items in the top system menu bar (e.g. Game -> Restart Game, Pause, Reset Camera).
"""

import sys
import ctypes
import ctypes.util
import pygame

RESTART_EVENT_TYPE = pygame.USEREVENT + 2
_CALLBACK_REFS = []


def _post_restart_event():
    """Post restart event into Pygame event queue."""
    try:
        pygame.event.post(pygame.event.Event(RESTART_EVENT_TYPE))
    except Exception as e:
        print(f"Error posting restart event: {e}")


def setup_system_menu():
    """Setup native macOS system menu items for Restart Game."""
    if sys.platform != 'darwin':
        return False

    try:
        objc_path = ctypes.util.find_library('objc')
        appkit_path = ctypes.util.find_library('AppKit')
        if not objc_path or not appkit_path:
            return False

        objc = ctypes.cdll.LoadLibrary(objc_path)
        ctypes.cdll.LoadLibrary(appkit_path)

        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]

        def send(target, sel_name, *args, restype=ctypes.c_void_p, argtypes=None):
            if not target:
                return None
            if argtypes is None:
                argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_void_p] * len(args)
            sel = objc.sel_registerName(sel_name.encode('utf-8'))
            proto = ctypes.CFUNCTYPE(restype, *argtypes)
            fn = ctypes.cast(objc.objc_msgSend, proto)
            return fn(target, sel, *args)

        def ns_str(s):
            NSString = objc.objc_getClass(b'NSString')
            return send(NSString, 'stringWithUTF8String:', ctypes.c_char_p(s.encode('utf-8')),
                        argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p])

        NSAppClass = objc.objc_getClass(b'NSApplication')
        app = send(NSAppClass, 'sharedApplication')
        if not app:
            return False

        NSMenuClass = objc.objc_getClass(b'NSMenu')
        NSMenuItemClass = objc.objc_getClass(b'NSMenuItem')
        NSObjectClass = objc.objc_getClass(b'NSObject')

        main_menu = send(app, 'mainMenu')
        if not main_menu:
            main_menu = send(send(NSMenuClass, 'alloc'), 'init')
            send(app, 'setMainMenu:', main_menu, argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p])

        # Define Objective-C action callback
        def on_restart_action(self_ptr, _cmd, sender):
            _post_restart_event()

        IMP_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        imp_restart = IMP_TYPE(on_restart_action)
        _CALLBACK_REFS.append(imp_restart)

        # Register RegnumMenuHandler class if not registered yet
        objc.objc_allocateClassPair.restype = ctypes.c_void_p
        objc.objc_allocateClassPair.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
        objc.class_addMethod.restype = ctypes.c_bool
        objc.class_addMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        objc.objc_registerClassPair.restype = None
        objc.objc_registerClassPair.argtypes = [ctypes.c_void_p]

        cls = objc.objc_getClass(b'RegnumSystemMenuHandler')
        if not cls:
            cls = objc.objc_allocateClassPair(NSObjectClass, b'RegnumSystemMenuHandler', 0)
            sel_restart = objc.sel_registerName(b'restartGameAction:')
            objc.class_addMethod(cls, sel_restart, ctypes.cast(imp_restart, ctypes.c_void_p), b'v@:@')
            objc.objc_registerClassPair(cls)

        handler_inst = send(send(cls, 'alloc'), 'init')
        _CALLBACK_REFS.append(handler_inst)

        # Create Top-Level "Game" menu
        game_menu_item = send(send(NSMenuItemClass, 'alloc'), 'init')
        game_sub_menu = send(send(NSMenuClass, 'alloc'), 'initWithTitle:', ns_str("Game"),
                             argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p])

        # 1. "Restart Game" (Cmd+R)
        restart_item = send(send(NSMenuItemClass, 'alloc'), 'initWithTitle:action:keyEquivalent:',
                            ns_str("Restart Game"),
                            objc.sel_registerName(b'restartGameAction:'),
                            ns_str("r"),
                            argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p])

        send(restart_item, 'setTarget:', handler_inst, argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p])
        send(game_sub_menu, 'addItem:', restart_item, argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p])

        send(game_menu_item, 'setSubmenu:', game_sub_menu, argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p])
        send(main_menu, 'addItem:', game_menu_item, argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p])

        return True
    except Exception as e:
        print(f"Notice: Native system menu setup skipped: {e}")
        return False
