import tkinter as tk
from tkinter import ttk
import threading
from client import ChatClient

class ChatClientGUI(ChatClient):
    """
    Subclass of ChatClient that notifies a Tkinter GUI of important responses.
    Also tracks the last op_code we sent so we can distinguish login, creation, 
    read/unread messages, etc.
    """
    def __init__(self, gui_app, host="127.0.0.1", port=5452):
        super().__init__(host, port)
        self.gui_app = gui_app
        self.last_request_op_code = None  # Track which op_code was last sent

    def _send(self, request: dict):
        """Override _send to remember what operation we're doing."""
        self.last_request_op_code = request.get("op_code")
        super()._send(request)

    def handle_server_response(self, response: dict):
        """
        Override to update the GUI in addition to the original prints/logic.
        """
        # Keep parent logic (printing, refresh_request, etc.)
        super().handle_server_response(response)

        op_code = response.get("op_code")
        payload = response.get("payload", {})

        # 1) Reaction to "create_account_username"
        if op_code == "exists":
            self.gui_app.after(0, self.gui_app.on_username_exists)
            return
        if op_code == "ok" and payload.get("message") == "Username available for creation.":
            self.gui_app.after(0, self.gui_app.on_username_ok)
            return

        # 2) Reaction to "list_accounts"
        if op_code == "ok" and "accounts" in payload:
            accounts = payload["accounts"]
            self.gui_app.after(0, self.gui_app.update_account_list, accounts)

        # 3) For all other op_code=="ok" or "error", check self.last_request_op_code
        if op_code == "ok":
            if self.last_request_op_code == "login":
                self.gui_app.after(0, self.gui_app.on_login_success)
            elif self.last_request_op_code == "create_account_password":
                self.gui_app.after(0, self.gui_app.on_account_creation_success)
            elif self.last_request_op_code == "retrieve_unread_count":
                unread_count = payload.get("unread_count", 0)
                self.gui_app.after(0, self.gui_app.update_unread_count, unread_count)
            elif self.last_request_op_code == "load_read_messages":
                messages = payload.get("messages", [])
                self.gui_app.after(0, self.gui_app.on_read_messages_loaded, messages)
            elif self.last_request_op_code == "delete_messages":
                # Refresh the read inbox after deletion
                self.gui_app.after(0, self.gui_app.on_delete_messages_success)
            elif self.last_request_op_code == "load_unread_messages":
                # We got a list of unread messages
                messages = payload.get("messages", [])
                self.gui_app.after(0, self.gui_app.on_unread_messages_loaded, messages)
            elif self.last_request_op_code == "read_message":
                # A single message was marked read => refresh the unread inbox
                self.gui_app.after(0, self.gui_app.on_read_message_success)
            elif self.last_request_op_code == "send_message":
                # Handle send message response (success)
                self.gui_app.after(0, self.gui_app.on_send_message_response, payload)
            elif self.last_request_op_code == "delete_account":
                # After successful deletion, direct the user to UsernamePage.
                self.gui_app.after(0, self.gui_app.on_delete_account_success, payload)

        elif op_code == "error":
            error_msg = payload.get("message", "Unknown error")
            if self.last_request_op_code == "login":
                self.gui_app.after(0, self.gui_app.show_login_error, error_msg)
            elif self.last_request_op_code == "create_account_password":
                self.gui_app.after(0, self.gui_app.show_account_creation_error, error_msg)
            elif self.last_request_op_code == "send_message":
                self.gui_app.after(0, self.gui_app.on_send_message_response, payload)
            elif self.last_request_op_code == "delete_account":
                self.gui_app.after(0, self.gui_app.on_delete_account_error, error_msg)
            else:
                print("[GUI] Unhandled error:", error_msg)


#
# ----------------------- PAGES -----------------------
#

