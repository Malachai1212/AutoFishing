from PyQt6 import QtWidgets, QtCore, QtGui
from time import struct_time
import csv, os

from modules.GlobalVariables import CSS, EXIT_ICON
from modules.SimpleComponents import WindowTitleBar, Button

class LogsWindow(QtWidgets.QMainWindow):
    logs: list = []

    REASON_MAP = {
        "fish": "Fish caught",
        "sunken": "Sunken treasure caught",
        "treasure": "Treasure caught",
        "start": "Session start",
        "stop": "Session end",
        "timeError": "Waiting time is up",
        "consumeMeal": "Consume lure",
        "consumePotion": "Consume potion",
        "repairFleet": "Repair fleet",
        "pauseFleet": "Fleet paused (low strength)"
    }

    def __init__(self, parent: QtWidgets.QMainWindow):
        super().__init__()

        self.parent = parent
        self.title = "AF  |  History"
        self.icon = parent.icon
        self.__exportData = []

        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QtGui.QIcon(self.icon))
        self.setFixedSize(350, 400)
        self.move(parent.pos().x() + parent.width(), parent.height() + 10)
        self.setObjectName("Window")
        self.setStyleSheet(CSS)

        windowTitle = WindowTitleBar(self)
        btn_close = Button(self, EXIT_ICON, self.width() - 28, 2, 26, 26, "btn_red", self.close)
        btn_close.setToolTip("Close window")
        btn_clear = Button(self, "Clear", self.width() - 80, 2, 50, 26, "btn_red", self.deleteLogs)
        btn_clear.setToolTip("Clear history")
        btn_export = Button(self, "Export", self.width() - 138, 2, 56, 26, "btn_standart", self.exportCSV)
        btn_export.setToolTip("Export history to CSV")

        self.__widget = QtWidgets.QWidget()
        self.__widget.setObjectName("widget")
        self.__vBox = QtWidgets.QVBoxLayout()  
        self.__vBox.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.__widget.setLayout(self.__vBox)

        self.__scrollArea = QtWidgets.QScrollArea(self)
        self.__scrollArea.move(2,32)
        self.__scrollArea.setFixedSize(self.width() - 4, self.height() - 34)
        self.__scrollArea.setObjectName("scrollArea")
        self.__scrollArea.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.__scrollArea.setWidgetResizable(True)
        self.__scrollArea.verticalScrollBar().rangeChanged.connect(self.scrollToBottom)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.checkLogs)
        self.timer.setInterval(500)
        self.timer.start()

    def scrollToBottom(self, min, max) -> None:
        self.__scrollArea.verticalScrollBar().setValue(max)

    def addLog(self, time: struct_time, reasonType: str, itemName: str = "") -> None:
        objectName = f"btn_{reasonType}_log"
        reason = self.REASON_MAP.get(reasonType, reasonType)

        date_str = f"{time.tm_year}-{time.tm_mon:02}-{time.tm_mday:02}"
        time_str = f"{time.tm_hour:02}:{time.tm_min:02}:{time.tm_sec:02}"
        self.__exportData.append([date_str, time_str, reasonType, reason, itemName])

        display = f"{time_str}  |  {reason}: {itemName}" if itemName else f"{time_str}  |  {reason}"
        btn = Button(self, display, 0, 0, 0, 0, objectName)
        self.__vBox.addWidget(btn)
        self.__scrollArea.setWidget(self.__widget)

    def exportCSV(self) -> None:
        if not self.__exportData:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export History", "fishing_log.csv", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Time", "Event", "Description", "Item"])
            writer.writerows(self.__exportData)

    def checkLogs(self) -> None:
        if len(self.logs) != 0:
            entry = self.logs[0]
            itemName = entry[2] if len(entry) > 2 else ""
            self.addLog(entry[0], entry[1], itemName)
            self.logs.pop(0)
        self.timer.start()

    def deleteLogs(self) -> None:
        while self.__vBox.itemAt(0):
            self.__vBox.removeWidget(self.__vBox.itemAt(0).widget())
        self.__exportData.clear()
        self.parent.resetFishCount()