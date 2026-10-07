import app
import ui
import game
import player
import mouseModule
import time
import os
import chat

import AutoPot
import Pickup
import Mobber
import Boosters
import AutoSkills
import SettingsStore
import FarmBot
try:
    import constInfo
except:
    constInfo = None

_panel = None
_settings = None
_booster_editor = None
_skill_editor = None
_analyzer = None

_chat_original_append = None
_chat_original_whisper = None
_chat_analyzer_active = False
_chat_log_file = r"D:\KowalMT2\data\me\ChatLog.txt"
_chat_log_count = 0

# Natywny logger czatu dla tego konkretnego KowalMT2.exe.
# RVAs ustalone na podstawie dostarczonego EXE.
_NATIVE_CHAT_APPEND_RVA = 0x39F840
_NATIVE_WHISPER_APPEND_RVA = 0x39FF10
_NATIVE_HOOKS = []
_NATIVE_HOOK_ACTIVE = False
_NATIVE_HOOK_ERROR = ""
_NATIVE_HOOK_SIZE_CHAT = 14
_NATIVE_HOOK_SIZE_WHISPER = 15
_NATIVE_CHAT_TYPES = {
    0: "TALKING",
    1: "INFO",
    2: "NOTICE",
    3: "EXP_INFO",
    4: "ITEM_INFO",
    5: "MONEY_INFO",
    6: "PARTY",
    7: "GUILD",
    8: "COMMAND",
    9: "SHOUT",
    10: "WHISPER",
    11: "BIG_NOTICE",
    12: "MONARCH_NOTICE",
    13: "DICE_INFO",
}

_original_on_key_down = None
_original_on_update = None

_settings_data = SettingsStore.Load()

IMG = "d:/KowalMT2/data/me/img/"


def _Save():
    try:
        _settings_data["boosters"] = Boosters.Export()
        _settings_data["auto_skills"] = AutoSkills.Export()
        SettingsStore.Save(_settings_data)
    except:
        pass


def _ApplySettings():
    AutoPot.SetEnabled(_settings_data["autopot"])
    AutoPot.SetThresholds(_settings_data["hp"], _settings_data["sp"])
    AutoPot.SetUseTypes(
        _settings_data["use_hp"],
        _settings_data["use_sp"]
    )

    Pickup.SetEnabled(_settings_data["autopickup"])
    Pickup.SetInterval(_settings_data["pickup_interval"])

    Mobber.SetEnabled(_settings_data["mobber"])
    Mobber.SetInterval(_settings_data["mobber_interval"])

    Boosters.SetEnabled(_settings_data["boosters_enabled"])

    Boosters.Load(_settings_data.get("boosters", []))
    AutoSkills.Load(_settings_data.get("auto_skills", []))


_ApplySettings()


def _MakeButton(parent, text, x, y, event, width=150):
    btn = ui.Button()
    btn.SetParent(parent)
    btn.SetPosition(x, y)
    btn.SetUpVisual("d:/ymir work/ui/public/middle_button_01.sub")
    btn.SetOverVisual("d:/ymir work/ui/public/middle_button_02.sub")
    btn.SetDownVisual("d:/ymir work/ui/public/middle_button_03.sub")
    btn.SetText(text)
    btn.SetEvent(ui.__mem_func__(event))
    btn.Show()
    return btn


def _MakeIcon(parent, filename, x, y, w=32, h=32):
    try:
        icon = ui.ImageBox()
        icon.SetParent(parent)
        icon.SetPosition(x, y)
        icon.LoadImage(IMG + filename)
        icon.SetSize(w, h)
        icon.Show()
        return icon
    except:
        return None


def _MakeLabel(parent, text, x, y):
    label = ui.TextLine()
    label.SetParent(parent)
    label.SetPosition(x, y)
    label.SetText(text)
    label.Show()
    return label


def _MakeSlider(parent, x, y, pos, event):
    slider = ui.SliderBar()
    slider.SetParent(parent)
    slider.SetPosition(x, y)
    slider.SetSliderPos(pos)
    slider.SetEvent(ui.__mem_func__(event))
    slider.Show()
    return slider


def _MakeSlot(parent, x, y, size=40):
    slot = ui.SlotWindow()
    slot.SetParent(parent)
    slot.SetPosition(x, y)
    slot.SetSize(size, size)
    slot.AppendSlot(0, 0, 0, size, size)

    try:
        slot.SetSlotBaseImage(
            IMG + "slot.png",
            1.0, 1.0, 1.0, 1.0
        )
    except:
        try:
            slot.SetSlotBaseImage(
                "d:/ymir work/ui/public/slot_base.sub",
                1.0, 1.0, 1.0, 1.0
            )
        except:
            pass

    slot.Show()
    return slot


