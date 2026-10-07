import app
import player
import net
import item

_enabled = False
_interval = 1500
_last_use = 0.0

# Standardowa Peleryna Męstwa w wielu klientach Metin2.
# Jeżeli klient ma inny VNUM, skaner niżej spróbuje znaleźć ją po nazwie.
_CAPE_VNUMS = (70043,)

_cape_slot = -1
_cape_vnum = 0


def SetEnabled(value):
    global _enabled
    _enabled = bool(value)


def IsEnabled():
    return _enabled


def SetInterval(milliseconds):
    global _interval
    _interval = max(100, min(5000, int(milliseconds)))


def GetInterval():
    return _interval


def GetDetectedCape():
    _FindCape()
    return _cape_vnum, _cape_slot


def _IsCapeName(name):
    if not name:
        return False

    try:
        name = name.lower()
    except:
        return False

    # Obsługa polskiej i angielskiej nazwy.
    return (
        "peleryn" in name or
        "cape" in name or
        "cloak of courage" in name or
        "courage" in name
    )


def _FindCape():
    global _cape_slot, _cape_vnum

    if _cape_slot >= 0 and _cape_vnum > 0:
        try:
            if (
                player.GetItemIndex(_cape_slot) == _cape_vnum
                and player.GetItemCount(_cape_slot) > 0
            ):
                return _cape_slot
        except:
            pass

    try:
        inventory_size = (
            player.INVENTORY_PAGE_SIZE *
            player.INVENTORY_PAGE_COUNT
        )

        # Najpierw znane VNUM-y.
        for slot in range(inventory_size):
            vnum = player.GetItemIndex(slot)
            count = player.GetItemCount(slot)

            if count <= 0:
                continue

            if vnum in _CAPE_VNUMS:
                _cape_slot = slot
                _cape_vnum = vnum
                return slot

        # Następnie nazwa itemu.
        for slot in range(inventory_size):
            vnum = player.GetItemIndex(slot)
            count = player.GetItemCount(slot)

            if count <= 0 or vnum <= 0:
                continue

            try:
                item.SelectItem(vnum)
                name = item.GetItemName()

                if _IsCapeName(name):
                    _cape_slot = slot
                    _cape_vnum = vnum
                    return slot

            except:
                pass

    except:
        pass

    _cape_slot = -1
    _cape_vnum = 0
    return -1


def Update():
    global _last_use

    if not _enabled:
        return

    try:
        now = app.GetTime()
        delay = float(_interval) / 1000.0

        if now - _last_use < delay:
            return

        slot = _FindCape()

        if slot < 0:
            return

        if player.GetItemCount(slot) <= 0:
            return

        net.SendItemUsePacket(slot)
        _last_use = now

    except:
        pass