class UsernamePage(tk.Frame):
    """
    Page #1:
      - Single combobox + "Submit" button.
      - If username is found, move to LoginPage; else move to AccountCreationPage.
    """
    def __init__(self, parent, controller: "App"):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        tk.Label(self, text="Enter or select a username:").grid(
            row=0, column=0, padx=10, pady=10, sticky="e"
        )

        self.username_var = tk.StringVar()
        self.username_combobox = ttk.Combobox(
            self, textvariable=self.username_var, state="normal"
        )
        self.username_combobox.grid(row=0, column=1, padx=10, pady=10, sticky="we")

        submit_btn = tk.Button(self, text="Submit", command=self.on_submit)
        submit_btn.grid(row=0, column=2, padx=10, pady=10, sticky="w")

        # Request list of accounts to populate combobox
        self.controller.client.list_accounts()

    def on_submit(self):
        username = self.username_var.get().strip()
        if username:
            self.controller.selected_username = username
            self.controller.client.account_creation_username(username)
        else:
            print("[GUI] No username entered.")


class LoginPage(tk.Frame):
    """
    Page #2:
      - Shows the chosen username (uneditable)
      - Password input
      - Submit => calls login
      - If success => UnreadMessagesCountPage
    """
    def __init__(self, parent, controller: "App"):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Login Page").pack(pady=10)

        self.username_var = tk.StringVar()
        tk.Label(self, textvariable=self.username_var).pack(pady=5)

        tk.Label(self, text="Password:").pack()
        self.password_var = tk.StringVar()
        self.password_entry = tk.Entry(self, textvariable=self.password_var, show="*")
        self.password_entry.pack(pady=5)

        submit_btn = tk.Button(self, text="Submit", command=self.on_submit)
        submit_btn.pack(pady=10)

        self.error_label = tk.Label(self, fg="red")
        self.error_label.pack(pady=5)

    def on_show(self):
        self.username_var.set(f"Username: {self.controller.selected_username}")
        # Note: We no longer clear error_label here so that any error remains visible.
        self.password_var.set("")

    def on_submit(self):
        username = self.controller.selected_username
        password = self.password_var.get()
        self.controller.client.login(username, password)

    def show_error(self, message):
        # Display a prefixed error message on login failure.
        self.error_label.config(text=f"Login failed: {message}")



class AccountCreationPage(tk.Frame):
    """
    Page #3:
      - Shows chosen username (uneditable)
      - Password input
      - Submit => create_account_password => auto-login => UnreadMessagesCountPage
    """
    def __init__(self, parent, controller: "App"):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Account Creation Page").pack(pady=10)

        self.username_var = tk.StringVar()
        tk.Label(self, textvariable=self.username_var).pack(pady=5)

        tk.Label(self, text="Password:").pack()
        self.password_var = tk.StringVar()
        self.password_entry = tk.Entry(self, textvariable=self.password_var, show="*")
        self.password_entry.pack(pady=5)

        submit_btn = tk.Button(self, text="Create Account", command=self.on_submit)
        submit_btn.pack(pady=10)

        self.error_label = tk.Label(self, fg="red")
        self.error_label.pack(pady=5)

    def on_show(self):
        self.username_var.set(f"Username: {self.controller.selected_username}")
        self.error_label.config(text="")
        self.password_var.set("")

    def on_submit(self):
        username = self.controller.selected_username
        password = self.password_var.get()
        self.controller.new_account_password = password
        self.controller.client.account_creation_password(username, password)

    def show_error(self, message):
        self.error_label.config(text=message)


