#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import importlib.util
import platform
import shutil
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QProgressBar, 
    QFormLayout, QDialogButtonBox, QMessageBox,
    QRadioButton, QButtonGroup, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QThread


class InstallThread(QThread):
    """执行安装任务的线程"""
    progress_signal = Signal(str)
    finished_signal = Signal(bool, str)
    
    def __init__(self, command, parent=None):
        super().__init__(parent)
        self.command = command
    
    def run(self):
        try:
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 读取进程输出
            for line in iter(process.stdout.readline, ''):
                self.progress_signal.emit(line.strip())
            
            # 等待进程完成
            exit_code = process.wait()
            if exit_code == 0:
                self.finished_signal.emit(True, "安装成功完成")
            else:
                self.finished_signal.emit(False, f"安装失败，退出代码: {exit_code}")
                
        except Exception as e:
            self.finished_signal.emit(False, f"安装过程中发生错误: {str(e)}")


class MirrorConfigDialog(QDialog):
    """镜像源配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置镜像源")
        self.resize(500, 300)
        
        layout = QVBoxLayout(self)
        
        # 预设镜像源
        self.mirrors = {
            "默认 (PyPI)": "https://pypi.org/simple",
            "阿里云": "https://mirrors.aliyun.com/pypi/simple/",
            "清华大学": "https://pypi.tuna.tsinghua.edu.cn/simple/",
            "中国科技大学": "https://pypi.mirrors.ustc.edu.cn/simple/",
            "华为云": "https://repo.huaweicloud.com/repository/pypi/simple/",
            "腾讯云": "https://mirrors.cloud.tencent.com/pypi/simple/",
            "豆瓣": "https://pypi.doubanio.com/simple/"
        }
        
        # 镜像选择
        mirror_group = QGroupBox("PyPI镜像源")
        mirror_layout = QFormLayout(mirror_group)
        
        self.mirror_combo = QComboBox()
        self.mirror_combo.addItems(list(self.mirrors.keys()))
        self.mirror_combo.currentIndexChanged.connect(self.on_mirror_changed)
        
        self.mirror_url = QLineEdit()
        self.mirror_url.setText(self.mirrors["默认 (PyPI)"])
        self.mirror_url.setReadOnly(False)
        
        mirror_layout.addRow("选择镜像:", self.mirror_combo)
        mirror_layout.addRow("镜像URL:", self.mirror_url)
        
        layout.addWidget(mirror_group)
        
        # 信任选项
        trust_group = QGroupBox("安全设置")
        trust_layout = QVBoxLayout(trust_group)
        
        self.trust_option = QButtonGroup(self)
        self.trust_radio = QRadioButton("信任镜像源 (推荐)")
        self.trust_radio.setChecked(True)
        self.no_trust_radio = QRadioButton("不信任镜像源")
        
        self.trust_option.addButton(self.trust_radio, 1)
        self.trust_option.addButton(self.no_trust_radio, 2)
        
        trust_layout.addWidget(self.trust_radio)
        trust_layout.addWidget(self.no_trust_radio)
        
        layout.addWidget(trust_group)
        
        # 按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        layout.addWidget(self.button_box)
    
    def on_mirror_changed(self, index):
        """镜像源选择改变时更新URL"""
        mirror_name = self.mirror_combo.currentText()
        self.mirror_url.setText(self.mirrors[mirror_name])
    
    def get_mirror_url(self):
        """获取当前选择的镜像URL"""
        return self.mirror_url.text()
    
    def is_trusted(self):
        """获取是否信任镜像源"""
        return self.trust_radio.isChecked()


class PytorchInstallDialog(QDialog):
    """PyTorch安装对话框"""
    
    def __init__(self, cuda_version=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("安装PyTorch")
        self.resize(600, 400)
        self.cuda_version = cuda_version
        
        layout = QVBoxLayout(self)
        
        # CUDA信息显示
        if cuda_version:
            cuda_label = QLabel(f"检测到CUDA版本: {cuda_version}")
            layout.addWidget(cuda_label)
        else:
            cuda_label = QLabel("未检测到CUDA，将安装CPU版本")
            layout.addWidget(cuda_label)
        
        # PyTorch版本选择
        version_group = QGroupBox("PyTorch版本")
        version_layout = QFormLayout(version_group)
        
        self.version_combo = QComboBox()
        self.version_combo.addItems(["2.0.0", "2.0.1", "2.1.0", "2.1.1", "2.1.2", "2.2.0", "2.2.1"])
        self.version_combo.setCurrentText("2.2.1")  # 默认最新版本
        
        version_layout.addRow("选择版本:", self.version_combo)
        layout.addWidget(version_group)
        
        # 镜像源配置
        mirror_group = QGroupBox("安装源")
        mirror_layout = QVBoxLayout(mirror_group)
        
        self.use_official_radio = QRadioButton("使用PyTorch官方源")
        self.use_mirror_radio = QRadioButton("使用国内镜像源 (推荐)")
        self.use_mirror_radio.setChecked(True)
        
        self.mirror_button_group = QButtonGroup(self)
        self.mirror_button_group.addButton(self.use_official_radio, 1)
        self.mirror_button_group.addButton(self.use_mirror_radio, 2)
        
        mirror_layout.addWidget(self.use_official_radio)
        mirror_layout.addWidget(self.use_mirror_radio)
        
        layout.addWidget(mirror_group)
        
        # 安装命令预览
        self.command_preview = QLabel("安装命令预览:")
        layout.addWidget(self.command_preview)
        
        self.command_text = QLineEdit()
        self.command_text.setReadOnly(True)
        layout.addWidget(self.command_text)
        
        # 更新安装命令
        self.update_command_preview()
        self.version_combo.currentIndexChanged.connect(self.update_command_preview)
        self.mirror_button_group.buttonClicked.connect(self.update_command_preview)
        
        # 进度条和日志
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.log_label = QLabel("准备安装...")
        layout.addWidget(self.log_label)
        
        # 按钮
        button_layout = QVBoxLayout()
        self.install_button = QPushButton("开始安装")
        self.install_button.clicked.connect(self.start_install)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.button_box.rejected.connect(self.reject)
        
        button_layout.addWidget(self.install_button)
        button_layout.addWidget(self.button_box)
        layout.addLayout(button_layout)
        
        # 安装线程
        self.install_thread = None
    
    def update_command_preview(self):
        """更新安装命令预览"""
        version = self.version_combo.currentText()
        
        if self.use_mirror_radio.isChecked():
            # 使用清华镜像
            if self.cuda_version:
                # CUDA版本，根据CUDA版本选择合适的PyTorch版本
                cuda_version_str = self.cuda_version.split('.')[0]
                cuda_version_minor = self.cuda_version.split('.')[1] if len(self.cuda_version.split('.')) > 1 else "0"
                
                if int(cuda_version_str) >= 11:
                    cuda_package = f"cu{cuda_version_str}{cuda_version_minor}"
                else:
                    cuda_package = f"cu{cuda_version_str}0"
                
                command = f"pip install torch=={version} torchvision torchaudio --index-url https://pypi.tuna.tsinghua.edu.cn/simple"
            else:
                # CPU版本
                command = f"pip install torch=={version} torchvision torchaudio --index-url https://pypi.tuna.tsinghua.edu.cn/simple"
        else:
            # 使用官方源
            if self.cuda_version:
                # CUDA版本
                cuda_version_str = self.cuda_version.split('.')[0]
                cuda_version_minor = self.cuda_version.split('.')[1] if len(self.cuda_version.split('.')) > 1 else "0"
                
                if int(cuda_version_str) >= 11:
                    cuda_package = f"cu{cuda_version_str}{cuda_version_minor}"
                else:
                    cuda_package = f"cu{cuda_version_str}0"
                
                command = f"pip install torch=={version} torchvision torchaudio"
            else:
                # CPU版本
                command = f"pip install torch=={version} torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu"
        
        self.command_text.setText(command)
    
    def start_install(self):
        """开始安装PyTorch"""
        command = self.command_text.text()
        command_args = command.split()
        
        # 禁用按钮并显示进度条
        self.install_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        # 创建并启动安装线程
        self.install_thread = InstallThread(command_args)
        self.install_thread.progress_signal.connect(self.update_progress)
        self.install_thread.finished_signal.connect(self.installation_finished)
        self.install_thread.start()
    
    def update_progress(self, message):
        """更新安装进度"""
        self.log_label.setText(message)
    
    def installation_finished(self, success, message):
        """安装完成回调"""
        self.progress_bar.setVisible(False)
        self.log_label.setText(message)
        
        if success:
            QMessageBox.information(self, "安装成功", "PyTorch已成功安装！")
        else:
            QMessageBox.warning(self, "安装失败", f"PyTorch安装失败: {message}")
        
        # 重新启用安装按钮
        self.install_button.setEnabled(True)


class EnvironmentChecker:
    """检查YOLOv8训练所需的环境"""
    
    def __init__(self):
        self.status = {
            'yolov8_installed': False,
            'cuda_available': False,
            'gpu_info': [],
            'python_version': platform.python_version(),
            'os_info': f"{platform.system()} {platform.release()}",
            'torch_version': "未安装",
            'cuda_version': "未安装"
        }
        
        # 尝试导入torch
        try:
            import torch
            self.status['torch_version'] = torch.__version__
        except ImportError:
            pass
    
    def check_all(self):
        """检查所有环境变量并返回状态"""
        self.check_yolov8()
        self.check_cuda()
        self.get_cuda_version()
        return self.status
    
    def check_yolov8(self):
        """检查是否安装了YOLOv8"""
        try:
            import ultralytics
            self.status['yolov8_installed'] = True
            self.status['yolov8_version'] = ultralytics.__version__
        except ImportError:
            self.status['yolov8_installed'] = False
    
    def check_cuda(self):
        """检查CUDA是否可用并获取GPU信息"""
        try:
            import torch
            if torch.cuda.is_available():
                self.status['cuda_available'] = True
                
                # 获取GPU信息
                gpu_count = torch.cuda.device_count()
                for i in range(gpu_count):
                    gpu_name = torch.cuda.get_device_name(i)
                    gpu_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)  # 转换为GB
                    self.status['gpu_info'].append({
                        'index': i,
                        'name': gpu_name,
                        'memory': f"{gpu_memory:.2f} GB"
                    })
            else:
                self.status['cuda_available'] = False
        except ImportError:
            self.status['cuda_available'] = False
    
    def get_cuda_version(self):
        """获取CUDA版本"""
        try:
            if self.status['cuda_available']:
                import torch
                cuda_version = torch.version.cuda
                self.status['cuda_version'] = cuda_version if cuda_version else "未知"
            else:
                # 尝试从系统中检测CUDA
                try:
                    nvcc_output = subprocess.check_output(['nvcc', '--version']).decode('utf-8')
                    for line in nvcc_output.split('\n'):
                        if 'release' in line:
                            # 通常格式为 "release x.y"
                            parts = line.split('release')
                            if len(parts) > 1:
                                version = parts[1].strip().split(' ')[0]
                                self.status['cuda_version'] = version
                                break
                except:
                    pass
        except:
            self.status['cuda_version'] = "无法检测"
    
    def install_yolov8(self, parent=None, use_mirror=True, mirror_url=None, trust=True):
        """安装YOLOv8，支持镜像源配置"""
        try:
            # 准备安装命令
            cmd = [sys.executable, "-m", "pip", "install", "ultralytics"]
            
            # 添加镜像源参数
            if use_mirror and mirror_url:
                cmd.extend(["-i", mirror_url])
                # 添加信任参数
                if trust:
                    cmd.append("--trusted-host")
                    # 提取主机名
                    from urllib.parse import urlparse
                    host = urlparse(mirror_url).netloc
                    cmd.append(host)
            
            if parent:
                # 使用图形界面显示安装进度
                dialog = QDialog(parent)
                dialog.setWindowTitle("安装YOLOv8")
                dialog.resize(500, 300)
                
                layout = QVBoxLayout(dialog)
                
                # 显示安装命令
                command_label = QLabel("执行安装命令:")
                layout.addWidget(command_label)
                
                command_text = QLineEdit()
                command_text.setText(" ".join(cmd))
                command_text.setReadOnly(True)
                layout.addWidget(command_text)
                
                # 进度条
                progress_bar = QProgressBar()
                progress_bar.setRange(0, 0)  # 不确定进度
                layout.addWidget(progress_bar)
                
                # 日志显示
                log_label = QLabel("正在安装...")
                layout.addWidget(log_label)
                
                # 按钮
                button_box = QDialogButtonBox(QDialogButtonBox.Cancel)
                button_box.rejected.connect(dialog.reject)
                layout.addWidget(button_box)
                
                # 创建安装线程
                install_thread = InstallThread(cmd)
                
                # 连接信号
                def update_progress(message):
                    log_label.setText(message)
                
                def installation_finished(success, message):
                    progress_bar.setVisible(False)
                    log_label.setText(message)
                    
                    if success:
                        QMessageBox.information(dialog, "安装成功", "YOLOv8已成功安装！")
                        dialog.accept()
                    else:
                        QMessageBox.warning(dialog, "安装失败", f"YOLOv8安装失败: {message}")
                        # 仍然允许关闭对话框
                        button_box.clear()
                        button_box.addButton(QDialogButtonBox.Close)
                        button_box.rejected.connect(dialog.reject)
                
                install_thread.progress_signal.connect(update_progress)
                install_thread.finished_signal.connect(installation_finished)
                
                # 显示对话框并启动线程
                install_thread.start()
                dialog.exec()
                
                # 安装后重新检查
                self.check_yolov8()
                return self.status['yolov8_installed']
            else:
                # 命令行模式安装
                result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                # 安装后重新检查
                self.check_yolov8()
                return self.status['yolov8_installed']
                
        except Exception as e:
            if parent:
                QMessageBox.critical(parent, "安装错误", f"安装YOLOv8时出错: {str(e)}")
            return False
    
    def install_pytorch(self, parent=None):
        """安装PyTorch，根据CUDA可用性选择版本"""
        try:
            dialog = PytorchInstallDialog(self.status.get('cuda_version'), parent)
            
            if dialog.exec() == QDialog.Accepted:
                return True
            return False
        except Exception as e:
            if parent:
                QMessageBox.critical(parent, "安装错误", f"安装PyTorch时出错: {str(e)}")
            return False
    
    def configure_mirror(self, parent=None):
        """配置镜像源对话框"""
        dialog = MirrorConfigDialog(parent)
        
        if dialog.exec() == QDialog.Accepted:
            return {
                'url': dialog.get_mirror_url(),
                'trusted': dialog.is_trusted()
            }
        
        return None


def get_python_executable():
    """获取当前Python解释器路径"""
    return sys.executable


def run_command(command, shell=False):
    """运行命令并返回输出"""
    try:
        result = subprocess.run(
            command, 
            shell=shell, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return e.stderr


def detect_nvidia_driver():
    """检测NVIDIA驱动版本"""
    try:
        if platform.system() == "Windows":
            # Windows: 使用nvidiasmi
            output = subprocess.check_output(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader']).decode('utf-8')
            return output.strip()
        elif platform.system() == "Linux":
            # Linux: 使用nvidia-smi
            output = subprocess.check_output(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader']).decode('utf-8')
            return output.strip()
        else:
            return "未知"
    except:
        return "未检测到驱动"


def detect_system_cuda():
    """检测系统CUDA安装情况"""
    try:
        if platform.system() == "Windows":
            # 检查环境变量
            cuda_path = os.environ.get('CUDA_PATH')
            if cuda_path and os.path.exists(cuda_path):
                # 尝试从路径中提取版本
                path_parts = cuda_path.split('\\')
                for part in path_parts:
                    if part.startswith('v'):
                        return part[1:]  # 去掉v前缀
            
            # 检查Program Files
            cuda_dirs = []
            try:
                for root_dir in ['C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA', 'C:\\Program Files\\NVIDIA\\CUDA']:
                    if os.path.exists(root_dir):
                        for dir_name in os.listdir(root_dir):
                            if dir_name.startswith('v'):
                                cuda_dirs.append((dir_name[1:], os.path.join(root_dir, dir_name)))
            except:
                pass
            
            if cuda_dirs:
                # 返回最新版本
                cuda_dirs.sort(key=lambda x: [int(v) for v in x[0].split('.')])
                return cuda_dirs[-1][0]
        
        elif platform.system() == "Linux":
            # 使用ldconfig检查
            try:
                output = subprocess.check_output(['ldconfig', '-p']).decode('utf-8')
                for line in output.split('\n'):
                    if 'libcudart.so.' in line:
                        # 提取版本号
                        import re
                        match = re.search(r'libcudart\.so\.(\d+\.\d+)', line)
                        if match:
                            return match.group(1)
            except:
                pass
            
            # 检查/usr/local目录
            try:
                cuda_dirs = []
                if os.path.exists('/usr/local'):
                    for dir_name in os.listdir('/usr/local'):
                        if dir_name.startswith('cuda-'):
                            cuda_dirs.append((dir_name[5:], os.path.join('/usr/local', dir_name)))
                
                if cuda_dirs:
                    # 返回最新版本
                    cuda_dirs.sort(key=lambda x: [int(v) for v in x[0].split('.')])
                    return cuda_dirs[-1][0]
            except:
                pass
                
        return "未检测到"
    except:
        return "检测失败"
