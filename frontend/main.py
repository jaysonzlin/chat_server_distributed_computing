import tkinter as tk
from tkinter import ttk

# Import the pages
from login_page import LoginPage
from chat_page import ChatPage

class MainApplication(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Chat/Login Application")
        self.geometry("800x800")
        
        # Create a container to stack the pages on top of each other
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        
        # Configure the grid to expand with the window
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # Dictionary to hold pages
        self.frames = {}
        
        # Instantiate each page and place them in the same location;
        # the one on the top of the stacking order will be visible.
        for PageClass, page_name in zip((LoginPage, ChatPage), ("LoginPage", "ChatPage")):
            frame = PageClass(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        # Show the login page first
        self.show_frame("LoginPage")
    
    def show_frame(self, page_name):
        """Bring the frame with the given page_name to the front."""
        frame = self.frames[page_name]
        frame.tkraise()

if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()
