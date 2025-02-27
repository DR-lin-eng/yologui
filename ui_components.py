#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime
import yaml
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QFileDialog, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox, 
    QTabWidget, QScrollArea, QGroupBox, QProgressBar, QTextEdit, QGridLayout,
    QSplitter, QFrame, QMessageBox, QToolButton, QStyle, QSizePolicy,
    QFormLayout, QToolTip, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, QSize, Slot, Signal, QPoint
from PySide6.QtGui import QFont, QIcon, QPixmap, QColor, QPalette

from parameters import parameter_descriptions, parse_data_yaml, save_data_yaml


class CollapsibleBox(QWidget):
    """可折叠的分组框"""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        
        # 创建标题按钮
        self.toggleButton = QToolButton()
        self.toggleButton.setStyleSheet("""
            QToolButton {
                font-weight: bold;
                font-size: 12px;
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
                text-align: left;
            }
            
            QToolButton:hover {
                background-color: #e5e5e5;
            }
            
            QToolButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.toggleButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggleButton.setArrowType(Qt.RightArrow)
        self.toggleButton.setText(title)
        self.toggleButton.setCheckable(True)
        self.toggleButton.setChecked(False)
        
        # 滚动区域
        self.contentArea = QScrollArea()
        self.contentArea.setFrameShape(QFrame.NoFrame)
        self.contentArea.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.contentArea.setMaximumHeight(0)
        self.contentArea.setMinimumHeight(0)
        
        # 内容控件
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 5, 5, 5)
        self.contentArea.setWidget(self.content_widget)
        self.contentArea.setWidgetResizable(True)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggleButton)
        layout.addWidget(self.contentArea)
        
        # 连接信号
        self.toggleButton.clicked.connect(self.toggle_contents)
        
        # 动画
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        self.animation = QPropertyAnimation(self.contentArea, b"maximumHeight")
        self.animation.setDuration(300)  # 300毫秒
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.finished.connect(self.animation_finished)
        
        # 计算内容高度
        self.content_height = 0
        
    def toggle_contents(self, checked):
        """切换内容区域的展开/折叠状态"""
        # 开始高度和结束高度
        start_height = 0 if checked else self.content_height
        end_height = self.content_height if checked else 0
        
        # 设置箭头方向
        self.toggleButton.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        
        # 设置动画参数
        self.animation.setStartValue(start_height)
        self.animation.setEndValue(end_height)
        
        # 开始动画
        self.animation.start()
    
    def animation_finished(self):
        """动画结束回调"""
        # 如果折叠，确保最大高度为0
        if not self.toggleButton.isChecked():
            self.contentArea.setMaximumHeight(0)
    
    def setContentLayout(self, layout):
        """设置内容区域的布局"""
        # 清除旧布局
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加新布局
        self.content_layout.addLayout(layout)
        
        # 计算内容高度
        self.content_widget.adjustSize()
        self.content_height = self.content_widget.height()
        
    def add_widget(self, widget):
        """添加控件到内容区域"""
        self.content_layout.addWidget(widget)
        
        # 重新计算内容高度
        self.content_widget.adjustSize()
        self.content_height = self.content_widget.height() 
        
    def expand(self):
        """展开内容区域"""
        if not self.toggleButton.isChecked():
            self.toggleButton.click()
            
    def collapse(self):
        """折叠内容区域"""
        if self.toggleButton.isChecked():
            self.toggleButton.click()


class ParameterWidget(QWidget):
    """参数设置控件"""
    
    parameterSelected = Signal(str, str)  # 发出信号: 参数名称, 描述
    
    def __init__(self, name, value, param_type, description="", parent=None):
        super().__init__(parent)
        self.name = name
        self.param_type = param_type
        self.description = description
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        
        # 参数名称标签
        name_label = QLabel(name + ":")
        name_label.setMinimumWidth(120)
        name_label.setToolTip(description)
        layout.addWidget(name_label)
        
        # 根据参数类型创建不同的输入控件
        if param_type == bool:
            self.input_widget = QCheckBox()
            self.input_widget.setChecked(value)
        elif param_type == int:
            self.input_widget = QSpinBox()
            self.input_widget.setRange(-999999, 999999)
            self.input_widget.setValue(value)
        elif param_type == float:
            self.input_widget = QDoubleSpinBox()
            self.input_widget.setRange(-999999.0, 999999.0)
            self.input_widget.setDecimals(4)
            self.input_widget.setValue(value)
        elif param_type == list:
            self.input_widget = QComboBox()
            self.input_widget.addItems(value)
            if isinstance(value, list) and len(value) > 0:
                self.input_widget.setCurrentIndex(0)
        else:  # str 或其他
            self.input_widget = QLineEdit(str(value))
        
        self.input_widget.setToolTip(description)
        layout.addWidget(self.input_widget)
        
        # 如果是文件路径，添加浏览按钮
        if name.endswith('_path') or name == 'model' or name == 'project':
            browse_button = QPushButton("浏览...")
            browse_button.clicked.connect(self.browse_file)
            layout.addWidget(browse_button)
        
        # 添加帮助按钮，点击显示详细描述
        if description:
            help_button = QPushButton("?")
            help_button.setFixedSize(24, 24)
            help_button.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border-radius: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            help_button.clicked.connect(self.show_description)
            layout.addWidget(help_button)
        
        # 鼠标悬停或点击时发出信号
        self.setMouseTracking(True)
    
    def browse_file(self):
        """浏览文件或目录"""
        if self.name == 'data_path':
            file_path, _ = QFileDialog.getOpenFileName(self, "选择数据配置文件", "", "YAML文件 (*.yaml)")
        elif self.name == 'model':
            file_path, _ = QFileDialog.getOpenFileName(self, "选择模型文件", "", "PyTorch模型 (*.pt);;All Files (*)")
        elif self.name == 'project':
            file_path = QFileDialog.getExistingDirectory(self, "选择项目目录")
        else:
            file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "")
            
        if file_path:
            if isinstance(self.input_widget, QLineEdit):
                self.input_widget.setText(file_path)
            elif isinstance(self.input_widget, QComboBox):
                if self.input_widget.findText(file_path) == -1:
                    self.input_widget.addItem(file_path)
                self.input_widget.setCurrentText(file_path)
    
    def show_description(self):
        """显示参数详细描述"""
        self.parameterSelected.emit(self.name, self.description)
    
    def enterEvent(self, event):
        """鼠标进入事件"""
        self.parameterSelected.emit(self.name, self.description)
        super().enterEvent(event)
    
    def get_value(self):
        """获取控件当前值"""
        if isinstance(self.input_widget, QCheckBox):
            return self.input_widget.isChecked()
        elif isinstance(self.input_widget, QSpinBox):
            return self.input_widget.value()
        elif isinstance(self.input_widget, QDoubleSpinBox):
            return self.input_widget.value()
        elif isinstance(self.input_widget, QComboBox):
            return self.input_widget.currentText()
        elif isinstance(self.input_widget, QLineEdit):
            value = self.input_widget.text()
            if self.param_type == int:
                try:
                    return int(value)
                except ValueError:
                    return 0
            elif self.param_type == float:
                try:
                    return float(value)
                except ValueError:
                    return 0.0
            return value
    
    def set_value(self, value):
        """设置控件值"""
        if isinstance(self.input_widget, QCheckBox):
            self.input_widget.setChecked(bool(value))
        elif isinstance(self.input_widget, QSpinBox):
            self.input_widget.setValue(int(value))
        elif isinstance(self.input_widget, QDoubleSpinBox):
            self.input_widget.setValue(float(value))
        elif isinstance(self.input_widget, QComboBox):
            index = self.input_widget.findText(str(value))
            if index >= 0:
                self.input_widget.setCurrentIndex(index)
            else:
                self.input_widget.addItem(str(value))
                self.input_widget.setCurrentText(str(value))
        elif isinstance(self.input_widget, QLineEdit):
            self.input_widget.setText(str(value))


class ParameterGroup(QWidget):
    """参数分组"""
    
    parameterSelected = Signal(str, str)  # 发出信号: 参数名称, 描述
    
    def __init__(self, title, params, parent=None):
        super().__init__(parent)
        self.title = title
        self.params = params
        self.param_widgets = {}
        
        # 创建可折叠分组
        self.box = CollapsibleBox(title)
        layout = QVBoxLayout(self)
        layout.addWidget(self.box)
        
        # 创建网格布局
        grid_layout = QGridLayout()
        grid_layout.setColumnStretch(1, 1)
        
        # 为每个参数创建控件
        row = 0
        for name, value in params.items():
            # 参数类型
            param_type = type(value)
            
            # 获取参数描述
            description = parameter_descriptions.get(name, "")
            
            # 创建参数控件
            param_widget = ParameterWidget(name, value, param_type, description)
            param_widget.parameterSelected.connect(self.on_parameter_selected)
            self.param_widgets[name] = param_widget
            
            # 添加到布局
            grid_layout.addWidget(param_widget, row, 0)
            row += 1
        
        # 设置分组的内容布局
        self.box.setContentLayout(grid_layout)
    
    def on_parameter_selected(self, name, description):
        """参数被选中的事件处理"""
        self.parameterSelected.emit(name, description)
    
    def get_values(self):
        """获取所有参数的当前值"""
        values = {}
        for name, widget in self.param_widgets.items():
            values[name] = widget.get_value()
        return values
    
    def set_values(self, values):
        """设置所有参数的值"""
        for name, value in values.items():
            if name in self.param_widgets:
                self.param_widgets[name].set_value(value)


class TrainingTab(QWidget):
    """训练选项卡"""
    
    def __init__(self, parameters, parent=None):
        super().__init__(parent)
        self.parameters = parameters
        self.param_groups = {}
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        
        # 左右分割区域
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧设置区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 数据选择区域
        data_group = QGroupBox("数据集选择")
        data_layout = QVBoxLayout(data_group)
        data_layout.setSpacing(10)
        
        # 选择任务类型
        task_layout = QHBoxLayout()
        self.task_label = QLabel("任务类型:")
        self.task_combo = QComboBox()
        self.task_combo.addItems(["目标检测 (detect)", "分割 (segment)", "分类 (classify)", "姿态估计 (pose)"])
        self.task_combo.setCurrentIndex(0)
        self.task_combo.currentIndexChanged.connect(self.on_task_changed)
        
        task_layout.addWidget(self.task_label)
        task_layout.addWidget(self.task_combo)
        task_layout.addStretch()
        
        data_layout.addLayout(task_layout)
        
        # 选择数据模式
        self.data_mode_label = QLabel("数据模式:")
        self.data_mode_combo = QComboBox()
        self.data_mode_combo.addItems(["YAML配置文件", "训练文件夹"])
        self.data_mode_combo.setCurrentIndex(0)
        self.data_mode_combo.currentIndexChanged.connect(self.on_data_mode_changed)
        
        data_mode_layout = QHBoxLayout()
        data_mode_layout.addWidget(self.data_mode_label)
        data_mode_layout.addWidget(self.data_mode_combo)
        data_mode_layout.addStretch()
        
        data_layout.addLayout(data_mode_layout)
        
        # YAML配置文件选择
        self.yaml_group = QWidget()
        yaml_layout = QHBoxLayout(self.yaml_group)
        yaml_layout.setContentsMargins(0, 0, 0, 0)
        
        self.data_path_label = QLabel("数据配置文件:")
        self.data_path_input = QLineEdit()
        self.data_path_input.setPlaceholderText("选择数据集YAML文件")
        self.data_path_browse = QPushButton("浏览...")
        self.data_path_browse.clicked.connect(self.browse_data_file)
        self.data_view_button = QPushButton("查看/编辑配置")
        self.data_view_button.clicked.connect(self.view_data_config)
        
        yaml_layout.addWidget(self.data_path_label)
        yaml_layout.addWidget(self.data_path_input, 1)
        yaml_layout.addWidget(self.data_path_browse)
        yaml_layout.addWidget(self.data_view_button)
        
        data_layout.addWidget(self.yaml_group)
        
        # 训练文件夹选择
        self.folder_group = QWidget()
        folder_layout = QVBoxLayout(self.folder_group)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(10)
        
        # 训练文件夹
        train_folder_layout = QHBoxLayout()
        self.train_folder_label = QLabel("训练文件夹:")
        self.train_folder_input = QLineEdit()
        self.train_folder_input.setPlaceholderText("选择训练数据文件夹")
        self.train_folder_browse = QPushButton("浏览...")
        self.train_folder_browse.clicked.connect(self.browse_train_folder)
        
        train_folder_layout.addWidget(self.train_folder_label)
        train_folder_layout.addWidget(self.train_folder_input, 1)
        train_folder_layout.addWidget(self.train_folder_browse)
        
        folder_layout.addLayout(train_folder_layout)
        
        # 分类任务设置
        self.class_task_frame = QFrame()
        self.class_task_frame.setFrameShape(QFrame.StyledPanel)
        self.class_task_frame.setStyleSheet("QFrame {background-color: #f8f9fa; border-radius: 5px; padding: 5px;}")
        class_task_layout = QVBoxLayout(self.class_task_frame)
        
        # 分类数据集结构选择
        self.dataset_struct_label = QLabel("数据集结构:")
        self.dataset_struct_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        
        # 单选按钮组
        self.dataset_struct_group = QButtonGroup(self)
        
        # 直接使用文件夹(不生成YAML)
        self.direct_folder_radio = QRadioButton("直接使用文件夹训练 (无需data.yaml)")
        self.direct_folder_radio.setChecked(True)
        self.direct_folder_radio.setToolTip("对于分类任务，可以直接使用文件夹路径进行训练，无需生成data.yaml")
        self.dataset_struct_group.addButton(self.direct_folder_radio, 1)
        
        # 预分割数据集结构
        self.presplit_folder_radio = QRadioButton("已分割的数据集 (含train/val/test文件夹)")
        self.presplit_folder_radio.setToolTip("数据集已包含train、val和test文件夹，每个文件夹下有类别子文件夹")
        self.dataset_struct_group.addButton(self.presplit_folder_radio, 2)
        
        # 单层类别文件夹结构
        self.single_folder_radio = QRadioButton("单层类别文件夹 (自动分割train/val)")
        self.single_folder_radio.setToolTip("数据集包含各个类别的文件夹，系统将自动分割为训练集和验证集")
        self.dataset_struct_group.addButton(self.single_folder_radio, 3)
        
        class_task_layout.addWidget(self.dataset_struct_label)
        class_task_layout.addWidget(self.direct_folder_radio)
        class_task_layout.addWidget(self.presplit_folder_radio)
        class_task_layout.addWidget(self.single_folder_radio)
        
        # 连接信号
        self.dataset_struct_group.buttonClicked.connect(self.on_dataset_struct_changed)
        
        # 文件夹结构说明
        self.struct_info_frame = QFrame()
        self.struct_info_frame.setFrameShape(QFrame.StyledPanel)
        self.struct_info_frame.setStyleSheet("background-color: #e9ecef; padding: 8px; border-radius: 5px;")
        struct_info_layout = QVBoxLayout(self.struct_info_frame)
        
        self.struct_info_label = QLabel("文件夹结构示例:\n"
                                    "└── dataset/\n"
                                    "    ├── class1/\n"
                                    "    │   ├── img1.jpg\n"
                                    "    │   └── ...\n"
                                    "    └── class2/\n"
                                    "        ├── img2.jpg\n"
                                    "        └── ...")
        self.struct_info_label.setStyleSheet("font-family: monospace; color: #495057;")
        struct_info_layout.addWidget(self.struct_info_label)
        
        class_task_layout.addWidget(self.struct_info_frame)
        
        folder_layout.addWidget(self.class_task_frame)
        self.class_task_frame.setVisible(False)
        
        # 非分类任务的设置
        self.nonclass_task_frame = QFrame()
        self.nonclass_task_frame.setFrameShape(QFrame.StyledPanel)
        self.nonclass_task_frame.setStyleSheet("QFrame {background-color: #f8f9fa; border-radius: 5px; padding: 5px;}")
        nonclass_task_layout = QVBoxLayout(self.nonclass_task_frame)
        
        # 验证集比例
        val_split_layout = QHBoxLayout()
        self.val_split_label = QLabel("验证集比例:")
        self.val_split_spin = QDoubleSpinBox()
        self.val_split_spin.setRange(0.0, 0.5)
        self.val_split_spin.setSingleStep(0.05)
        self.val_split_spin.setValue(0.2)
        self.val_split_spin.setDecimals(2)
        
        val_split_layout.addWidget(self.val_split_label)
        val_split_layout.addWidget(self.val_split_spin)
        val_split_layout.addStretch()
        
        # 生成YAML按钮
        self.generate_yaml_button = QPushButton("生成YAML配置")
        self.generate_yaml_button.clicked.connect(self.generate_yaml_config)
        
        nonclass_task_layout.addLayout(val_split_layout)
        nonclass_task_layout.addWidget(self.generate_yaml_button)
        
        folder_layout.addWidget(self.nonclass_task_frame)
        
        data_layout.addWidget(self.folder_group)
        
        # 默认显示YAML配置模式
        self.folder_group.setVisible(False)
        
        left_layout.addWidget(data_group)
        
        # 模型选择区域
        model_group = QGroupBox("模型选择")
        model_layout = QHBoxLayout(model_group)
        
        self.model_label = QLabel("模型:")
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "yolov8n.pt",  # Nano
            "yolov8s.pt",  # Small
            "yolov8m.pt",  # Medium
            "yolov8l.pt",  # Large
            "yolov8x.pt"   # XLarge
        ])
        self.model_browse = QPushButton("浏览...")
        self.model_browse.clicked.connect(self.browse_model_file)
        
        model_layout.addWidget(self.model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.model_browse)
        
        left_layout.addWidget(model_group)
        
        # CUDA选择
        cuda_group = QGroupBox("CUDA设置")
        cuda_layout = QHBoxLayout(cuda_group)
        
        self.cuda_available_label = QLabel("CUDA可用: 未检测")
        self.use_cuda_checkbox = QCheckBox("使用CUDA训练")
        self.use_cuda_checkbox.setChecked(True)
        self.device_label = QLabel("设备:")
        self.device_combo = QComboBox()
        self.device_combo.addItem("")  # 自动选择
        
        cuda_layout.addWidget(self.cuda_available_label)
        cuda_layout.addWidget(self.use_cuda_checkbox)
        cuda_layout.addWidget(self.device_label)
        cuda_layout.addWidget(self.device_combo)
        
        left_layout.addWidget(cuda_group)
        
        # 创建参数分组的滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 训练参数分组
        for group_name, group_params in parameters.items():
            param_group = ParameterGroup(group_name.capitalize(), group_params)
            param_group.parameterSelected.connect(self.on_parameter_selected)
            self.param_groups[group_name] = param_group
            scroll_layout.addWidget(param_group)
        
        scroll_area.setWidget(scroll_widget)
        left_layout.addWidget(scroll_area, 1)  # 添加滚动区并设置拉伸因子
        
        # 右侧参数说明区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # 参数说明标题
        self.param_desc_title = QLabel("参数说明")
        self.param_desc_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #333;
            padding: 5px;
            border-bottom: 1px solid #ddd;
        """)
        
        # 参数名称
        self.param_name_label = QLabel("")
        self.param_name_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #444;
            padding: 5px;
        """)
        
        # 参数描述
        self.param_desc_text = QTextEdit()
        self.param_desc_text.setReadOnly(True)
        self.param_desc_text.setStyleSheet("""
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            padding: 5px;
            font-size: 13px;
        """)
        
        right_layout.addWidget(self.param_desc_title)
        right_layout.addWidget(self.param_name_label)
        right_layout.addWidget(self.param_desc_text, 1)
        
        # 添加左右区域到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)  # 左侧占比更大
        splitter.setStretchFactor(1, 1)  # 右侧占比较小
        
        main_layout.addWidget(splitter, 1)
        
        # 训练控制按钮
        control_layout = QHBoxLayout()
        self.start_training_button = QPushButton("开始训练")
        self.start_training_button.setMinimumHeight(40)
        self.stop_training_button = QPushButton("停止训练")
        self.stop_training_button.setMinimumHeight(40)
        self.stop_training_button.setEnabled(False)
        
        control_layout.addWidget(self.start_training_button)
        control_layout.addWidget(self.stop_training_button)
        
        main_layout.addLayout(control_layout)
        
        # 初始状态下显示一些默认说明文字
        self.param_name_label.setText("参数使用说明")
        self.param_desc_text.setText("鼠标悬停在参数上可查看该参数的详细说明。\n\n"
                                  "点击参数后的问号按钮也可以查看详细说明。\n\n"
                                  "常见参数说明：\n"
                                  "- data_path: 数据集配置文件路径，YAML格式\n"
                                  "- batch: 训练批次大小，根据显存调整\n"
                                  "- imgsz: 输入图像大小，单位为像素\n"
                                  "- epochs: 训练总轮数\n"
                                  "- device: 训练设备，空为自动选择")
    
    def on_parameter_selected(self, name, description):
        """参数被选择时更新右侧说明区域"""
        if not description:
            return
            
        self.param_name_label.setText(f"参数: {name}")
        self.param_desc_text.setText(description)
    
    def on_task_changed(self, index):
        """任务类型切换"""
        task_text = self.task_combo.currentText()
        
        # 检查是否为分类任务
        is_classification = "分类" in task_text or "classify" in task_text.lower()
        
        # 更新UI显示
        self.class_task_frame.setVisible(is_classification)
        self.nonclass_task_frame.setVisible(not is_classification)
        
        # 如果是分类任务，更新数据模式提示
        if is_classification:
            self.train_folder_label.setText("分类数据文件夹:")
            self.train_folder_input.setPlaceholderText("选择包含各个类别文件夹的目录")
            
            # 更新文件夹结构说明，默认显示单层结构
            self.update_folder_structure_info(1)
        else:
            self.train_folder_label.setText("训练文件夹:")
            self.train_folder_input.setPlaceholderText("选择包含images和labels的目录")
    
    def on_data_mode_changed(self, index):
        """数据模式切换"""
        if index == 0:  # YAML配置文件
            self.yaml_group.setVisible(True)
            self.folder_group.setVisible(False)
        else:  # 训练文件夹
            self.yaml_group.setVisible(False)
            self.folder_group.setVisible(True)
            
            # 如果是分类任务，显示分类任务相关控件
            task_text = self.task_combo.currentText()
            is_classification = "分类" in task_text or "classify" in task_text.lower()
            self.class_task_frame.setVisible(is_classification)
            self.nonclass_task_frame.setVisible(not is_classification)
    
    def on_dataset_struct_changed(self, button):
        """数据集结构选择改变时更新UI"""
        if button == self.direct_folder_radio:
            struct_type = 1  # 直接使用文件夹
        elif button == self.presplit_folder_radio:
            struct_type = 2  # 预分割的数据集
        elif button == self.single_folder_radio:
            struct_type = 3  # 单层类别文件夹
        else:
            struct_type = 1  # 默认
        
        self.update_folder_structure_info(struct_type)
    
    def update_folder_structure_info(self, struct_type):
        """更新文件夹结构说明"""
        if struct_type == 1:  # 直接使用文件夹
            self.struct_info_label.setText("文件夹结构示例:\n"
                                      "└── dataset/\n"
                                      "    ├── class1/\n"
                                      "    │   ├── img1.jpg\n"
                                      "    │   └── ...\n"
                                      "    └── class2/\n"
                                      "        ├── img2.jpg\n"
                                      "        └── ...")
        elif struct_type == 2:  # 预分割的数据集
            self.struct_info_label.setText("文件夹结构示例:\n"
                                      "└── dataset/\n"
                                      "    ├── train/\n"
                                      "    │   ├── class1/\n"
                                      "    │   └── class2/\n"
                                      "    ├── val/\n"
                                      "    │   ├── class1/\n"
                                      "    │   └── class2/\n"
                                      "    └── test/ (可选)\n"
                                      "        ├── class1/\n"
                                      "        └── class2/")
        elif struct_type == 3:  # 单层类别文件夹
            self.struct_info_label.setText("文件夹结构示例:\n"
                                      "└── dataset/\n"
                                      "    ├── class1/\n"
                                      "    │   ├── img1.jpg\n"
                                      "    │   └── ...\n"
                                      "    └── class2/\n"
                                      "        ├── img2.jpg\n"
                                      "        └── ...\n\n"
                                      "系统将自动分割为训练集和验证集")

    def browse_data_file(self):
        """浏览选择数据配置文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择数据配置文件", "", "YAML文件 (*.yaml)")
        if file_path:
            self.data_path_input.setText(file_path)
    
    def browse_train_folder(self):
        """浏览选择训练文件夹"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择训练数据文件夹")
        if folder_path:
            self.train_folder_input.setText(folder_path)
            # 自动检测文件夹结构类型
            self.detect_folder_structure(folder_path)
    
    def detect_folder_structure(self, folder_path):
        """检测文件夹结构类型，自动选择合适的选项"""
        if not os.path.isdir(folder_path):
            return
            
        # 检查是否为预分割结构（有train/val子文件夹）
        train_dir = os.path.join(folder_path, 'train')
        val_dir = os.path.join(folder_path, 'val')
        
        if os.path.isdir(train_dir) and os.path.isdir(val_dir):
            # 检查train目录下是否有类别子文件夹
            has_class_dirs = False
            for item in os.listdir(train_dir):
                if os.path.isdir(os.path.join(train_dir, item)) and not item.startswith('.'):
                    has_class_dirs = True
                    break
            
            if has_class_dirs:
                # 这是预分割的分类数据集结构
                self.presplit_folder_radio.setChecked(True)
                self.update_folder_structure_info(2)
                return
        
        # 检查是否为单层类别文件夹结构
        has_potential_class_dirs = False
        has_images = False
        
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                has_potential_class_dirs = True
                
                # 检查文件夹中是否有图像文件
                for file in os.listdir(item_path):
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                        has_images = True
                        break
                
                if has_images:
                    break
        
        if has_potential_class_dirs and has_images:
            # 这可能是单层类别文件夹结构
            self.single_folder_radio.setChecked(True)
            self.update_folder_structure_info(3)
            return
        
        # 默认使用直接文件夹模式
        self.direct_folder_radio.setChecked(True)
        self.update_folder_structure_info(1)
    
    def generate_yaml_config(self):
        """从训练文件夹生成YAML配置"""
        train_folder = self.train_folder_input.text()
        if not train_folder or not os.path.isdir(train_folder):
            QMessageBox.warning(self, "错误", "请选择有效的训练文件夹")
            return
        
        try:
            # 创建YAML配置
            import yaml
            import os.path as osp
            import shutil
            
            # 检查是否为分类任务
            task_text = self.task_combo.currentText()
            is_classification = "分类" in task_text or "classify" in task_text.lower()
            
            # 创建配置
            config = {}
            
            if is_classification:
                # 分类任务
                # 获取当前选择的数据集结构类型
                if self.direct_folder_radio.isChecked():
                    # 直接使用文件夹，不生成YAML
                    QMessageBox.information(self, "直接使用文件夹", 
                                       "已选择直接使用文件夹模式，无需生成YAML配置。\n"
                                       "训练时将直接使用该文件夹路径。")
                    return
                    
                elif self.presplit_folder_radio.isChecked():
                    # 已分割的数据集结构
                    config['path'] = train_folder
                    config['train'] = 'train'
                    config['val'] = 'val'
                    if os.path.isdir(os.path.join(train_folder, 'test')):
                        config['test'] = 'test'
                    
                    # 检测类别
                    train_dir = os.path.join(train_folder, 'train')
                    classes = []
                    for item in os.listdir(train_dir):
                        if os.path.isdir(os.path.join(train_dir, item)) and not item.startswith('.'):
                            classes.append(item)
                    
                elif self.single_folder_radio.isChecked():
                    # 单层类别文件夹结构，需要自动分割
                    # 首先获取所有类别
                    classes = []
                    for item in os.listdir(train_folder):
                        if os.path.isdir(os.path.join(train_folder, item)) and not item.startswith('.'):
                            classes.append(item)
                    
                    # 创建train和val目录
                    train_dir = os.path.join(train_folder, 'train')
                    val_dir = os.path.join(train_folder, 'val')
                    
                    # 检查目录是否已存在
                    if os.path.exists(train_dir) or os.path.exists(val_dir):
                        reply = QMessageBox.question(
                            self, 
                            "目录已存在", 
                            "train或val目录已存在，是否覆盖？",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.No:
                            return
                        
                        # 删除已存在的目录
                        if os.path.exists(train_dir):
                            shutil.rmtree(train_dir)
                        if os.path.exists(val_dir):
                            shutil.rmtree(val_dir)
                    
                    # 创建目录
                    os.makedirs(train_dir, exist_ok=True)
                    os.makedirs(val_dir, exist_ok=True)
                    
                    # 为每个类别创建子目录
                    for cls in classes:
                        os.makedirs(os.path.join(train_dir, cls), exist_ok=True)
                        os.makedirs(os.path.join(val_dir, cls), exist_ok=True)
                    
                    # 获取验证集比例
                    val_ratio = self.val_split_spin.value()
                    
                    # 分割数据
                    import random
                    random.seed(42)  # 固定随机种子以确保可重复
                    
                    for cls in classes:
                        cls_dir = os.path.join(train_folder, cls)
                        images = [f for f in os.listdir(cls_dir) 
                                 if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
                        
                        # 随机打乱
                        random.shuffle(images)
                        
                        # 计算分割点
                        split_idx = int(len(images) * (1 - val_ratio))
                        train_images = images[:split_idx]
                        val_images = images[split_idx:]
                        
                        # 复制到train和val目录
                        for img in train_images:
                            shutil.copy2(
                                os.path.join(cls_dir, img),
                                os.path.join(train_dir, cls, img)
                            )
                        
                        for img in val_images:
                            shutil.copy2(
                                os.path.join(cls_dir, img),
                                os.path.join(val_dir, cls, img)
                            )
                    
                    # 更新配置
                    config['path'] = train_folder
                    config['train'] = 'train'
                    config['val'] = 'val'
                
                # 设置类别信息
                config['nc'] = len(classes)
                config['names'] = {i: name for i, name in enumerate(classes)}
                
            else:
                # 检测/分割任务
                config['path'] = train_folder
                config['train'] = 'images/train'
                config['val'] = 'images/val'
                config['test'] = 'images/test'
                
                # 尝试自动检测类别
                if os.path.exists(os.path.join(train_folder, 'labels')):
                    classes = set()
                    label_dir = os.path.join(train_folder, 'labels')
                    
                    for file in os.listdir(label_dir):
                        if file.endswith('.txt'):
                            with open(os.path.join(label_dir, file), 'r') as f:
                                for line in f:
                                    parts = line.strip().split()
                                    if parts:
                                        class_id = int(parts[0])
                                        classes.add(class_id)
                    
                    config['nc'] = max(classes) + 1 if classes else 0
                    config['names'] = {i: f'class{i}' for i in range(config['nc'])}
                else:
                    config['nc'] = 0
                    config['names'] = {}
            
            # 保存YAML文件
            yaml_path = os.path.join(train_folder, 'data.yaml')
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            
            # 更新UI
            self.data_path_input.setText(yaml_path)
            self.data_mode_combo.setCurrentIndex(0)  # 切换到YAML模式
            
            QMessageBox.information(self, "成功", f"已生成YAML配置文件:\n{yaml_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成YAML配置失败:\n{str(e)}")
    
    def browse_model_file(self):
        """浏览选择模型文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择模型文件", "", "PyTorch模型 (*.pt);;All Files (*)")
        if file_path:
            if self.model_combo.findText(file_path) == -1:
                self.model_combo.addItem(file_path)
            self.model_combo.setCurrentText(file_path)
    
    def view_data_config(self):
        """查看/编辑数据配置"""
        data_path = self.data_path_input.text()
        if not data_path or not os.path.exists(data_path):
            QMessageBox.warning(self, "错误", "请先选择有效的数据配置文件")
            return
        
        # 解析YAML文件
        data_config = parse_data_yaml(data_path)
        if not data_config:
            QMessageBox.warning(self, "错误", "无法解析数据配置文件")
            return
        
        # 显示数据配置对话框
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextEdit, QVBoxLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("数据配置")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 显示YAML内容
        text_edit = QTextEdit()
        text_edit.setPlainText(yaml.dump(data_config, allow_unicode=True))
        layout.addWidget(text_edit)
        
        # 对话框按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(lambda: self.save_data_config(data_path, text_edit.toPlainText(), dialog))
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.exec()
    
    def save_data_config(self, file_path, yaml_content, dialog):
        """保存数据配置"""
        try:
            data = yaml.safe_load(yaml_content)
            with open(file_path, 'w', encoding='utf-8') as file:
                yaml.dump(data, file, allow_unicode=True)
            dialog.accept()
        except Exception as e:
            QMessageBox.critical(dialog, "保存错误", f"保存YAML时出错：{str(e)}")
    
    def get_training_parameters(self):
        """获取所有训练参数"""
        params = {}
        
        # 获取任务类型
        task_text = self.task_combo.currentText()
        if "检测" in task_text or "detect" in task_text.lower():
            params['task'] = 'detect'
        elif "分割" in task_text or "segment" in task_text.lower():
            params['task'] = 'segment'
        elif "分类" in task_text or "classify" in task_text.lower():
            params['task'] = 'classify'
            params['is_classification'] = True
        elif "姿态" in task_text or "pose" in task_text.lower():
            params['task'] = 'pose'
        
        # 获取数据路径
        if self.data_mode_combo.currentIndex() == 0:  # YAML配置文件模式
            params['data_path'] = self.data_path_input.text()
        else:  # 训练文件夹模式
            train_folder = self.train_folder_input.text()
            
            # 分类任务
            if params.get('is_classification', False):
                # 根据选择的数据集结构类型处理
                if self.direct_folder_radio.isChecked():
                    # 直接使用文件夹
                    params['train_folder'] = train_folder
                    params['direct_folder_mode'] = True
                elif self.presplit_folder_radio.isChecked() or self.single_folder_radio.isChecked():
                    # 已分割或自动分割的数据集，生成或使用YAML
                    yaml_path = os.path.join(train_folder, 'data.yaml')
                    
                    if not os.path.exists(yaml_path):
                        reply = QMessageBox.question(
                            self, 
                            "配置文件不存在", 
                            "数据集YAML配置文件不存在，是否立即生成？",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        
                        if reply == QMessageBox.Yes:
                            self.generate_yaml_config()
                            params['data_path'] = yaml_path
                        else:
                            return None  # 用户取消训练
                    else:
                        params['data_path'] = yaml_path
            else:
                # 检测/分割任务
                yaml_path = os.path.join(train_folder, 'data.yaml')
                
                if not os.path.exists(yaml_path):
                    reply = QMessageBox.question(
                        self, 
                        "配置文件不存在", 
                        "数据集YAML配置文件不存在，是否立即生成？",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        self.generate_yaml_config()
                        params['data_path'] = yaml_path
                    else:
                        return None  # 用户取消训练
                else:
                    params['data_path'] = yaml_path
        
        # 获取模型
        params['model'] = self.model_combo.currentText()
        
        # 如果是分类任务，确保使用分类模型
        if params.get('is_classification', False) and not params['model'].endswith('-cls.pt'):
            model_name = params['model'].split('.')[0]
            if not model_name.endswith('-cls'):
                model_name += '-cls'
            params['model'] = f"{model_name}.pt"
            
            # 提示用户使用分类模型
            QMessageBox.information(
                self,
                "模型自动调整",
                f"检测到分类任务，已自动调整为分类模型: {params['model']}"
            )
        
        # 获取CUDA设置
        if self.use_cuda_checkbox.isChecked():
            params['device'] = self.device_combo.currentText()
        else:
            params['device'] = 'cpu'
        
        # 获取各个分组的参数
        for group_name, param_group in self.param_groups.items():
            group_params = param_group.get_values()
            params.update(group_params)
        
        return params
    
    def update_cuda_status(self, available):
        """更新CUDA状态显示"""
        if available:
            self.cuda_available_label.setText("CUDA可用: 是")
            self.use_cuda_checkbox.setEnabled(True)
            self.use_cuda_checkbox.setChecked(True)
        else:
            self.cuda_available_label.setText("CUDA可用: 否")
            self.use_cuda_checkbox.setEnabled(False)
            self.use_cuda_checkbox.setChecked(False)
    
    def set_training_mode(self, training):
        """设置界面的训练/非训练状态"""
        self.start_training_button.setEnabled(not training)
        self.stop_training_button.setEnabled(training)
        
        # 禁用/启用参数编辑
        self.task_combo.setEnabled(not training)
        self.data_mode_combo.setEnabled(not training)
        self.data_path_input.setEnabled(not training)
        self.data_path_browse.setEnabled(not training)
        self.data_view_button.setEnabled(not training)
        self.train_folder_input.setEnabled(not training)
        self.train_folder_browse.setEnabled(not training)
        self.direct_folder_radio.setEnabled(not training)
        self.presplit_folder_radio.setEnabled(not training)
        self.single_folder_radio.setEnabled(not training)
        self.val_split_spin.setEnabled(not training)
        self.generate_yaml_button.setEnabled(not training)
        self.model_combo.setEnabled(not training)
        self.model_browse.setEnabled(not training)
        self.use_cuda_checkbox.setEnabled(not training)
        self.device_combo.setEnabled(not training)
        
        # 禁用/启用所有参数分组
        for group_name, param_group in self.param_groups.items():
            for name, widget in param_group.param_widgets.items():
                widget.setEnabled(not training)


class ProgressTab(QWidget):
    """训练进度选项卡"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        
        # 进度显示区域
        progress_group = QGroupBox("训练进度")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(10)
        
        # 概览信息 - 使用卡片样式
        from PySide6.QtWidgets import QFrame
        overview_frame = QFrame()
        overview_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                border: 1px solid #e9ecef;
            }
            QLabel {
                font-size: 14px;
                color: #212529;
            }
        """)
        overview_layout = QHBoxLayout(overview_frame)
        
        self.current_epoch_label = QLabel("当前轮次: 0/0")
        self.current_epoch_label.setStyleSheet("font-weight: bold;")
        
        self.elapsed_time_label = QLabel("已用时间: 00:00:00")
        self.elapsed_time_label.setStyleSheet("color: #495057;")
        
        self.eta_label = QLabel("预计剩余: 00:00:00")
        self.eta_label.setStyleSheet("color: #0d6efd;")
        
        overview_layout.addWidget(self.current_epoch_label)
        overview_layout.addWidget(self.elapsed_time_label)
        overview_layout.addWidget(self.eta_label)
        
        progress_layout.addWidget(overview_frame)
        
        # 进度条 - 美化
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 5px;
                background-color: #e9ecef;
                text-align: center;
                height: 25px;
                font-weight: bold;
            }
            
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d6efd, stop:1 #0dcaf0);
                border-radius: 5px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        # 指标显示 - 改为卡片式布局
        metrics_frame = QFrame()
        metrics_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                border: 1px solid #e9ecef;
            }
            QLabel {
                font-size: 14px;
            }
        """)
        metrics_layout = QGridLayout(metrics_frame)
        metrics_layout.setContentsMargins(15, 10, 15, 10)
        metrics_layout.setSpacing(10)
        
        metrics_title = QLabel("性能指标")
        metrics_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #212529;")
        metrics_layout.addWidget(metrics_title, 0, 0, 1, 3)
        
        # 指标标签
        self.mAP_label = QLabel("mAP50-95: -")
        self.mAP_label.setStyleSheet("color: #0d6efd;")
        
        self.mAP50_label = QLabel("mAP50: -")
        self.mAP50_label.setStyleSheet("color: #20c997;")
        
        self.precision_label = QLabel("Precision: -")
        self.precision_label.setStyleSheet("color: #fd7e14;")
        
        self.recall_label = QLabel("Recall: -")
        self.recall_label.setStyleSheet("color: #6f42c1;")
        
        metrics_layout.addWidget(self.mAP_label, 1, 0)
        metrics_layout.addWidget(self.mAP50_label, 1, 1)
        metrics_layout.addWidget(self.precision_label, 2, 0)
        metrics_layout.addWidget(self.recall_label, 2, 1)
        
        progress_layout.addWidget(metrics_frame)
        
        main_layout.addWidget(progress_group)
        
        # 日志显示区域
        log_group = QGroupBox("训练日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #212529;
                color: #f8f9fa;
                border: none;
                border-radius: 5px;
                font-family: Consolas, Monospace;
                font-size: 12px;
                padding: 5px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        main_layout.addWidget(log_group, 1)  # 添加拉伸因子
    
    def update_progress(self, progress_info):
        """更新进度信息"""
        # 更新输出日志
        if 'output_line' in progress_info:
            self.log_text.append(progress_info['output_line'])
            # 滚动到底部
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
        
        # 更新进度信息
        if 'current_epoch' in progress_info and 'total_epochs' in progress_info:
            self.current_epoch_label.setText(
                f"当前轮次: {progress_info['current_epoch']}/{progress_info['total_epochs']}"
            )
        
        # 更新时间信息
        if 'elapsed_time' in progress_info:
            self.elapsed_time_label.setText(f"已用时间: {progress_info['elapsed_time']}")
        
        if 'eta' in progress_info:
            self.eta_label.setText(f"预计剩余: {progress_info['eta']}")
        
        # 更新进度条
        if 'progress' in progress_info:
            self.progress_bar.setValue(int(progress_info['progress']))
        
        # 更新指标
        if 'metrics' in progress_info:
            metrics = progress_info['metrics']
            if 'mAP50-95' in metrics:
                self.mAP_label.setText(f"mAP50-95: {metrics['mAP50-95']:.4f}")
            if 'mAP50' in metrics:
                self.mAP50_label.setText(f"mAP50: {metrics['mAP50']:.4f}")
            if 'precision' in metrics:
                self.precision_label.setText(f"Precision: {metrics['precision']:.4f}")
            if 'recall' in metrics:
                self.recall_label.setText(f"Recall: {metrics['recall']:.4f}")


class EnvironmentTab(QWidget):
    """环境信息选项卡"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 系统信息
        system_group = QGroupBox("系统信息")
        system_layout = QGridLayout(system_group)
        
        self.os_label = QLabel("操作系统: 未检测")
        self.python_version_label = QLabel("Python版本: 未检测")
        
        system_layout.addWidget(self.os_label, 0, 0)
        system_layout.addWidget(self.python_version_label, 0, 1)
        
        main_layout.addWidget(system_group)
        
        # YOLOv8信息
        yolo_group = QGroupBox("YOLOv8")
        yolo_layout = QGridLayout(yolo_group)
        
        self.yolo_installed_label = QLabel("安装状态: 未检测")
        self.yolo_version_label = QLabel("版本: 未检测")
        self.install_yolo_button = QPushButton("安装YOLOv8")
        
        yolo_layout.addWidget(self.yolo_installed_label, 0, 0)
        yolo_layout.addWidget(self.yolo_version_label, 0, 1)
        yolo_layout.addWidget(self.install_yolo_button, 0, 2)
        
        main_layout.addWidget(yolo_group)
        
        # CUDA信息
        cuda_group = QGroupBox("CUDA")
        cuda_layout = QGridLayout(cuda_group)
        
        self.cuda_available_label = QLabel("CUDA可用: 未检测")
        self.cuda_version_label = QLabel("CUDA版本: 未检测")
        self.torch_version_label = QLabel("PyTorch版本: 未检测")
        
        cuda_layout.addWidget(self.cuda_available_label, 0, 0)
        cuda_layout.addWidget(self.cuda_version_label, 0, 1)
        cuda_layout.addWidget(self.torch_version_label, 1, 0, 1, 2)
        
        main_layout.addWidget(cuda_group)
        
        # GPU信息
        gpu_group = QGroupBox("GPU信息")
        gpu_layout = QVBoxLayout(gpu_group)
        
        self.gpu_info_text = QTextEdit()
        self.gpu_info_text.setReadOnly(True)
        gpu_layout.addWidget(self.gpu_info_text)
        
        main_layout.addWidget(gpu_group, 1)  # 添加拉伸因子
        
        # 底部工具栏
        tools_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("刷新")
        tools_layout.addWidget(self.refresh_button)
        
        main_layout.addLayout(tools_layout)
    
    def update_environment_info(self, status):
        """更新环境信息"""
        # 系统信息
        self.os_label.setText(f"操作系统: {status.get('os_info', '未知')}")
        self.python_version_label.setText(f"Python版本: {status.get('python_version', '未知')}")
        
        # YOLOv8信息
        if status.get('yolov8_installed', False):
            self.yolo_installed_label.setText("安装状态: 已安装")
            self.yolo_version_label.setText(f"版本: {status.get('yolov8_version', '未知')}")
            self.install_yolo_button.setEnabled(False)
        else:
            self.yolo_installed_label.setText("安装状态: 未安装")
            self.yolo_version_label.setText("版本: -")
            self.install_yolo_button.setEnabled(True)
        
        # CUDA信息
        if status.get('cuda_available', False):
            self.cuda_available_label.setText("CUDA可用: 是")
        else:
            self.cuda_available_label.setText("CUDA可用: 否")
        
        self.cuda_version_label.setText(f"CUDA版本: {status.get('cuda_version', '未知')}")
        self.torch_version_label.setText(f"PyTorch版本: {status.get('torch_version', '未知')}")
        
        # GPU信息
        gpu_info = status.get('gpu_info', [])
        if gpu_info:
            gpu_text = ""
            for gpu in gpu_info:
                gpu_text += f"GPU {gpu['index']}: {gpu['name']} ({gpu['memory']})\n"
            self.gpu_info_text.setText(gpu_text)
        else:
            self.gpu_info_text.setText("未检测到GPU")


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self, parameters, parent=None):
        super().__init__(parent)
        self.parameters = parameters
        
        # 设置窗口属性
        self.setWindowTitle("YOLOv8 训练工具")
        self.resize(1200, 800)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cccccc;
                border-radius: 5px;
                background-color: #ffffff;
            }
            
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 16px;
                min-width: 100px;
                font-weight: bold;
            }
            
            QTabBar::tab:selected {
                background-color: #ffffff;
                border-bottom: 1px solid #ffffff;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #e5e5e5;
            }
            
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background: #a0a0a0;
                min-height: 20px;
                border-radius: 6px;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #2980b9;
            }
            
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            
            QGroupBox {
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 1.5ex;
                font-weight: bold;
                font-size: 12px;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                color: #333333;
            }
            
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
                background-color: #ffffff;
                selection-background-color: #3498db;
            }
            
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 1px solid #3498db;
            }
            
            QProgressBar {
                border: none;
                border-radius: 5px;
                background-color: #f0f0f0;
                text-align: center;
                height: 20px;
            }
            
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 5px;
            }
            
            QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 5px;
                background-color: #ffffff;
                selection-background-color: #3498db;
            }
        """)
        
        # 训练选项卡
        self.training_tab = TrainingTab(parameters)
        tab_widget.addTab(self.training_tab, "训练设置")
        
        # 进度选项卡
        self.progress_tab = ProgressTab()
        tab_widget.addTab(self.progress_tab, "训练进度")
        
        # 环境选项卡
        self.environment_tab = EnvironmentTab()
        tab_widget.addTab(self.environment_tab, "环境信息")
        
        main_layout.addWidget(tab_widget)
        
        # 获取训练控制按钮的引用
        self.start_training_button = self.training_tab.start_training_button
        self.stop_training_button = self.training_tab.stop_training_button
        
        # 设置应用程序图标
        try:
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon("icon.png"))  # 您需要提供一个图标文件
        except:
            pass
        
        # 状态栏
        self.statusBar().showMessage("YOLOv8 训练工具已就绪")
    
    def update_cuda_status(self, available):
        """更新CUDA状态"""
        self.training_tab.update_cuda_status(available)
    
    def update_environment_info(self, status):
        """更新环境信息"""
        self.environment_tab.update_environment_info(status)
        
        # 更新CUDA设备选择
        if status.get('cuda_available', False):
            self.training_tab.device_combo.clear()
            self.training_tab.device_combo.addItem("")  # 自动选择
            
            # 添加每个GPU
            for gpu in status.get('gpu_info', []):
                self.training_tab.device_combo.addItem(
                    f"cuda:{gpu['index']} ({gpu['name']})"
                )
    
    def update_progress(self, progress_info):
        """更新进度信息"""
        self.progress_tab.update_progress(progress_info)
    
    def set_training_mode(self, training):
        """设置界面的训练/非训练状态"""
        self.training_tab.set_training_mode(training)
    
    def get_training_parameters(self):
        """获取所有训练参数"""
        return self.training_tab.get_training_parameters()
