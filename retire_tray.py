{\rtf1\ansi\ansicpg936\cocoartf2868
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx566\tx1133\tx1700\tx2267\tx2834\tx3401\tx3968\tx4535\tx5102\tx5669\tx6236\tx6803\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import tkinter as tk\
from tkinter import messagebox\
import pystray\
from PIL import Image, ImageDraw, ImageFont\
import json\
import os\
import sys\
from datetime import datetime, date\
from dateutil.relativedelta import relativedelta\
import threading\
import time\
import math\
import platform\
\
# ---------- \uc0\u37197 \u32622 \u36335 \u24452  ----------\
APP_NAME = "RetireProgress"\
if platform.system() == "Windows":\
    CONFIG_DIR = os.path.join(os.environ['APPDATA'], APP_NAME)\
else:\
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), "." + APP_NAME)\
os.makedirs(CONFIG_DIR, exist_ok=True)\
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")\
\
# ---------- \uc0\u40664 \u35748 \u37197 \u32622  ----------\
DEFAULT_CONFIG = \{\
    "target_amount": 1000000.0,\
    "current_savings": 0.0,\
    "monthly_savings": 5000.0,\
    "annual_rate": 3.0,\
    "last_update_month": ""\
\}\
\
# ---------- \uc0\u36864 \u20241 \u35745 \u31639 \u20989 \u25968  ----------\
def calculate_retirement(P, M, r_percent, F):\
    """\uc0\u36820 \u22238  (\u21097 \u20313 \u26376 \u25968 , \u30446 \u26631 \u26085 \u26399 , \u21487 \u35835 \u23383 \u31526 \u20018 )"""\
    if P >= F:\
        return 0, datetime.now().date(), "\uc0\u55356 \u57225  \u24050 \u36798 \u26631 \u65281 "\
    r = r_percent / 100.0\
    if r == 0:\
        if M <= 0:\
            return float('inf'), None, "\uc0\u26376 \u20648 \u33988 \u24517 \u39035 \u22823 \u20110 0"\
        months_needed = (F - P) / M\
    else:\
        rm = r / 12\
        if P + M/rm <= 0:\
            return float('inf'), None, "\uc0\u21442 \u25968 \u38169 \u35823 "\
        numerator = (F + M/rm) / (P + M/rm)\
        if numerator <= 0:\
            return float('inf'), None, "\uc0\u26080 \u27861 \u36798 \u21040 \u30446 \u26631 "\
        months_needed = math.log(numerator) / math.log(1 + rm)\
\
    today = datetime.now().date()\
    days_needed = months_needed * 30.44  # \uc0\u24179 \u22343 \u27599 \u26376 \u22825 \u25968 \
    target_date = today + relativedelta(days=int(days_needed))\
    delta = relativedelta(target_date, today)\
    readable = f"\{delta.years\}\uc0\u24180 \{delta.months\}\u26376 \{delta.days\}\u22825 "\
    return months_needed, target_date, readable\
\
# ---------- \uc0\u25176 \u30424 \u22270 \u26631 \u22270 \u20687  ----------\
def create_image():\
    width, height = 64, 64\
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))\
    draw = ImageDraw.Draw(image)\
    try:\
        font = ImageFont.truetype("seguiemj.ttf", 48)  # Windows\uc0\u34920 \u24773 \u23383 \u20307 \
    except:\
        font = ImageFont.load_default()\
    draw.text((8, 8), "\uc0\u55356 \u57302 \u65039 ", fill="black", font=font)\
    return image\
\
# ---------- \uc0\u20027 \u24212 \u29992 \u31243 \u24207  ----------\
class RetirementApp:\
    def __init__(self):\
        self.config = self.load_config()\
        self.window = None\
        self.tray_icon = None\
        self.running = True\
        self.init_tray()\
        self.start_update_checker()\
\
    def load_config(self):\
        if os.path.exists(CONFIG_FILE):\
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:\
                return json.load(f)\
        return DEFAULT_CONFIG.copy()\
\
    def save_config(self):\
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:\
            json.dump(self.config, f, indent=2)\
\
    def init_tray(self):\
        menu = pystray.Menu(\
            pystray.MenuItem("\uc0\u25171 \u24320 \u35774 \u32622 ", self.show_window),\
            pystray.MenuItem("\uc0\u36864 \u20986 ", self.quit_app)\
        )\
        self.tray_icon = pystray.Icon("retire_icon", create_image, "\uc0\u36864 \u20241 \u36827 \u24230 \u26465 ", menu)\
        threading.Thread(target=self.tray_icon.run, daemon=True).start()\
\
    def show_window(self):\
        if self.window is not None and self.window.winfo_exists():\
            self.window.lift()\
            return\
        self.window = tk.Tk()\
        self.window.title("\uc0\u36864 \u20241 \u36827 \u24230 \u35774 \u32622 ")\
        self.window.geometry("400x350")\
        self.window.resizable(False, False)\
\
        # \uc0\u36755 \u20837 \u23383 \u27573 \
        tk.Label(self.window, text="\uc0\u30446 \u26631 \u36864 \u20241 \u37329 \u39069  (\'a5)").pack(pady=5)\
        self.entry_target = tk.Entry(self.window)\
        self.entry_target.pack()\
        self.entry_target.insert(0, str(self.config['target_amount']))\
\
        tk.Label(self.window, text="\uc0\u24403 \u21069 \u24050 \u26377 \u20648 \u33988  (\'a5)").pack(pady=5)\
        self.entry_current = tk.Entry(self.window)\
        self.entry_current.pack()\
        self.entry_current.insert(0, str(self.config['current_savings']))\
\
        tk.Label(self.window, text="\uc0\u26412 \u26376 \u39044 \u35745 \u20648 \u33988  (\'a5)").pack(pady=5)\
        self.entry_monthly = tk.Entry(self.window)\
        self.entry_monthly.pack()\
        self.entry_monthly.insert(0, str(self.config['monthly_savings']))\
\
        tk.Label(self.window, text="\uc0\u39044 \u26399 \u24180 \u21270 \u25910 \u30410 \u29575  (%)").pack(pady=5)\
        self.entry_rate = tk.Entry(self.window)\
        self.entry_rate.pack()\
        self.entry_rate.insert(0, str(self.config['annual_rate']))\
\
        self.result_label = tk.Label(self.window, text="", fg="blue", justify="left")\
        self.result_label.pack(pady=10)\
\
        tk.Button(self.window, text="\uc0\u35745 \u31639 \u24182 \u20445 \u23384 ", command=self.calculate_and_save).pack(pady=10)\
\
        self.update_result_display()\
        self.window.protocol("WM_DELETE_WINDOW", self.hide_window)\
        self.window.mainloop()\
\
    def hide_window(self):\
        self.window.destroy()\
        self.window = None\
\
    def calculate_and_save(self):\
        try:\
            target = float(self.entry_target.get())\
            current = float(self.entry_current.get())\
            monthly = float(self.entry_monthly.get())\
            rate = float(self.entry_rate.get())\
        except ValueError:\
            messagebox.showerror("\uc0\u38169 \u35823 ", "\u35831 \u36755 \u20837 \u26377 \u25928 \u30340 \u25968 \u23383 ")\
            return\
\
        self.config['target_amount'] = target\
        self.config['current_savings'] = current\
        self.config['monthly_savings'] = monthly\
        self.config['annual_rate'] = rate\
        self.save_config()\
        self.update_result_display()\
\
    def update_result_display(self):\
        if self.window is None or not self.window.winfo_exists():\
            return\
        P = self.config['current_savings']\
        M = self.config['monthly_savings']\
        r = self.config['annual_rate']\
        F = self.config['target_amount']\
        months, target_date, readable = calculate_retirement(P, M, r, F)\
        if target_date:\
            text = f"\uc0\u30446 \u26631 \u36864 \u20241 \u26085 \u65306 \{target_date\}\\n\u21097 \u20313 \u65306 \{readable\}\\n(\u22522 \u20110 \u26376 \u22797 \u21033 \u20272 \u31639 )"\
        else:\
            text = readable\
        self.result_label.config(text=text)\
\
    def start_update_checker(self):\
        def check():\
            while self.running:\
                today = datetime.now()\
                if today.day == 1:\
                    current_month = today.strftime("%Y-%m")\
                    if self.config.get('last_update_month') != current_month:\
                        self.apply_monthly_update()\
                time.sleep(3600)  # \uc0\u27599 \u23567 \u26102 \u26816 \u26597 \u19968 \u27425 \
        threading.Thread(target=check, daemon=True).start()\
\
    def apply_monthly_update(self):\
        """\uc0\u27599 \u26376 1\u21495 \u25191 \u34892 \u65306 \u20808 \u21152 \u26376 \u21033 \u24687 \u65292 \u20877 \u21152 \u26376 \u23384 \u27454 """\
        if self.config['annual_rate'] > 0:\
            monthly_rate = self.config['annual_rate'] / 100 / 12\
            interest = self.config['current_savings'] * monthly_rate\
            self.config['current_savings'] = round(self.config['current_savings'] + interest, 2)\
        self.config['current_savings'] += self.config['monthly_savings']\
        self.config['last_update_month'] = datetime.now().strftime("%Y-%m")\
        self.save_config()\
        if self.tray_icon:\
            self.tray_icon.notify("\uc0\u55357 \u56517  \u27599 \u26376 \u26356 \u26032 ", f"\u24050 \u23384 \u20837 \u26412 \u26376 \'a5\{self.config['monthly_savings']:,.2f\}\\n\u24403 \u21069 \u24635 \u20648 \u33988 \u65306 \'a5\{self.config['current_savings']:,.2f\}")\
        # \uc0\u22914 \u26524 \u31383 \u21475 \u24320 \u30528 \u65292 \u21047 \u26032 \u26174 \u31034 \
        if self.window and self.window.winfo_exists():\
            self.window.after(0, self.update_result_display)\
\
    def quit_app(self):\
        self.running = False\
        if self.tray_icon:\
            self.tray_icon.stop()\
        sys.exit(0)\
\
if __name__ == "__main__":\
    app = RetirementApp()}