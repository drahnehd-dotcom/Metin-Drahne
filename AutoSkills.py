# -*- coding: utf-8 -*-
"""F8 Farm Auto Skills extracted from the original uiFarmSkills controller.
External version for D:\\KowalMT2\\data\\me.
"""
import app
import chat
import net
import player
import skill
import ui
import constInfo

_enabled = False
_controller = None
_saved_slots = []


def _config():
    try:
        cfg = getattr(constInfo, "F8_FARM_SKILL_CONFIG", {})
        return dict(cfg) if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _save_config(slots):
    try:
        cfg = _config()
        cfg["slots"] = [int(x) for x in slots]
        constInfo.F8_FARM_SKILL_CONFIG = cfg
    except Exception:
        pass


class FarmSkillController(object):
    ROW_H = 43
    MAX_SCAN_SLOTS = 96

    def __init__(self):
        self.rows = []
        self.selected = {}
        self.remount_at = 0.0
        self.remount_pending = False
        self.was_mounted = False
        self.pending_skill_slot = -1
        self.pending_skill_idx = 0
        self.last_mount_command = -9999.0
        self.remount_deadline = 0.0
        self.last_cast = {}
        self.window = None
        self.board = None
        self._Build()
        self.LoadConfig(_saved_slots if _saved_slots else _config().get("slots", []))
        self.RefreshSkills()
        self.window.Hide()

    def _Build(self):
        self.window = ui.ScriptWindow()
        self.window.SetSize(330, 360)
        self.window.SetPosition(500, 180)

        self.board = ui.BoardWithTitleBar()
        self.board.SetParent(self.window)
        self.board.SetSize(330, 360)
        self.board.SetPosition(0, 0)
        self.board.SetTitleName("Auto Skile F8")
        self.board.SetCloseEvent(ui.__mem_func__(self.Hide))
        self.board.Show()

        self.info = ui.TextLine()
        self.info.SetParent(self.board)
        self.info.SetPosition(12, 30)
        self.info.SetText("Skile z okna V. Zaznacz te, ktore maja byc uzywane.")
        self.info.Show()

        self.refreshBtn = ui.Button()
        self.refreshBtn.SetParent(self.board)
        self.refreshBtn.SetPosition(12, 52)
        self.refreshBtn.SetUpVisual("d:/ymir work/ui/public/middle_button_01.sub")
        self.refreshBtn.SetOverVisual("d:/ymir work/ui/public/middle_button_02.sub")
        self.refreshBtn.SetDownVisual("d:/ymir work/ui/public/middle_button_03.sub")
        self.refreshBtn.SetText("ODSWIEZ SKILE")
        self.refreshBtn.SetEvent(ui.__mem_func__(self.RefreshSkills))
        self.refreshBtn.Show()

        self.status = ui.TextLine()
        self.status.SetParent(self.board)
        self.status.SetPosition(150, 58)
        self.status.SetText("Wybrano: 0")
        self.status.Show()

        self.rows_board = ui.Window()
        self.rows_board.SetParent(self.board)
        self.rows_board.SetPosition(8, 82)
        self.rows_board.SetSize(314, 225)
        self.rows_board.Show()

        self.masterBtn = ui.Button()
        self.masterBtn.SetParent(self.board)
        self.masterBtn.SetPosition(12, 318)
        self.masterBtn.SetUpVisual("d:/ymir work/ui/public/middle_button_01.sub")
        self.masterBtn.SetOverVisual("d:/ymir work/ui/public/middle_button_02.sub")
        self.masterBtn.SetDownVisual("d:/ymir work/ui/public/middle_button_03.sub")
        self.masterBtn.SetEvent(ui.__mem_func__(self.ToggleEnabled))
        self.masterBtn.Show()
        self._RefreshMaster()

    def _skill_type_allowed(self, skill_index):
        try:
            st = skill.GetSkillType(int(skill_index))
            passive = getattr(skill, "SKILL_TYPE_PASSIVE", -9999)
            guild = getattr(skill, "SKILL_TYPE_GUILD", -9998)
            return st not in (passive, guild)
        except Exception:
            return True

    def _collect_skills(self):
        result = []
        riding = getattr(player, "SKILL_INDEX_RIDING", -99999)
        seen = set()
        for slot in range(self.MAX_SCAN_SLOTS):
            try:
                idx = int(player.GetSkillIndex(slot))
                level = int(player.GetSkillLevel(slot))
            except Exception:
                continue
            if idx <= 0 or level <= 0 or idx in seen:
                continue
            if idx == riding:
                continue
            if not self._skill_type_allowed(idx):
                continue
            seen.add(idx)
            try:
                name = skill.GetSkillName(idx)
            except Exception:
                name = "Skill %d" % idx
            result.append((slot, idx, level, name))
        return result

    def RefreshSkills(self):
        for row in self.rows:
            for obj in row[:3]:
                try:
                    obj.Hide()
                except Exception:
                    pass
        self.rows = []

        skills = self._collect_skills()
        y = 0
        for slot, idx, level, name in skills:
            if y >= 215:
                break

            icon = ui.SlotWindow()
            icon.SetParent(self.rows_board)
            icon.SetPosition(0, y)
            icon.SetSize(40, 40)
            icon.AppendSlot(0, 0, 0, 40, 40)
            try:
                grade = int(player.GetSkillGrade(slot))
            except Exception:
                grade = 0
            try:
                icon.SetSkillSlotNew(0, idx, grade, level)
            except Exception:
                pass
            icon.Show()

            label = ui.TextLine()
            label.SetParent(self.rows_board)
            label.SetPosition(48, y + 5)
            label.SetText("%s [slot %d]" % (name, slot))
            label.Show()

            box = ui.RespCheckBox()
            box.SetParent(self.rows_board)
            box.SetPosition(274, y + 8)
            box.SetEvent(ui.__mem_func__(lambda _unused=None, s=slot: self._toggle_slot(s)))
            box.SetUncheckEvent(ui.__mem_func__(lambda _unused=None, s=slot: self._toggle_slot(s)))
            box.SetCheck(bool(self.selected.get(slot, False)))
            box.Show()

            self.rows.append((icon, label, box, slot, idx, name))
            y += self.ROW_H

        self._refresh_status()

    def _toggle_slot(self, slot):
        for row in self.rows:
            if row[3] == slot:
                self.selected[slot] = bool(row[2].IsChecked())
                break
        self._refresh_status()
        self._save_config()

    def _refresh_status(self):
        count = len([x for x in self.selected.values() if x])
        self.status.SetText("Wybrano: %d" % count)

    def _save_config(self):
        _save_config(self.GetSelectedSlots())

    def GetSelectedSlots(self):
        return [int(slot) for slot, enabled in self.selected.items() if enabled]

    def LoadConfig(self, slots):
        self.selected = {}
        for slot in slots or []:
            try:
                self.selected[int(slot)] = True
            except Exception:
                pass
        self._refresh_status()

    def Open(self):
        self.RefreshSkills()
        self._RefreshMaster()
        self.window.Show()
        self.window.SetTop()

    def Hide(self):
        try:
            self.window.Hide()
        except Exception:
            pass

    def IsShow(self):
        try:
            return self.window.IsShow()
        except Exception:
            return False

    def ToggleEnabled(self):
        global _enabled
        _enabled = not _enabled
        self._RefreshMaster()
        _save_config(self.GetSelectedSlots())

    def SetEnabled(self, value):
        global _enabled
        _enabled = bool(value)
        self._RefreshMaster()

    def IsEnabled(self):
        return bool(_enabled)

    def _RefreshMaster(self):
        try:
            self.masterBtn.SetText("AUTO SKILE: %s" % ("ON" if _enabled else "OFF"))
        except Exception:
            pass

    def _can_cast(self, slot):
        try:
            idx = int(player.GetSkillIndex(slot))
            if idx <= 0 or int(player.GetSkillLevel(slot)) <= 0:
                return False, idx
            if player.IsSkillCoolTime(slot):
                return False, idx
            if not skill.CanUseSkill(idx):
                return False, idx
            return True, idx
        except Exception:
            return False, 0

    def Tick(self, farm_running=True):
        if not _enabled or not farm_running:
            return

        now = app.GetTime()

        if self.pending_skill_slot >= 0:
            try:
                mounted = bool(player.IsMountingHorse())
            except Exception:
                mounted = False
            if mounted:
                return
            if now < self.remount_at:
                return

            slot = int(self.pending_skill_slot)
            self.pending_skill_slot = -1
            idx = int(self.pending_skill_idx)
            self.pending_skill_idx = 0
            try:
                if idx > 0:
                    player.ClickSkillSlot(slot)
                    self.last_cast[slot] = now
                    chat.AppendChat(chat.CHAT_TYPE_INFO, "[F8 Farma] Uzywam skilla: %s" % skill.GetSkillName(idx))
                    if self.was_mounted:
                        self.remount_pending = True
                        self.remount_at = now + 0.75
                        self.remount_deadline = now + 8.0
                        self.last_mount_command = -9999.0
                    else:
                        self.was_mounted = False
                    return
            except Exception:
                pass

        if self.remount_pending:
            try:
                mounted = bool(player.IsMountingHorse())
            except Exception:
                mounted = False
            if mounted:
                self.remount_pending = False
                self.was_mounted = False
                self.remount_deadline = 0.0
            else:
                if now >= self.remount_at and now - float(self.last_mount_command) >= 0.65:
                    try:
                        net.SendChatPacket('/user_horse_ride')
                        self.last_mount_command = now
                    except Exception:
                        pass
                    if self.remount_deadline <= 0.0:
                        self.remount_deadline = now + 8.0
                if self.remount_deadline > 0.0 and now < self.remount_deadline:
                    return
                if self.remount_deadline > 0.0 and now >= self.remount_deadline:
                    self.remount_pending = False
                    self.was_mounted = False
                    self.remount_deadline = 0.0

        for slot in self.GetSelectedSlots():
            if now - float(self.last_cast.get(slot, -9999.0)) < 0.25:
                continue
            can_cast, idx = self._can_cast(slot)
            if not can_cast:
                continue

            try:
                is_active = bool(player.IsSkillActive(slot))
            except Exception:
                is_active = False

            try:
                if skill.IsToggleSkill(idx):
                    is_attack = False
                else:
                    st = skill.GetSkillType(idx)
                    active_type = getattr(skill, "SKILL_TYPE_ACTIVE", -9999)
                    is_attack = (st == active_type)
            except Exception:
                is_attack = True

            if not is_attack and is_active:
                continue

            if is_attack:
                try:
                    if int(player.GetTargetVID()) <= 0:
                        continue
                except Exception:
                    continue

            try:
                mounted = bool(player.IsMountingHorse())
            except Exception:
                mounted = False

            if mounted:
                try:
                    net.SendChatPacket('/unmount')
                except Exception:
                    continue
                self.was_mounted = True
                self.pending_skill_slot = int(slot)
                self.pending_skill_idx = int(idx)
                self.remount_at = now + 0.75
                return

            try:
                player.ClickSkillSlot(int(slot))
                self.last_cast[slot] = now
                chat.AppendChat(chat.CHAT_TYPE_INFO, "[F8 Farma] Uzywam skilla: %s" % skill.GetSkillName(idx))
                return
            except Exception:
                continue



def _GetController():
    global _controller
    if _controller is None:
        _controller = FarmSkillController()
    return _controller


def Open():
    return _GetController().Open()


def Hide():
    if _controller:
        _controller.Hide()


def RefreshSkills():
    return _GetController().RefreshSkills()


def SetEnabled(value):
    global _enabled
    _enabled = bool(value)
    if _controller is not None:
        _controller._RefreshMaster()


def IsEnabled():
    return bool(_enabled)


def LoadCharacterSkills():
    c = _GetController()
    c.RefreshSkills()
    return c.GetSelectedSlots()


def GetSelectedSlots():
    return _GetController().GetSelectedSlots()


def Export():
    return {
        "slots": GetSelectedSlots(),
        "enabled": bool(_enabled),
    }


def Load(value):
    global _enabled, _saved_slots
    if isinstance(value, dict):
        _saved_slots = list(value.get("slots", []))
        _enabled = bool(value.get("enabled", False))
    elif isinstance(value, list):
        _saved_slots = list(value)
    if _controller is not None:
        _controller.LoadConfig(_saved_slots)
        _controller._RefreshMaster()


def Update():
    if _controller is not None:
        _controller.Tick(True)