class UnreadMessagesCountPage(tk.Frame):
    """
    Page #4:
      - Shows how many unread messages the user has (retrieve_unread_count).
      - "Continue" => go to UnreadInboxPage
    """
    def __init__(self, parent, controller: "App"):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Unread Messages Count").pack(pady=10)

        self.unread_label_var = tk.StringVar(value="Loading...")
        tk.Label(self, textvariable=self.unread_label_var, font=("Arial", 14)).pack(pady=20)

        continue_btn = tk.Button(self, text="Continue", command=self.on_continue)
        continue_btn.pack(pady=10)

    def on_show(self):
        self.unread_label_var.set("Fetching unread messages count...")
        self.controller.client.retrieve_number_of_unread_messages()

    def update_unread_count(self, count):
        self.unread_label_var.set(f"You have {count} unread message(s).")

    def on_continue(self):
        # Navigate to the UnreadInboxPage
        self.controller.show_frame("UnreadInboxPage")


class UnreadInboxPage(tk.Frame):
    """
    Page #5:
      - Displays the user's unread messages in an inbox area.
      - Has a number input (default=5) to call load_unread_messages(n).
      - Each message has a "Read Message" button.
      - Contains buttons to go to the ReadMessagesPage, SendMessagePage, and DeleteAccountPage.
    """
    def __init__(self, parent, controller: "App"):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Unread Messages Inbox").pack(pady=10)

        # Container for messages
        self.inbox_frame = tk.Frame(self)
        self.inbox_frame.pack(pady=10, fill="both", expand=True)

        # Controls at bottom
        control_frame = tk.Frame(self)
        control_frame.pack(side="bottom", fill="x", pady=10)

        tk.Label(control_frame, text="Number of messages:").pack(side="left", padx=5)

        self.num_var = tk.StringVar(value="5")
        self.number_entry = tk.Entry(control_frame, textvariable=self.num_var, width=5)
        self.number_entry.pack(side="left", padx=5)

        refresh_btn = tk.Button(control_frame, text="Refresh", command=self.on_refresh)
        refresh_btn.pack(side="left", padx=5)

        send_message_btn = tk.Button(control_frame, text="Send Message", command=self.goto_send_message)
        send_message_btn.pack(side="left", padx=5)

        goto_read_btn = tk.Button(control_frame, text="Go to Read Messages", command=self.goto_read_messages)
        goto_read_btn.pack(side="left", padx=5)

        delete_account_btn = tk.Button(control_frame, text="Delete Account", command=self.goto_delete_account)
        delete_account_btn.pack(side="left", padx=5)

    def on_show(self):
        """When showing this page, load up to 5 unread messages by default."""
        self.load_unread_messages(5)

    def on_refresh(self):
        """Reload using the number from self.num_var."""
        try:
            n = int(self.num_var.get())
        except ValueError:
            n = 5
            self.num_var.set("5")
        self.load_unread_messages(n)

    def goto_read_messages(self):
        """Go to the read messages page."""
        self.controller.show_frame("ReadMessagesPage")

    def goto_send_message(self):
        """Go to the send message page."""
        self.controller.show_frame("SendMessagePage")

    def goto_delete_account(self):
        """Go to the delete account page."""
        self.controller.show_frame("DeleteAccountPage")

    def load_unread_messages(self, n: int):
        """Calls the client's load_unread_messages(n)."""
        self.controller.client.load_unread_messages(n)

    def display_messages(self, messages):
        """Display the unread messages in self.inbox_frame."""
        for child in self.inbox_frame.winfo_children():
            child.destroy()

        if not messages:
            tk.Label(self.inbox_frame, text="No unread messages.").pack(pady=5)
            return

        for msg in messages:
            sender = msg.get("sender", "")
            msg_id = msg.get("message_id", "")
            text = msg.get("message", "")

            frame = tk.Frame(self.inbox_frame, bd=1, relief="solid", padx=5, pady=5)
            frame.pack(fill="x", pady=2)

            tk.Label(frame, text=f"Sender: {sender}").pack(anchor="w")
            tk.Label(frame, text=f"Message ID: {msg_id}").pack(anchor="w")
            tk.Label(frame, text=f"Message: {text}").pack(anchor="w")

            btn = tk.Button(frame, text="Read Message", 
                            command=lambda mid=msg_id: self.on_read_message(mid))
            btn.pack(anchor="e", pady=2)

    def on_read_message(self, message_id):
        """Call read_message for this message. On success, refresh the list."""
        self.controller.client.read_message(message_id)


