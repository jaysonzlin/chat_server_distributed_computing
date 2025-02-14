import tkinter as tk
from tkinter import ttk

class ChatPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        # Title Label
        label = ttk.Label(self, text="Chat Page", font=("TkDefaultFont", 16))
        label.pack(pady=10, padx=10)
        
        # Chat Display Area (read-only Text widget)
        self.chat_display = tk.Text(self, state="disabled", width=50, height=10)
        self.chat_display.pack(pady=5, padx=5)
        
        # Frame to hold the message entry and Send button side by side
        entry_frame = tk.Frame(self)
        entry_frame.pack(pady=5, padx=5)
        
        # Message Entry
        self.message_entry = ttk.Entry(entry_frame, width=40)
        self.message_entry.pack(side="left", pady=5, padx=5)
        self.message_entry.bind("<Return>", self.send_message)  # Allow Enter key to send
        
        # Send Button
        send_button = ttk.Button(entry_frame, text="Send", command=self.send_message)
        send_button.pack(side="left", pady=5, padx=5)
        
        # Logout Button to return to the Login page
        logout_button = ttk.Button(self, text="Logout", command=lambda: controller.show_frame("LoginPage"))
        logout_button.pack(pady=5, padx=5)
    
    def send_message(self, event=None):
        message = self.message_entry.get().strip()
        if message:
            # Enable the text widget, insert the message, then disable it again
            self.chat_display.config(state="normal")
            self.chat_display.insert("end", f"You: {message}\n")
            self.chat_display.config(state="disabled")
            # Clear the message entry
            self.message_entry.delete(0, tk.END)
