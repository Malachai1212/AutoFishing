from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
import sys, os
import time
import threading
import cv2, pyautogui, numpy, keyboard
import json
import ctypes
import ctypes.wintypes as wt
import re

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("WARNING: pytesseract not installed - item names will not be captured")

# --- Raw Win32 SendInput for Roblox UI clicks ---
user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE        = 0x0001
MOUSEEVENTF_LEFTDOWN    = 0x0002
MOUSEEVENTF_LEFTUP      = 0x0004
MOUSEEVENTF_ABSOLUTE    = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG),
                ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p)]

class _IU(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("iu", _IU)]

def _send(*events):
    arr = (INPUT * len(events))(*events)
    user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))

def _mi(flags, dx=0, dy=0):
    return INPUT(INPUT_MOUSE, _IU(MOUSEINPUT(dx, dy, 0, flags, 0, None)))

def _abs_coords(x, y):
    sx = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    sy = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return int(x * 65535 / (sx - 1)), int(y * 65535 / (sy - 1))

def directClick(x, y):
    """Move-nudge-click pattern that works with Roblox GUI buttons.
    Roblox only processes click edges when a fresh mouse-move event
    arrives in its raw input queue. A tiny relative nudge (+1 then -1)
    forces that queue flush. Restores cursor to original position after."""
    # 0. Save current cursor position
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    saved_x, saved_y = pt.x, pt.y

    # 1. Bring Roblox to foreground
    hwnd = user32.FindWindowW(None, "Roblox")
    if hwnd:
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.05)

    # 2. Absolute move to target
    ax, ay = _abs_coords(int(x), int(y))
    _send(_mi(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay))
    time.sleep(0.03)

    # 3. CRITICAL: relative nudge to unstick Roblox input queue
    _send(_mi(MOUSEEVENTF_MOVE, 1, 0))
    _send(_mi(MOUSEEVENTF_MOVE, -1, 0))
    time.sleep(0.03)

    # 4. Click
    _send(_mi(MOUSEEVENTF_LEFTDOWN))
    time.sleep(0.05)
    _send(_mi(MOUSEEVENTF_LEFTUP))
    time.sleep(0.3)

    # 5. Restore cursor to original position (with nudge so Roblox sees it)
    rx, ry = _abs_coords(saved_x, saved_y)
    _send(_mi(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, rx, ry))
    time.sleep(0.02)
    _send(_mi(MOUSEEVENTF_MOVE, 1, 0))
    _send(_mi(MOUSEEVENTF_MOVE, -1, 0))

from modules.SimpleComponents import Button, Label
from modules.GlobalVariables import *
from modules.SettingsWindow import SettingsWindow
from modules.LogsWindow import LogsWindow

# Vetex, this message is for you. If I get caught, I think I deserve to be praised...

# Ha-ha
# while I was writing the program I spent 10 days and caught only two sunken treasures (i caught 5000+ fish)
# but i got Expert Angler title, hah

def locateImage(img, threshold: float):
    screenshot = pyautogui.screenshot()
    screenshot = numpy.array(screenshot)
    screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
    image = numpy.uint8(img)
    result = cv2.matchTemplate(screenshot, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    if max_val >= threshold:
        return (max_loc[0], max_loc[1])
    return None

def getLastSize() -> list[int]:
    file = open("DB.json", "r")
    data = json.loads(file.read())
    size = data["screenSize"][0]
    return [size["width"], size["height"]]

def changeLastSize(newSize: list[int]) -> None:
    with open("DB.json", "r") as file:
        data = json.loads(file.read())
        settings = data["settings"][0]
    newDBobject = {
        "settings": [settings],
        "screenSize": [{
            "width": newSize[0],
            "height": newSize[1]
        }]}
    with open('DB.json', 'w') as file:
        json.dump(newDBobject, file)

def changeImageSize(path: str, monitorSize: list[int], lastUsedSize: list[int]) -> None:
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"WARNING: Could not read image: {path}")
        return
    imgW = img.shape[1]
    imgH = img.shape[0]
    ratioW = monitorSize[0] * 100 / lastUsedSize[0] * 0.01
    ratioH = monitorSize[1] * 100 / lastUsedSize[1] * 0.01
    targetSize = (int(ratioW*imgW)+4, int(ratioH*imgH)+1)
    outIMG = cv2.resize(img, targetSize, cv2.INTER_LINEAR)
    cv2.imwrite(path, outIMG)

