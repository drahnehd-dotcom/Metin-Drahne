# -*- coding: utf-8 -*-
"""FarmBot - prosty tryb TRASA / PUNKTY TP.

TRASA:
- NAGRAJ TRASE zapisuje aktualna pozycje gracza,
- bot porusza sie po zapisanych punktach,
- podczas ruchu szuka wlaczonych targetow,
- najpierw podchodzi do celu, dopiero potem atakuje,
- po zabiciu wraca do trasy.

PUNKTY TP:
- DODAJ PUNKT zapisuje aktualna pozycje,
- bot teleportuje sie do punktu,
- po TP sprawdza targety,
- do celu podchodzi i atakuje tylko w zasiegu,
- po ostatnim punkcie moze zmienic CH i zaczac od poczatku.
"""

import json
import os
import app
import background
import chr
import player
import ui

try:
    import eXLib
except:
    eXLib = None

try:
    import nonplayer
except:
    nonplayer = None

try:
    import net
except:
    net = None

_CFG_PATH = r"D:\KowalMT2\data\me\farmbot.json"

_window = None
_TARGET_PAGE = 0
_POINT_PAGE = 0
_ROWS_PER_PAGE = 7
ATTACK_DISTANCE = 300.0
MOVE_RETRY = 0.35

_DEFAULT_CFG = {
    "mode": "tp",
    "targets": [],
    "tp_points": [],
    "route": [],
    "change_channel": False,
    "channels": [1, 2, 3, 4],
    "channel_index": 0,
    "tp_wait": 1.0,
    "route_point_wait": 0.4
}

_cfg = {}
_cfg.update(_DEFAULT_CFG)


def _log(text):
    try:
        import dbg
        dbg.TraceError("[FARMBOT] %s" % str(text))
    except:
        pass


def _load():
    global _cfg
    try:
        f = open(_CFG_PATH, "r")
        data = json.load(f)
        f.close()
        if isinstance(data, dict):
            for key in _DEFAULT_CFG:
                if key in data:
                    _cfg[key] = data[key]
    except:
        pass

    for key in ("targets", "tp_points", "route"):
        if not isinstance(_cfg.get(key), list):
            _cfg[key] = []

    if not isinstance(_cfg.get("channels"), list):
        _cfg["channels"] = [1, 2, 3, 4]

    for target in _cfg["targets"]:
        if not isinstance(target, dict):
            continue
        try:
            target["vnum"] = int(target.get("vnum", 0))
        except:
            target["vnum"] = 0
        target["name"] = str(target.get("name", ""))
        target["use"] = bool(target.get("use", True))


def _save():
    try:
        folder = os.path.dirname(_CFG_PATH)
        if not os.path.exists(folder):
            os.makedirs(folder)
        f = open(_CFG_PATH, "w")
        json.dump(_cfg, f)
        f.close()
    except Exception as exc:
        _log("BLAD ZAPISU: %s" % exc)


def _position():
    try:
        x, y, z = player.GetMainCharacterPosition()
        return int(x), int(y), int(z)
    except:
        return None


def _target_vnum(vid):
    try:
        if nonplayer:
            value = int(nonplayer.GetVnumByVID(int(vid)))
            if value > 0:
                return value
    except:
        pass
    try:
        if eXLib:
            value = int(eXLib.GetInstanceRace(int(vid)))
            if value > 0:
                return value
    except:
        pass
    try:
        return int(chr.GetVirtualNumber(int(vid)))
    except:
        return 0


def _target_name(vid):
    try:
        return str(chr.GetNameByVID(int(vid)))
    except:
        return ""


def _wanted_vnums():
    result = []
    for target in _cfg.get("targets", []):
        try:
            if target.get("use", True):
                vnum = int(target.get("vnum", 0))
                if vnum > 0:
                    result.append(vnum)
        except:
            pass
    return result


def _is_dead(vid):
    try:
        if eXLib:
            return bool(eXLib.IsDead(int(vid)))
    except:
        pass
    try:
        return bool(chr.IsDead(int(vid)))
    except:
        return False


def _target_position(vid):
    try:
        x, y, z = chr.GetPixelPosition(int(vid))
        return int(x), int(y), int(z)
    except:
        return None


