#Program to run the charge discharge control in different processes for each channel.

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton
import charge_discharge_control as cdc
from multiprocessing import Process

class MainTestWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		
		self.setWindowTitle("Battery Tester App")
		button = QPushButton("Start Test")
		button.setCheckable(False)
		button.clicked.connect(self.batt_test_process)
		self.setCentralWidget(button)
	
	def batt_test_process(self):
		process1 = Process(target=cdc.charge_discharge_control)
		process1.start()

def main():
	app = QApplication([])
	test_window = MainTestWindow()
	test_window.show()
	app.exec()
	
if __name__ == '__main__':
	main()