def _MakeCheck(parent, text, x, y, event):
    box = ui.CheckBox()
    box.SetParent(parent)
    box.SetPosition(x, y)
    box.SetTextInfo(text)
    # Metin2 ui.CheckBox przekazuje do callbacku również nazwę zdarzenia
    # ("ON_CHECK" / "ON_UNCKECK"). W poprzedniej wersji callback przyjmował
    # tylko bool, więc event kończył się błędem i stan slotu nie był zapisywany.
    box.SetEvent(ui.__mem_func__(lambda _event_name: event(True)), "ON_CHECK")
    box.SetEvent(ui.__mem_func__(lambda _event_name: event(False)), "ON_UNCKECK")
    box.Show()
    return box


def _SetCheckMark(parent, x, y, visible):
    try:
        mark = ui.ImageBox()
        mark.SetParent(parent)
        mark.SetPosition(x, y)
        mark.LoadImage(IMG + "box_on.png")
        mark.Show() if visible else mark.Hide()
        return mark
    except:
        return None


def _GetAttachedItem():
    if not mouseModule.mouseController.isAttached():
        return -1, 0, 0

    try:
        attached_type = mouseModule.mouseController.GetAttachedType()

        if attached_type != player.SLOT_TYPE_INVENTORY:
            return -1, 0, 0

        slot = mouseModule.mouseController.GetAttachedSlotNumber()
        vnum = mouseModule.mouseController.GetAttachedItemIndex()
        count = mouseModule.mouseController.GetAttachedItemCount()

        if slot < 0 or vnum <= 0:
            return -1, 0, 0

        return slot, vnum, count

    except:
        return -1, 0, 0


def _GetAttachedSkill():
    if not mouseModule.mouseController.isAttached():
        return -1

    try:
        attached_type = mouseModule.mouseController.GetAttachedType()

        if attached_type != player.SLOT_TYPE_SKILL:
            return -1

        return mouseModule.mouseController.GetAttachedSlotNumber()

    except:
        return -1


class BoosterEditor(ui.BoardWithTitleBar):

    def __init__(self):
        ui.BoardWithTitleBar.__init__(self)
        self.SetSize(610, 500)
        self.SetCenterPosition()
        self.AddFlag("movable")
        self.AddFlag("float")
        self.SetTitleName("Dopalacze - ustawienia")
        self.SetCloseEvent(self.Close)
        self.slots=[]; self.checks=[]; self.edits=[]
        for index in range(30):
            col=index%5; row=index//5; x=18+col*118; y=38+row*58
            slot=_MakeSlot(self,x,y,40)
            slot.SetSelectEmptySlotEvent(ui.__mem_func__(lambda _slot_index, idx=index:self._AssignSlot(idx)))
            slot.SetSelectItemSlotEvent(ui.__mem_func__(lambda _slot_index, idx=index:self._AssignSlot(idx)))
            slot.SetUseSlotEvent(ui.__mem_func__(lambda _slot_index, idx=index:self._AssignSlot(idx)))
            if hasattr(slot, "SetUnselectEmptySlotEvent"):
                slot.SetUnselectEmptySlotEvent(ui.__mem_func__(lambda _slot_index, idx=index:self._AssignSlot(idx)))
            if hasattr(slot, "SetUnselectItemSlotEvent"):
                slot.SetUnselectItemSlotEvent(ui.__mem_func__(lambda _slot_index, idx=index:self._AssignSlot(idx)))
            self.slots.append(slot)
            check=_MakeCheck(self,"ON",x+44,y,lambda state,idx=index:self._CheckChanged(idx,state))
            self.checks.append(check)
            edit=ui.EditLine(); edit.SetParent(self); edit.SetPosition(x+44,y+24); edit.SetSize(45,17); edit.SetText("10")
            try: edit.SetNumberMode(); edit.SetMax(4)
            except: pass
            edit.SetReturnEvent(ui.__mem_func__(lambda idx=index:self._IntervalReturn(idx)))
            edit.SetEscapeEvent(ui.__mem_func__(lambda idx=index:self._IntervalCancel(idx)))
            edit.Show(); self.edits.append(edit)
            _MakeLabel(self,"sek.",x+91,y+24)
        _MakeLabel(self,"Przeciągnij item z EQ na slot. Timer wpisujesz w sekundach.",18,390)
        _MakeButton(self,"ZAMKNIJ",455,420,self.Close,120)
        self._Refresh(); self.Show()

    def _GetAttachedVnum(self):
        if not mouseModule.mouseController.isAttached(): return 0
        try:
            if mouseModule.mouseController.GetAttachedType()!=player.SLOT_TYPE_INVENTORY: return 0
            return int(mouseModule.mouseController.GetAttachedItemIndex())
        except: return 0

    def _AssignSlot(self,index):
        vnum=self._GetAttachedVnum()
        if vnum>0:
            e=Boosters.GetEntries()[index]
            Boosters.SetEntry(index,vnum,int(e.get("interval",10)),bool(e.get("use",True)))
            try: mouseModule.mouseController.DeattachObject()
            except: pass
            _Save(); self._Refresh(); return
        e=Boosters.GetEntries()[index]
        if int(e.get("vnum",0))>0:
            Boosters.RemoveEntry(index); _Save(); self._Refresh()

    def _CheckChanged(self,index,state):
        Boosters.SetEntryUse(index,bool(state)); _Save(); self._Refresh()

    def _IntervalReturn(self,index):
        try: value=int(self.edits[index].GetText())
        except: value=10
        value=max(1,min(3600,value)); Boosters.SetEntryInterval(index,value); self.edits[index].SetText(str(value)); _Save()

    def _IntervalCancel(self,index):
        self.edits[index].SetText(str(int(Boosters.GetEntries()[index].get("interval",10))))

    def _Refresh(self):
        entries=Boosters.GetEntries()
        for i in range(30):
            self.slots[i].ClearSlot(0); e=entries[i]; v=int(e.get("vnum",0))
            if v>0:
                self.slots[i].SetItemSlot(0,v,1); self.checks[i].SetCheckStatus(bool(e.get("use",False)))
            else: self.checks[i].SetCheckStatus(False)
            self.edits[i].SetText(str(int(e.get("interval",10))))

    def Close(self):
        global _booster_editor; _booster_editor=None; self.Hide()
    def Destroy(self): self.Close()