class ReadMessagesPage(tk.Frame):
    """
    Page #6:
      - Displays read messages with checkboxes for deletion.
      - Has a number input to load_read_messages(n) and a button to delete selected messages.
      - Contains buttons to go to the UnreadInboxPage, SendMessagePage, and DeleteAccountPage.
    """
    def __init__(self, parent, controller: "App"):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Read Messages Inbox").pack(pady=10)

        # Container for messages
        self.inbox_frame = tk.Frame(self)
        self.inbox_frame.pack(pady=10, fill="both", expand=True)

        # Controls at bottom
        control_frame = tk.Frame(self)
        control_frame.pack(side="bottom", fill="x", pady=10)

        tk.Label(control_frame, text="Number of messages:").pack(side="left", padx=5)

        self.num_var = tk.StringVar(value="5")
        self.number_entry = tk.Entry(control_frame, textvariable=self.num_var, width=5)
        self.number_entry.pack(side="left", padx=5)

        refresh_btn = tk.Button(control_frame, text="Refresh", command=self.on_refresh)
        refresh_btn.pack(side="left", padx=5)

        delete_selected_btn = tk.Button(control_frame, text="Delete Selected", command=self.on_delete_selected)
        delete_selected_btn.pack(side="left", padx=5)

        send_message_btn = tk.Button(control_frame, text="Send Message", command=self.goto_send_message)
        send_message_btn.pack(side="left", padx=5)

        goto_unread_btn = tk.Button(control_frame, text="Go to Unread Inbox", command=self.goto_unread_inbox)
        goto_unread_btn.pack(side="left", padx=5)

        delete_account_btn = tk.Button(control_frame, text="Delete Account", command=self.goto_delete_account)
        delete_account_btn.pack(side="left", padx=5)

        self.check_vars = {}

    def on_show(self):
        self.load_messages(5)

    def load_messages(self, n: int):
        self.controller.client.load_read_messages(n)

    def on_refresh(self):
        try:
            n = int(self.num_var.get())
        except ValueError:
            n = 5
            self.num_var.set("5")
        self.load_messages(n)

    def on_delete_selected(self):
        selected_ids = [msg_id for msg_id, var in self.check_vars.items() if var.get()]
        if selected_ids:
            self.controller.client.delete_messages(selected_ids)

    def goto_unread_inbox(self):
        self.controller.show_frame("UnreadInboxPage")
        
    def goto_send_message(self):
        self.controller.show_frame("SendMessagePage")

    def goto_delete_account(self):
        self.controller.show_frame("DeleteAccountPage")

    def display_messages(self, messages):
        for child in self.inbox_frame.winfo_children():
            child.destroy()

        self.check_vars.clear()

        if not messages:
            tk.Label(self.inbox_frame, text="No read messages.").pack(pady=5)
            return

        for msg in messages:
            sender = msg.get("sender", "")
            msg_id = msg.get("message_id", "")
            text = msg.get("message", "")

            var = tk.BooleanVar()
            self.check_vars[msg_id] = var

            frame = tk.Frame(self.inbox_frame, bd=1, relief="solid", padx=5, pady=5)
            frame.pack(fill="x", pady=2)

            chk = tk.Checkbutton(frame, variable=var)
            chk.pack(anchor="ne")

            tk.Label(frame, text=f"Sender: {sender}").pack(anchor="w")
            tk.Label(frame, text=f"Message ID: {msg_id}").pack(anchor="w")
            tk.Label(frame, text=f"Message: {text}").pack(anchor="w")


