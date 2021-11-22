#Program to run the charge discharge control in different threads.

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