class SkillEditor(object):
    """Wrapper for the original F8 Farm Auto Skill selector.

    The real UI/controller lives in AutoSkills.py and is created lazily.
    """
    def __init__(self):
        AutoSkills.Open()

    def SetTop(self):
        AutoSkills.Open()

    def Open(self):
        AutoSkills.Open()

    def Hide(self):
        AutoSkills.Hide()

    def Close(self):
        global _skill_editor
        _skill_editor = None
        AutoSkills.Hide()

    def Destroy(self):
        self.Close()


def _ChatSafeText(value):
    try:
        if isinstance(value, bytes):
            try:
                text = value.decode("utf-8", "replace")
                if text.count("\ufffd") > 0:
                    try:
                        return value.decode("cp1250", "replace")
                    except:
                        pass
                return text
            except:
                return repr(value)
        return str(value)
    except:
        return "<nieznany>"


def _ChatWrite(kind, args):
    """Natychmiast dopisuje komunikat do pliku."""
    global _chat_log_count

    if not _chat_analyzer_active:
        return

    try:
        parts = []
        for value in args:
            parts.append(_ChatSafeText(value))

        line = "[%s] [%s] %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S"),
            kind,
            " | ".join(parts)
        )

        folder = os.path.dirname(_chat_log_file)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        f = open(_chat_log_file, "a")
        try:
            f.write(line)
            f.flush()
        finally:
            f.close()

        _chat_log_count += 1
    except:
        pass


def _ChatWriteForce(kind, text):
    try:
        folder = os.path.dirname(_chat_log_file)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        f = open(_chat_log_file, "a")
        try:
            f.write("[%s] [%s] %s\n" % (
                time.strftime("%Y-%m-%d %H:%M:%S"),
                kind,
                _ChatSafeText(text)
            ))
            f.flush()
        finally:
            f.close()
    except:
        pass


def _NativeReadText(ptr):
    try:
        if not ptr:
            return ""
        raw = ctypes.string_at(ptr, 4096)
        if not raw:
            return ""
        zero = raw.find(b"\x00")
        if zero >= 0:
            raw = raw[:zero]
        return _ChatSafeText(raw)
    except:
        return "<BLAD_ODCZYTU_TEKSTU>"


def _NativeChatType(value):
    try:
        ivalue = int(value)
        return "%d:%s" % (
            ivalue,
            _NATIVE_CHAT_TYPES.get(ivalue, "UNKNOWN")
        )
    except:
        return "?:UNKNOWN"


def _NativeProtect(address, size, protection):
    try:
        kernel32 = ctypes.windll.kernel32
        old = ctypes.c_ulong(0)
        if not kernel32.VirtualProtect(
                ctypes.c_void_p(address),
                ctypes.c_size_t(size),
                ctypes.c_ulong(protection),
                ctypes.byref(old)):
            return None
        return old.value
    except:
        return None


def _NativeWrite(address, data):
    old = _NativeProtect(address, len(data), 0x40)
    if old is None:
        return False
    try:
        ctypes.memmove(
            ctypes.c_void_p(address),
            data,
            len(data)
        )
        try:
            ctypes.windll.kernel32.FlushInstructionCache(
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.c_void_p(address),
                ctypes.c_size_t(len(data))
            )
        except:
            pass
        return True
    finally:
        _NativeProtect(address, len(data), old)