class MainWindow(QMainWindow):
    title: str = "title"
    isFishing: bool = False
    tryCatchFish: bool = False
    startThisTry: float = 0
    maxTimeForWait: int = 70
    startFishingTimer: float = 0
    startCheckMealTimer: float = 0
    checkMealTimer: int = 0
    startCheckPotionTimer: float = 0
    checkPotionTimer: int = 0
    startCheckFleetTimer: float = 0
    checkFleetTimer: int = 0
    shouldStopFishing: bool = False
    fishCount: int = 0

    def __init__(self, title: str):
        super().__init__()

        self.title: str = title
        self.icon = APP_ICON
        
        self.setObjectName("MainWindow")

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon(self.icon))
        self.setFixedSize(300, 30)
        self.move((screenSize.width() // 2) - (self.width() // 2), 0)
        self.setStyleSheet(CSS)

        self.fishingThread = threading.Thread(target = self.fishing)

        self.settingsWindow = SettingsWindow(self)
        self.logsWindow = LogsWindow(self)

        self.btn_start = Button(self, "START", 2, 2, 75, 26, "btn_standart", self.startFishing)
        self.btn_start.setToolTip("Start fishing")
        btn_close = Button(self, EXIT_ICON, self.width() - 28, 2, 26, 26, "btn_red", self.closeEvent)
        btn_close.setToolTip("Close window")
        btn_settings = Button(self, SETTING_ICON, self.width() - 56, 2, 26, 26, "btn_standart", self.openSettings)
        btn_settings.setToolTip("Settings window")
        btn_logs = Button(self, LOGS_ICON, self.width() - 84, 2, 26, 26, "btn_standart", self.openLogsWindow)
        btn_logs.setToolTip("History window")
        self.__countLabel = Label(self, 79, 2, 135, 26, "", f"Caught: {self.fishCount}")

        self.ShouldStopFishingTimer = QTimer(self)
        self.ShouldStopFishingTimer.setInterval(500)
        self.ShouldStopFishingTimer.timeout.connect(self.checkShouldStopFishing)
        self.ShouldStopFishingTimer.start()

    def openSettings(self) -> None:
        if self.settingsWindow.isVisible():
            self.settingsWindow.hide()
        else:
            self.settingsWindow.show()

    def openLogsWindow(self) -> None:
        if self.logsWindow.isVisible():
            self.logsWindow.hide()
        else:
            self.logsWindow.show()

    def startFishing(self) -> None:
        self.isFishing = not (self.isFishing)
        if self.isFishing and not self.shouldStopFishing:
            self.btn_start.setObjectName("btn_red")
            self.btn_start.setText("STOP")
            self.btn_start.setToolTip("Stop fishing")
            self.isFishing = True
            self.startFishingTimer = time.time()
            self.startCheckMealTimer = time.time()
            self.startCheckPotionTimer = time.time()
            self.startCheckFleetTimer = time.time()
            drachma = self.readDrachma()
            self.logsWindow.logs.append([time.localtime(), "start", f"{drachma} Drachma" if drachma else ""])
            self.setStyleSheet(CSS)
        else:
            self.shouldStopFishing = True

    def checkShouldStopFishing(self) -> None:
        if self.shouldStopFishing:
            self.btn_start.setObjectName("btn_standart")
            self.btn_start.setText("START")
            self.btn_start.setToolTip("Start fishing")
            self.isFishing = False
            self.tryCatchFish = False
            drachma = self.readDrachma()
            self.logsWindow.logs.append([time.localtime(), "stop", f"{drachma} Drachma" if drachma else ""])
            self.setStyleSheet(CSS)
            self.shouldStopFishing = False
        self.ShouldStopFishingTimer.start()

    def closeEvent(self, event) -> None:
        self.settingsWindow.close()
        self.logsWindow.close()
        self.close()

    def fishing(self) -> None:
        while self.isVisible():
            if self.isFishing:
                self.timeForWait = time.time() - self.startFishingTimer
                self.checkMealTimer = time.time() - self.startCheckMealTimer
                self.checkPotionTimer = time.time() - self.startCheckPotionTimer
                self.checkFleetTimer = time.time() - self.startCheckFleetTimer
                if locateImage(IMG_START, 0.7):
                    self.tryCatchFish = True
                    self.startThisTry = time.time()
                    while self.tryCatchFish:
                        pyautogui.click(button = "left")
                        timeForThisTry = time.time() - self.startThisTry

                        if (locateImage(IMG_FISH, 0.8) or locateImage(IMG_JUNK, 0.8)) and (timeForThisTry <= self.settingsWindow.timeForTry):
                            catch_ss = pyautogui.screenshot()
                            item = self.readCatchName(catch_ss)
                            self.endTry("fish", item)
                            self.addFishCount()
                        elif locateImage(IMG_TREASURE, 0.7) and (timeForThisTry <= self.settingsWindow.timeForTry) and self.tryCatchFish:
                            catch_ss = pyautogui.screenshot()
                            item = self.readCatchName(catch_ss)
                            self.endTry("treasure", item)
                            self.addFishCount()
                        elif locateImage(IMG_SUNKEN, 0.8) and (timeForThisTry <= self.settingsWindow.timeForTry) and self.tryCatchFish:
                            catch_ss = pyautogui.screenshot()
                            item = self.readCatchName(catch_ss)
                            self.endTry("sunken", item)
                            self.addFishCount()
                        elif timeForThisTry > self.settingsWindow.timeForTry:
                            time.sleep(1)
                            self.endTry("timeError")
                        else:
                            pyautogui.click(button = "left")

                elif self.timeForWait >= self.maxTimeForWait:
                    if locateImage(IMG_DISCONNECTED, 0.8): self.shouldStopFishing = True
                    else: self.endTry("timeError")

                elif (self.checkMealTimer >= self.settingsWindow.mealTimer) and (self.settingsWindow.useMeal):
                    keyboard.press_and_release(f"{self.settingsWindow.mealKey}")
                    pyautogui.click(button = "left")
                    time.sleep(0.75)
                    keyboard.press_and_release(f"{self.settingsWindow.rodKey}")
                    self.selectBait()
                    pyautogui.click(button = "left")
                    self.logsWindow.logs.append([time.localtime(), "consumeMeal"])
                    self.startFishingTimer = time.time()
                    self.startCheckMealTimer = time.time()
                elif (self.checkPotionTimer >= self.settingsWindow.potionTimer) and (self.settingsWindow.usePotion):
                    keyboard.press_and_release(f"{self.settingsWindow.potionKey}")
                    if self.settingsWindow.potionKey != "e":
                        pyautogui.click(button = "left")
                        time.sleep(0.75)
                        keyboard.press_and_release(f"{self.settingsWindow.rodKey}")
                        self.selectBait()
                        pyautogui.click(button = "left")
                    self.logsWindow.logs.append([time.localtime(), "consumePotion"])
                    self.startFishingTimer = time.time()
                    self.startCheckPotionTimer = time.time()

                elif (self.checkFleetTimer >= self.settingsWindow.fleetRepairTimer) and (self.settingsWindow.useFleetRepair):
                    repair_cost = self.repairFleet()
                    cost_str = f"{repair_cost} Drachma" if repair_cost else ""
                    self.logsWindow.logs.append([time.localtime(), "repairFleet", cost_str])
                    self.startFishingTimer = time.time()
                    self.startCheckFleetTimer = time.time()

                time.sleep(0.25)

    def _extractItemName(self, text: str) -> str:
        """Extract item name from OCR text, handling garbled 'You caught a/an' prefixes
        and leading junk from item image contamination."""
        # Pattern 1: find "a/an" followed by a capitalized word (handles all garbled prefixes)
        m = re.search(r'\ba\s+([A-Z][A-Za-z].*?)$', text)
        if m:
            return m.group(1).strip()
        m = re.search(r'\ban\s+([A-Z][A-Za-z].*?)$', text)
        if m:
            return m.group(1).strip()

        # Pattern 2: clean "You caught a/an" prefix
        cleaned = re.sub(r'^.*?[Yy]ou\s*caught\s+(?:an?\s+)?', '', text).strip()
        if cleaned and cleaned != text:
            return cleaned

        # Pattern 3: find first capitalized word and take everything from there
        # (strips lowercase junk/symbols from item image contamination)
        m = re.search(r'([A-Z][A-Za-z][\w\s\'\-]*)', text)
        if m and sum(c.isalpha() for c in m.group(1)) >= 3:
            return m.group(1).strip()

        return text

    def readCatchName(self, pil_screenshot=None) -> str:
        """OCR the item name from the catch notification.
        Locates the header by matching existing catch templates (IMG_FISH, IMG_JUNK,
        IMG_TREASURE, IMG_SUNKEN) in the screenshot, then reads the item name just below."""
        if not HAS_OCR:
            return ""
        try:
            if pil_screenshot is not None:
                ss = numpy.array(pil_screenshot)
                ss = cv2.cvtColor(ss, cv2.COLOR_RGB2BGR)
            else:
                ss = numpy.array(pyautogui.screenshot())
                ss = cv2.cvtColor(ss, cv2.COLOR_RGB2BGR)

            # Find the catch header using the same templates that detected the catch
            best_loc = None
            best_val = 0
            best_tmpl_h = 0
            best_tmpl_w = 0
            for tmpl in [IMG_FISH, IMG_JUNK, IMG_TREASURE, IMG_SUNKEN]:
                if tmpl is None:
                    continue
                result = cv2.matchTemplate(ss, tmpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if max_val > best_val:
                    best_val = max_val
                    best_loc = max_loc
                    best_tmpl_h = tmpl.shape[0]
                    best_tmpl_w = tmpl.shape[1]

            if best_val < 0.5 or best_loc is None:
                print(f"readCatchName: header not found (best match {best_val:.2f})")
                return ""

            h, w = ss.shape[:2]
            # Item name sits just below the matched header, right-aligned
            # Start from center of header match to avoid item image on the left
            strip_top = best_loc[1] + best_tmpl_h + 2
            strip_bot = min(strip_top + 28, h)
            strip_left = best_loc[0] + int(best_tmpl_w * 0.5)
            strip_right = min(best_loc[0] + best_tmpl_w + 150, w)

            item_strip = ss[strip_top:strip_bot, strip_left:strip_right, :]
            if item_strip.size == 0:
                print("readCatchName: item strip is empty")
                return ""

            gray = cv2.cvtColor(item_strip, cv2.COLOR_BGR2GRAY)

            # Upscale 3x — text is too small for pytesseract at native resolution
            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

            preprocessed = [
                cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
                cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY, 21, 5),
            ]

            for i, img in enumerate(preprocessed):
                text = pytesseract.image_to_string(img, config='--psm 7').strip()
                if text and sum(c.isalpha() for c in text) >= 3:
                    name = self._extractItemName(text)
                    if name and sum(c.isalpha() for c in name) >= 3:
                        print(f"readCatchName (pass {i+1}): '{name}' (raw: '{text}')")
                        return name

            print("readCatchName: OCR passes returned no valid text")
            return ""
        except Exception as e:
            print(f"readCatchName: OCR failed: {e}")
            return ""

    def endTry(self, log: str, itemName: str = "") -> None:
        rodKey = f"{self.settingsWindow.rodKey}"
        self.tryCatchFish = False
        self.startFishingTimer = time.time()
        self.logsWindow.logs.append([time.localtime(), log, itemName])
        time.sleep(0.2)
        keyboard.press_and_release(rodKey)
        keyboard.press_and_release(rodKey)
        time.sleep(0.2)
        self.selectBait()
        pyautogui.click(button = "left")

    def selectBait(self) -> None:
        baitType = self.settingsWindow.baitType
        print(f"selectBait called, baitType={baitType}")
        if baitType == "none":
            return
        baitImg = IMG_BAIT.get(baitType)
        if baitImg is None:
            print(f"ERROR: No image for bait type {baitType}")
            return
        print(f"Looking for bait image ({baitImg.shape[1]}x{baitImg.shape[0]})...")
        time.sleep(0.3)
        for i in range(10):
            loc = locateImage(baitImg, 0.55)
            if loc:
                h, w = baitImg.shape[:2]
                cx, cy = loc[0] + w // 2, loc[1] + h // 2
                print(f"Found bait at {loc}, clicking ({cx}, {cy})")
                directClick(cx, cy)
                time.sleep(0.3)
                return
            time.sleep(0.2)
        print("FAILED: Could not find bait image on screen after 10 attempts")

    def clickImage(self, img, threshold=0.7, attempts=20) -> bool:
        # Phase 1: find the image
        for _ in range(attempts):
            loc = locateImage(img, threshold)
            if loc:
                h, w = img.shape[:2]
                cx, cy = loc[0] + w // 2, loc[1] + h // 2
                print(f"clickImage: found target at ({cx},{cy}), clicking...")
                directClick(cx, cy)
                time.sleep(0.5)
                # Phase 2: wait for image to disappear (confirms click registered)
                for _ in range(15):
                    if not locateImage(img, threshold):
                        print("clickImage: target disappeared, click confirmed")
                        return True
                    time.sleep(0.3)
                # Image still visible - click may not have registered, try again
                print("clickImage: target still visible, retrying click...")
                continue
            time.sleep(0.5)
        print("clickImage: FAILED after all attempts")
        return False

    def readFleetStrength(self) -> int:
        """Read fleet strength % by measuring the red fill ratio of the strength bar.
        Uses grayscale template matching to find the STRENGTH label (robust to
        varying fill colors behind the text), then measures the bar pixel-by-pixel."""
        # Grayscale matching is more robust to background color changes from varying fill levels
        screenshot = pyautogui.screenshot()
        screenshot = numpy.array(screenshot)
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
        gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        gray_template = cv2.cvtColor(IMG_FLEET_STRENGTH, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(gray_screen, gray_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val < 0.45:
            print(f"readFleetStrength: STRENGTH label not found (best match {max_val:.2f})")
            return -1

        loc_x, loc_y = max_loc
        th, tw = IMG_FLEET_STRENGTH.shape[:2]

        # The full bar extends ~3.15x the template width from the template's left edge
        bar_right = loc_x + int(tw * 3.15)
        # Use a middle strip (30%-70% height) to avoid top/bottom borders
        strip_top = loc_y + int(th * 0.3)
        strip_bot = loc_y + int(th * 0.7)

        # Clamp to screen bounds
        bar_right = min(bar_right, screenshot.shape[1])
        strip_bot = min(strip_bot, screenshot.shape[0])

        strip = screenshot[strip_top:strip_bot, loc_x:bar_right, :]

        red_cols = 0
        dark_cols = 0
        for x in range(strip.shape[1]):
            col = strip[:, x, :]
            avg_b, avg_g, avg_r = col.mean(axis=0)
            is_red = avg_r > 80 and avg_r > avg_g * 1.3 and avg_r > avg_b * 1.3
            is_dark = avg_r < 30 and avg_g < 30 and avg_b < 30
            if is_red:
                red_cols += 1
            elif is_dark:
                dark_cols += 1

        total = red_cols + dark_cols
        if total == 0:
            print("readFleetStrength: no bar pixels detected")
            return -1

        pct = int(red_cols * 100 / total)
        print(f"readFleetStrength: {pct}% (red={red_cols}, dark={dark_cols})")
        return pct

    def readRepairCost(self) -> str:
        """OCR the repair cost from the confirmation dialog (visible when YES/NO is shown)."""
        if not HAS_OCR:
            return ""
        try:
            ss = numpy.array(pyautogui.screenshot())
            ss = cv2.cvtColor(ss, cv2.COLOR_RGB2BGR)

            # Find the YES button to locate the dialog
            result = cv2.matchTemplate(ss, IMG_FLEET_YES, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val < 0.5:
                print("readRepairCost: YES button not found")
                return ""

            yes_h = IMG_FLEET_YES.shape[0]
            # Cost text is ~90-100px above the YES button, spanning the dialog width
            strip_top = max(max_loc[1] - 110, 0)
            strip_bot = max_loc[1] - 10
            strip_left = max(max_loc[0] - 50, 0)
            strip_right = min(max_loc[0] + 500, ss.shape[1])

            cost_strip = ss[strip_top:strip_bot, strip_left:strip_right, :]
            if cost_strip.size == 0:
                return ""

            gray = cv2.cvtColor(cost_strip, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            text = pytesseract.image_to_string(thresh, config='--psm 6').strip()
            # Extract number before "Drachma"
            m = re.search(r'(\d[\d,\.]*)\s*[Dd]rachma', text)
            if m:
                cost = m.group(1).replace(',', '')
                print(f"readRepairCost: {cost} Drachma")
                return cost
            # Fallback: just find any number in the text
            m = re.search(r'(\d[\d,\.]+)', text)
            if m:
                cost = m.group(1).replace(',', '')
                print(f"readRepairCost (fallback): {cost}")
                return cost
            print(f"readRepairCost: no number found (raw: '{text}')")
            return ""
        except Exception as e:
            print(f"readRepairCost: failed: {e}")
            return ""

    def readDrachma(self) -> str:
        """OCR the player's Drachma balance from the HUD.
        Uses grayscale coin template matching (robust to background changes)
        and digit-only OCR config."""
        if not HAS_OCR:
            return ""
        try:
            ss = numpy.array(pyautogui.screenshot())
            ss = cv2.cvtColor(ss, cv2.COLOR_RGB2BGR)

            # Grayscale matching for the coin icon — robust to varying backgrounds
            gray_ss = cv2.cvtColor(ss, cv2.COLOR_BGR2GRAY)
            gray_coin = cv2.cvtColor(IMG_DRACHMA_COIN, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(gray_ss, gray_coin, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val < 0.4:
                print(f"readDrachma: coin not found (best match {max_val:.2f})")
                return ""

            coin_h, coin_w = IMG_DRACHMA_COIN.shape[:2]
            # Number is to the right of the coin
            num_left = max_loc[0] + coin_w - 5
            num_top = max_loc[1]
            num_right = min(num_left + 200, ss.shape[1])
            num_bot = min(num_top + coin_h, ss.shape[0])

            num_strip = ss[num_top:num_bot, num_left:num_right, :]
            if num_strip.size == 0:
                return ""

            gray = cv2.cvtColor(num_strip, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

            # Multiple passes for different backgrounds
            preprocessed = [
                cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
                cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)[1],
            ]

            for i, img in enumerate(preprocessed):
                text = pytesseract.image_to_string(
                    img, config='--psm 7 -c tessedit_char_whitelist=0123456789,.').strip()
                # Clean and validate: should be digits with commas/periods
                digits = text.replace(' ', '').replace('.', ',')
                if digits and sum(c.isdigit() for c in digits) >= 2:
                    print(f"readDrachma (pass {i+1}): {digits}")
                    return digits

            print("readDrachma: OCR failed to read number")
            return ""
        except Exception as e:
            print(f"readDrachma: failed: {e}")
            return ""

    def repairFleet(self) -> str:
        """Repair fleet and return the cost as a string."""
        rodKey = f"{self.settingsWindow.rodKey}"
        keyboard.press_and_release(rodKey)
        time.sleep(0.5)
        keyboard.press_and_release("u")
        time.sleep(1.5)

        # Step 1: Click View Fleet Info, wait for it to disappear
        if not self.clickImage(IMG_FLEET_VIEW):
            print("repairFleet: View Fleet Info not found, aborting")
            keyboard.press_and_release("u")
            time.sleep(0.3)
            keyboard.press_and_release(rodKey)
            self.selectBait()
            pyautogui.click(button="left")
            return ""
        time.sleep(1.0)

        # Step 2: Click Repair All, then wait for Yes to appear (not for Repair All to disappear)
        if not self.clickImageThenWaitFor(IMG_FLEET_REPAIR, IMG_FLEET_YES):
            print("repairFleet: Repair All failed, aborting")
            keyboard.press_and_release("u")
            time.sleep(0.3)
            keyboard.press_and_release(rodKey)
            self.selectBait()
            pyautogui.click(button="left")
            return ""
        time.sleep(0.5)

        # Step 2.5: OCR the repair cost while confirmation dialog is visible
        repair_cost = self.readRepairCost()

        # Step 3: Click Yes, wait for it to disappear
        if not self.clickImage(IMG_FLEET_YES):
            print("repairFleet: Yes button failed, aborting")

        time.sleep(1.5)

        # Step 4: Check fleet strength — if below threshold, pause fleet operations
        strength = self.readFleetStrength()
        if strength >= 0 and strength < FLEET_STRENGTH_THRESHOLD:
            print(f"repairFleet: Strength {strength}% < {FLEET_STRENGTH_THRESHOLD}%, pausing fleet")
            if self.clickImage(IMG_FLEET_PAUSE, threshold=0.7, attempts=10):
                self.logsWindow.logs.append([time.localtime(), "pauseFleet"])
                time.sleep(0.5)
            else:
                print("repairFleet: PAUSE FLEET OPERATIONS button not found")
        elif strength >= 0:
            print(f"repairFleet: Strength {strength}% >= {FLEET_STRENGTH_THRESHOLD}%, no pause needed")

        keyboard.press_and_release("u")
        time.sleep(0.5)
        keyboard.press_and_release(rodKey)
        time.sleep(0.2)
        self.selectBait()
        pyautogui.click(button="left")
        return repair_cost

    def clickImageThenWaitFor(self, click_img, wait_img, threshold=0.7, attempts=20) -> bool:
        """Click click_img, then verify by waiting for wait_img to appear."""
        for _ in range(attempts):
            loc = locateImage(click_img, threshold)
            if loc:
                h, w = click_img.shape[:2]
                cx, cy = loc[0] + w // 2, loc[1] + h // 2
                print(f"clickImageThenWaitFor: clicking target at ({cx},{cy})...")
                directClick(cx, cy)
                time.sleep(0.5)
                # Wait for the NEXT button to appear
                for _ in range(15):
                    if locateImage(wait_img, threshold):
                        print("clickImageThenWaitFor: next target appeared, confirmed")
                        return True
                    time.sleep(0.3)
                print("clickImageThenWaitFor: next target not yet visible, retrying...")
                continue
            time.sleep(0.5)
        print("clickImageThenWaitFor: FAILED after all attempts")
        return False

    def addFishCount(self) -> None:
        self.fishCount += 1
        self.__countLabel.setText(f"Caught: {self.fishCount}")

    def resetFishCount(self) -> None:
        self.fishCount = 0
        self.__countLabel.setText(f"Caught: {self.fishCount}")

if __name__ == "__main__":
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()

    app = QApplication(sys.argv)
    screenSize = app.primaryScreen().geometry()

    basePath = os.path.abspath(os.path.dirname(sys.argv[0]))

    allImagesPath = [
        Rf'{basePath}/images/forScript/start.png',
        Rf'{basePath}/images/forScript/fish.png',
        Rf'{basePath}/images/forScript/treasure.png',
        Rf'{basePath}/images/forScript/junk.png',
        Rf'{basePath}/images/forScript/sunken.png',
        Rf'{basePath}/images/forScript/disconnected.png'
    ]

    baitImagesPath = [
        Rf'{basePath}/images/forScript/bait_normal.png',
        Rf'{basePath}/images/forScript/bait_swarm.png',
        Rf'{basePath}/images/forScript/bait_giant.png',
        Rf'{basePath}/images/forScript/bait_magic.png'
    ]

    fleetImagesPath = [
        Rf'{basePath}/images/forScript/fleet_view.png',
        Rf'{basePath}/images/forScript/fleet_repair.png',
        Rf'{basePath}/images/forScript/fleet_yes.png',
        Rf'{basePath}/images/forScript/fleet_strength.png',
        Rf'{basePath}/images/forScript/fleet_pause.png'
    ]

    actualScreenSize = [user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)]
    lastUsedSize = getLastSize()

    print(f"Screen: {actualScreenSize}, DB says: {lastUsedSize}")

    if lastUsedSize[0] != actualScreenSize[0]:
        print("Resolution mismatch - scaling images...")
        for i in allImagesPath:
            changeImageSize(i, actualScreenSize, lastUsedSize)
        # NOTE: bait/fleet images are at native screen resolution
        # and should NOT be scaled by the auto-scaler
        changeLastSize(actualScreenSize)
        print("Scaling complete.")

    IMG_START = cv2.imread(allImagesPath[0])
    IMG_FISH = cv2.imread(allImagesPath[1])
    IMG_TREASURE = cv2.imread(allImagesPath[2])
    IMG_JUNK = cv2.imread(allImagesPath[3])
    IMG_SUNKEN = cv2.imread(allImagesPath[4])
    IMG_DISCONNECTED = cv2.imread(allImagesPath[5])

    IMG_BAIT = {
        "normal": cv2.imread(baitImagesPath[0]),
        "swarm": cv2.imread(baitImagesPath[1]),
        "giant": cv2.imread(baitImagesPath[2]),
        "magic": cv2.imread(baitImagesPath[3])
    }

    IMG_FLEET_VIEW = cv2.imread(fleetImagesPath[0])
    IMG_FLEET_REPAIR = cv2.imread(fleetImagesPath[1])
    IMG_FLEET_YES = cv2.imread(fleetImagesPath[2])
    IMG_FLEET_STRENGTH = cv2.imread(fleetImagesPath[3])
    IMG_FLEET_PAUSE = cv2.imread(fleetImagesPath[4])

    IMG_DRACHMA_COIN = cv2.imread(Rf'{basePath}/images/forScript/drachma_coin.png')

    FLEET_STRENGTH_THRESHOLD = 54  # Pause fleet if strength falls below this %

    # Diagnostic: verify all images loaded
    for name, img in [("START", IMG_START), ("FISH", IMG_FISH), ("TREASURE", IMG_TREASURE),
                       ("JUNK", IMG_JUNK), ("SUNKEN", IMG_SUNKEN), ("DISCONNECTED", IMG_DISCONNECTED),
                       ("BAIT_NORMAL", IMG_BAIT["normal"]), ("BAIT_SWARM", IMG_BAIT["swarm"]),
                       ("BAIT_GIANT", IMG_BAIT["giant"]), ("BAIT_MAGIC", IMG_BAIT["magic"]), ("FLEET_VIEW", IMG_FLEET_VIEW),
                       ("FLEET_REPAIR", IMG_FLEET_REPAIR), ("FLEET_YES", IMG_FLEET_YES),
                       ("FLEET_STRENGTH", IMG_FLEET_STRENGTH), ("FLEET_PAUSE", IMG_FLEET_PAUSE),
                       ("DRACHMA_COIN", IMG_DRACHMA_COIN)]:
        if img is None:
            print(f"ERROR: Failed to load {name}")
        else:
            print(f"OK: {name} = {img.shape[1]}x{img.shape[0]}")

    window = MainWindow("Auto fishing")
    window.show()
    window.fishingThread.start()
    sys.exit(app.exec())

#  pyinstaller -w -F -i"images\icons\APP_ICON.ico" -n "auto fishing" main.py