def _distance_to_vid(vid):
    try:
        return float(player.GetCharacterDistance(int(vid)))
    except:
        pass
    try:
        pos = _position()
        target = _target_position(vid)
        if not pos or not target:
            return 999999.0
        dx = float(pos[0]) - float(target[0])
        dy = float(pos[1]) - float(target[1])
        return (dx * dx + dy * dy) ** 0.5
    except:
        return 999999.0


# Skanowanie VIDs: nie polegamy na eXLib.InstancesList, bo w tym kliencie
# lista nie zawiera wszystkich widocznych potworow/metinow. Skanujemy natywne
# instancje chr.HasInstance() partiami i budujemy cache kandydatow.
_SCAN_MIN = 1
_SCAN_MAX = 500000
_SCAN_CHUNK = 10000
_SCAN_INTERVAL = 0.10
_scan_vid = _SCAN_MIN
_last_scan = -999.0
_known_vids = set()
_target_snapshot = []
_VNUM_CACHE = {}


def _is_instance(vid):
    try:
        return bool(chr.HasInstance(int(vid)))
    except:
        return False


def _is_enemy(vid):
    try:
        return bool(chr.IsEnemy(int(vid)))
    except:
        return False


def _is_attackable(vid):
    try:
        return bool(player.CanAttackInstance(int(vid)))
    except:
        return _is_enemy(vid)


def _instance_kind_allowed(vid):
    try:
        kind = int(chr.GetInstanceType(int(vid)))
    except:
        return True

    allowed = []
    for obj, names in ((chr, (
        'INSTANCE_TYPE_MONSTER', 'INSTANCE_TYPE_STONE',
        'INSTANCE_TYPE_NPC'
    )), (eXLib, ('MONSTER_TYPE', 'METIN_TYPE'))):
        if obj is None:
            continue
        for name in names:
            try:
                value = int(getattr(obj, name))
                if value not in allowed:
                    allowed.append(value)
            except:
                pass

    # Jezeli klient nie udostepnia stalych typow, nie odrzucamy instancji
    # na podstawie typu. VNUM + CanAttackInstance sa wtedy filtrem glownym.
    if not allowed:
        return True
    return kind in allowed


def _target_vnum(vid):
    iv = int(vid or 0)
    if iv <= 0:
        return 0

    cached = _VNUM_CACHE.get(iv, 0)
    if cached > 0:
        return cached

    value = 0
    try:
        getter = getattr(nonplayer, 'GetVnumByVID', None)
        if getter:
            value = int(getter(iv) or 0)
    except:
        value = 0

    if value <= 0:
        try:
            value = int(chr.GetVirtualNumber(iv) or 0)
        except:
            value = 0

    if value <= 0:
        try:
            value = int(eXLib.GetInstanceRace(iv) or 0)
        except:
            value = 0

    if value > 0:
        _VNUM_CACHE[iv] = value
    return value


def _target_name(vid):
    try:
        return str(chr.GetNameByVID(int(vid)))
    except:
        return ""


def _is_dead(vid):
    try:
        if eXLib:
            return bool(eXLib.IsDead(int(vid)))
    except:
        pass
    try:
        return bool(chr.IsDead(int(vid)))
    except:
        return False


def _target_position(vid):
    try:
        result = chr.GetPixelPosition(int(vid))
        if result is not None and len(result) >= 3:
            return int(result[0]), int(result[1]), int(result[2])
    except:
        pass
    return None


def _distance_to_vid(vid):
    try:
        value = float(player.GetCharacterDistance(int(vid)))
        if value >= 0.0:
            return value
    except:
        pass
    try:
        pos = _position()
        target = _target_position(vid)
        if pos and target:
            dx = float(pos[0]) - float(target[0])
            dy = float(pos[1]) - float(target[1])
            return (dx * dx + dy * dy) ** 0.5
    except:
        pass
    return 999999999.0


def _refresh_target_snapshot(now):
    global _target_snapshot
    wanted = set(_wanted_vnums())
    if not wanted:
        _target_snapshot = []
        return

    try:
        main_vid = int(player.GetMainCharacterIndex())
    except:
        main_vid = 0

    candidates = []
    for vid in tuple(_known_vids):
        try:
            iv = int(vid)
            if iv <= 0 or iv == main_vid:
                continue
            if not _is_instance(iv):
                _known_vids.discard(iv)
                continue
            if _is_dead(iv):
                continue
            if not _instance_kind_allowed(iv):
                continue
            vnum = _target_vnum(iv)
            if vnum not in wanted:
                continue
            # Dla celu automatycznego wymagamy rzeczywistej mozliwosci ataku.
            # Nie wymagamy IsEnemy(), bo w niektorych buildach kamienie/metiny
            # nie przechodza przez ten test.
            if not _is_attackable(iv):
                continue
            distance = _distance_to_vid(iv)
            if distance < 0:
                continue
            candidates.append((float(distance), iv, vnum))
        except:
            continue

    candidates.sort(key=lambda row: (row[0], row[1]))
    _target_snapshot = candidates


