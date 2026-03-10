#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
躺平进度条 - Windows系统托盘退休倒计时工具

功能说明:
- 在系统托盘显示图标，显示距离退休还剩多少时间
- 每月第一天自动提醒更新存款（支持点击通知直接打开更新窗口）
- 支持考虑年化收益率的复利计算

===========================================================================
                          一键打包说明
===========================================================================

方法1：使用打包脚本（推荐）
--------------------------
1. 确保已安装 Python 3.8 或更高版本

2. 双击运行 pack.bat 或在命令行执行:
   .\pack.bat

3. 打包完成后，exe 文件位于 dist/躺平进度条.exe

方法2：手动打包
--------------------------
1. 安装依赖:
   pip install pystray Pillow python-dateutil plyer win10toast-click pyinstaller

2. 使用 PyInstaller 打包为单个 exe 文件:
   pyinstaller --onefile --noconsole ^
       --hidden-import=pystray ^
       --hidden-import=PIL ^
       --hidden-import=PIL._imagingtk ^
       --hidden-import=PIL._tkinter_finder ^
       --hidden-import=dateutil ^
       --hidden-import=plyer ^
       --hidden-import=plyer.platforms.win.notification ^
       --hidden-import=win10toast_click ^
       --add-data "config.json;." ^
       --name="躺平进度条" ^
       retirement_tray.py

3. 打包完成后，exe 文件位于 dist/躺平进度条.exe

===========================================================================
                          依赖说明
===========================================================================

必需依赖:
- pystray: 系统托盘图标
- Pillow (PIL): 图标生成
- python-dateutil: 精确日期计算（处理闰年和月份差异）
- tkinter: GUI界面（Python内置）

可选依赖:
- plyer: Windows 通知（可选）
- win10toast-click: 支持点击通知的Windows通知库（推荐）

