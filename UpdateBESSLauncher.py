import sys
import requests
import csv
import os
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QFileDialog
from openpyxl import Workbook
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QPushButton,
    QHBoxLayout, QLineEdit, QMessageBox, QFrame
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import pyqtgraph as pg

API_URL = "https://raw.githubusercontent.com/TkZJZ/Server_Thesis/main/config.json"
CSV_FILE = "power_log.csv"

# =============================
# Thread ดึงข้อมูล API
# =============================
class ApiThread(QThread):
    dataReceived = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.running = True
        self.url = API_URL

    def run(self):
        while self.running:
            try:
                config = requests.get(self.url, timeout=5).json()
                real_api = config.get("api_url")

                if real_api:
                    r = requests.get(real_api + "/data", timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        self.dataReceived.emit(data)

            except Exception as e:
                print("Thread Error:", e)

            self.msleep(1000)

    def stop(self):
        self.running = False
        self.wait()

# =============================
# Main UI
# =============================
class MonitorApp(QWidget):
    def __init__(self):
        super().__init__()

        self.current_data = {}
        self.monitor_running = True

        # ✅ ต้องสร้าง history ก่อน initUI
        self.history = {
            "P_Total": [],
            "V_Main": [],
            "V_Shunt": [],
            "I_Total": [],
            "I_Shunt": [],
            "I_ACS712": [],
            "I_ACS758": [],
            "I_Probe1": [],
            "I_Probe2": [],
            "P_Shunt": [],
            "P_ACS712": [],
            "P_ACS758": [],
            "P_Probe1": [],
            "P_Probe2": [],
            "Temp1": [],
            "Temp2": []
        }

        self.units = {
            "V_Main": "V",
            "V_Shunt": "V",
            "I_Total": "A",
            "I_Shunt": "A",
            "I_ACS712": "A",
            "I_ACS758": "A",
            "I_Probe1": "A",
            "I_Probe2": "A",
            "P_Total": "W",
            "P_Shunt": "W",
            "P_ACS712": "W",
            "P_ACS758": "W",
            "P_Probe1": "W",
            "P_Probe2": "W",
            "Temp1": "°C",
            "Temp2": "°C"
        }

        self.initUI()
        self.startThread()

    def calculatePowers(self, data):
        try:
            V_main = float(data.get("V_Main", 0))
            V_shunt = float(data.get("V_Shunt", 0))

            powers = {
                "P_Shunt": V_shunt * float(data.get("I_Shunt", 0)),
                "P_ACS712": V_main * float(data.get("I_ACS712", 0)),
                "P_ACS758": V_main * float(data.get("I_ACS758", 0)),
                "P_Probe1": V_main * float(data.get("I_Probe1", 0)),
                "P_Probe2": V_main * float(data.get("I_Probe2", 0)),
            }

            return powers

        except:
            return {}
        
    def initUI(self):
        self.setWindowTitle("Power Monitor")
        self.setGeometry(300, 100, 700, 700)
        title = QLabel("POWER MONITOR")
        title.setFont(QFont("Arial", 22, QFont.Bold))
        layout = QVBoxLayout()


        for lbl in [self.v_label, self.i_label, self.p_label,   
                    self.acs712_label, self.acs_pz_label, self.acs758_label]:
            lbl.setFont(QFont("Consolas", 14))

        self.btn_toggle = QPushButton("Stop Monitor")
        self.btn_toggle.clicked.connect(self.toggleMonitor)
        self.clear_btn = QPushButton("Clear Graph")
        self.clear_btn.clicked.connect(self.clearGraph)
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.clicked.connect(self.exportCSV)
       

        self.url_input = QLineEdit(API_URL)
        self.url_input.textChanged.connect(self.updateApiUrl)

        self.graph = pg.PlotWidget()
        self.graph_line = self.graph.plot([], pen=pg.mkPen('g', width=2))
        self.selected_label = QLabel("Selected: ---")
        self.selected_label.setFont(QFont("Consolas", 16, QFont.Bold))
        layout.addWidget(self.selected_label)

        self.graph_selector = QComboBox()
        self.graph_selector.addItems(self.history.keys())

        # เปิด zoom / pan
        self.graph.setMouseEnabled(x=True, y=True)
        self.graph.enableAutoRange()

        
        layout.addWidget(title)
        layout.addWidget(self.v_label)
        layout.addWidget(self.i_label)
        layout.addWidget(self.p_label)
        layout.addWidget(self.acs712_label)
        layout.addWidget(self.acs_pz_label)
        layout.addWidget(self.acs758_label)
        layout.addWidget(self.graph)
        layout.addWidget(QLabel("API URL:"))
        layout.addWidget(self.url_input)
        layout.addWidget(self.btn_toggle)
        layout.addWidget(QLabel("Select Graph Parameter:"))
        layout.addWidget(self.graph_selector)
        layout.addWidget(self.clear_btn)
        layout.addWidget(self.export_btn)

        self.setLayout(layout)
#/////////////////////////////////////////////////////////////////////////////////////////
    def clearGraph(self):
        for key in self.history:
            self.history[key].clear()

        self.graph_line.clear()
    def startThread(self):
        self.th = ApiThread()
        self.th.dataReceived.connect(self.updateUI)
        self.th.start()

        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self.saveCSV)
        self.save_timer.start(5000)

    def updateApiUrl(self):
        self.th.url = self.url_input.text().strip()

    def toggleMonitor(self):
        self.monitor_running = not self.monitor_running
        self.btn_toggle.setText("Stop Monitor" if self.monitor_running else "Start Monitor")

    def updateUI(self, data):
        if not self.monitor_running:
            return

        self.current_data = data

        try:
            V_main = float(data.get("V_Main", 0))
            V_shunt = float(data.get("V_Shunt", 0))
            I_total = float(data.get("I_Total", 0))
            I_shunt = float(data.get("I_Shunt", 0))
            I_712 = float(data.get("I_ACS712", 0))
            I_758 = float(data.get("I_ACS758", 0))
            I_p1 = float(data.get("I_Probe1", 0))
            I_p2 = float(data.get("I_Probe2", 0))
            T1 = float(data.get("Temp1", 0))
            T2 = float(data.get("Temp2", 0))

            # ---- คำนวณ Power ----
            P_total = V_main * I_total
            powers = self.calculatePowers(data)

            # รวม power เข้า data
            data.update(powers)
            data["P_Total"] = P_total

            # ---- Update Label ปกติ (แสดงค่าหลักคงที่ได้ถ้าต้องการ) ----
            self.v_label.setText(f"V_Main: {V_main:.2f} V")
            self.i_label.setText(f"I_Total: {I_total:.2f} A")
            self.p_label.setText(f"P_Total: {P_total:.2f} W")

            # ---- Label แสดงค่าตามที่เลือก ----
            selected = self.graph_selector.currentText()
            selected_value = float(data.get(selected, 0))

            unit = self.units.get(selected, "")
            self.selected_label.setText(f"{selected}: {selected_value:.3f} {unit}")

            # ---- เก็บ history (รอบเดียวเท่านั้น) ----
            for key in self.history:
                value = float(data.get(key, 0))
                self.history[key].append(value)

                if len(self.history[key]) > 200:
                    self.history[key].pop(0)

            # ---- แสดงกราฟ ----
            self.graph_line.setData(self.history[selected])
            self.graph.enableAutoRange(axis='y')

        except Exception as e:
            print("Update UI Error:", e)

    def saveCSV(self):
        if not self.current_data:
            return

        try:
            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                self.current_data.get("V_Main", 0),
                self.current_data.get("I_Total", 0),
                self.current_data.get("I_Probe1", 0),
                self.current_data.get("I_ACS712", 0),
                self.current_data.get("I_ACS758", 0)
            ]

            new_file = not os.path.exists(CSV_FILE)
            with open(CSV_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                if new_file:
                    writer.writerow(["Time", "V_Main", "I_Total",
                                    "I_Probe1", "I_ACS712", "I_ACS758"])
                writer.writerow(row)

        except Exception as e:
            print("Save CSV Error:", e)

    def exportCSV(self):
        if not any(self.history.values()):
            QMessageBox.warning(self, "No Data", "No graph data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV",
            "",
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='') as file:
                writer = csv.writer(file)

                # Header
                writer.writerow(self.history.keys())

                # Data rows
                rows = zip(*self.history.values())
                for row in rows:
                    writer.writerow(row)

            QMessageBox.information(self, "Success", "CSV Exported Successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed:\n{e}")

    def closeEvent(self, event):
        self.th.stop()
        event.accept()


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    win = MonitorApp()
    win.show()
    sys.exit(app.exec_())