def _scan_vids(now):
    global _scan_vid, _last_scan
    if now - _last_scan < _SCAN_INTERVAL:
        return
    _last_scan = now

    # Najpierw utrzymujemy cache znanych instancji.
    for vid in tuple(_known_vids):
        if not _is_instance(vid):
            _known_vids.discard(vid)

    end = min(_scan_vid + _SCAN_CHUNK, _SCAN_MAX + 1)
    for vid in range(_scan_vid, end):
        try:
            if chr.HasInstance(vid):
                _known_vids.add(vid)
        except:
            pass

    if end > _SCAN_MAX:
        _scan_vid = _SCAN_MIN
    else:
        _scan_vid = end

    _refresh_target_snapshot(now)


def _find_target():
    wanted = _wanted_vnums()
    if not wanted:
        return 0

    # Aktualny cel jest tylko szybkim fallbackiem. Nie jest wymagany.
    try:
        current = int(player.GetTargetVID())
        if current > 0 and _target_vnum(current) in wanted and not _is_dead(current):
            if _is_attackable(current):
                return current
    except:
        pass

    now = app.GetTime()
    _scan_vids(now)

    for distance, vid, vnum in _target_snapshot:
        try:
            if vnum in wanted and _is_instance(vid) and not _is_dead(vid):
                if _is_attackable(vid):
                    return int(vid)
        except:
            continue
    return 0

def _stop_attack():
    try:
        player.SetAttackKeyState(False)
    except:
        pass


def _attack(vid):
    try:
        player.SetTarget(int(vid))
    except:
        pass
    try:
        if eXLib:
            eXLib.NewAttack()
            return True
    except:
        pass
    try:
        player.SetAttackKeyState(True)
        return True
    except:
        return False


def _move_to_target(vid):
    target = _target_position(vid)
    if not target:
        return False
    pos = _position()
    if not pos:
        return False
    try:
        main_vid = int(player.GetMainCharacterIndex())
        if main_vid <= 0:
            return False
        chr.SelectInstance(main_vid)
        # Natywny ruch klienta. Nie wlaczamy ataku podczas podejscia.
        chr.MoveToDestPosition(main_vid, int(target[0]), int(target[1]))
        return True
    except Exception as exc:
        _log("RUCH DO CELU BLAD: %s" % exc)
        return False



def _move_route_point(point):
    try:
        tx, ty, tz = int(point[0]), int(point[1]), int(point[2]) if len(point) > 2 else 0
        main_vid = int(player.GetMainCharacterIndex())
        if main_vid <= 0:
            return False
        chr.SelectInstance(main_vid)
        chr.MoveToDestPosition(main_vid, tx, ty)
        return True
    except Exception as exc:
        _log("BLAD RUCHU TRASY: %s" % exc)
        return False

def _change_channel():
    if not _cfg.get("change_channel") or not net:
        return
    channels = []
    for value in _cfg.get("channels", [1, 2, 3, 4]):
        try:
            value = int(value)
            if 1 <= value <= 4:
                channels.append(value)
        except:
            pass
    if not channels:
        return
    index = int(_cfg.get("channel_index", 0)) % len(channels)
    channel = channels[index]
    _cfg["channel_index"] = (index + 1) % len(channels)
    _save()
    try:
        net.MoveChannelGame(channel)
        _log("FARMBOT: zmiana na CH%d" % channel)
    except Exception as exc:
        _log("FARMBOT: BLAD CH: %s" % exc)


