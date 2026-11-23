import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from agent_engine import EmployeeMonitorEngine, load_config, save_config

class EmployeeMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UltraMonitor - Client Software")
        self.root.geometry("640 x 680")
        self.root.minsize(580, 600)
        
        # Dark Theme Palette
        self.bg_color = "#0f172a"
        self.card_bg = "#1e293b"
        self.fg_color = "#f8fafc"
        self.muted_color = "#94a3b8"
        self.accent_blue = "#3b82f6"
        self.accent_green = "#10b981"
        self.accent_red = "#ef4444"
        
        self.root.configure(bg=self.bg_color)
        
        # Load Config
        self.config = load_config()
        
        # Initialize Engine
        self.engine = EmployeeMonitorEngine(log_callback=self.log_message)
        
        self._build_ui()
        self._load_config_to_fields()
        
        # Auto start if configured
        if self.config.get('auto_start', False):
            self.start_service()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TFrame', background=self.bg_color)
        style.configure('Card.TFrame', background=self.card_bg)

        # Header Frame
        header = tk.Frame(self.root, bg=self.card_bg, padx=20, pady=15)
        header.pack(fill='x')
        
        title_lbl = tk.Label(header, text="💻 UltraMonitor Client", font=("Segoe UI", 16, "bold"), fg="#ffffff", bg=self.card_bg)
        title_lbl.pack(anchor='w')
        
        subtitle_lbl = tk.Label(header, text="Records laptop screen activity & streams compressed clips to Django server", font=("Segoe UI", 9), fg=self.muted_color, bg=self.card_bg)
        subtitle_lbl.pack(anchor='w')

        # Status Bar Frame
        status_frame = tk.Frame(self.root, bg=self.bg_color, padx=20, pady=10)
        status_frame.pack(fill='x')

        tk.Label(status_frame, text="Service Status:", font=("Segoe UI", 10, "bold"), fg=self.fg_color, bg=self.bg_color).pack(side='left')
        
        self.status_lbl = tk.Label(
            status_frame, 
            text="STOPPED", 
            font=("Segoe UI", 9, "bold"), 
            fg="#ffffff", 
            bg=self.accent_red, 
            padx=10, 
            pady=3
        )
        self.status_lbl.pack(side='left', padx=10)

        # Configuration Card
        config_card = tk.LabelFrame(self.root, text=" Server & Employee Connection Settings ", font=("Segoe UI", 10, "bold"), fg=self.accent_blue, bg=self.card_bg, padx=15, pady=15)
        config_card.pack(fill='x', padx=20, pady=10)

        # Server URL
        tk.Label(config_card, text="Django Server URL:", font=("Segoe UI", 9), fg=self.fg_color, bg=self.card_bg).grid(row=0, column=0, sticky='w', pady=5)
        self.server_url_entry = tk.Entry(config_card, font=("Segoe UI", 9), bg="#0f172a", fg="#ffffff", insertbackground="#ffffff", borderwidth=1)
        self.server_url_entry.grid(row=0, column=1, sticky='ew', pady=5, padx=10)

        # Employee Code
        tk.Label(config_card, text="Employee Code:", font=("Segoe UI", 9), fg=self.fg_color, bg=self.card_bg).grid(row=1, column=0, sticky='w', pady=5)
        self.emp_code_entry = tk.Entry(config_card, font=("Segoe UI", 9), bg="#0f172a", fg="#ffffff", insertbackground="#ffffff", borderwidth=1)
        self.emp_code_entry.grid(row=1, column=1, sticky='ew', pady=5, padx=10)

        # Employee Name
        tk.Label(config_card, text="Employee Name:", font=("Segoe UI", 9), fg=self.fg_color, bg=self.card_bg).grid(row=2, column=0, sticky='w', pady=5)
        self.emp_name_entry = tk.Entry(config_card, font=("Segoe UI", 9), bg="#0f172a", fg="#ffffff", insertbackground="#ffffff", borderwidth=1)
        self.emp_name_entry.grid(row=2, column=1, sticky='ew', pady=5, padx=10)

        # Video Segment Duration Dropdown (5, 15, 30, 60 minutes / 1 Hour)
        tk.Label(config_card, text="Clip Duration:", font=("Segoe UI", 9), fg=self.fg_color, bg=self.card_bg).grid(row=3, column=0, sticky='w', pady=5)
        self.duration_combo = ttk.Combobox(
            config_card, 
            values=["5 Minutes", "15 Minutes", "30 Minutes", "60 Minutes (1 Hour)"],
            state="readonly",
            font=("Segoe UI", 9)
        )
        self.duration_combo.grid(row=3, column=1, sticky='ew', pady=5, padx=10)

        config_card.columnconfigure(1, weight=1)

        # Action Buttons Frame
        btn_frame = tk.Frame(self.root, bg=self.bg_color, padx=20, pady=5)
        btn_frame.pack(fill='x')

        self.start_btn = tk.Button(
            btn_frame, 
            text="▶ Start Monitoring", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.accent_green, 
            fg="#ffffff", 
            activebackground="#059669", 
            activeforeground="#ffffff", 
            padx=15, 
            pady=6, 
            borderwidth=0, 
            command=self.start_service
        )
        self.start_btn.pack(side='left', marginRight=10, padx=5)

        self.stop_btn = tk.Button(
            btn_frame, 
            text="⏹ Stop Service", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.accent_red, 
            fg="#ffffff", 
            activebackground="#dc2626", 
            activeforeground="#ffffff", 
            padx=15, 
            pady=6, 
            borderwidth=0, 
            state='disabled', 
            command=self.stop_service
        )
        self.stop_btn.pack(side='left', padx=5)

        self.save_btn = tk.Button(
            btn_frame, 
            text="💾 Save Config", 
            font=("Segoe UI", 9), 
            bg="#334155", 
            fg="#ffffff", 
            padx=10, 
            pady=6, 
            borderwidth=0, 
            command=self.save_settings
        )
        self.save_btn.pack(side='right', padx=5)

        self.test_btn = tk.Button(
            btn_frame, 
            text="🔌 Test Connection", 
            font=("Segoe UI", 9), 
            bg="#334155", 
            fg="#ffffff", 
            padx=10, 
            pady=6, 
            borderwidth=0, 
            command=self.test_connection
        )
        self.test_btn.pack(side='right', padx=5)

        # Live Console Output Window
        console_frame = tk.LabelFrame(self.root, text=" Software Activity Log ", font=("Segoe UI", 10, "bold"), fg=self.muted_color, bg=self.card_bg, padx=10, pady=10)
        console_frame.pack(fill='both', expand=True, padx=20, pady=10)

        self.log_area = scrolledtext.ScrolledText(
            console_frame, 
            wrap=tk.WORD, 
            font=("Consolas", 9), 
            bg="#090d16", 
            fg="#38bdf8", 
            insertbackground="#ffffff"
        )
        self.log_area.pack(fill='both', expand=True)

    def _load_config_to_fields(self):
        self.server_url_entry.delete(0, tk.END)
        self.server_url_entry.insert(0, self.config.get('server_url', 'http://127.0.0.1:8000'))
        
        self.emp_code_entry.delete(0, tk.END)
        self.emp_code_entry.insert(0, self.config.get('employee_code', 'EMP001'))

        self.emp_name_entry.delete(0, tk.END)
        self.emp_name_entry.insert(0, self.config.get('employee_name', 'Demo Employee'))

        dur_mins = self.config.get('chunk_duration_minutes', 60)
        if dur_mins == 60:
            self.duration_combo.set("60 Minutes (1 Hour)")
        elif dur_mins == 30:
            self.duration_combo.set("30 Minutes")
        elif dur_mins == 15:
            self.duration_combo.set("15 Minutes")
        else:
            self.duration_combo.set("5 Minutes")

    def save_settings(self):
        dur_str = self.duration_combo.get()
        if "60" in dur_str or "1 Hour" in dur_str:
            dur_mins = 60
        elif "30" in dur_str:
            dur_mins = 30
        elif "15" in dur_str:
            dur_mins = 15
        else:
            dur_mins = 5

        new_config = {
            "server_url": self.server_url_entry.get().strip(),
            "employee_code": self.emp_code_entry.get().strip(),
            "employee_name": self.emp_name_entry.get().strip(),
            "chunk_duration_minutes": dur_mins,
            "fps": 2,
            "target_width": 1280,
            "target_height": 720
        }

        if save_config(new_config):
            self.config = new_config
            self.engine.reload_config()
            messagebox.showinfo("Success", "Configuration saved successfully!")
            self.log_message("Settings saved.")
        else:
            messagebox.showerror("Error", "Failed to write configuration file!")

    def test_connection(self):
        self.save_settings()
        self.log_message("Testing connection to Django server...")
        def _test():
            ok, msg = self.engine.test_connection()
            if ok:
                messagebox.showinfo("Connection Test", msg)
                self.log_message(f"Test Success: {msg}")
            else:
                messagebox.showerror("Connection Test", msg)
                self.log_message(f"Test Failed: {msg}")
        threading.Thread(target=_test, daemon=True).start()

    def start_service(self):
        self.save_settings()
        self.engine.start_recording_service()
        self.status_lbl.config(text="RECORDING ACTIVE", bg=self.accent_green)
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.log_message("Monitoring service STARTED. Recording screen in background...")

    def stop_service(self):
        self.engine.stop_recording_service()
        self.status_lbl.config(text="STOPPED", bg=self.accent_red)
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.log_message("Monitoring service STOPPED.")

    def log_message(self, message):
        def _write():
            self.log_area.insert(tk.END, f"{message}\n")
            self.log_area.see(tk.END)
        self.root.after(0, _write)

if __name__ == "__main__":
    root = tk.Tk()
    app = EmployeeMonitorApp(root)
    root.mainloop()
