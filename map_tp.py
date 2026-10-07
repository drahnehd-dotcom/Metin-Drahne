# -*- coding: utf-8 -*-

"""Shift + LPM na mapie M teleportuje do kordow pod kursorem."""

import app
import background
import chr
import miniMap
import os
import player
import ui
import wndMgr


_INSTALLED = False
_ORIGINAL_ATLAS_DOWN = None
_ORIGINAL_RENDERER_DOWN = None
_ORIGINAL_ATLAS_SHOW = None
_COLLISION_CACHE = {}
_COLLISION_DIR = r"D:\KowalMT2\data\me\Maps"


def _log(text):
    try:
        import dbg
        dbg.TraceError("[MAP_TP] %s" % text)
    except:
        pass


def _shift_pressed():
    try:
        return (
            app.IsPressed(app.DIK_LSHIFT) or
            app.IsPressed(app.DIK_RSHIFT)
        )
    except:
        return False


def _collision_allowed(map_x, map_y):
    """Zwraca True dla pola 1, False dla pola 0, None gdy brak maski."""
    try:
        map_name = str(background.GetCurrentMapName())
        if not map_name:
            _log("Brak nazwy aktualnej mapy")
            return None

        rows = _COLLISION_CACHE.get(map_name)
        if rows is None:
            path = os.path.join(_COLLISION_DIR, map_name + ".dat")
            collision_file = open(path, "r")
            try:
                lines = collision_file.read().splitlines()
            finally:
                collision_file.close()

            if not lines:
                _log("Pusta maska kolizji: %s" % path)
                return None

            size = lines[0].split()
            if len(size) < 2:
                _log("Niepoprawny naglowek maski: %s" % path)
                return None

            width = int(size[0])
            height = int(size[1])
            rows = lines[1:1 + height]
            _COLLISION_CACHE[map_name] = (width, height, rows)

        width, height, rows = rows
        if map_x < 0 or map_y < 0 or map_x >= width or map_y >= height:
            _log("Punkt poza maska: mapa=%s x=%d y=%d" %
                 (map_name, map_x, map_y))
            return False

        if map_y >= len(rows) or map_x >= len(rows[map_y]):
            _log("Brak komorki maski: mapa=%s x=%d y=%d" %
                 (map_name, map_x, map_y))
            return False

        allowed = rows[map_y][map_x] == "1"
        if not allowed:
            _log("TP zablokowane przez kolizje: mapa=%s x=%d y=%d" %
                 (map_name, map_x, map_y))
        return allowed
    except Exception as exc:
        _log("BLAD odczytu maski kolizji: %s" % exc)
        # Przy wlaczonej kontroli kolizji brak poprawnej maski blokuje TP.
        return False


def _teleport_to_atlas_point():
    if not _shift_pressed():
        return False

    try:
        mouse_x, mouse_y = wndMgr.GetMousePosition()
        result = miniMap.GetAtlasInfo(mouse_x, mouse_y)
        if not result or len(result) < 4:
            _log("GetAtlasInfo nie zwrocil kordynatow")
            return False

        _found, _name, map_x, map_y = result[:4]
        map_x = int(map_x)
        map_y = int(map_y)

        collision_allowed = _collision_allowed(map_x, map_y)
        if collision_allowed is False:
            return True

        current_x, current_y, _current_z = player.GetMainCharacterPosition()
        _map_name, base_x, base_y = background.GlobalPositionToMapInfo(
            int(current_x), int(current_y)
        )
        world_x = int(base_x) + map_x * 100
        world_y = int(base_y) + map_y * 100

        _pos_x, _pos_y, pos_z = player.GetMainCharacterPosition()
        main_vid = int(player.GetMainCharacterIndex())
        if main_vid <= 0:
            _log("Brak MainCharacterIndex")
            return False

        chr.SelectInstance(main_vid)
        chr.SetPixelPosition(world_x, world_y, int(pos_z))

        try:
            player.ClearTarget()
        except:
            pass
        try:
            player.SetAttackKeyState(False)
        except:
            pass

        _log("TP Atlas -> mapa=(%d,%d), global=(%d,%d)" %
             (map_x, map_y, world_x, world_y))
        return True
    except Exception as exc:
        _log("BLAD TP Atlas: %s" % exc)
        return False


