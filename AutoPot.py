import app
import player
import net
import item

_enabled = False

_hp_threshold = 50
_sp_threshold = 30

_use_hp = True
_use_sp = True

_last_use = 0.0
_USE_DELAY = 0.60

_HP_VNUMS = (27051, 27122, 27201, 27202, 27203, 70056, 71108, 76033)
_SP_VNUMS = (27052, 27204, 27205, 27206)

_hp_slot = -1
_sp_slot = -1
_hp_vnum = 0
_sp_vnum = 0


def SetEnabled(value):
    global _enabled
    _enabled = bool(value)


def IsEnabled():
    return _enabled


def SetThresholds(hp, sp):
    global _hp_threshold, _sp_threshold
    _hp_threshold = max(1, min(99, int(hp)))
    _sp_threshold = max(1, min(99, int(sp)))


def GetThresholds():
    return _hp_threshold, _sp_threshold


def SetUseTypes(use_hp, use_sp):
    global _use_hp, _use_sp
    _use_hp = bool(use_hp)
    _use_sp = bool(use_sp)


def GetUseTypes():
    return _use_hp, _use_sp


def GetDetectedPotions():
    _FindPotionSlot("hp")
    _FindPotionSlot("sp")

    return (
        _hp_vnum,
        _hp_slot,
        _sp_vnum,
        _sp_slot,
    )


def _IsPotionVnum(vnum, kind):
    if not vnum:
        return False

    if kind == "hp" and vnum in _HP_VNUMS:
        return True

    if kind == "sp" and vnum in _SP_VNUMS:
        return True

    try:
        item.SelectItem(vnum)

        sub_type = item.GetItemSubType()

        if sub_type not in (
            item.USE_POTION,
            item.USE_POTION_NODELAY
        ):
            return False

        heal_hp = item.GetValue(0)
        heal_sp = item.GetValue(1)
        heal_percent_hp = item.GetValue(3)
        heal_percent_sp = item.GetValue(4)

        if kind == "hp":
            return heal_hp > 0 or heal_percent_hp > 0

        return heal_sp > 0 or heal_percent_sp > 0

    except:
        return False


def _FindPotionSlot(kind):
    global _hp_slot, _sp_slot, _hp_vnum, _sp_vnum

    cached_slot = _hp_slot if kind == "hp" else _sp_slot
    wanted_vnum = _hp_vnum if kind == "hp" else _sp_vnum

    # 1. Zapamiętany slot.
    if cached_slot >= 0:
        try:
            if (
                player.GetItemIndex(cached_slot) == wanted_vnum
                and player.GetItemCount(cached_slot) > 0
            ):
                return cached_slot
        except:
            pass

    try:
        inventory_size = (
            player.INVENTORY_PAGE_SIZE *
            player.INVENTORY_PAGE_COUNT
        )

        # 2. Zapamiętany VNUM.
        if wanted_vnum > 0:
            for slot in range(inventory_size):
                if (
                    player.GetItemIndex(slot) == wanted_vnum
                    and player.GetItemCount(slot) > 0
                ):
                    if kind == "hp":
                        _hp_slot = slot
                    else:
                        _sp_slot = slot
                    return slot

        # 3. Automatyczne wykrycie pierwszej pasującej potki.
        for slot in range(inventory_size):
            vnum = player.GetItemIndex(slot)
            count = player.GetItemCount(slot)

            if count <= 0:
                continue

            if not _IsPotionVnum(vnum, kind):
                continue

            if kind == "hp":
                _hp_slot = slot
                _hp_vnum = vnum
            else:
                _sp_slot = slot
                _sp_vnum = vnum

            return slot

    except:
        pass

    # Nie znaleziono.
    if kind == "hp":
        _hp_slot = -1
        _hp_vnum = 0
    else:
        _sp_slot = -1
        _sp_vnum = 0

    return -1


def _Percent(current, maximum):
    if maximum <= 0:
        return 100.0

    return float(current) * 100.0 / float(maximum)


def _Use(kind):
    global _last_use

    slot = _FindPotionSlot(kind)

    if slot < 0:
        return False

    try:
        vnum = player.GetItemIndex(slot)

        if vnum <= 0 or player.GetItemCount(slot) <= 0:
            return False

        if not _IsPotionVnum(vnum, kind):
            return False

        net.SendItemUsePacket(slot)
        _last_use = app.GetTime()
        return True

    except:
        return False


def Update():
    if not _enabled:
        return

    try:
        now = app.GetTime()

        if now - _last_use < _USE_DELAY:
            return

        hp = player.GetStatus(player.HP)
        max_hp = player.GetStatus(player.MAX_HP)
        sp = player.GetStatus(player.SP)
        max_sp = player.GetStatus(player.MAX_SP)

        hp_percent = _Percent(hp, max_hp)
        sp_percent = _Percent(sp, max_sp)

        # HP ma pierwszeństwo.
        if _use_hp and hp > 0 and hp_percent <= _hp_threshold:
            if _Use("hp"):
                return

        if _use_sp and sp > 0 and sp_percent <= _sp_threshold:
            _Use("sp")

    except:
        pass
