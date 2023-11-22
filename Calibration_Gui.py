import Calibration_Script
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel

class MultimeterCalibrationApp(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.cal_class = Calibration_Script.CalibrationClass()

    def init_ui(self):
        self.setWindowTitle('Multimeter Calibration')
        self.setGeometry(100, 100, 500, 200)

        self.connect_btn1 = QPushButton('Connect to Multimeter to Calibrate', self)
        self.connect_btn1.clicked.connect(self.connect_multimeter_to_calibrate)
        self.connected_label1 = QLabel('None', self)

        self.connect_btn2 = QPushButton('Connect to Calibrated Multimeter', self)
        self.connect_btn2.clicked.connect(self.connect_calibrated_multimeter)
        self.connected_label2 = QLabel('None', self)

        self.connect_btn3 = QPushButton('Connect to Power Supply', self)
        self.connect_btn3.clicked.connect(self.connect_power_supply)
        self.connected_label3 = QLabel('None', self)

        self.calibrate_btn = QPushButton('Calibrate Multimeter', self)
        self.calibrate_btn.clicked.connect(self.calibrate_multimeter)

        self.check_calibration_btn = QPushButton('Check Calibration', self)
        self.check_calibration_btn.clicked.connect(self.check_calibration)
        
        dut_layout = QHBoxLayout()
        dut_layout.addWidget(self.connect_btn1)
        dut_layout.addWidget(self.connected_label1)
        
        dmm_layout = QHBoxLayout()
        dmm_layout.addWidget(self.connect_btn2)
        dmm_layout.addWidget(self.connected_label2)
        
        psu_layout = QHBoxLayout()
        psu_layout.addWidget(self.connect_btn3)
        psu_layout.addWidget(self.connected_label3)

        control_layout = QVBoxLayout()
        control_layout.addLayout(dut_layout)
        control_layout.addLayout(dmm_layout)
        control_layout.addLayout(psu_layout)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.calibrate_btn)
        action_layout.addWidget(self.check_calibration_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(control_layout)
        main_layout.addLayout(action_layout)

        self.setLayout(main_layout)

    def connect_multimeter_to_calibrate(self):
        # Add your connection logic here
        self.cal_class.connect_dut()
        self.connected_label1.setText(self.cal_class.dut_idn)

    def connect_calibrated_multimeter(self):
        # Add your connection logic here
        self.cal_class.connect_dmm()
        self.connected_label2.setText(self.cal_class.dmm_idn)

    def connect_power_supply(self):
        # Add your connection logic here
        self.cal_class.connect_psu()
        self.connected_label3.setText(self.cal_class.psu_idn)

    def calibrate_multimeter(self):
        # Add your calibration logic here
        print('Calibrating Multimeter...')
        self.cal_class.calibrate_voltage_meter()

    def check_calibration(self):
        # Add your calibration check logic here
        print('Checking Calibration...')
        self.cal_class.check_voltage_calibration()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MultimeterCalibrationApp()
    window.show()
    sys.exit(app.exec())