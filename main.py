import os
from user_data_manager import UserDataManager
from gui import LoginWindow, AddFacesGUI

if __name__ == "__main__":
    data_manager = UserDataManager()
    LoginWindow(lambda: AddFacesGUI(data_manager).mainloop())