def _farmbot_atlas_click():
    """Pozwala FarmBotowi przechwycic klikniecie w trybie edycji punktu."""
    try:
        import FarmBot
        return bool(FarmBot.HandleAtlasClick())
    except Exception as exc:
        _log("BLAD edycji punktu FarmBot: %s" % exc)
        return False


def _atlas_down(self):
    if _farmbot_atlas_click():
        return True
    if _teleport_to_atlas_point():
        return True
    if _ORIGINAL_ATLAS_DOWN:
        return _ORIGINAL_ATLAS_DOWN(self)
    return False


def _renderer_down(self):
    _log("Klik AtlasRenderer")
    if _teleport_to_atlas_point():
        return True
    if _ORIGINAL_RENDERER_DOWN:
        return _ORIGINAL_RENDERER_DOWN(self)
    return False


def _atlas_show(self):
    result = None
    if _ORIGINAL_ATLAS_SHOW:
        result = _ORIGINAL_ATLAS_SHOW(self)

    # W niektorych wersjach uiMiniMap renderer nie dostaje rozmiaru.
    # Mapa jest wtedy widoczna, ale nie odbiera klikniec myszy.
    try:
        renderer = getattr(self, "AtlasMainWindow", None)
        board = getattr(self, "board", None)
        if renderer is not None and board is not None:
            try:
                renderer.RemoveFlag("not_pick")
            except Exception:
                pass

            # Callback przypiety do instancji UI jest wywolywany bez self.
            # Zachowujemy ewentualny stary callback jako funkcje bezargumentowa.
            old_down = getattr(renderer, "OnMouseLeftButtonDown", None)

            def _instance_down():
                if _farmbot_atlas_click():
                    return True
                if _teleport_to_atlas_point():
                    return True
                if old_down:
                    return old_down()
                return False

            renderer.OnMouseLeftButtonDown = ui.__mem_func__(_instance_down)
            renderer.SetSize(
                max(1, board.GetWidth() - 14),
                max(1, board.GetHeight() - 37)
            )
            renderer.Show()
    except Exception as exc:
        _log("BLAD rozmiaru AtlasRenderer: %s" % exc)

    return result


def _install():
    global _INSTALLED
    global _ORIGINAL_ATLAS_DOWN
    global _ORIGINAL_RENDERER_DOWN
    global _ORIGINAL_ATLAS_SHOW

    if _INSTALLED:
        return

    try:
        import uiMiniMap

        atlas = uiMiniMap.AtlasWindow
        if hasattr(atlas, "Show"):
            _ORIGINAL_ATLAS_SHOW = atlas.Show
            atlas.Show = _atlas_show

        if hasattr(atlas, "OnMouseLeftButtonDown"):
            _ORIGINAL_ATLAS_DOWN = atlas.OnMouseLeftButtonDown
            atlas.OnMouseLeftButtonDown = _atlas_down

        renderer = getattr(atlas, "AtlasRenderer", None)
        if renderer is not None:
            # Aktywna wersja uiMiniMap oznacza renderer jako not_pick,
            # dlatego widoczna mapa nie odbiera klikniec.
            if hasattr(renderer, "OnMouseLeftButtonDown"):
                _ORIGINAL_RENDERER_DOWN = renderer.OnMouseLeftButtonDown

        _INSTALLED = True
        _log("MODUL ZAINSTALOWANY - Shift+LPM na mapie M aktywne")
    except Exception as exc:
        _log("BLAD INSTALACJI: %s" % exc)


_install()
