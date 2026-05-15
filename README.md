# Auto Fishing — Arcane Odyssey

Automatic fishing bot for Roblox Arcane Odyssey with OCR-powered item logging, fleet management, and session tracking.

**Forked from [Zombie-220/Fishing](https://github.com/Zombie-220/Fishing)** — original application and core fishing logic by [Zombie-220](https://github.com/Zombie-220).

---

## What It Does

- Automatically fishes, detects catches, and re-casts with bait selection
- **OCR item identification** — logs the specific fish or treasure caught (e.g. "Southern Cod", "Knight's Greataxe")
- **Fleet repair** — periodically repairs your fleet on a configurable timer
- **Fleet strength monitoring** — pauses fleet operations if strength drops below a threshold
- **Repair cost tracking** — logs the Drachma cost of each repair
- **Drachma balance tracking** — records your balance at session start and end
- **CSV export** — export your full fishing history with timestamps, item names, and costs

## Quick Start

### 1. Download

Grab the latest release from the [Releases page](https://github.com/Malachai1212/AutoFishing/releases) and extract the zip.

### (Optional) 2. Install Tesseract OCR

Download and run the installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) (`tesseract-ocr-w64-setup-5.x.x.exe`). Install with default settings to `C:\Program Files\Tesseract-OCR\`.  
  
Required for Fish/Item Name and Fleet Strength/Repair Cost tracking

### 3. Run

Double-click `auto fishing.exe` in the extracted folder.

### 4. In-Game Setup

1. Stand near water where your character won't move
2. Zoom the camera in as close as possible, then press **O** once
3. Cast your fishing rod
4. Press **START** in the bot window

## Settings

Open the settings window (gear icon) to configure:

| Setting | Description |
|---|---|
| Rod key | Hotbar key for your fishing rod (0-9) |
| Lure / Potion | Toggle auto-consumption with key and timer |
| Bait type | None, Normal, Swarm, Giant, or Magic |
| Fleet repair | Toggle auto-repair with timer interval |
| Sea choice | Normal sea or Dark sea (adjusts catch timeout) |

## History & Export

The History window logs every event with timestamps. Click **Export** to save as CSV with columns: Date, Time, Event, Description, Item.

Session start/end entries include your Drachma balance. Repair entries include the cost. Fish and treasure entries include the specific item name.

## Building from Source

If you'd prefer to run from source or build the exe yourself:

```sh
git clone https://github.com/Malachai1212/AutoFishing.git
cd AutoFishing
pip install pyqt6 opencv-python pyautogui keyboard numpy pytesseract pyinstaller
python -m PyInstaller -w -F -i "images\icons\APP_ICON.ico" -n "auto fishing" main.py
```

The exe will appear in the `dist/` folder. Copy it back to the root folder (next to `images/` and `DB.json`) to run.

## Troubleshooting

**OCR not capturing item names** — Make sure Tesseract is installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`. If installed elsewhere, update the path in `main.py`.

**Images not matching** — Template images were captured at 2560×1440. The auto-scaler handles core fishing images, but bait/fleet images may need to be re-captured at your resolution. Crop the relevant UI elements and replace files in `images/forScript/`.

**Bot not clicking Roblox buttons** — The bot uses low-level Windows input. Make sure Roblox is in the foreground and not minimized.

## Credits

- **[Zombie-220](https://github.com/Zombie-220)** — original [Fishing](https://github.com/Zombie-220/Fishing) application, core fishing logic, UI framework, and image matching system
- **Malachai1212** — OCR item detection, fleet management, strength monitoring, Drachma tracking, CSV export, and bait selection improvements