class FarmController(object):
    def __init__(self):
        self.running = False
        self.recording = False
        self.point_index = 0
        self.target_vid = 0
        self.phase = "STOP"
        self.state = "STOP"
        self.state_until = 0.0
        self.last_record_time = 0.0
        self.last_move_time = 0.0

    def start(self):
        self.running = True
        self.recording = False
        self.point_index = 0
        self.target_vid = 0
        self.phase = "TP" if _cfg.get("mode") == "tp" else "ROUTE"
        self.state_until = 0.0
        self.last_move_time = 0.0
        self.state = "START"
        _stop_attack()
        global _scan_vid, _last_scan, _target_snapshot
        _scan_vid = _SCAN_MIN
        _last_scan = -999.0
        _target_snapshot = []
        _log("START | tryb=%s | TP=%d | TRASA=%d | TARGETY=%d" % (
            _cfg.get("mode"), len(_cfg.get("tp_points", [])),
            len(_cfg.get("route", [])), len(_wanted_vnums())))

    def stop(self):
        self.running = False
        self.target_vid = 0
        self.phase = "STOP"
        self.state = "STOP"
        _stop_attack()
        _log("STOP")

    def toggle_recording(self):
        if self.recording:
            self.recording = False
            _save()
            _log("NAGRYWANIE TRASY STOP | punktow=%d" % len(_cfg.get("route", [])))
        else:
            _cfg["route"] = []
            self.recording = True
            self.last_record_time = 0.0
            _save()
            _log("NAGRYWANIE TRASY START")

    def _points(self):
        if _cfg.get("mode") == "tp":
            return _cfg.get("tp_points", [])
        return _cfg.get("route", [])

    def _point_position(self, point):
        try:
            return int(point[0]), int(point[1]), int(point[2]) if len(point) > 2 else 0
        except:
            return None

    def _advance_tp_point(self, now):
        points = self._points()
        if not points:
            self.phase = "STOP"
            self.state = "BRAK PUNKTOW TP"
            return

        old = self.point_index
        self.point_index += 1
        if self.point_index >= len(points):
            self.point_index = 0
            self.state = "PELNA PETLA TP"
            _change_channel()
            _log("TP: zakonczono wszystkie %d punktow, powrot do punktu 01" % len(points))
        else:
            self.state = "PRZEJSCIE TP %02d -> %02d" % (old + 1, self.point_index + 1)

        self.target_vid = 0
        _stop_attack()
        self.phase = "TP"
        self.state_until = now + 0.25

    def _tp_step(self, now):
        points = self._points()
        if not points:
            self.state = "BRAK PUNKTOW TP"
            return

        if self.point_index >= len(points):
            self.point_index = 0

        # 1. TELEPORT DO KONKRETNEGO PUNKTU. Tylko raz na punkt.
        if self.phase == "TP":
            point = self._point_position(points[self.point_index])
            if not point:
                self._advance_tp_point(now)
                return
            try:
                main = int(player.GetMainCharacterIndex())
                if main <= 0:
                    self.state = "BLAD: brak VID gracza"
                    return
                chr.SelectInstance(main)
                chr.SetPixelPosition(point[0], point[1], point[2])
                self.state = "TP %02d/%02d | X:%d Y:%d" % (
                    self.point_index + 1, len(points), point[0], point[1]
                )
                self.phase = "SCAN"
                self.state_until = now + max(0.1, float(_cfg.get("tp_wait", 1.0)))
                self.target_vid = 0
                _stop_attack()
            except Exception as exc:
                _log("BLAD TP %02d: %s" % (self.point_index + 1, exc))
                self._advance_tp_point(now)
            return

        # 2. PO TP CZEKA, A POTEM SZUKA CELU W TYM PUNKCIE.
        if self.phase == "SCAN":
            if now < self.state_until:
                return
            vid = _find_target()
            if vid:
                self.target_vid = int(vid)
                self.phase = "TARGET"
                self.last_move_time = 0.0
                self.state = "CEL %d | SPRAWDZANIE" % int(vid)
                return
            self._advance_tp_point(now)
            return

        # 3. PODEJSCIE / ATAK. Po zabiciu wracamy do SCAN TEGO SAMEGO PUNKTU.
        if self.phase == "TARGET":
            vid = int(self.target_vid)
            if vid <= 0 or _is_dead(vid) or not _is_instance(vid) or not _is_attackable(vid):
                self.target_vid = 0
                _stop_attack()
                self.phase = "SCAN"
                self.state_until = now + 0.2
                self.state = "CEL ZABITY | PUNKT %02d" % (self.point_index + 1)
                return

            distance = _distance_to_vid(vid)
            if distance > ATTACK_DISTANCE:
                _stop_attack()
                if now - self.last_move_time >= MOVE_RETRY:
                    self.last_move_time = now
                    if not _move_to_target(vid):
                        self.target_vid = 0
                        self.phase = "SCAN"
                        self.state_until = now + 0.2
                        self.state = "NIE MOZNA PODEJSC | PONOWNE SZUKANIE"
                        return
                self.state = "PODEJSCIE DO CELU | %.0f" % distance
                return

            _attack(vid)
            self.state = "ATAK | VID %d | %.0f" % (vid, distance)
            return

    def _route_step(self, now):
        points = self._points()
        if not points:
            self.state = "BRAK NAGRANEJ TRASY"
            return

        # Cel ma zawsze pierwszenstwo nad ruchem po trasie.
        if self.target_vid:
            vid = int(self.target_vid)
            if vid <= 0 or _is_dead(vid) or not _is_instance(vid) or not _is_attackable(vid):
                self.target_vid = 0
                _stop_attack()
                self.state_until = now + 0.2
                self.state = "CEL ZABITY | POWROT NA TRASE"
                return

            distance = _distance_to_vid(vid)
            if distance > ATTACK_DISTANCE:
                _stop_attack()
                if now - self.last_move_time >= MOVE_RETRY:
                    self.last_move_time = now
                    if not _move_to_target(vid):
                        self.target_vid = 0
                        return
                self.state = "PODEJSCIE DO CELU | %.0f" % distance
                return

            _attack(vid)
            self.state = "ATAK | VID %d | %.0f" % (vid, distance)
            return

        if now < self.state_until:
            return

        vid = _find_target()
        if vid:
            self.target_vid = int(vid)
            self.last_move_time = 0.0
            self.state = "ZNALEZIONO CEL %d" % int(vid)
            return

        if self.point_index >= len(points):
            self.point_index = 0

        target = self._point_position(points[self.point_index])
        if not target:
            self.point_index = (self.point_index + 1) % len(points)
            return

        pos = _position()
        if not pos:
            return

        distance = ((float(pos[0]) - target[0]) ** 2 +
                    (float(pos[1]) - target[1]) ** 2) ** 0.5
        if distance <= 120.0:
            old = self.point_index
            self.point_index += 1
            if self.point_index >= len(points):
                self.point_index = 0
                self.state = "TRASA | PELNA PETLA"
                _change_channel()
            else:
                self.state = "TRASA | PUNKT %02d -> %02d" % (
                    old + 1, self.point_index + 1
                )
            self.state_until = now + max(0.1, float(_cfg.get("route_point_wait", 0.4)))
            return

        if now - self.last_move_time < MOVE_RETRY:
            return
        self.last_move_time = now
        if not _move_route_point(target):
            self.state = "BLAD RUCHU TRASY"
        else:
            self.state = "TRASA -> %02d | X:%d Y:%d" % (self.point_index + 1, target[0], target[1])

    def _record_update(self, now, pos):
        if not self.recording or not pos or now - self.last_record_time < 0.35:
            return
        self.last_record_time = now
        route = _cfg["route"]
        if not route:
            route.append([pos[0], pos[1], pos[2]])
            _save()
            return
        last = route[-1]
        distance = ((pos[0] - int(last[0])) ** 2 +
                    (pos[1] - int(last[1])) ** 2) ** 0.5
        if distance >= 100:
            route.append([pos[0], pos[1], pos[2]])
            _save()

    def update(self):
        now = app.GetTime()
        pos = _position()
        self._record_update(now, pos)
        if not self.running:
            return
        try:
            if _cfg.get("mode") == "tp":
                self._tp_step(now)
            else:
                self._route_step(now)
        except Exception as exc:
            self.state = "BLAD FARM: %s" % exc
            _log(self.state)


