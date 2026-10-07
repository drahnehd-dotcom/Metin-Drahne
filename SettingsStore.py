import os
import json

_PATH = r"D:\KowalMT2\data\me\kowal_settings.json"

_DEFAULTS = {
    "autopot": False,
    "hp": 50,
    "sp": 30,
    "use_hp": True,
    "use_sp": True,
    "autopickup": False,
    "pickup_interval": 200,
    "mobber": False,
    "mobber_interval": 1500,
    "boosters_enabled": False,
    "boosters": [],
    "auto_skills": {"slots": [None] * 6, "active": [False] * 6, "enabled": False},
}


def _CopyDefaults():
    data = {}
    for key, value in _DEFAULTS.items():
        if isinstance(value, list):
            data[key] = list(value)
        else:
            data[key] = value
    return data


def Load():
    data = _CopyDefaults()

    try:
        if not os.path.exists(_PATH):
            return data

        f = open(_PATH, "r")
        loaded = json.load(f)
        f.close()

        if isinstance(loaded, dict):
            for key in data:
                if key in loaded:
                    data[key] = loaded[key]

    except:
        pass

    return data


def Save(data):
    try:
        folder = os.path.dirname(_PATH)

        if not os.path.exists(folder):
            os.makedirs(folder)

        f = open(_PATH, "w")
        json.dump(data, f, sort_keys=True)
        f.close()
        return True

    except:
        return False
