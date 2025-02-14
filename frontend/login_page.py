import tkinter as tk
from tkinter import ttk

class LoginPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        # Title Label
        label = ttk.Label(self, text="Login Page", font=("TkDefaultFont", 16))
        label.pack(pady=10, padx=10)
        
        # Username Entry
        self.username_entry = ttk.Entry(self)
        self.username_entry.pack(pady=5, padx=5)
        self.username_entry.insert(0, "Username")
        
        # Password Entry
        self.password_entry = ttk.Entry(self, show="*")
        self.password_entry.pack(pady=5, padx=5)
        self.password_entry.insert(0, "Password")
        
        # Login Button
        login_button = ttk.Button(self, text="Login", command=self.login)
        login_button.pack(pady=5, padx=5)
    
    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        # Here you could validate the credentials
        print(f"Logging in with username: {username} and password: {password}")
        # For demo purposes, we switch to the chat page after login
        self.controller.show_frame("ChatPage")
