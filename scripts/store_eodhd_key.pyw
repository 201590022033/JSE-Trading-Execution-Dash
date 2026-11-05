"""User-operated masked EODHD key entry into Windows Credential Manager."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from application.opportunities.africa_api_credentials import save_key

root = tk.Tk()
root.withdraw()
key = simpledialog.askstring('EODHD research key', 'Paste the API key here; it will not be displayed or saved in the repository:', show='*', parent=root)
if key is not None:
    try:
        save_key(key.strip(), target='JSETrading/EODHD/Research')
        messagebox.showinfo('EODHD', 'Key stored in Windows Credential Manager for this Windows account.', parent=root)
    except Exception:
        messagebox.showerror('EODHD', 'The key could not be stored.', parent=root)
root.destroy()
