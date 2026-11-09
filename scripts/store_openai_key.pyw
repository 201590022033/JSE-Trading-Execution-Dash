"""Store an OpenAI API key locally, without changing account sign-in."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from application.opportunities.africa_api_credentials import save_key

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
key = simpledialog.askstring(
    'OpenAI API key',
    'Paste your OpenAI API key. It will be stored in Windows Credential Manager '
    'for this Windows account. This does not change your ChatGPT sign-in.',
    show='*', parent=root,
)
if key is not None:
    try:
        save_key(key.strip(), target='JSETrading/OpenAI/Research')
        messagebox.showinfo('OpenAI API key',
            'Stored in Windows Credential Manager. The dashboard is not yet connected to this key.', parent=root)
    except Exception:
        messagebox.showerror('OpenAI API key', 'The key could not be stored. Check the key and try again.', parent=root)
root.destroy()
