#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
生成应用程序图标
"""

from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QFont, QLinearGradient
from PySide6.QtCore import Qt, QSize, QRect
import os

def create_app_icon():
    """创建应用程序图标并保存为文件"""
    # 创建图标
    icon_size = 256
    pixmap = QPixmap(icon_size, icon_size)
    pixmap.fill(Qt.transparent)
    
    # 开始绘制
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    
    # 创建渐变背景
    gradient = QLinearGradient(0, 0, icon_size, icon_size)
    gradient.setColorAt(0, QColor(52, 152, 219))  # 蓝色
    gradient.setColorAt(1, QColor(41, 128, 185))  # 深蓝色
    
    # 绘制圆形背景
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(10, 10, icon_size - 20, icon_size - 20)
    
    # 绘制文字
    font = QFont("Arial", int(icon_size / 3))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QPen(QColor(255, 255, 255)))
    
    text_rect = QRect(10, 10, icon_size - 20, icon_size - 20)
    painter.drawText(text_rect, Qt.AlignCenter, "Y8")
    
    # 结束绘制
    painter.end()
    
    # 保存图标
    pixmap.save("icon.png", "PNG")
    
    return QIcon(pixmap)

def generate_app_icon():
    """生成应用程序图标文件（如果不存在）"""
    if not os.path.exists("icon.png"):
        create_app_icon()

if __name__ == "__main__":
    create_app_icon()
    print("图标已保存为icon.png")