def _NativeMakeJump(destination):
    # mov rax, imm64 ; jmp rax
    return b"\x48\xB8" + ctypes.c_uint64(destination).value.to_bytes(8, "little") + b"\xFF\xE0"


def _NativeInstallOne(rva, hook_size, expected, callback_factory, kind):
    base = int(ctypes.windll.kernel32.GetModuleHandleW(None))
    if not base:
        raise RuntimeError("GetModuleHandleW zwrocil 0")

    target = base + int(rva)
    current = ctypes.string_at(target, len(expected))
    if current != expected:
        raise RuntimeError(
            "%s: niezgodny kod klienta przy RVA 0x%X" %
            (kind, rva)
        )

    # Gateway: oryginalne bajty + powrot za nadpisany prolog.
    gateway_size = hook_size + 16
    kernel32 = ctypes.windll.kernel32
    gateway = kernel32.VirtualAlloc(
        None,
        ctypes.c_size_t(gateway_size),
        0x3000,
        0x40
    )
    if not gateway:
        raise RuntimeError("VirtualAlloc gateway nieudany: %s" % kind)

    original = ctypes.string_at(target, hook_size)
    gateway_jump_back = _NativeMakeJump(target + hook_size)
    ctypes.memmove(
        ctypes.c_void_p(gateway),
        original + gateway_jump_back,
        len(original + gateway_jump_back)
    )

    callback = callback_factory(gateway)
    callback_address = ctypes.cast(callback, ctypes.c_void_p).value
    patch = _NativeMakeJump(callback_address)
    patch += b"\x90" * (hook_size - len(patch))

    if not _NativeWrite(target, patch):
        raise RuntimeError("VirtualProtect/Write nieudany: %s" % kind)

    return {
        "target": target,
        "size": hook_size,
        "original": original,
        "gateway": gateway,
        "callback": callback,
        "kind": kind,
    }


def _NativeInstallHooks():
    global _NATIVE_HOOKS
    global _NATIVE_HOOK_ACTIVE
    global _NATIVE_HOOK_ERROR

    if _NATIVE_HOOK_ACTIVE:
        return True

    _NATIVE_HOOK_ERROR = ""

    try:
        # CPythonChat::AppendChat(this, type, text, flag)
        def make_chat_callback(gateway):
            original = ctypes.WINFUNCTYPE(
                None,
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_void_p,
                ctypes.c_ubyte
            )(gateway)

            def _hook(this_ptr, chat_type, text_ptr, flag):
                try:
                    if _chat_analyzer_active:
                        _ChatWrite(
                            "NATIVE_CHAT",
                            (
                                "type=%s" % _NativeChatType(chat_type),
                                "flag=%d" % int(flag),
                                _NativeReadText(text_ptr)
                            )
                        )
                except:
                    pass
                return original(this_ptr, chat_type, text_ptr, flag)

            return ctypes.WINFUNCTYPE(
                None,
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_void_p,
                ctypes.c_ubyte
            )(_hook)

        # CWhisper::AppendChat(this, type, text)
        def make_whisper_callback(gateway):
            original = ctypes.WINFUNCTYPE(
                None,
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_void_p
            )(gateway)

            def _hook(this_ptr, chat_type, text_ptr):
                try:
                    if _chat_analyzer_active:
                        _ChatWrite(
                            "NATIVE_WHISPER",
                            (
                                "type=%s" % _NativeChatType(chat_type),
                                _NativeReadText(text_ptr)
                            )
                        )
                except:
                    pass
                return original(this_ptr, chat_type, text_ptr)

            return ctypes.WINFUNCTYPE(
                None,
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_void_p
            )(_hook)

        chat_hook = _NativeInstallOne(
            _NATIVE_CHAT_APPEND_RVA,
            _NATIVE_HOOK_SIZE_CHAT,
            b"\x48\x89\x5c\x24\x10\x55\x56\x57\x41\x54\x41\x55\x41\x56",
            make_chat_callback,
            "CPythonChat::AppendChat"
        )

        whisper_hook = _NativeInstallOne(
            _NATIVE_WHISPER_APPEND_RVA,
            _NATIVE_HOOK_SIZE_WHISPER,
            b"\x48\x89\x5c\x24\x10\x55\x56\x57\x41\x56\x41\x57\x48\x83\xec",
            make_whisper_callback,
            "CWhisper::AppendChat"
        )

        _NATIVE_HOOKS = [chat_hook, whisper_hook]
        _NATIVE_HOOK_ACTIVE = True
        _ChatWriteForce(
            "ANALIZA_NATIVE",
            "HOOKI NATIVE ON: CPythonChat::AppendChat RVA=0x%X; CWhisper::AppendChat RVA=0x%X" %
            (_NATIVE_CHAT_APPEND_RVA, _NATIVE_WHISPER_APPEND_RVA)
        )
        return True
    except Exception as exc:
        _NATIVE_HOOK_ERROR = _ChatSafeText(exc)
        _ChatWriteForce(
            "ANALIZA_NATIVE_ERROR",
            _NATIVE_HOOK_ERROR
        )
        return False


