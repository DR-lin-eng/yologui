#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QSplashScreen
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap, QIcon

from ui_components import MainWindow
from environment import EnvironmentChecker
from parameters import load_default_parameters
from training import TrainingManager
from icon import generate_app_icon


class YOLOv8TrainerApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("YOLOv8 训练工具")
        self.app.setStyle("Fusion")  # 使用Fusion样式，看起来更现代
        
        # 生成应用图标
        generate_app_icon()
        if os.path.exists("icon.png"):
            self.app.setWindowIcon(QIcon("icon.png"))
        
        # 显示启动画面
        splash_pixmap = QPixmap(400, 300)
        splash_pixmap.fill(Qt.white)
        self.splash = QSplashScreen(splash_pixmap)
        self.splash.showMessage("正在加载YOLOv8训练工具...", Qt.AlignCenter, Qt.black)
        self.splash.show()
        self.app.processEvents()
        
        # 加载默认参数
        self.splash.showMessage("加载训练参数...", Qt.AlignCenter, Qt.black)
        self.app.processEvents()
        self.parameters = load_default_parameters()
        
        # 创建主窗口
        self.splash.showMessage("初始化界面...", Qt.AlignCenter, Qt.black)
        self.app.processEvents()
        self.main_window = MainWindow(self.parameters)
        
        # 创建训练管理器
        self.training_manager = TrainingManager()
        
        # 连接信号和槽
        self.connect_signals()
        
        # 第一次运行检查
        self.splash.showMessage("检查环境...", Qt.AlignCenter, Qt.black)
        self.app.processEvents()
        self.first_run_check()

    def connect_signals(self):
        """连接UI组件的信号和槽"""
        # 开始训练按钮
        self.main_window.start_training_button.clicked.connect(self.start_training)
        
        # 停止训练按钮
        self.main_window.stop_training_button.clicked.connect(self.stop_training)
        
        # 训练管理器的信号
        self.training_manager.progress_update.connect(self.main_window.update_progress)
        self.training_manager.training_finished.connect(self.training_finished)
        self.training_manager.training_error.connect(self.training_error)

    def first_run_check(self):
        """首次运行时检查环境"""
        env_checker = EnvironmentChecker()
        status = env_checker.check_all()
        
        if not status['yolov8_installed']:
            msg = QMessageBox()
            msg.setWindowTitle("环境检查")
            msg.setText("未检测到YOLOv8。是否安装？")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            if msg.exec_() == QMessageBox.Yes:  # 注意这里使用 exec_()
                env_checker.install_yolov8()
        
        # 更新CUDA状态
        self.main_window.update_cuda_status(status['cuda_available'])
        
        # 显示环境信息
        self.main_window.update_environment_info(status)

    def start_training(self):
        """开始训练过程"""
        # 从UI获取参数
        training_params = self.main_window.get_training_parameters()
        
        # 如果用户取消，则退出
        if training_params is None:
            return
        
        # 验证参数
        if not self.validate_parameters(training_params):
            return
        
        # 启动训练
        self.training_manager.start_training(training_params)
        
        # 更新UI状态
        self.main_window.set_training_mode(True)

    def stop_training(self):
        """停止训练过程"""
        self.training_manager.stop_training()
        
    def training_finished(self, success):
        """训练完成回调"""
        self.main_window.set_training_mode(False)
        if success:
            QMessageBox.information(self.main_window, "训练完成", "YOLOv8 训练已成功完成！")
        
    def training_error(self, error_message):
        """训练错误回调"""
        self.main_window.set_training_mode(False)
        QMessageBox.critical(self.main_window, "训练错误", f"训练过程中发生错误：\n{error_message}")
    
    def validate_parameters(self, params):
        """验证训练参数是否有效"""
        # 检查数据集
        if not params['data_path'] or not os.path.exists(params['data_path']):
            QMessageBox.warning(self.main_window, "参数错误", "请选择有效的数据集配置文件")
            return False
            
        # 检查模型
        if not params['model']:
            QMessageBox.warning(self.main_window, "参数错误", "请选择模型类型")
            return False
            
        return True
    
    def run(self):
        """运行应用程序"""
        # 显示主窗口
        self.main_window.show()
        
        # 关闭启动画面
        if hasattr(self, 'splash'):
            self.splash.finish(self.main_window)
        
        return self.app.exec()


if __name__ == "__main__":
    app = YOLOv8TrainerApp()
    sys.exit(app.run())
