import app
import player
import net

_enabled = False

# ZAWSZE 30 pozycji. Puste sloty pozostaja na swoim miejscu.
_entries = [None] * 30


def _Empty():
    return {
        "vnum": 0,
        "interval": 10,
        "use": False,
        "last": 0.0,
    }


def _NormalizeEntry(value):
    entry = _Empty()
    try:
        if isinstance(value, dict):
            entry["vnum"] = int(value.get("vnum", 0))
            entry["interval"] = max(1, min(3600, int(value.get("interval", 10))))
            entry["use"] = bool(value.get("use", False))
    except:
        pass
    return entry


def Load(values):
    global _entries
    _entries = [_Empty() for _ in range(30)]

    if isinstance(values, list):
        for i, value in enumerate(values[:30]):
            _entries[i] = _NormalizeEntry(value)


def Export():
    return [
        {
            "vnum": int(entry["vnum"]),
            "interval": int(entry["interval"]),
            "use": bool(entry["use"]),
        }
        for entry in _entries
    ]


def SetEnabled(value):
    global _enabled
    _enabled = bool(value)


def IsEnabled():
    return bool(_enabled)


def GetEntries():
    return _entries


def SetEntry(index, vnum, interval=10, use=True):
    try:
        index = int(index)
        vnum = int(vnum)
    except:
        return

    if index < 0 or index >= 30 or vnum <= 0:
        return

    _entries[index]["vnum"] = vnum
    _entries[index]["interval"] = max(1, min(3600, int(interval)))
    _entries[index]["use"] = bool(use)
    _entries[index]["last"] = 0.0


def RemoveEntry(index):
    try:
        index = int(index)
    except:
        return

    if 0 <= index < 30:
        _entries[index] = _Empty()


def SetEntryInterval(index, seconds):
    try:
        index = int(index)
        seconds = int(seconds)
    except:
        return

    if 0 <= index < 30:
        _entries[index]["interval"] = max(1, min(3600, seconds))


def SetEntryUse(index, value):
    try:
        index = int(index)
    except:
        return

    if 0 <= index < 30 and _entries[index]["vnum"] > 0:
        _entries[index]["use"] = bool(value)


def _FindInventorySlot(vnum):
    try:
        size = player.INVENTORY_PAGE_SIZE * player.INVENTORY_PAGE_COUNT
        for slot in range(size):
            if player.GetItemIndex(slot) == vnum and player.GetItemCount(slot) > 0:
                return slot
    except:
        pass
    return -1


def Update():
    if not _enabled:
        return

    now = app.GetTime()

    for entry in _entries:
        if not entry["use"] or entry["vnum"] <= 0:
            continue

        interval = float(entry["interval"])
        if now - entry["last"] < interval:
            continue

        slot = _FindInventorySlot(entry["vnum"])
        if slot < 0:
            continue

        try:
            net.SendItemUsePacket(slot)
            entry["last"] = now
        except:
            pass