class SendMessagePage(tk.Frame):
    """
    Page for sending a message:
      - Contains a dropdown to select a recipient (excluding the current user).
      - Contains a multi-line input field for the message.
      - A Send button calls send_message.
      - Displays the result (success or error) returned from the server.
      - Also includes a button to go to the ReadMessagesPage.
    """
    def __init__(self, parent, controller: "App"):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Send Message Page", font=("Arial", 16)).pack(pady=20)

        # Recipient dropdown input
        recipient_frame = tk.Frame(self)
        recipient_frame.pack(pady=10, fill="x", padx=20)
        tk.Label(recipient_frame, text="Recipient:").pack(side="left")
        self.recipient_var = tk.StringVar()
        self.recipient_combobox = ttk.Combobox(recipient_frame, textvariable=self.recipient_var, state="readonly")
        self.recipient_combobox.pack(side="left", fill="x", expand=True, padx=5)

        # Message input field (Text widget)
        tk.Label(self, text="Message:").pack(pady=(10, 0))
        self.message_text = tk.Text(self, height=10, width=50)
        self.message_text.pack(pady=5, padx=20)

        # Send button
        send_btn = tk.Button(self, text="Send", command=self.send_message)
        send_btn.pack(pady=10)

        # Label to display the server response result
        self.result_label = tk.Label(self, text="", fg="blue")
        self.result_label.pack(pady=5)

        # Button to go to Read Messages page
        goto_read_btn = tk.Button(self, text="Go to Read Messages", command=self.goto_read_messages)
        goto_read_btn.pack(pady=10)

    def on_show(self):
        # Clear the message field and result label each time this page is shown.
        self.message_text.delete("1.0", tk.END)
        self.result_label.config(text="")
        # Refresh the recipient list.
        self.controller.client.list_accounts()

    def send_message(self):
        recipient = self.recipient_var.get().strip()
        message = self.message_text.get("1.0", tk.END).strip()
        if not recipient:
            self.result_label.config(text="Please select a recipient.", fg="red")
            return
        if not message:
            self.result_label.config(text="Please enter a message.", fg="red")
            return

        # Call the client's send_message function.
        self.controller.client.send_message(recipient, message)

    def display_result(self, result_message):
        self.result_label.config(text=result_message, fg="blue")

    def goto_read_messages(self):
        self.controller.show_frame("ReadMessagesPage")


class DeleteAccountPage(tk.Frame):
    """
    New Page: Delete Account
      - Displays a warning that deleting the account will permanently delete all messages.
      - Contains a button to call delete_account.
      - After a successful deletion, the user is directed to the UsernamePage.
      - Also includes a Cancel button to return to the UnreadInboxPage.
    """
    def __init__(self, parent, controller: "App"):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Delete Account", font=("Arial", 16)).pack(pady=20)

        warning_text = ("Warning: Deleting your account will permanently delete all your messages.\n"
                        "Are you sure you want to proceed?")
        tk.Label(self, text=warning_text, wraplength=400, fg="red").pack(pady=10)

        delete_btn = tk.Button(self, text="Delete Account", command=self.delete_account)
        delete_btn.pack(pady=10)

        self.result_label = tk.Label(self, text="", fg="blue")
        self.result_label.pack(pady=5)

        cancel_btn = tk.Button(self, text="Cancel", command=self.cancel)
        cancel_btn.pack(pady=10)

    def on_show(self):
        self.result_label.config(text="")

    def delete_account(self):
        self.controller.client.delete_account()

    def display_result(self, message, error=False):
        color = "red" if error else "blue"
        self.result_label.config(text=message, fg=color)

    def cancel(self):
        self.controller.show_frame("UnreadInboxPage")


#
# ---------------------- MAIN APP ----------------------
#