_controller = FarmController()
_load()


class FarmWindow(ui.BoardWithTitleBar):
    def __init__(self):
        ui.BoardWithTitleBar.__init__(self)
        self.SetSize(780, 590)
        self.SetCenterPosition()
        self.AddFlag("movable")
        self.AddFlag("float")
        self.SetTitleName("FarmBot  |  TRASA / PUNKTY TP")
        self.SetCloseEvent(self.Close)
        self._static = []
        self.target_rows = []
        self.point_rows = []
        self._build()
        self._refresh()
        self.Show()

    def _button(self, text, x, y, callback, width=110, parent=None):
        b = ui.Button(); b.SetParent(parent or self); b.SetPosition(x, y)
        b.SetUpVisual("d:/ymir work/ui/public/middle_button_01.sub")
        b.SetOverVisual("d:/ymir work/ui/public/middle_button_02.sub")
        b.SetDownVisual("d:/ymir work/ui/public/middle_button_03.sub")
        b.SetText(text); b.SetEvent(ui.__mem_func__(callback)); b.SetSize(width, 25); b.Show()
        if parent is None: self._static.append(b)
        return b

    def _label(self, text, x, y, parent=None):
        t = ui.TextLine(); t.SetParent(parent or self); t.SetPosition(x, y); t.SetText(str(text)); t.Show()
        if parent is None: self._static.append(t)
        return t

    def _edit(self, value, x, y, width=70, parent=None):
        e = ui.EditLine(); e.SetParent(parent or self); e.SetPosition(x, y); e.SetSize(width, 18); e.SetText(str(value))
        try: e.SetMax(20)
        except: pass
        e.Show()
        if parent is None: self._static.append(e)
        return e

    def _check(self, text, x, y, callback):
        c = ui.CheckBox(); c.SetParent(self); c.SetPosition(x, y)
        try: c.SetTextInfo(text)
        except: pass
        try:
            c.SetEvent(ui.__mem_func__(lambda arg: callback(True)), "ON_CHECK")
            c.SetEvent(ui.__mem_func__(lambda arg: callback(False)), "ON_UNCKECK")
        except: pass
        c.Show(); self._static.append(c); return c

    def _build(self):
        self._label("TRYB FARMOWANIA", 18, 30)
        self.mode_tp = self._button("PUNKTY TP", 18, 50, self._set_tp_mode, 125)
        self.mode_route = self._button("TRASA", 148, 50, self._set_route_mode, 125)
        self.record_button = self._button("NAGRAJ TRASE", 278, 50, self._record, 125)
        self.add_point_button = self._button("DODAJ PUNKT", 408, 50, self._add_point, 125)
        self.start_button = self._button("START FARM", 538, 50, self._start, 105)
        self.stop_button = self._button("STOP", 648, 50, self._stop, 80)
        self.status = self._label("STATUS: STOP", 18, 84)

        self._label("TARGETY", 18, 112)
        self.target_vnum = self._edit("", 18, 134, 75)
        self.target_name = self._edit("", 100, 134, 120)
        self._button("DODAJ TARGET", 225, 131, self._add_target, 110)
        self._button("DODAJ Z ZAZNACZONEGO", 340, 131, self._add_current_target, 165)
        self.target_count = self._label("TARGETOW: 0", 515, 138)

        self.target_list = ui.Window(); self.target_list.SetParent(self); self.target_list.SetPosition(18, 168); self.target_list.SetSize(485, 250); self.target_list.Show(); self._static.append(self.target_list)
        self.target_prev = self._button("<", 18, 425, self._target_prev, 35)
        self.target_next = self._button(">", 58, 425, self._target_next, 35)
        self.target_page = self._label("1 / 1", 105, 431)

        self._label("PUNKTY", 525, 112)
        self.point_count = self._label("TP: 0", 525, 138)
        self.point_list = ui.Window(); self.point_list.SetParent(self); self.point_list.SetPosition(525, 168); self.point_list.SetSize(235, 250); self.point_list.Show(); self._static.append(self.point_list)
        self.point_prev = self._button("<", 525, 425, self._point_prev, 35)
        self.point_next = self._button(">", 565, 425, self._point_next, 35)
        self.point_page = self._label("1 / 1", 612, 431)

        self._label("USTAWIENIA", 18, 463)
        self.channel_check = self._check("Zmieniaj CH po pelnej petli", 18, 486, self._channel_changed)
        self.channel_check.SetCheckStatus(bool(_cfg.get("change_channel")))
        self._label("Czas sprawdzania celu po TP:", 290, 489)
        self.tp_wait_edit = self._edit(_cfg.get("tp_wait", 1.0), 470, 486, 50)
        self._button("ZAPISZ", 528, 483, self._save_settings, 70)
        self._label("TRASA: nagraj trase -> START. TP: dodaj punkty -> START. Cel: najpierw podejscie, potem atak.", 18, 530)

    def _clear_rows(self, rows):
        for row in rows:
            for obj in row:
                try: obj.Hide()
                except: pass

    def _refresh(self):
        global _TARGET_PAGE, _POINT_PAGE
        self._clear_rows(self.target_rows); self._clear_rows(self.point_rows)
        self.target_rows = []; self.point_rows = []
        if _cfg.get("mode") == "tp":
            self.mode_tp.SetText(">>> PUNKTY TP <<<"); self.mode_route.SetText("TRASA")
            self.record_button.SetText("NAGRAJ TRASE")
            self.add_point_button.SetText("DODAJ PUNKT")
        else:
            self.mode_tp.SetText("PUNKTY TP"); self.mode_route.SetText(">>> TRASA <<<")
            self.record_button.SetText("STOP NAGRYWANIA" if _controller.recording else "NAGRAJ TRASE")
            self.add_point_button.SetText("DODAJ PUNKT")
        self.status.SetText(("STATUS: FARM ON | " if _controller.running else "STATUS: STOP | ") + str(_controller.state))
        self.target_count.SetText("TARGETOW: %d" % len(_cfg["targets"]))
        points = _controller._points()
        self.point_count.SetText(("TP" if _cfg.get("mode") == "tp" else "TRASA") + ": %d" % len(points))

        targets = _cfg["targets"]
        pages = max(1, (len(targets) + _ROWS_PER_PAGE - 1) // _ROWS_PER_PAGE)
        _TARGET_PAGE = max(0, min(_TARGET_PAGE, pages - 1))
        start = _TARGET_PAGE * _ROWS_PER_PAGE; end = min(len(targets), start + _ROWS_PER_PAGE)
        for index in range(start, end):
            target = targets[index]; y = (index - start) * 31
            check = ui.CheckBox(); check.SetParent(self.target_list); check.SetPosition(0, y + 5)
            try: check.SetTextInfo("")
            except: pass
            check.SetEvent(ui.__mem_func__(lambda arg, i=index: self._target_check(i, True)), "ON_CHECK")
            check.SetEvent(ui.__mem_func__(lambda arg, i=index: self._target_check(i, False)), "ON_UNCKECK")
            check.SetCheckStatus(bool(target.get("use", True))); check.Show()
            number = self._label("%02d" % (index + 1), 25, y + 6, self.target_list)
            vnum = self._edit(target.get("vnum", 0), 55, y + 1, 75, self.target_list)
            name = self._edit(target.get("name", ""), 135, y + 1, 125, self.target_list)
            save = self._button("ZAPISZ", 265, y, lambda i=index, v=vnum, n=name: self._save_target(i, v, n), 65, self.target_list)
            delete = self._button("USUN", 335, y, lambda i=index: self._delete_target(i), 60, self.target_list)
            self.target_rows.append((check, number, vnum, name, save, delete))
        self.target_page.SetText("%d / %d" % (_TARGET_PAGE + 1, pages))

        ppages = max(1, (len(points) + _ROWS_PER_PAGE - 1) // _ROWS_PER_PAGE)
        _POINT_PAGE = max(0, min(_POINT_PAGE, ppages - 1))
        start = _POINT_PAGE * _ROWS_PER_PAGE; end = min(len(points), start + _ROWS_PER_PAGE)
        for index in range(start, end):
            point = points[index]; y = (index - start) * 31
            number = self._label("%02d" % (index + 1), 0, y + 6, self.point_list)
            self._label("X:%d" % int(point[0]), 28, y + 6, self.point_list)
            self._label("Y:%d" % int(point[1]), 112, y + 6, self.point_list)
            delete = self._button("USUN", 166, y, lambda i=index: self._delete_point(i), 55, self.point_list)
            self.point_rows.append((number, delete))
        self.point_page.SetText("%d / %d" % (_POINT_PAGE + 1, ppages))

    def _set_tp_mode(self):
        _controller.stop(); _cfg["mode"] = "tp"; _save(); self._refresh()
    def _set_route_mode(self):
        _controller.stop(); _cfg["mode"] = "route"; _save(); self._refresh()

    def _add_point(self):
        if _cfg.get("mode") != "tp":
            self.status.SetText("DODAJ PUNKT dziala w trybie PUNKTY TP. W TRASIE uzyj NAGRAJ TRASE.")
            return
        pos = _position()
        if not pos:
            self.status.SetText("BLAD: nie mozna pobrac pozycji gracza.")
            return
        _cfg["tp_points"].append([pos[0], pos[1], pos[2]])
        _save(); self._refresh()

    def _add_target(self):
        try: vnum = int(self.target_vnum.GetText())
        except: vnum = 0
        if vnum <= 0:
            self.status.SetText("BLAD: VNUM musi byc > 0"); return
        _cfg["targets"].append({"vnum": vnum, "name": str(self.target_name.GetText()), "use": True})
        self.target_vnum.SetText(""); self.target_name.SetText(""); _save(); self._refresh()

    def _add_current_target(self):
        try: vid = int(player.GetTargetVID())
        except: vid = 0
        if vid <= 0:
            self.status.SetText("BLAD: zaznacz target w grze"); return
        vnum = _target_vnum(vid)
        if vnum <= 0:
            self.status.SetText("BLAD: nie znaleziono VNUM"); return
        _cfg["targets"].append({"vnum": vnum, "name": _target_name(vid), "use": True}); _save(); self._refresh()

    def _target_check(self, index, value):
        if 0 <= index < len(_cfg["targets"]): _cfg["targets"][index]["use"] = bool(value); _save()
    def _save_target(self, index, vnum_edit, name_edit):
        if not 0 <= index < len(_cfg["targets"]): return
        try: vnum = int(vnum_edit.GetText())
        except: vnum = 0
        if vnum <= 0: self.status.SetText("BLAD: VNUM musi byc > 0"); return
        _cfg["targets"][index]["vnum"] = vnum; _cfg["targets"][index]["name"] = str(name_edit.GetText()); _save(); self._refresh()
    def _delete_target(self, index):
        if 0 <= index < len(_cfg["targets"]): del _cfg["targets"][index]; _save(); self._refresh()
    def _target_prev(self):
        global _TARGET_PAGE
        if _TARGET_PAGE > 0: _TARGET_PAGE -= 1; self._refresh()
    def _target_next(self):
        global _TARGET_PAGE
        pages = max(1, (len(_cfg["targets"]) + _ROWS_PER_PAGE - 1) // _ROWS_PER_PAGE)
        if _TARGET_PAGE + 1 < pages: _TARGET_PAGE += 1; self._refresh()
    def _point_prev(self):
        global _POINT_PAGE
        if _POINT_PAGE > 0: _POINT_PAGE -= 1; self._refresh()
    def _point_next(self):
        global _POINT_PAGE
        points = _controller._points(); pages = max(1, (len(points) + _ROWS_PER_PAGE - 1) // _ROWS_PER_PAGE)
        if _POINT_PAGE + 1 < pages: _POINT_PAGE += 1; self._refresh()
    def _delete_point(self, index):
        points = _controller._points()
        if 0 <= index < len(points): del points[index]; _save(); self._refresh()
    def _record(self):
        if _cfg.get("mode") != "route":
            self.status.SetText("NAGRYWANIE: przelacz tryb TRASA")
            return
        _controller.toggle_recording(); self._refresh()
    def _start(self):
        if _cfg.get("mode") == "tp" and not _cfg.get("tp_points"):
            self.status.SetText("START: brak punktow TP"); return
        if _cfg.get("mode") == "route" and not _cfg.get("route"):
            self.status.SetText("START: brak nagranej trasy"); return
        _controller.start(); self._refresh()
    def _stop(self):
        _controller.stop(); self._refresh()
    def _channel_changed(self, value):
        _cfg["change_channel"] = bool(value); _save()
    def _save_settings(self):
        try: _cfg["tp_wait"] = max(0.1, float(self.tp_wait_edit.GetText()))
        except: pass
        _save(); self.status.SetText("USTAWIENIA ZAPISANE")
    def Close(self):
        global _window
        _controller.stop(); _window = None; self.Hide()
    def Destroy(self): self.Close()


def Open():
    global _window
    if _window:
        _window.SetTop(); return
    _window = FarmWindow()


def Update():
    try:
        _controller.update()
        if _window and _controller.running:
            # Odświeżamy tylko status, nie przebudowujemy listy UI co klatke.
            _window.status.SetText("STATUS: FARM ON | " + str(_controller.state))
            _window.record_button.SetText("STOP NAGRYWANIA" if _controller.recording else "NAGRAJ TRASE")
    except Exception as exc:
        _log("BLAD UPDATE: %s" % exc)