作者: Claude Code
日期: 2026-03-10
"""

import os
import sys
import json
import math
import logging
import threading
from datetime import date, datetime
from pathlib import Path

# 配置日志
log_file = Path(__file__).parent / "retirement_app.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 尝试导入可选依赖
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    logger.error("tkinter 未安装，GUI功能将不可用")

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.error("Pillow 未安装，图标生成功能将不可用")

try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    logger.error("pystray 未安装，托盘功能将不可用")

try:
    from dateutil.relativedelta import relativedelta
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False
    logger.error("python-dateutil 未安装，日期计算功能将不可用")

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    logger.warning("plyer 未安装，将使用 tkinter.messagebox 作为通知降级方案")

try:
    from win10toast_click import ToastNotifier
    WIN10TOAST_AVAILABLE = True
except ImportError:
    WIN10TOAST_AVAILABLE = False
    logger.info("win10toast_click 未安装，通知将不支持点击功能")


class ConfigManager:
    """配置管理器"""

    DEFAULT_CONFIG = {
        "target_amount": 0,
        "current_amount": 0,
        "monthly_savings": 0,
        "annual_rate": 0,
        "target_date": None,
        "last_reminder_date": None
    }

    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path(__file__).parent / "config.json"
        self.config_path = Path(config_path)
        self.config = self.load_config()

    def load_config(self):
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置，确保所有字段存在
                    merged = self.DEFAULT_CONFIG.copy()
                    merged.update(config)
                    logger.info(f"配置文件已加载: {self.config_path}")
                    return merged
        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {e}")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")

        logger.info("使用默认配置")
        return self.DEFAULT_CONFIG.copy()

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info(f"配置文件已保存: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False

    def is_configured(self):
        """检查是否已完成基本配置"""
        return (
            self.config.get("target_amount", 0) > 0 and
            self.config.get("monthly_savings", 0) > 0
        )


class RetirementCalculator:
    """退休日期计算器"""

    @staticmethod
    def format_number(num):
        """数字添加千分符

        参数:
            num: 要格式化的数字

        返回:
            带千分符的字符串，如 1,000,000
        """
        try:
            return f"{int(float(num)):,}"
        except (ValueError, TypeError):
            return str(num)

    @staticmethod
    def calculate_target_date(config):
        """
        计算目标退休日期

        参数:
            config: 包含 target_amount, current_amount, monthly_savings, annual_rate 的字典

        返回:
            date 对象表示的目标日期，或 None 如果无法计算
        """
        try:
            target = float(config.get("target_amount", 0))
            current = float(config.get("current_amount", 0))
            monthly = float(config.get("monthly_savings", 0))
            rate = float(config.get("annual_rate", 0))

            if target <= 0 or monthly <= 0:
                return None

            gap = target - current

            # 已达标
            if gap <= 0:
                return date.today()

            # 情况1: 不考虑收益
            if rate == 0:
                months_needed = math.ceil(gap / monthly)
                return date.today() + relativedelta(months=months_needed)

            # 情况2: 考虑收益（月复利）
            monthly_rate = rate / 100 / 12
            balance = current
            months = 0
            max_months = 1200  # 最多计算100年，防止无限循环

            while balance < target and months < max_months:
                balance = balance * (1 + monthly_rate) + monthly
                months += 1

            return date.today() + relativedelta(months=months)

        except Exception as e:
            logger.error(f"计算目标日期失败: {e}")
            return None

    @staticmethod
    def get_remaining_time_text(target_date):
        """
        获取剩余时间的显示文本

        参数:
            target_date: 目标日期 date 对象

        返回:
            格式化的剩余时间字符串
        """
        if target_date is None:
            return "请先设置"

        today = date.today()

        if target_date <= today:
            return "🏖️ 已达标 随时退休"

        diff = relativedelta(target_date, today)

        parts = []
        if diff.years > 0:
            parts.append(f"{diff.years}年")
        if diff.months > 0:
            parts.append(f"{diff.months}个月")
        if diff.days > 0:
            parts.append(f"{diff.days}天")

        if not parts:
            return "还剩不到1天"

        return "还剩 " + " ".join(parts)


class IconGenerator:
    """图标生成器"""

    @staticmethod
    def create_icon(size=64):
        """
        生成托盘图标

        返回:
            PIL Image 对象
        """
        try:
            # 创建一个带有渐变效果的圆形图标
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 绘制圆形背景（蓝色渐变效果）
            margin = 4
            draw.ellipse(
                [margin, margin, size - margin, size - margin],
                fill=(66, 133, 244, 255),  # 蓝色
                outline=(25, 103, 210, 255),  # 深蓝边框
                width=2
            )

            # 尝试绘制"躺"字或沙滩椅符号
            try:
                # 尝试使用系统字体
                font_size = size // 2
                try:
                    font = ImageFont.truetype("msyh.ttc", font_size)  # 微软雅黑
                except:
                    try:
                        font = ImageFont.truetype("simhei.ttf", font_size)  # 黑体
                    except:
                        font = ImageFont.load_default()

                text = "躺"
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (size - text_width) // 2
                y = (size - text_height) // 2 - 2

                draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
            except Exception as e:
                # 如果文字绘制失败，画一个简单的沙滩椅图案
                logger.warning(f"文字绘制失败，使用备选图案: {e}")
                center = size // 2
                # 画一个简单的沙滩椅/躺椅图案
                draw.line([(center - 15, center + 10), (center + 15, center + 10)],
                         fill=(255, 255, 255, 255), width=3)
                draw.line([(center - 15, center + 10), (center - 10, center - 10)],
                         fill=(255, 255, 255, 255), width=3)
                draw.line([(center + 15, center + 10), (center + 10, center - 5)],
                         fill=(255, 255, 255, 255), width=3)
                # 画个太阳
                draw.ellipse([center + 8, center - 15, center + 18, center - 5],
                           fill=(255, 220, 100, 255))

            return img

        except Exception as e:
            logger.error(f"图标生成失败: {e}")
            # 返回一个简单的默认图标
            img = Image.new('RGBA', (size, size), (66, 133, 244, 255))
            return img


class SettingsWindow:
    """设置窗口 - Win11风格"""

    # Win11配色方案
    COLORS = {
        'bg_primary': '#f3f3f3',
        'bg_card': '#ffffff',
        'accent': '#0078d4',
        'accent_hover': '#006cbe',
        'text_primary': '#202020',
        'text_secondary': '#5f5f5f',
        'border': '#e0e0e0',
    }

    def __init__(self, config_manager, on_save_callback=None):
        self.config_manager = config_manager
        self.on_save_callback = on_save_callback
        self.window = None

    def _get_font(self, size=12, bold=False):
        """获取字体，优先使用 Segoe UI，回退到微软雅黑"""
        family = 'Segoe UI'
        try:
            from tkinter import font as tkfont
            available_fonts = tkfont.families()
            if 'Segoe UI' not in available_fonts:
                family = 'Microsoft YaHei'
            if 'Microsoft YaHei' not in available_fonts:
                family = 'SimHei'
        except:
            family = 'Microsoft YaHei'

        weight = 'bold' if bold else 'normal'
        return (family, size, weight)

    def _apply_win11_style(self):
        """应用Win11圆角窗口样式"""
        try:
            from ctypes import windll, c_int, c_void_p
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWM_WINDOW_CORNER_PREFERENCE = c_int
            DWMWCP_ROUND = 2

            hwnd = windll.user32.GetParent(self.window.winfo_id())
            preference = c_int(DWMWCP_ROUND)
            windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                c_void_p(c_int(preference)),
                4
            )
        except Exception:
            pass  # 如果失败，使用默认方形窗口

    def show(self):
        """显示设置窗口"""
        if not TKINTER_AVAILABLE:
            logger.error("tkinter 不可用，无法显示设置窗口")
            return

        try:
            self.window = tk.Toplevel()
            self.window.title("躺平进度条 - 设置")
            self.window.geometry("420x360")
            self.window.resizable(False, False)
            self.window.configure(bg=self.COLORS['bg_primary'])

            # 应用Win11圆角样式
            self._apply_win11_style()

            # 窗口居中
            self.window.update_idletasks()
            x = (self.window.winfo_screenwidth() // 2) - (420 // 2)
            y = (self.window.winfo_screenheight() // 2) - (360 // 2)
            self.window.geometry(f"+{x}+{y}")

            # 主容器
            main_frame = tk.Frame(self.window, bg=self.COLORS['bg_primary'], padx=24, pady=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # 标题
            title_label = tk.Label(
                main_frame,
                text="设置",
                font=self._get_font(18, bold=True),
                fg=self.COLORS['text_primary'],
                bg=self.COLORS['bg_primary']
            )
            title_label.pack(anchor=tk.W, pady=(0, 16))

            # 设置卡片
            card = tk.Frame(
                main_frame,
                bg=self.COLORS['bg_card'],
                padx=20,
                pady=20,
                highlightbackground=self.COLORS['border'],
                highlightthickness=1
            )
            card.pack(fill=tk.X)

            # 目标金额
            row0 = tk.Frame(card, bg=self.COLORS['bg_card'])
            row0.pack(fill=tk.X, pady=4)
            tk.Label(row0, text="目标退休金额:", font=self._get_font(11),
                    bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary']).pack(side=tk.LEFT)

            entry_frame0 = tk.Frame(row0, bg=self.COLORS['bg_card'])
            entry_frame0.pack(side=tk.RIGHT)
            self.target_var = tk.StringVar(
                value=RetirementCalculator.format_number(self.config_manager.config.get("target_amount", "")).replace(',', '')
            )
            entry0 = tk.Entry(entry_frame0, textvariable=self.target_var, width=18,
                            font=self._get_font(11), relief=tk.FLAT,
                            highlightbackground=self.COLORS['border'], highlightthickness=1)
            entry0.pack(side=tk.LEFT, padx=(0, 8))
            tk.Label(entry_frame0, text="元", font=self._get_font(11),
                    bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary']).pack(side=tk.LEFT)

            # 当前存款
            row1 = tk.Frame(card, bg=self.COLORS['bg_card'])
            row1.pack(fill=tk.X, pady=4)
            tk.Label(row1, text="当前已存金额:", font=self._get_font(11),
                    bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary']).pack(side=tk.LEFT)

            entry_frame1 = tk.Frame(row1, bg=self.COLORS['bg_card'])
            entry_frame1.pack(side=tk.RIGHT)
            self.current_var = tk.StringVar(
                value=RetirementCalculator.format_number(self.config_manager.config.get("current_amount", "")).replace(',', '')
            )
            entry1 = tk.Entry(entry_frame1, textvariable=self.current_var, width=18,
                            font=self._get_font(11), relief=tk.FLAT,
                            highlightbackground=self.COLORS['border'], highlightthickness=1)
            entry1.pack(side=tk.LEFT, padx=(0, 8))
            tk.Label(entry_frame1, text="元", font=self._get_font(11),
                    bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary']).pack(side=tk.LEFT)

            # 每月储蓄
            row2 = tk.Frame(card, bg=self.COLORS['bg_card'])
            row2.pack(fill=tk.X, pady=4)
            tk.Label(row2, text="每月储蓄金额:", font=self._get_font(11),
                    bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary']).pack(side=tk.LEFT)

            entry_frame2 = tk.Frame(row2, bg=self.COLORS['bg_card'])
            entry_frame2.pack(side=tk.RIGHT)
            self.monthly_var = tk.StringVar(
                value=RetirementCalculator.format_number(self.config_manager.config.get("monthly_savings", "")).replace(',', '')
            )
            entry2 = tk.Entry(entry_frame2, textvariable=self.monthly_var, width=18,
                            font=self._get_font(11), relief=tk.FLAT,
                            highlightbackground=self.COLORS['border'], highlightthickness=1)
            entry2.pack(side=tk.LEFT, padx=(0, 8))
            tk.Label(entry_frame2, text="元", font=self._get_font(11),
                    bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary']).pack(side=tk.LEFT)

            # 年化收益率
            row3 = tk.Frame(card, bg=self.COLORS['bg_card'])
            row3.pack(fill=tk.X, pady=4)
            tk.Label(row3, text="预期年化收益率:", font=self._get_font(11),
                    bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary']).pack(side=tk.LEFT)

            entry_frame3 = tk.Frame(row3, bg=self.COLORS['bg_card'])
            entry_frame3.pack(side=tk.RIGHT)
            self.rate_var = tk.StringVar(value=str(self.config_manager.config.get("annual_rate", "")))
            entry3 = tk.Entry(entry_frame3, textvariable=self.rate_var, width=18,
                            font=self._get_font(11), relief=tk.FLAT,
                            highlightbackground=self.COLORS['border'], highlightthickness=1)
            entry3.pack(side=tk.LEFT, padx=(0, 8))
            tk.Label(entry_frame3, text="%（可选）", font=self._get_font(11),
                    bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary']).pack(side=tk.LEFT)

            # 说明文字
            info_label = tk.Label(
                main_frame,
                text="保存后将自动重新计算目标退休日期",
                font=self._get_font(10),
                fg=self.COLORS['text_secondary'],
                bg=self.COLORS['bg_primary']
            )
            info_label.pack(anchor=tk.W, pady=(12, 16))

            # 按钮区域
            button_frame = tk.Frame(main_frame, bg=self.COLORS['bg_primary'])
            button_frame.pack(fill=tk.X)

            # 取消按钮
            cancel_btn = tk.Button(
                button_frame,
                text="取消",
                font=self._get_font(11),
                bg=self.COLORS['bg_card'],
                fg=self.COLORS['text_primary'],
                activebackground=self.COLORS['border'],
                relief=tk.FLAT,
                padx=20,
                pady=8,
                cursor='hand2',
                command=self.window.destroy
            )
            cancel_btn.pack(side=tk.LEFT)

            # 保存按钮（Win11蓝色主按钮）
            save_btn = tk.Button(
                button_frame,
                text="保存",
                font=self._get_font(11),
                bg=self.COLORS['accent'],
                fg='white',
                activebackground=self.COLORS['accent_hover'],
                activeforeground='white',
                relief=tk.FLAT,
                padx=20,
                pady=8,
                cursor='hand2',
                command=self._on_save
            )
            save_btn.pack(side=tk.RIGHT)

            # 使窗口置顶
            self.window.transient()
            self.window.grab_set()
            self.window.focus_set()

        except Exception as e:
            logger.error(f"创建设置窗口失败: {e}")
            messagebox.showerror("错误", f"无法打开设置窗口: {e}")

    def _on_save(self):
        """保存设置"""
        try:
            # 验证输入（去除千分符逗号）
            target = self.target_var.get().strip().replace(',', '')
            current = self.current_var.get().strip().replace(',', '') or "0"
            monthly = self.monthly_var.get().strip().replace(',', '')
            rate = self.rate_var.get().strip().replace(',', '') or "0"

            # 转换为数字
            try:
                target_val = float(target)
                current_val = float(current)
                monthly_val = float(monthly)
                rate_val = float(rate)
            except ValueError:
                messagebox.showerror("输入错误", "请输入有效的数字")
                return

            # 验证逻辑
            if target_val <= 0:
                messagebox.showerror("输入错误", "目标退休金额必须大于0")
                return
            if current_val < 0:
                messagebox.showerror("输入错误", "当前已存金额不能为负数")
                return
            if monthly_val <= 0:
                messagebox.showerror("输入错误", "每月储蓄金额必须大于0")
                return
            if rate_val < 0:
                messagebox.showerror("输入错误", "年化收益率不能为负数")
                return

            # 保存配置
            self.config_manager.config["target_amount"] = target_val
            self.config_manager.config["current_amount"] = current_val
            self.config_manager.config["monthly_savings"] = monthly_val
            self.config_manager.config["annual_rate"] = rate_val

            if self.config_manager.save_config():
                messagebox.showinfo("成功", "设置已保存")
                self.window.destroy()
                if self.on_save_callback:
                    self.on_save_callback()
            else:
                messagebox.showerror("错误", "保存配置失败")

        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            messagebox.showerror("错误", f"保存失败: {e}")


class UpdateDepositWindow:
    """更新存款窗口 - Win11风格"""

    # Win11配色方案
    COLORS = {
        'bg_primary': '#f3f3f3',
        'bg_card': '#ffffff',
        'accent': '#0078d4',
        'accent_hover': '#006cbe',
        'text_primary': '#202020',
        'text_secondary': '#5f5f5f',
        'border': '#e0e0e0',
    }

    def __init__(self, config_manager, on_update_callback=None):
        self.config_manager = config_manager
        self.on_update_callback = on_update_callback
        self.window = None

    def _get_font(self, size=12, bold=False):
        """获取字体，优先使用 Segoe UI，回退到微软雅黑"""
        family = 'Segoe UI'
        try:
            from tkinter import font as tkfont
            available_fonts = tkfont.families()
            if 'Segoe UI' not in available_fonts:
                family = 'Microsoft YaHei'
            if 'Microsoft YaHei' not in available_fonts:
                family = 'SimHei'
        except:
            family = 'Microsoft YaHei'

        weight = 'bold' if bold else 'normal'
        return (family, size, weight)

    def _apply_win11_style(self):
        """应用Win11圆角窗口样式"""
        try:
            from ctypes import windll, c_int, c_void_p
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWM_WINDOW_CORNER_PREFERENCE = c_int
            DWMWCP_ROUND = 2

            hwnd = windll.user32.GetParent(self.window.winfo_id())
            preference = c_int(DWMWCP_ROUND)
            windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                c_void_p(c_int(preference)),
                4
            )
        except Exception:
            pass  # 如果失败，使用默认方形窗口

    def show(self):
        """显示更新存款窗口"""
        if not TKINTER_AVAILABLE:
            logger.error("tkinter 不可用，无法显示更新窗口")
            return

        try:
            self.window = tk.Toplevel()
            self.window.title("更新当前存款")
            self.window.geometry("360x240")
            self.window.resizable(False, False)
            self.window.configure(bg=self.COLORS['bg_primary'])

            # 应用Win11圆角样式
            self._apply_win11_style()

            # 窗口居中
            self.window.update_idletasks()
            x = (self.window.winfo_screenwidth() // 2) - (360 // 2)
            y = (self.window.winfo_screenheight() // 2) - (240 // 2)
            self.window.geometry(f"+{x}+{y}")

            # 主容器
            main_frame = tk.Frame(self.window, bg=self.COLORS['bg_primary'], padx=24, pady=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # 标题
            title_label = tk.Label(
                main_frame,
                text="更新当前存款",
                font=self._get_font(18, bold=True),
                fg=self.COLORS['text_primary'],
                bg=self.COLORS['bg_primary']
            )
            title_label.pack(anchor=tk.W, pady=(0, 16))

            # 卡片
            card = tk.Frame(
                main_frame,
                bg=self.COLORS['bg_card'],
                padx=20,
                pady=20,
                highlightbackground=self.COLORS['border'],
                highlightthickness=1
            )
            card.pack(fill=tk.X)

            # 当前存款行
            row_frame = tk.Frame(card, bg=self.COLORS['bg_card'])
            row_frame.pack(fill=tk.X)

            tk.Label(
                row_frame,
                text="当前已存金额:",
                font=self._get_font(11),
                bg=self.COLORS['bg_card'],
                fg=self.COLORS['text_secondary']
            ).pack(side=tk.LEFT)

            entry_frame = tk.Frame(row_frame, bg=self.COLORS['bg_card'])
            entry_frame.pack(side=tk.RIGHT)

            current_value = RetirementCalculator.format_number(
                self.config_manager.config.get("current_amount", "")
            ).replace(',', '')
            self.current_var = tk.StringVar(value=current_value)
            self.entry = tk.Entry(
                entry_frame,
                textvariable=self.current_var,
                width=18,
                font=self._get_font(11),
                relief=tk.FLAT,
                highlightbackground=self.COLORS['border'],
                highlightthickness=1
            )
            self.entry.pack(side=tk.LEFT, padx=(0, 8))

            tk.Label(
                entry_frame,
                text="元",
                font=self._get_font(11),
                bg=self.COLORS['bg_card'],
                fg=self.COLORS['text_secondary']
            ).pack(side=tk.LEFT)

            # 说明文字
            info_label = tk.Label(
                main_frame,
                text="更新后将重新计算退休目标日期",
                font=self._get_font(10),
                fg=self.COLORS['text_secondary'],
                bg=self.COLORS['bg_primary']
            )
            info_label.pack(anchor=tk.W, pady=(12, 16))

            # 按钮区域
            button_frame = tk.Frame(main_frame, bg=self.COLORS['bg_primary'])
            button_frame.pack(fill=tk.X)

            # 取消按钮
            cancel_btn = tk.Button(
                button_frame,
                text="取消",
                font=self._get_font(11),
                bg=self.COLORS['bg_card'],
                fg=self.COLORS['text_primary'],
                activebackground=self.COLORS['border'],
                relief=tk.FLAT,
                padx=20,
                pady=8,
                cursor='hand2',
                command=self.window.destroy
            )
            cancel_btn.pack(side=tk.LEFT)

            # 更新按钮（Win11蓝色主按钮）
            update_btn = tk.Button(
                button_frame,
                text="更新",
                font=self._get_font(11),
                bg=self.COLORS['accent'],
                fg='white',
                activebackground=self.COLORS['accent_hover'],
                activeforeground='white',
                relief=tk.FLAT,
                padx=20,
                pady=8,
                cursor='hand2',
                command=self._on_update
            )
            update_btn.pack(side=tk.RIGHT)

            # 使窗口置顶
            self.window.transient()
            self.window.grab_set()
            self.window.focus_set()

            # 选中输入框内容
            self.entry.select_range(0, tk.END)
            self.entry.focus()

        except Exception as e:
            logger.error(f"创建更新窗口失败: {e}")
            messagebox.showerror("错误", f"无法打开更新窗口: {e}")

    def _on_update(self):
        """更新存款"""
        try:
            current = self.current_var.get().strip().replace(',', '')

            try:
                current_val = float(current)
            except ValueError:
                messagebox.showerror("输入错误", "请输入有效的数字")
                return

            if current_val < 0:
                messagebox.showerror("输入错误", "当前已存金额不能为负数")
                return

            # 保存配置
            self.config_manager.config["current_amount"] = current_val

            # 清除上次提醒日期（这样下个月1号会正常提醒）
            self.config_manager.config["last_reminder_date"] = None

            if self.config_manager.save_config():
                messagebox.showinfo("成功", "存款已更新")
                self.window.destroy()
                if self.on_update_callback:
                    self.on_update_callback()
            else:
                messagebox.showerror("错误", "保存配置失败")

        except Exception as e:
            logger.error(f"更新存款失败: {e}")
            messagebox.showerror("错误", f"更新失败: {e}")


class CountdownWindow:
    """Win11 风格倒计时窗口 - 点击托盘图标显示实时倒计时"""

    # Win11 配色方案
    COLORS = {
        'bg_primary': '#f3f3f3',
        'bg_card': '#ffffff',
        'accent': '#0078d4',
        'accent_hover': '#006cbe',
        'text_primary': '#202020',
        'text_secondary': '#5f5f5f',
        'border': '#e0e0e0',
        'success': '#107c10',
        'warning': '#ffc107',
    }

    def __init__(self, config_manager, calculator):
        self.config_manager = config_manager
        self.calculator = calculator
        self.window = None
        self.update_timer = None
        self.time_labels = {}
        self.is_visible = False

    def show(self):
        """显示倒计时窗口"""
        if not TKINTER_AVAILABLE:
            logger.error("tkinter 不可用，无法显示倒计时窗口")
            return

        # 如果窗口已存在，直接显示
        if self.window is not None and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return

        try:
            self.window = tk.Toplevel()
            self.window.title("躺平进度条")
            self.window.geometry("420x520")
            self.window.resizable(False, False)
            self.is_visible = True

            # 窗口居中
            self.window.update_idletasks()
            x = (self.window.winfo_screenwidth() // 2) - (420 // 2)
            y = (self.window.winfo_screenheight() // 2) - (520 // 2)
            self.window.geometry(f"+{x}+{y}")

            # 应用 Win11 样式
            self._apply_win11_style()

            # 创建 UI
            self._create_ui()

            # 立即更新一次显示
            self._update_display()

            # 启动每秒更新的定时器
            self._start_update_timer()

            # 绑定关闭事件
            self.window.protocol("WM_DELETE_WINDOW", self.close)

        except Exception as e:
            logger.error(f"创建倒计时窗口失败: {e}")

    def _apply_win11_style(self):
        """应用 Win11 风格样式"""
        # 设置窗口背景
        self.window.configure(bg=self.COLORS['bg_primary'])

        # 尝试设置圆角窗口（Windows 10/11）
        try:
            from ctypes import windll, c_int, c_void_p
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWM_WINDOW_CORNER_PREFERENCE = c_int
            DWMWCP_ROUND = 2

            hwnd = windll.user32.GetParent(self.window.winfo_id())
            preference = c_int(DWMWCP_ROUND)
            windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                c_void_p(c_int(preference)),
                4
            )
        except Exception:
            pass  # 如果失败，使用默认方形窗口

    def _create_ui(self):
        """创建用户界面"""
        # 主容器
        main_frame = tk.Frame(
            self.window,
            bg=self.COLORS['bg_primary'],
            padx=24,
            pady=24
        )
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = tk.Label(
            main_frame,
            text="距离退休还有",
            font=self._get_font(20, bold=True),
            bg=self.COLORS['bg_primary'],
            fg=self.COLORS['text_primary']
        )
        title_label.pack(pady=(0, 16))

        # 倒计时卡片
        countdown_card = tk.Frame(
            main_frame,
            bg=self.COLORS['bg_card'],
            padx=20,
            pady=20,
            relief=tk.FLAT,
            highlightbackground=self.COLORS['border'],
            highlightthickness=1
        )
        countdown_card.pack(fill=tk.X, pady=(0, 16))

        # 时间单位容器
        time_frame = tk.Frame(countdown_card, bg=self.COLORS['bg_card'])
        time_frame.pack()

        # 创建时间单位显示
        time_units = [
            ('years', '年'),
            ('months', '个月'),
            ('days', '天'),
            ('hours', '时'),
            ('minutes', '分'),
            ('seconds', '秒'),
        ]

        for i, (key, unit) in enumerate(time_units):
            unit_frame = tk.Frame(time_frame, bg=self.COLORS['bg_card'])
            unit_frame.pack(side=tk.LEFT, padx=4)

            # 数字标签
            num_label = tk.Label(
                unit_frame,
                text="0",
                font=self._get_font(28 if key in ['years', 'months', 'days'] else 20, bold=True),
                bg=self.COLORS['bg_card'],
                fg=self.COLORS['accent'] if key in ['years', 'months', 'days'] else self.COLORS['text_secondary']
            )
            num_label.pack()
            self.time_labels[key] = num_label

            # 单位标签
            unit_label = tk.Label(
                unit_frame,
                text=unit,
                font=self._get_font(12),
                bg=self.COLORS['bg_card'],
                fg=self.COLORS['text_secondary']
            )
            unit_label.pack()

        # 财务信息卡片
        self._create_finance_card(main_frame)

        # 按钮区域
        button_frame = tk.Frame(main_frame, bg=self.COLORS['bg_primary'])
        button_frame.pack(fill=tk.X, pady=(16, 0))

        # 设置按钮
        settings_btn = tk.Button(
            button_frame,
            text="设置",
            font=self._get_font(11),
            bg=self.COLORS['bg_card'],
            fg=self.COLORS['text_primary'],
            activebackground=self.COLORS['border'],
            activeforeground=self.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor='hand2',
            command=self._on_settings
        )
        settings_btn.pack(side=tk.LEFT, padx=(0, 8))

        # 更新存款按钮
        update_btn = tk.Button(
            button_frame,
            text="更新存款",
            font=self._get_font(11),
            bg=self.COLORS['accent'],
            fg='white',
            activebackground=self.COLORS['accent_hover'],
            activeforeground='white',
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor='hand2',
            command=self._on_update
        )
        update_btn.pack(side=tk.LEFT)

        # 关闭按钮
        close_btn = tk.Button(
            button_frame,
            text="关闭",
            font=self._get_font(11),
            bg=self.COLORS['bg_card'],
            fg=self.COLORS['text_primary'],
            activebackground=self.COLORS['border'],
            activeforeground=self.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor='hand2',
            command=self.close
        )
        close_btn.pack(side=tk.RIGHT)

    def _create_finance_card(self, parent):
        """创建财务信息卡片"""
        card = tk.Frame(
            parent,
            bg=self.COLORS['bg_card'],
            padx=20,
            pady=16,
            relief=tk.FLAT,
            highlightbackground=self.COLORS['border'],
            highlightthickness=1
        )
        card.pack(fill=tk.X)

        # 目标金额
        self._create_finance_row(card, "目标金额", "target_amount", 0)
        # 当前存款
        self._create_finance_row(card, "当前存款", "current_amount", 1)
        # 每月储蓄
        self._create_finance_row(card, "每月储蓄", "monthly_savings", 2)
        # 预期收益
        self._create_finance_row(card, "预期年化", "annual_rate", 3, suffix='%')

    def _create_finance_row(self, parent, label, config_key, row, suffix=' 元'):
        """创建财务信息行"""
        row_frame = tk.Frame(parent, bg=self.COLORS['bg_card'])
        row_frame.pack(fill=tk.X, pady=4)

        label_widget = tk.Label(
            row_frame,
            text=label + ':',
            font=self._get_font(12),
            bg=self.COLORS['bg_card'],
            fg=self.COLORS['text_secondary']
        )
        label_widget.pack(side=tk.LEFT)

        value = self.config_manager.config.get(config_key, 0)
        if config_key == 'annual_rate':
            display_value = f"{value}{suffix}"
        else:
            display_value = self.calculator.format_number(value) + suffix

        value_label = tk.Label(
            row_frame,
            text=display_value,
            font=self._get_font(12, bold=True),
            bg=self.COLORS['bg_card'],
            fg=self.COLORS['text_primary']
        )
        value_label.pack(side=tk.RIGHT)

        # 保存引用以便更新
        if not hasattr(self, 'finance_labels'):
            self.finance_labels = {}
        self.finance_labels[config_key] = value_label

    def _get_font(self, size, bold=False):
        """获取字体，优先使用 Segoe UI，回退到微软雅黑"""
        family = 'Segoe UI'
        try:
            # 测试字体是否可用
            from tkinter import font as tkfont
            available_fonts = tkfont.families()
            if 'Segoe UI' not in available_fonts:
                family = 'Microsoft YaHei'
            if 'Microsoft YaHei' not in available_fonts:
                family = 'SimHei'
        except:
            family = 'Microsoft YaHei'

        weight = 'bold' if bold else 'normal'
        return (family, size, weight)

    def _update_display(self):
        """更新倒计时显示"""
        if not self.is_visible or self.window is None:
            return

        try:
            if not self.config_manager.is_configured():
                return

            target_date_str = self.config_manager.config.get("target_date")
            if target_date_str:
                try:
                    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                except ValueError:
                    target_date = None
            else:
                target_date = None

            if target_date is None:
                target_date = self.calculator.calculate_target_date(self.config_manager.config)
                if target_date:
                    self.config_manager.config["target_date"] = target_date.isoformat()
                    self.config_manager.save_config()

            if target_date:
                # 计算剩余时间
                now = datetime.now()
                target_datetime = datetime.combine(target_date, datetime.min.time())

                if target_datetime <= now:
                    # 已达标
                    self.time_labels['years'].config(text="0", fg=self.COLORS['success'])
                    self.time_labels['months'].config(text="0", fg=self.COLORS['success'])
                    self.time_labels['days'].config(text="0", fg=self.COLORS['success'])
                    self.time_labels['hours'].config(text="0")
                    self.time_labels['minutes'].config(text="0")
                    self.time_labels['seconds'].config(text="0")
                else:
                    diff = target_datetime - now
                    total_seconds = int(diff.total_seconds())

                    years = total_seconds // (365 * 24 * 3600)
                    remaining = total_seconds % (365 * 24 * 3600)
                    months = remaining // (30 * 24 * 3600)
                    remaining = remaining % (30 * 24 * 3600)
                    days = remaining // (24 * 3600)
                    remaining = remaining % (24 * 3600)
                    hours = remaining // 3600
                    remaining = remaining % 3600
                    minutes = remaining // 60
                    seconds = remaining % 60

                    self.time_labels['years'].config(text=str(years))
                    self.time_labels['months'].config(text=str(months))
                    self.time_labels['days'].config(text=str(days))
                    self.time_labels['hours'].config(text=f"{hours:02d}")
                    self.time_labels['minutes'].config(text=f"{minutes:02d}")
                    self.time_labels['seconds'].config(text=f"{seconds:02d}")

                    # 更新财务标签
                    self._update_finance_labels()

        except Exception as e:
            logger.error(f"更新倒计时显示失败: {e}")

    def _update_finance_labels(self):
        """更新财务信息标签"""
        if hasattr(self, 'finance_labels'):
            for key, label in self.finance_labels.items():
                value = self.config_manager.config.get(key, 0)
                if key == 'annual_rate':
                    label.config(text=f"{value}%")
                else:
                    label.config(text=self.calculator.format_number(value) + " 元")

    def _start_update_timer(self):
        """启动更新定时器"""
        if not self.is_visible:
            return

        self._update_display()

        if self.window and self.window.winfo_exists():
            self.update_timer = self.window.after(1000, self._start_update_timer)

    def _on_settings(self):
        """打开设置窗口"""
        self.close()
        # 通过 app 引用调用设置
        if hasattr(self, '_app_ref') and self._app_ref:
            self._app_ref.on_settings()

    def _on_update(self):
        """打开更新存款窗口"""
        self.close()
        if hasattr(self, '_app_ref') and self._app_ref:
            self._app_ref.on_update_deposit()

    def set_app_ref(self, app):
        """设置应用引用"""
        self._app_ref = app

    def close(self):
        """关闭窗口"""
        self.is_visible = False
        if self.update_timer:
            try:
                self.window.after_cancel(self.update_timer)
            except:
                pass
            self.update_timer = None

        if self.window:
            try:
                self.window.destroy()
            except:
                pass
            self.window = None


class RetirementTrayApp:
    """退休倒计时托盘应用主类"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.calculator = RetirementCalculator()
        self.icon_generator = IconGenerator()
        self.tray_icon = None
        self.reminder_timer = None
        self.root = None
        self.countdown_window = None

        # 创建隐藏的tkinter根窗口（用于弹出对话框）
        if TKINTER_AVAILABLE:
            self.root = tk.Tk()
            self.root.withdraw()

    def get_tooltip_text(self):
        """获取托盘图标的tooltip文本"""
        if not self.config_manager.is_configured():
            return "躺平进度条 - 请先设置"

        target_date_str = self.config_manager.config.get("target_date")
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            except ValueError:
                target_date = None
        else:
            target_date = None

        if target_date is None:
            # 重新计算
            target_date = self.calculator.calculate_target_date(self.config_manager.config)
            if target_date:
                self.config_manager.config["target_date"] = target_date.isoformat()
                self.config_manager.save_config()

        remaining_text = self.calculator.get_remaining_time_text(target_date)
        return f"躺平进度条 - {remaining_text}"

    def update_tooltip(self):
        """更新托盘tooltip"""
        if self.tray_icon:
            try:
                self.tray_icon.title = self.get_tooltip_text()
            except Exception as e:
                logger.error(f"更新tooltip失败: {e}")

    def on_settings(self):
        """打开设置窗口"""
        try:
            settings = SettingsWindow(
                self.config_manager,
                on_save_callback=self._on_config_updated
            )
            settings.show()
        except Exception as e:
            logger.error(f"打开设置窗口失败: {e}")
            self._show_error("无法打开设置窗口")

    def on_update_deposit(self):
        """打开更新存款窗口"""
        try:
            update_window = UpdateDepositWindow(
                self.config_manager,
                on_update_callback=self._on_config_updated
            )
            update_window.show()
        except Exception as e:
            logger.error(f"打开更新窗口失败: {e}")
            self._show_error("无法打开更新窗口")

    def _on_config_updated(self):
        """配置更新后的回调"""
        # 重新计算目标日期
        target_date = self.calculator.calculate_target_date(self.config_manager.config)
        if target_date:
            self.config_manager.config["target_date"] = target_date.isoformat()
            self.config_manager.save_config()

        # 更新tooltip
        self.update_tooltip()

    def on_exit(self):
        """退出程序"""
        logger.info("程序退出")
        if self.reminder_timer:
            self.reminder_timer.cancel()
        if self.tray_icon:
            self.tray_icon.stop()

    def _show_error(self, message):
        """显示错误消息"""
        if TKINTER_AVAILABLE:
            messagebox.showerror("错误", message)

    def _show_notification(self, title, message, on_click=None):
        """显示通知

        参数:
            title: 通知标题
            message: 通知内容
            on_click: 点击通知时的回调函数（仅 win10toast_click 支持）
        """
        try:
            # 优先使用 win10toast_click（支持点击回调）
            if WIN10TOAST_AVAILABLE and on_click:
                toaster = ToastNotifier()
                toaster.show_toast(
                    title,
                    message,
                    icon_path=None,
                    duration=10,
                    callback_on_click=on_click,
                    threaded=True
                )
                logger.info(f"通知已发送（支持点击）: {title}")
            elif PLYER_AVAILABLE:
                notification.notify(
                    title=title,
                    message=message,
                    app_name="躺平进度条",
                    timeout=10
                )
                logger.info(f"通知已发送: {title}")
            elif TKINTER_AVAILABLE:
                # 降级方案：弹窗，关闭后可选择打开更新窗口
                result = messagebox.askyesno(
                    title,
                    f"{message}\n\n是否立即更新存款？"
                )
                if result and on_click:
                    self.root.after(0, on_click)
        except Exception as e:
            logger.error(f"显示通知失败: {e}")

    def check_monthly_reminder(self):
        """检查并触发月度提醒"""
        try:
            today = date.today()

            # 只有每月1号提醒
            if today.day != 1:
                return

            # 检查今天是否已经提醒过
            last_reminder = self.config_manager.config.get("last_reminder_date")
            if last_reminder == today.isoformat():
                return

            # 检查是否已配置
            if not self.config_manager.is_configured():
                return

            # 发送提醒（点击后打开更新窗口）
            self._show_notification(
                "退休倒计时提醒",
                "📅 每月提醒：请更新当前存款金额，以便倒计时更准确。",
                on_click=self.on_update_deposit
            )

            # 更新上次提醒日期
            self.config_manager.config["last_reminder_date"] = today.isoformat()
            self.config_manager.save_config()

            logger.info(f"月度提醒已触发: {today}")

        except Exception as e:
            logger.error(f"月度提醒检查失败: {e}")
        finally:
            # 重新设置定时器（每分钟检查一次）
            self.reminder_timer = threading.Timer(60, self.check_monthly_reminder)
            self.reminder_timer.daemon = True
            self.reminder_timer.start()

    def on_show_countdown(self):
        """显示倒计时窗口"""
        try:
            if self.countdown_window is None:
                self.countdown_window = CountdownWindow(
                    self.config_manager,
                    self.calculator
                )
                self.countdown_window.set_app_ref(self)
            self.root.after(0, self.countdown_window.show)
        except Exception as e:
            logger.error(f"打开倒计时窗口失败: {e}")

    def create_menu(self):
        """创建托盘右键菜单"""
        def on_show(icon, item):
            self.root.after(0, self.on_show_countdown)

        def on_settings(icon, item):
            self.root.after(0, self.on_settings)

        def on_update(icon, item):
            self.root.after(0, self.on_update_deposit)

        def on_exit(icon, item):
            self.root.after(0, self._do_exit)

        return pystray.Menu(
            pystray.MenuItem("打开倒计时", on_show),
            pystray.MenuItem("设置", on_settings),
            pystray.MenuItem("更新当前存款", on_update),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_exit)
        )

    def _do_exit(self):
        """执行退出"""
        self.on_exit()
        self.root.quit()

    def run(self):
        """运行应用"""
        logger.info("躺平进度条启动")

        # 检查依赖
        if not PYSTRAY_AVAILABLE:
            logger.error("缺少必需依赖: pystray")
            if TKINTER_AVAILABLE:
                messagebox.showerror(
                    "缺少依赖",
                    "请先安装 pystray:\npip install pystray"
                )
            return

        if not PIL_AVAILABLE:
            logger.error("缺少必需依赖: Pillow")
            if TKINTER_AVAILABLE:
                messagebox.showerror(
                    "缺少依赖",
                    "请先安装 Pillow:\npip install Pillow"
                )
            return

        if not DATEUTIL_AVAILABLE:
            logger.error("缺少必需依赖: python-dateutil")
            if TKINTER_AVAILABLE:
                messagebox.showerror(
                    "缺少依赖",
                    "请先安装 python-dateutil:\npip install python-dateutil"
                )
            return

        # 初始计算目标日期
        if self.config_manager.is_configured():
            target_date = self.calculator.calculate_target_date(self.config_manager.config)
            if target_date:
                self.config_manager.config["target_date"] = target_date.isoformat()
                self.config_manager.save_config()

        # 创建托盘图标
        icon_image = self.icon_generator.create_icon()

        # 创建托盘图标实例
        self.tray_icon = pystray.Icon(
            "retirement_tray",
            icon_image,
            title=self.get_tooltip_text(),
            menu=self.create_menu()
        )

        # 设置默认动作（左键点击）为打开倒计时窗口
        self.tray_icon.on_activate = lambda icon, item: self.root.after(0, self.on_show_countdown)

        # 启动月度提醒定时器
        self.reminder_timer = threading.Timer(60, self.check_monthly_reminder)
        self.reminder_timer.daemon = True
        self.reminder_timer.start()

        # 启动定时更新tooltip（每10分钟更新一次，确保日期变化时tooltip正确）
        self._schedule_tooltip_update()

        logger.info("托盘图标已创建，进入主循环")

        # 运行托盘图标
        self.tray_icon.run()

    def _schedule_tooltip_update(self):
        """定时更新tooltip"""
        def update():
            self.update_tooltip()
            self._schedule_tooltip_update()

        # 每1分钟更新一次
        threading.Timer(60, lambda: self.root.after(0, update)).start()


def main():
    """主函数"""
    try:
        app = RetirementTrayApp()
        app.run()
    except Exception as e:
        logger.critical(f"程序异常退出: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