def _NativeRemoveHooks():
    global _NATIVE_HOOKS
    global _NATIVE_HOOK_ACTIVE

    for hook in list(_NATIVE_HOOKS):
        try:
            _NativeWrite(
                hook["target"],
                hook["original"]
            )
        except:
            pass
    _NATIVE_HOOKS = []
    _NATIVE_HOOK_ACTIVE = False


def _InstallChatHooks():
    global _chat_analyzer_active
    # Najpierw natywny hook z analizowanego EXE. To jest główne źródło logu.
    if _NativeInstallHooks():
        _chat_analyzer_active = True
        return True

    # Awaryjny fallback Python API dla innych buildow klienta.
    try:
        import chat as _chat
        installed = []
        for name in ("AppendChat", "AppendChatWithDelay", "AppendWhisper"):
            try:
                original = getattr(_chat, name, None)
                if not callable(original) or getattr(original, "_kowal_chat_analyzer", False):
                    continue

                def _make_wrapper(_name, _original):
                    def _wrapper(*args, **kwargs):
                        _ChatWrite(_name, args)
                        if kwargs:
                            _ChatWrite(_name + "_KW", tuple(
                                ["%s=%s" % (k, _ChatSafeText(v))
                                 for k, v in kwargs.items()]
                            ))
                        return _original(*args, **kwargs)
                    _wrapper._kowal_chat_analyzer = True
                    _wrapper._kowal_chat_original = _original
                    return _wrapper

                wrapper = _make_wrapper(name, original)
                setattr(_chat, name, wrapper)
                if getattr(_chat, name, None) is wrapper:
                    installed.append(name)
            except:
                pass

        if installed:
            _chat_analyzer_active = True
            _ChatWriteForce(
                "ANALIZA",
                "FALLBACK PYTHON HOOK: " + ", ".join(installed)
            )
            return True
    except:
        pass

    _chat_analyzer_active = False
    return False


def _RemoveChatHooks():
    global _chat_analyzer_active
    _NativeRemoveHooks()

    try:
        import chat as _chat
        for name in dir(_chat):
            try:
                current = getattr(_chat, name)
                original = getattr(current, "_kowal_chat_original", None)
                if original is not None:
                    setattr(_chat, name, original)
            except:
                pass
    except:
        pass

    _chat_analyzer_active = False


def _EnsureChatHooks():
    if not _chat_analyzer_active:
        return
    if _NATIVE_HOOK_ACTIVE:
        return
    _InstallChatHooks()


def _StartChatAnalysis():
    global _chat_log_count
    global _chat_analyzer_active

    _chat_log_count = 0
    _ChatWriteForce(
        "ANALIZA",
        "===== START ANALIZY CZATU %s =====" %
        time.strftime("%Y-%m-%d %H:%M:%S")
    )

    # Flaga aktywna podczas instalacji, aby pierwsze natywne komunikaty
    # również mogly zostac zapisane.
    _chat_analyzer_active = True

    if _InstallChatHooks():
        _ChatWriteForce(
            "ANALIZA",
            "REJESTRACJA NATIVE AKTYWNA"
        )
    else:
        _chat_analyzer_active = False
        _ChatWriteForce(
            "ANALIZA_ERROR",
            "Nie udalo sie uruchomic natywnego hooka czatu: %s" %
            _NATIVE_HOOK_ERROR
        )

    if _analyzer:
        _analyzer._Refresh()


def _StopChatAnalysis():
    _ChatWriteForce(
        "ANALIZA",
        "===== STOP ANALIZY CZATU %s =====" %
        time.strftime("%Y-%m-%d %H:%M:%S")
    )
    _RemoveChatHooks()

    if _analyzer:
        _analyzer._Refresh()


class ChatAnalyzerWindow(ui.BoardWithTitleBar):
    def __init__(self):
        ui.BoardWithTitleBar.__init__(self)
        self.SetSize(430, 280)
        self.SetCenterPosition()
        self.AddFlag("movable")
        self.AddFlag("float")
        self.SetTitleName("Analiza | pelny log czatu")
        self.SetCloseEvent(self.Close)

        _MakeLabel(self, "REJESTRACJA CZATU", 20, 40)
        _MakeLabel(self,
                   "Zapisuje wiadomosci przekazywane przez klienta do czatu.",
                   20, 65)
        _MakeLabel(self,
                   "Serwer, gracz, info, szept i pozostale komunikaty czatu.",
                   20, 85)

        self.status = _MakeLabel(self, "STATUS: STOP", 20, 120)
        self.count = _MakeLabel(self, "ZAPISANYCH WIADOMOSCI: 0", 20, 145)
        self.path = _MakeLabel(self, "PLIK: " + _chat_log_file, 20, 170)

        self.start_button = _MakeButton(
            self, "START", 20, 205, self.Start, 110
        )
        self.stop_button = _MakeButton(
            self, "STOP", 140, 205, self.Stop, 110
        )
        _MakeButton(self, "ZAMKNIJ", 290, 205, self.Close, 110)

        self._Refresh()
        self.Show()

    def _Refresh(self):
        self.status.SetText(
            "STATUS: REJESTRACJA ON"
            if _chat_analyzer_active else
            "STATUS: STOP"
        )
        self.count.SetText(
            "ZAPISANYCH WIADOMOSCI: %d" % _chat_log_count
        )

    def Start(self):
        _StartChatAnalysis()

    def Stop(self):
        _StopChatAnalysis()

    def OnUpdate(self):
        self._Refresh()

    def Close(self):
        global _analyzer
        _analyzer = None
        self.Hide()

    def Destroy(self):
        self.Close()


