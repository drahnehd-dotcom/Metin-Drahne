import app
import player

_enabled = False
_interval = 200
_last_pickup = 0.0


def SetEnabled(value):
    global _enabled
    _enabled = bool(value)


def IsEnabled():
    return _enabled


def SetInterval(milliseconds):
    global _interval
    _interval = max(10, min(2000, int(milliseconds)))


def GetInterval():
    return _interval


def Update():
    global _last_pickup

    if not _enabled:
        return

    try:
        now = app.GetTime()
        delay = float(_interval) / 1000.0

        if now - _last_pickup < delay:
            return

        player.PickCloseItem()
        _last_pickup = now

    except:
        pass
