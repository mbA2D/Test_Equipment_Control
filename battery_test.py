#Program to run the charge discharge control in different threads.

'''
#Tkinter had some weird interaction with EasyGui (which is based on TKinter). After closing a window
#in the thread, the main window would lock up.

import tkinter as tk
import threading
import charge_discharge_control as cdc

def batt_test_thread():
	thread1 = threading.Thread(target=cdc.charge_discharge_control, args = (), daemon = True)
	thread1.start()

window = tk.Tk()
window.title('Battery Test')

frm_1 = tk.Frame(master = window, relief = tk.GROOVE, borderwidth = 5)

lbl_1 = tk.Label(master = frm_1, text = "Testing Application")
lbl_1.pack(pady = 20)

#btn_1 = tk.Button(master = frm_1, text = "Start Test", command = cdc.charge_discharge_control())
btn_1 = tk.Button(master = frm_1, text = "Start Test", command = batt_test_thread)
btn_1.pack(pady = 20)

frm_1.pack()

window.mainloop()
'''


from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
import sys

import charge_discharge_control as cdc

class CDC_Class(QThread):
	def __init__(self):
		QThread.__init__(self)
	
	def __del__(self):
		self.wait()
		
	def run(self):
		cdc.charge_discharge_control()


def main():
	app = QtGui.QApplication(sys.argv)
	test_window = 
	test_window.show()
	app.exec_()
	

if __name__ == '__main__':
	main()
	