# -*- coding: utf-8 -*-

"""
metiny_bosy_panel.py

Odblokowanie oryginalnego panelu Metiny / Wladcy.
Nie tworzy nowego panelu od zera. Uzywa oryginalnego RespawnDialog
znajdujacego sie w kliencie i dynamicznie przywraca elementy
wylaczone w czystej paczce przez ENABLE_RESP_SYSTEM / F8.

F8 = otworz/zamknij panel.
"""

import sys

import app
import game
import constInfo


_INSTALLED = False
_INTERFACE = None
_RESP_CLASS = None
_ORIGINAL_ON_KEY_DOWN = None
_ORIGINAL_ON_UPDATE = None


def _log(msg):
    try:
        import dbg
        dbg.TraceError("[METINY_BOSY] %s" % msg)
    except:
        pass


def _find_respawn_class():
    # Najpierw normalny modul, jesli jest dostepny pod oryginalna nazwa.
    try:
        import uiRespawn
        cls = getattr(uiRespawn, "RespawnDialog", None)
        if cls:
            return cls
    except:
        pass

    # W paczce klasa jest w module zhashowanym. Szukamy jej
    # wsrod juz zaladowanych modulow.
    for module in list(sys.modules.values()):
        try:
            if module is None:
                continue
            cls = getattr(module, "RespawnDialog", None)
            if cls is not None:
                return cls
        except:
            pass

    return None


def _get_interface():
    try:
        interface = constInfo.GetInterfaceInstance()
        if interface:
            return interface
    except:
        pass

    # awaryjnie sprawdzamy popularne miejsca
    try:
        import interfaceModule
        obj = getattr(interfaceModule, "interface", None)
        if obj:
            return obj
    except:
        pass

    return None


def _ensure_window():
    global _INTERFACE
    global _RESP_CLASS

    interface = _get_interface()
    if interface is None:
        return None

    _INTERFACE = interface

    # Jesli klient juz posiada wndResp, tylko go zwracamy.
    wnd = getattr(interface, "wndResp", None)
    if wnd is not None:
        return wnd

    if _RESP_CLASS is None:
        _RESP_CLASS = _find_respawn_class()

    if _RESP_CLASS is None:
        _log("Nie znaleziono RespawnDialog")
        return None

    try:
        wnd = _RESP_CLASS()
        wnd.Hide()
        interface.wndResp = wnd

        _log("RespawnDialog utworzony")
        return wnd
    except Exception as exc:
        _log("Blad tworzenia RespawnDialog: %s" % exc)
        return None


def _open_respawn():
    wnd = _ensure_window()

    if wnd is None:
        _log("Nie mozna otworzyc panelu: wndResp=None")
        return False

    try:
        if wnd.IsShow():
            wnd.Hide()
        else:
            wnd.Show()

        _log("Panel Metiny/Bossy: %s" %
             ("OPEN" if wnd.IsShow() else "CLOSE"))

        return True
    except Exception as exc:
        _log("Blad OpenRespWindow: %s" % exc)
        return False


def _binary_set_mob_resp(self, mobVnum, data):
    wnd = _ensure_window()
    if wnd:
        try:
            wnd.SetMobRespData(mobVnum, data)
        except Exception as exc:
            _log("BINARY_SetMobRespData: %s" % exc)


def _binary_set_mob_drop(self, mobVnum, data):
    wnd = _ensure_window()
    if wnd:
        try:
            wnd.SetMobDropData(mobVnum, data)
        except Exception as exc:
            _log("BINARY_SetMobDropData: %s" % exc)


def _binary_set_map(self, data, currentBossCount, maxBossCount,
                    currentMetinCount, maxMetinCount):
    wnd = _ensure_window()
    if wnd:
        try:
            wnd.SetMapData(
                data,
                currentBossCount,
                maxBossCount,
                currentMetinCount,
                maxMetinCount
            )
        except Exception as exc:
            _log("BINARY_SetMapData: %s" % exc)


def _binary_refresh_resp(self, id, mobVnum, time, cord):
    wnd = _ensure_window()
    if wnd:
        try:
            wnd.RefreshRest(id, mobVnum, time, cord)
        except Exception as exc:
            _log("BINARY_RefreshResp: %s" % exc)


def _patch_binary_callbacks():
    """
    Oryginalnie te metody sa definiowane tylko gdy:
        app.ENABLE_RESP_SYSTEM == True

    W czystej paczce flaga jest wylaczona, wiec przywracamy
    cztery callbacki bez przebudowy GameWindow.
    """
    gw = game.GameWindow

    if not hasattr(gw, "BINARY_SetMobRespData"):
        gw.BINARY_SetMobRespData = _binary_set_mob_resp

    if not hasattr(gw, "BINARY_SetMobDropData"):
        gw.BINARY_SetMobDropData = _binary_set_mob_drop

    if not hasattr(gw, "BINARY_SetMapData"):
        gw.BINARY_SetMapData = _binary_set_map

    if not hasattr(gw, "BINARY_RefreshResp"):
        gw.BINARY_RefreshResp = _binary_refresh_resp

    _log("callbacki BINARY odblokowane")


def _on_key_down(self, key):
    # F8
    try:
        if key == app.DIK_F8:
            if _open_respawn():
                return True
    except:
        pass

    if _ORIGINAL_ON_KEY_DOWN:
        try:
            return _ORIGINAL_ON_KEY_DOWN(self, key)
        except:
            pass

    return False


def _on_update(self):
    # Czekamy az Interface zostanie utworzony.
    try:
        _ensure_window()
    except:
        pass

    if _ORIGINAL_ON_UPDATE:
        try:
            return _ORIGINAL_ON_UPDATE(self)
        except:
            pass

    return True


def _install():
    global _INSTALLED
    global _ORIGINAL_ON_KEY_DOWN
    global _ORIGINAL_ON_UPDATE

    if _INSTALLED:
        return

    try:
        # Nie zmieniamy plikow klienta ani nie wymagamy
        # przeladowania root. Przywracamy tylko funkcjonalnosc
        # w runtime.
        try:
            app.ENABLE_RESP_SYSTEM = True
        except:
            pass

        _patch_binary_callbacks()

        _ORIGINAL_ON_KEY_DOWN = game.GameWindow.OnKeyDown
        game.GameWindow.OnKeyDown = _on_key_down

        _ORIGINAL_ON_UPDATE = game.GameWindow.OnUpdate
        game.GameWindow.OnUpdate = _on_update

        _INSTALLED = True

        _log("MODUL ZAINSTALOWANY - F8 aktywne")

    except Exception as exc:
        _log("Blad instalacji: %s" % exc)


_install()