class App(tk.Tk):
    """
    Main Tk app controlling 8 pages:
      1) UsernamePage
      2) LoginPage
      3) AccountCreationPage
      4) UnreadMessagesCountPage
      5) UnreadInboxPage
      6) ReadMessagesPage
      7) SendMessagePage
      8) DeleteAccountPage  <-- New page for account deletion
    """
    def __init__(self, host="127.0.0.1", port=5452):
        super().__init__()
        self.title("Chat Client GUI")
        self.geometry("1024x1024")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

        self.selected_username = ""
        self.new_account_password = ""

        self.client = ChatClientGUI(self, host, port)
        self.client.connect()

        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        # Create the 8 pages
        for PageClass in (
            UsernamePage,
            LoginPage,
            AccountCreationPage,
            UnreadMessagesCountPage,
            UnreadInboxPage,
            ReadMessagesPage,
            SendMessagePage,
            DeleteAccountPage
        ):
            page_name = PageClass.__name__
            frame = PageClass(container, self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Start on UsernamePage
        self.show_frame("UsernamePage")

    def show_frame(self, page_name):
        """
        Lift the specified page and call .on_show() if it exists.
        """
        frame = self.frames[page_name]
        if hasattr(frame, "on_show"):
            frame.on_show()
        frame.tkraise()

    def on_window_close(self):
        self.client.quit()
        self.destroy()

    # === Methods called by ChatClientGUI ===

    def on_username_exists(self):
        self.show_frame("LoginPage")

    def on_username_ok(self):
        self.show_frame("AccountCreationPage")

    def on_login_success(self):
        # Go to the "count" page
        self.show_frame("UnreadMessagesCountPage")

    def show_login_error(self, error_message):
        login_page = self.frames["LoginPage"]
        login_page.show_error(error_message)
        self.show_frame("LoginPage")

    def on_account_creation_success(self):
        self.client.login(self.selected_username, self.new_account_password)

    def show_account_creation_error(self, error_message):
        creation_page = self.frames["AccountCreationPage"]
        creation_page.show_error(error_message)
        self.show_frame("AccountCreationPage")

    def update_unread_count(self, count):
        """
        Update the UnreadMessagesCountPage with the unread count.
        """
        page = self.frames["UnreadMessagesCountPage"]
        page.update_unread_count(count)

    def on_read_messages_loaded(self, messages):
        """
        Show read messages in the ReadMessagesPage.
        """
        page = self.frames["ReadMessagesPage"]
        page.display_messages(messages)

    def on_delete_messages_success(self):
        """
        After delete_messages is successful, re-refresh the ReadMessagesPage.
        """
        page = self.frames["ReadMessagesPage"]
        page.on_refresh()

    def update_account_list(self, accounts):
        """
        Fill the combobox in UsernamePage with the list of accounts.
        Also update the recipient dropdown in SendMessagePage, excluding the current user.
        """
        page = self.frames["UsernamePage"]
        page.username_combobox["values"] = accounts

        send_page = self.frames["SendMessagePage"]
        if self.selected_username:
            recipients = [user for user in accounts if user != self.selected_username]
        else:
            recipients = accounts
        send_page.recipient_combobox["values"] = recipients

    def on_unread_messages_loaded(self, messages):
        """
        Called after load_unread_messages returns.
        """
        unread_inbox = self.frames["UnreadInboxPage"]
        unread_inbox.display_messages(messages)

    def on_read_message_success(self):
        """
        Called after read_message. Refresh the UnreadInboxPage.
        """
        unread_inbox = self.frames["UnreadInboxPage"]
        unread_inbox.on_refresh()

    def on_send_message_response(self, payload):
        """
        Called after send_message returns.
        Displays the result on the SendMessagePage.
        """
        page = self.frames["SendMessagePage"]
        message = payload.get("message", "")
        page.display_result(message)

    def on_delete_account_success(self, payload):
        """
        Called after a successful delete_account response.
        Clears the current user and directs the user to the UsernamePage.
        """
        self.selected_username = ""
        self.show_frame("UsernamePage")

    def on_delete_account_error(self, error_msg):
        """
        Called if delete_account returns an error.
        Displays the error on the DeleteAccountPage.
        """
        page = self.frames["DeleteAccountPage"]
        page.display_result(error_msg, error=True)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
