# main.py


import tkinter as tk
from gui import Application
import threading
import time

def show_splash():
    splash = tk.Tk()
    splash.title("")
    splash.geometry("400x180")
    splash.overrideredirect(True)
    splash.configure(bg="#2c3e50")
    label = tk.Label(splash, text="Getting things ready for you, please wait...", font=("Arial", 14), fg="white", bg="#2c3e50")
    label.pack(expand=True, fill="both")
    splash.update()
    return splash

def main():
    splash = show_splash()
    # Simulate loading time (or do heavy loading here)
    splash.after(1200, splash.destroy)  # 1.2 seconds
    splash.mainloop()
    # Now launch main app
    app = Application()
    app.mainloop()

if __name__ == "__main__":
    main()
