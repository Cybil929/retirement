import tkinter as tk
from tkinter import messagebox
import pystray
from PIL import Image, ImageDraw, ImageFont
import json
import os
import sys
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import threading
import time
import math
import platform

# ---------- 配置路径 ----------
APP_NAME = "RetireProgress"
if platform.system() == "Windows":
    CONFIG_DIR = os.path.join(os.environ['APPDATA'], APP_NAME)
else:
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), "." + APP_NAME)
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# ---------- 默认配置 ----------
DEFAULT_CONFIG = {
    "target_amount": 1000000.0,
    "current_savings": 0.0,
    "monthly_savings": 5000.0,
    "annual_rate": 3.0,
    "last_update_month": ""
}

# ---------- 退休计算函数 ----------
def calculate_retirement(P, M, r_percent, F):
    """返回 (剩余月数, 目标日期, 可读字符串)"""
    if P >= F:
        return 0, datetime.now().date(), "🎉 已达标！"
    r = r_percent / 100.0
    if r == 0:
        if M <= 0:
            return float('inf'), None, "月储蓄必须大于0"
        months_needed = (F - P) / M
    else:
        rm = r / 12
        if P + M/rm <= 0:
            return float('inf'), None, "参数错误"
        numerator = (F + M/rm) / (P + M/rm)
        if numerator <= 0:
            return float('inf'), None, "无法达到目标"
        months_needed = math.log(numerator) / math.log(1 + rm)

    today = datetime.now().date()
    days_needed = months_needed * 30.44  # 平均每月天数
    target_date = today + relativedelta(days=int(days_needed))
    delta = relativedelta(target_date, today)
    readable = f"{delta.years}年{delta.months}月{delta.days}天"
    return months_needed, target_date, readable

# ---------- 托盘图标图像 ----------
def create_image():
    width, height = 64, 64
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("seguiemj.ttf", 48)  # Windows表情字体
    except:
        font = ImageFont.load_default()
    draw.text((8, 8), "🏖️", fill="black", font=font)
    return image

# ---------- 主应用程序 ----------
class RetirementApp:
    def __init__(self):
        self.config = self.load_config()
        self.window = None
        self.tray_icon = None
        self.running = True
        self.init_tray()
        self.start_update_checker()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)

    def init_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("打开设置", self.show_window),
            pystray.MenuItem("退出", self.quit_app)
        )
        self.tray_icon = pystray.Icon("retire_icon", create_image, "退休进度条", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.lift()
            return
        self.window = tk.Tk()
        self.window.title("退休进度设置")
        self.window.geometry("400x350")
        self.window.resizable(False, False)

        # 输入字段
        tk.Label(self.window, text="目标退休金额 (¥)").pack(pady=5)
        self.entry_target = tk.Entry(self.window)
        self.entry_target.pack()
        self.entry_target.insert(0, str(self.config['target_amount']))

        tk.Label(self.window, text="当前已有储蓄 (¥)").pack(pady=5)
        self.entry_current = tk.Entry(self.window)
        self.entry_current.pack()
        self.entry_current.insert(0, str(self.config['current_savings']))

        tk.Label(self.window, text="本月预计储蓄 (¥)").pack(pady=5)
        self.entry_monthly = tk.Entry(self.window)
        self.entry_monthly.pack()
        self.entry_monthly.insert(0, str(self.config['monthly_savings']))

        tk.Label(self.window, text="预期年化收益率 (%)").pack(pady=5)
        self.entry_rate = tk.Entry(self.window)
        self.entry_rate.pack()
        self.entry_rate.insert(0, str(self.config['annual_rate']))

        self.result_label = tk.Label(self.window, text="", fg="blue", justify="left")
        self.result_label.pack(pady=10)

        tk.Button(self.window, text="计算并保存", command=self.calculate_and_save).pack(pady=10)

        self.update_result_display()
        self.window.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.window.mainloop()

    def hide_window(self):
        self.window.destroy()
        self.window = None

    def calculate_and_save(self):
        try:
            target = float(self.entry_target.get())
            current = float(self.entry_current.get())
            monthly = float(self.entry_monthly.get())
            rate = float(self.entry_rate.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return

        self.config['target_amount'] = target
        self.config['current_savings'] = current
        self.config['monthly_savings'] = monthly
        self.config['annual_rate'] = rate
        self.save_config()
        self.update_result_display()

    def update_result_display(self):
        if self.window is None or not self.window.winfo_exists():
            return
        P = self.config['current_savings']
        M = self.config['monthly_savings']
        r = self.config['annual_rate']
        F = self.config['target_amount']
        months, target_date, readable = calculate_retirement(P, M, r, F)
        if target_date:
            text = f"目标退休日：{target_date}\n剩余：{readable}\n(基于月复利估算)"
        else:
            text = readable
        self.result_label.config(text=text)

    def start_update_checker(self):
        def check():
            while self.running:
                today = datetime.now()
                if today.day == 1:
                    current_month = today.strftime("%Y-%m")
                    if self.config.get('last_update_month') != current_month:
                        self.apply_monthly_update()
                time.sleep(3600)  # 每小时检查一次
        threading.Thread(target=check, daemon=True).start()

    def apply_monthly_update(self):
        """每月1号执行：先加月利息，再加月存款"""
        if self.config['annual_rate'] > 0:
            monthly_rate = self.config['annual_rate'] / 100 / 12
            interest = self.config['current_savings'] * monthly_rate
            self.config['current_savings'] = round(self.config['current_savings'] + interest, 2)
        self.config['current_savings'] += self.config['monthly_savings']
        self.config['last_update_month'] = datetime.now().strftime("%Y-%m")
        self.save_config()
        if self.tray_icon:
            self.tray_icon.notify("📅 每月更新", f"已存入本月¥{self.config['monthly_savings']:,.2f}\n当前总储蓄：¥{self.config['current_savings']:,.2f}")
        # 如果窗口开着，刷新显示
        if self.window and self.window.winfo_exists():
            self.window.after(0, self.update_result_display)

    def quit_app(self):
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()
        sys.exit(0)

if __name__ == "__main__":
    app = RetirementApp()