class SettingsWindow(ui.BoardWithTitleBar):

    def __init__(self):
        ui.BoardWithTitleBar.__init__(self)

        self.SetSize(420, 560)
        self.SetCenterPosition()
        self.AddFlag("movable")
        self.AddFlag("float")
        self.SetTitleName("KowalMT2 - Ustawienia")
        self.SetCloseEvent(self.Close)

        self._refresh_timer = 0.0

        self._Build()
        self._Refresh()
        self.Show()

    def _Build(self):

        # ---------------- AUTO POT ----------------

        self.auto_pot_btn = _MakeButton(
            self,
            "AUTO POT: OFF",
            20, 38,
            self._ToggleAutoPot
        )

        self.hp_slot = _MakeSlot(self, 20, 82, 42)
        self.hp_check = _MakeCheck(
            self,
            "Czerwona",
            72, 82,
            self._ToggleHP
        )
        self.hp_label = _MakeLabel(
            self,
            "HP: 50%",
            72, 107
        )
        self.hp_slider = _MakeSlider(
            self,
            72, 125,
            0.50,
            self._HpSlider
        )

        self.sp_slot = _MakeSlot(self, 20, 160, 42)
        self.sp_check = _MakeCheck(
            self,
            "Niebieska",
            72, 160,
            self._ToggleSP
        )
        self.sp_label = _MakeLabel(
            self,
            "SP: 30%",
            72, 185
        )
        self.sp_slider = _MakeSlider(
            self,
            72, 203,
            0.30,
            self._SpSlider
        )

        # ---------------- PICKUP ----------------

        self.pickup_btn = _MakeButton(
            self,
            "AUTO PICKUP: OFF",
            20, 245,
            self._TogglePickup
        )

        self.pickup_label = _MakeLabel(
            self,
            "Czestotliwosc: 200 ms",
            20, 278
        )

        self.pickup_slider = _MakeSlider(
            self,
            20, 298,
            0.095,
            self._PickupSlider
        )

        # ---------------- MOBBER ----------------

        self.mobber_btn = _MakeButton(
            self,
            "MOBBER: OFF",
            20, 330,
            self._ToggleMobber
        )

        self.mobber_slot = _MakeSlot(self, 190, 323, 42)

        self.mobber_label = _MakeLabel(
            self,
            "Peleryna",
            240, 332
        )

        self.mobber_time = _MakeLabel(
            self,
            "1500 ms",
            240, 352
        )

        self.mobber_slider = _MakeSlider(
            self,
            20, 380,
            0.286,
            self._MobberSlider
        )

        # ---------------- DOPALACZE ----------------

        self.boosters_btn = _MakeButton(
            self,
            "DOPALACZE: OFF",
            20, 415,
            self._ToggleBoosters
        )

        self.boosters_edit = _MakeButton(
            self,
            "EDYTUJ",
            190, 415,
            self.OpenBoosters
        )

        # ---------------- AUTO SKILE ----------------
        # Użytkownik nie dostaje ON/OFF. To tylko konfiguracja.

        self.skills_edit = _MakeButton(
            self,
            "EDYTUJ AUTO SKILE",
            20, 455,
            self.OpenSkills
        )

        _MakeIcon(
            self.skills_edit,
            "skile.png",
            5, 2,
            28, 28
        )

        # Ikona Edytuj. Gdy klient nie przyjmie PNG, zwykły
        # przycisk nadal działa.
        _MakeIcon(
            self.boosters_edit,
            "edit_1.png",
            5, 2,
            28, 28
        )

        # ---------------- AUTO LOGIN ----------------
        self.auto_login_check = _MakeCheck(
            self,
            "AUTO LOGIN po rozlaczeniu",
            20, 500,
            self._ToggleAutoLogin
        )
        self.resume_farmbot_check = _MakeCheck(
            self,
            "Wznow FarmBot po zalogowaniu",
            20, 525,
            self._ToggleResumeFarmBot
        )

    def _ToggleAutoLogin(self, state):
        _settings_data["auto_login"] = bool(state)
        # Klient posiada juz obsluge auto-loginu AutoHunt. Ustawiamy tylko
        # flage; dane konta/postaci pozostaja w natywnym autoHuntAutoLoginDict.
        try:
            if constInfo and hasattr(constInfo, "autoHuntAutoLoginDict"):
                constInfo.autoHuntAutoLoginDict["status"] = 1 if state else 0
        except:
            pass
        _Save()

    def _ToggleResumeFarmBot(self, state):
        _settings_data["resume_farmbot"] = bool(state)
        try:
            FarmBot._cfg["auto_login"] = bool(state)
            FarmBot._cfg["resume_after_login"] = bool(state)
            FarmBot._save()
        except:
            pass
        _Save()

    def _ToggleAutoPot(self):
        _settings_data["autopot"] = not _settings_data["autopot"]
        AutoPot.SetEnabled(_settings_data["autopot"])
        _Save()
        self._Refresh()

    def _ToggleHP(self, state):
        _settings_data["use_hp"] = bool(state)
        AutoPot.SetUseTypes(
            _settings_data["use_hp"],
            _settings_data["use_sp"]
        )
        _Save()

    def _ToggleSP(self, state):
        _settings_data["use_sp"] = bool(state)
        AutoPot.SetUseTypes(
            _settings_data["use_hp"],
            _settings_data["use_sp"]
        )
        _Save()

    def _HpSlider(self):
        value = int(
            round(self.hp_slider.GetSliderPos() * 98.0)
        ) + 1

        _settings_data["hp"] = max(1, min(99, value))
        AutoPot.SetThresholds(
            _settings_data["hp"],
            _settings_data["sp"]
        )

        _Save()
        self.hp_label.SetText(
            "HP: %d%%" % _settings_data["hp"]
        )

    def _SpSlider(self):
        value = int(
            round(self.sp_slider.GetSliderPos() * 98.0)
        ) + 1

        _settings_data["sp"] = max(1, min(99, value))
        AutoPot.SetThresholds(
            _settings_data["hp"],
            _settings_data["sp"]
        )

        _Save()
        self.sp_label.SetText(
            "SP: %d%%" % _settings_data["sp"]
        )

    def _TogglePickup(self):
        _settings_data["autopickup"] = not _settings_data["autopickup"]
        Pickup.SetEnabled(_settings_data["autopickup"])
        _Save()
        self._Refresh()

    def _PickupSlider(self):
        value = int(
            round(
                self.pickup_slider.GetSliderPos() *
                1990.0
            )
        ) + 10

        _settings_data["pickup_interval"] = value
        Pickup.SetInterval(value)
        _Save()

        self.pickup_label.SetText(
            "Czestotliwosc: %d ms" % value
        )

    def _ToggleMobber(self):
        _settings_data["mobber"] = not _settings_data["mobber"]
        Mobber.SetEnabled(_settings_data["mobber"])
        _Save()
        self._Refresh()

    def _MobberSlider(self):
        value = int(
            round(
                self.mobber_slider.GetSliderPos() *
                4900.0
            )
        ) + 100

        _settings_data["mobber_interval"] = value
        Mobber.SetInterval(value)
        _Save()

        self.mobber_time.SetText(
            "%d ms" % value
        )

    def _ToggleBoosters(self):
        _settings_data["boosters_enabled"] = not _settings_data["boosters_enabled"]
        Boosters.SetEnabled(
            _settings_data["boosters_enabled"]
        )
        _Save()
        self._Refresh()

    def OpenBoosters(self):
        global _booster_editor

        if _booster_editor:
            _booster_editor.SetTop()
            return

        _booster_editor = BoosterEditor()

    def OpenSkills(self):
        global _skill_editor

        if _skill_editor:
            _skill_editor.SetTop()
            return

        _skill_editor = SkillEditor()

    def _RefreshPotionIcons(self):
        try:
            hp_vnum, hp_slot, sp_vnum, sp_slot = AutoPot.GetDetectedPotions()

            self.hp_slot.ClearSlot(0)
            self.sp_slot.ClearSlot(0)

            if hp_vnum > 0 and hp_slot >= 0:
                self.hp_slot.SetItemSlot(
                    0,
                    hp_vnum,
                    player.GetItemCount(hp_slot)
                )

            if sp_vnum > 0 and sp_slot >= 0:
                self.sp_slot.SetItemSlot(
                    0,
                    sp_vnum,
                    player.GetItemCount(sp_slot)
                )
        except:
            pass

    def _RefreshMobberIcon(self):
        try:
            vnum, slot = Mobber.GetDetectedCape()

            self.mobber_slot.ClearSlot(0)

            if vnum > 0 and slot >= 0:
                self.mobber_slot.SetItemSlot(
                    0,
                    vnum,
                    player.GetItemCount(slot)
                )
        except:
            pass

    def _Refresh(self):
        self.auto_pot_btn.SetText(
            "AUTO POT: ON"
            if _settings_data["autopot"]
            else "AUTO POT: OFF"
        )

        self.pickup_btn.SetText(
            "AUTO PICKUP: ON"
            if _settings_data["autopickup"]
            else "AUTO PICKUP: OFF"
        )

        self.mobber_btn.SetText(
            "MOBBER: ON"
            if _settings_data["mobber"]
            else "MOBBER: OFF"
        )

        self.boosters_btn.SetText(
            "DOPALACZE: ON"
            if _settings_data["boosters_enabled"]
            else "DOPALACZE: OFF"
        )

        self.hp_check.SetCheckStatus(
            _settings_data["use_hp"]
        )

        self.sp_check.SetCheckStatus(
            _settings_data["use_sp"]
        )

        self.hp_label.SetText(
            "HP: %d%%" % _settings_data["hp"]
        )

        self.sp_label.SetText(
            "SP: %d%%" % _settings_data["sp"]
        )

        self.pickup_label.SetText(
            "Czestotliwosc: %d ms" %
            _settings_data["pickup_interval"]
        )

        self.mobber_time.SetText(
            "%d ms" % _settings_data["mobber_interval"]
        )

        self.hp_slider.SetSliderPos(
            float(_settings_data["hp"] - 1) / 98.0
        )

        self.sp_slider.SetSliderPos(
            float(_settings_data["sp"] - 1) / 98.0
        )

        self.pickup_slider.SetSliderPos(
            float(_settings_data["pickup_interval"] - 10) / 1990.0
        )

        self.mobber_slider.SetSliderPos(
            float(_settings_data["mobber_interval"] - 100) / 4900.0
        )

        self.auto_login_check.SetCheckStatus(
            bool(_settings_data.get("auto_login", False))
        )
        self.resume_farmbot_check.SetCheckStatus(
            bool(_settings_data.get("resume_farmbot", True))
        )

        self._RefreshPotionIcons()
        self._RefreshMobberIcon()

    def OnUpdate(self):
        now = app.GetTime()

        if now - self._refresh_timer >= 1.0:
            self._refresh_timer = now
            self._RefreshPotionIcons()
            self._RefreshMobberIcon()

    def Close(self):
        global _settings
        _settings = None
        self.Hide()

    def Destroy(self):
        self.Close()


