"""User-operated masked entry; stores the key in Windows Credential Manager."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from application.opportunities.africa_api_credentials import save_key

root=tk.Tk(); root.withdraw()
key=simpledialog.askstring('Africa API research key','Paste the key here; it will not be shown or written to the repository:',show='*',parent=root)
if key is not None:
    try:
        save_key(key.strip())
        messagebox.showinfo('Africa API','Key stored in Windows Credential Manager for this Windows account.',parent=root)
    except Exception:
        messagebox.showerror('Africa API','The key could not be stored. No key was printed or saved to a project file.',parent=root)
root.destroy()