class MainPanel(ui.BoardWithTitleBar):

    def __init__(self):
        ui.BoardWithTitleBar.__init__(self)

        self.SetSize(300, 230)
        self.SetCenterPosition()
        self.AddFlag("movable")
        self.AddFlag("float")
        self.SetTitleName("KowalMT2 Panel")
        self.SetCloseEvent(self.Close)

        self.settings_button = _MakeButton(
            self,
            "USTAWIENIA",
            55, 45,
            self.OpenSettings
        )

        self.close_button = _MakeButton(
            self,
            "ZAMKNIJ",
            55, 85,
            self.Close
        )

        self.farmbot_button = _MakeButton(
            self,
            "FARMBOT",
            55, 125,
            FarmBot.Open
        )

        self.analysis_button = _MakeButton(
            self,
            "ANALIZA",
            55, 165,
            self.OpenAnalyzer
        )

        self.Show()

    def OpenSettings(self):
        global _settings

        if _settings:
            _settings.SetTop()
            return

        _settings = SettingsWindow()

    def OpenAnalyzer(self):
        global _analyzer

        if _analyzer:
            _analyzer.SetTop()
            return

        _analyzer = ChatAnalyzerWindow()

    def Close(self):
        global _panel
        _panel = None
        self.Hide()

    def Destroy(self):
        self.Close()


def _OpenPanel():
    global _panel

    if _panel:
        _panel.SetTop()
        return

    _panel = MainPanel()


def _OnKeyDown(self, key):
    if key == app.DIK_HOME:
        _OpenPanel()
        return True

    if _original_on_key_down:
        return _original_on_key_down(self, key)

    return False


def _OnUpdate(self):
    _EnsureChatHooks()

    if _original_on_update:
        _original_on_update(self)

    try:
        AutoPot.Update()
    except:
        pass

    try:
        Pickup.Update()
    except:
        pass

    try:
        Mobber.Update()
    except:
        pass

    try:
        Boosters.Update()
    except:
        pass

    try:
        AutoSkills.Update()
    except:
        pass

    try:
        FarmBot.Update()
    except:
        pass


_original_on_key_down = game.GameWindow.OnKeyDown
game.GameWindow.OnKeyDown = _OnKeyDown

_original_on_update = game.GameWindow.OnUpdate
game.GameWindow.OnUpdate = _OnUpdate
