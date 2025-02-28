#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import threading
import signal
import re
import shutil
from datetime import datetime, timedelta
import subprocess
from PySide6.QtCore import QObject, Signal, QThread, QMutex, QWaitCondition

from parameters import get_command_line_args


class TrainingThread(QThread):
    """用于执行YOLOv8训练的线程"""
    
    def __init__(self, command, env=None):
        super().__init__()
        self.command = command
        self.env = env if env else os.environ.copy()
        # 设置UTF-8编码环境变量以解决中文路径问题
        self.env["PYTHONIOENCODING"] = "utf-8"
        self.process = None
        self.stopped = False
        self.mutex = QMutex()
        self.condition = QWaitCondition()
    
    def run(self):
        """运行训练进程"""
        # 启动进程并重定向输出
        try:
            # 确保使用UTF-8编码处理所有输出
            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=self.env,
                encoding='utf-8',  # 明确指定UTF-8编码
                errors='replace'   # 对于无法解码的字符，使用替代方式而不是报错
            )
            
            # 读取进程输出
            while self.process.poll() is None and not self.stopped:
                try:
                    line = self.process.stdout.readline()
                    if line:
                        # 发送进度更新
                        self.progress_line.emit(line.strip())
                except UnicodeDecodeError as e:
                    # 捕获并报告解码错误，但不中断训练
                    print(f"解码错误: {str(e)}")
                    self.progress_line.emit(f"[警告] 输出解码错误: {str(e)}")
            
            # 如果进程仍在运行但线程被要求停止
            if self.process.poll() is None and self.stopped:
                # 尝试正常终止
                self.process.terminate()
                # 给进程一些时间来清理
                time.sleep(2)
                # 如果进程仍在运行，强制终止
                if self.process.poll() is None:
                    self.process.kill()
            
            # 检查进程返回值
            exit_code = self.process.wait()
            if exit_code == 0 and not self.stopped:
                self.finished.emit(True)
            else:
                self.finished.emit(False)
                
        except Exception as e:
            self.error.emit(str(e))
    
    def stop(self):
        """停止训练线程"""
        self.stopped = True
        self.mutex.lock()
        self.condition.wakeAll()
        self.mutex.unlock()
    
    # 定义信号
    progress_line = Signal(str)
    finished = Signal(bool)
    error = Signal(str)


class TrainingManager(QObject):
    """管理YOLOv8训练过程"""
    
    def __init__(self):
        super().__init__()
        self.training_thread = None
        self.start_time = None
        self.current_epoch = 0
        self.total_epochs = 0
        self.current_metrics = {}
        self.training_dir = ""
    
    def start_training(self, params):
        """启动训练进程"""
        # 如果已经有一个训练线程在运行，先停止它
        if self.training_thread and self.training_thread.isRunning():
            self.stop_training()
        
        # 重置状态
        self.start_time = datetime.now()
        self.current_epoch = 0
        self.total_epochs = int(params.get('epochs', 100))
        self.current_metrics = {}
        
        # 构建命令 - 使用yolo命令行格式
        # 首先查找是否有yolo命令可用
        yolo_cmd = "yolo"
        
        # 如果没有yolo命令可用，则回退到python模块调用
        if shutil.which(yolo_cmd) is None:
            cmd = [sys.executable, "-m", "ultralytics"]
        else:
            cmd = [yolo_cmd]
        
        # 确定任务类型
        task = params.get('task', 'detect')
        is_classification = params.get('is_classification', False) or task == 'classify'
        if is_classification:
            task = 'classify'
        
        # 添加任务类型和train命令
        cmd.append(task)
        cmd.append('train')
        
        # 处理数据路径 - 确保使用正斜杠以避免Windows路径转义问题
        data_arg_added = False  # 跟踪是否已经添加了data参数
        
        if is_classification and params.get('direct_folder_mode', False):
            # 分类任务直接使用文件夹 - 确保直接指向目录而不是YAML文件
            folder_path = params['train_folder'].replace('\\', '/')
            # 移除末尾的斜杠（如果有）
            folder_path = folder_path.rstrip('/')
            
            # 检查目录结构
            train_dir_exists = os.path.isdir(os.path.join(folder_path, 'train'))
            val_dir_exists = os.path.isdir(os.path.join(folder_path, 'val'))
            
            # 如果文件夹结构正确 (有train和val子目录)
            if train_dir_exists and val_dir_exists:
                # 直接使用该目录
                cmd.append(f"data={folder_path}")
                data_arg_added = True
            else:
                # 检查目录中是否有类别子目录
                has_class_dirs = False
                class_dirs = []
                
                for item in os.listdir(folder_path):
                    item_path = os.path.join(folder_path, item)
                    if os.path.isdir(item_path) and not item.startswith('.'):
                        has_class_dirs = True
                        class_dirs.append(item)
                
                # 如果有类别子目录，则可以使用split参数
                if has_class_dirs:
                    cmd.append(f"data={folder_path}")
                    cmd.append("split=0.9")  # 90%训练、10%验证
                    data_arg_added = True
                    print(f"检测到分类数据文件夹，将使用自动分割: {folder_path}")
                    print(f"发现类别: {', '.join(class_dirs)}")
                else:
                    self.error.emit(f"无效的分类数据目录: {folder_path}\n需要train/val子目录或类别子目录")
                    return
        
        # 如果尚未添加data参数，处理常规模式
        if not data_arg_added:
            if 'data_path' in params:
                # 确保对于分类任务，我们传递的是目录而不是YAML文件
                data_path = params['data_path'].replace('\\', '/')
                
                # 检查如果是分类任务，且路径以.yaml结尾
                if is_classification and data_path.lower().endswith('.yaml'):
                    # 尝试读取YAML文件以获取正确的数据路径
                    try:
                        import yaml
                        with open(data_path, 'r', encoding='utf-8') as f:
                            yaml_data = yaml.safe_load(f)
                        
                        # 如果YAML包含路径信息，使用它
                        if 'path' in yaml_data:
                            actual_path = yaml_data['path']
                            # 如果是相对路径，相对于YAML所在目录
                            if not os.path.isabs(actual_path):
                                yaml_dir = os.path.dirname(data_path)
                                actual_path = os.path.join(yaml_dir, actual_path)
                            cmd.append(f"data={actual_path.replace('\\', '/')}")
                        else:
                            # 使用YAML文件所在的目录
                            cmd.append(f"data={os.path.dirname(data_path).replace('\\', '/')}")
                    except Exception as e:
                        print(f"处理YAML文件时出错: {e}")
                        # 回退到使用原始路径
                        cmd.append(f"data={data_path}")
                else:
                    # 非分类任务或非YAML文件，直接使用
                    cmd.append(f"data={data_path}")
            elif is_classification and 'train_folder' in params:
                # 如果没有data_path但有train_folder，使用训练文件夹
                folder_path = params['train_folder'].replace('\\', '/')
                cmd.append(f"data={folder_path}")
        
        # 添加模型参数
        if 'model' in params:
            model_param = params['model']
            if task == 'classify' and 'cls' not in model_param:
                # 确保分类任务使用分类模型
                model_name = model_param.split('.')[0]
                if not model_name.endswith('-cls'):
                    model_name += '-cls'
                cmd.append(f"model={model_name}.pt")
            else:
                cmd.append(f"model={model_param}")
        
        # 添加图像大小参数 - 对于分类任务非常重要
        if is_classification:
            imgsz = params.get('imgsz', 224)  # 分类默认使用224
            cmd.append(f"imgsz={imgsz}")
        
        # 添加其他参数 - 只添加非默认参数
        default_params = {
            'batch': 16,
            'imgsz': 640,  # 检测默认640，分类默认224
            'epochs': 100,
            'patience': 50,
            'lr0': 0.01,
            'lrf': 0.01
        }
        
        # 设置工作目录为项目目录，避免路径问题
        if 'project' in params:
            project_path = params['project'].replace('\\', '/')
            cmd.append(f"project={project_path}")
        
        for key, value in params.items():
            if key not in ['data_path', 'train_folder', 'is_classification', 'direct_folder_mode', 'model', 'task', 'project', 'imgsz']:
                # 只添加非默认值或明确需要的值
                if key not in default_params or value != default_params.get(key):
                    # 如果是路径类型的参数，确保使用正斜杠
                    if key.endswith('_path') or key in ['save_dir']:
                        if isinstance(value, str):
                            value = value.replace('\\', '/')
                    cmd.append(f"{key}={value}")
        
        print(f"执行命令: {' '.join(cmd)}")
        
        # 设置环境变量
        env_vars = os.environ.copy()
        # 添加PYTHONIOENCODING环境变量以确保正确处理UTF-8
        env_vars["PYTHONIOENCODING"] = "utf-8"
        if 'device' in params and params['device']:
            env_vars['CUDA_VISIBLE_DEVICES'] = params['device'].replace('cuda:', '')
        
        # 创建并启动训练线程
        self.training_thread = TrainingThread(cmd, env_vars)
        self.training_thread.progress_line.connect(self.process_progress_line)
        self.training_thread.finished.connect(self.training_finished)
        self.training_thread.error.connect(self.training_error)
        self.training_thread.start()
    
    def stop_training(self):
        """停止训练进程"""
        if self.training_thread and self.training_thread.isRunning():
            self.training_thread.stop()
            self.training_thread.wait()  # 等待线程结束
    
    def process_progress_line(self, line):
        """处理训练进程的输出行"""
        # 尝试解析YOLOv8的输出
        try:
            # 捕获训练目录
            if "Results saved to" in line:
                try:
                    self.training_dir = re.search(r"Results saved to\s+([^\s]+)", line).group(1)
                except:
                    # 如果无法解析路径，使用一个安全的默认值
                    self.training_dir = "runs/train/exp"
                    print(f"无法解析训练目录，使用默认值: {self.training_dir}")
            
            # 捕获训练进度
            if "Epoch" in line and "/" in line:
                # 提取当前轮次和总轮次
                try:
                    epoch_match = re.search(r"Epoch\s+(\d+)/(\d+)", line)
                    if epoch_match:
                        self.current_epoch = int(epoch_match.group(1))
                        self.total_epochs = int(epoch_match.group(2))
                except:
                    print("无法解析轮次信息")
                
                # 提取指标
                metrics = {}
                try:
                    metrics_matches = re.findall(r"(\w+)=([\d\.]+)", line)
                    for key, value in metrics_matches:
                        try:
                            metrics[key] = float(value)
                        except ValueError:
                            metrics[key] = value
                    
                    self.current_metrics = metrics
                except:
                    print("无法解析训练指标")
                
                # 计算估计剩余时间
                elapsed_time = (datetime.now() - self.start_time).total_seconds()
                if self.current_epoch > 0:
                    time_per_epoch = elapsed_time / self.current_epoch
                    remaining_epochs = self.total_epochs - self.current_epoch
                    eta_seconds = time_per_epoch * remaining_epochs
                    eta = str(timedelta(seconds=int(eta_seconds)))
                else:
                    eta = "计算中..."
                
                # 发送进度更新
                progress_info = {
                    'current_epoch': self.current_epoch,
                    'total_epochs': self.total_epochs,
                    'metrics': self.current_metrics,
                    'elapsed_time': str(timedelta(seconds=int(elapsed_time))),
                    'eta': eta,
                    'progress': self.current_epoch / self.total_epochs * 100,
                    'output_line': line
                }
                
                self.progress_update.emit(progress_info)
            else:
                # 其他输出行
                progress_info = {
                    'current_epoch': self.current_epoch,
                    'total_epochs': self.total_epochs,
                    'metrics': self.current_metrics,
                    'output_line': line
                }
                self.progress_update.emit(progress_info)
                
        except Exception as e:
            print(f"处理输出行时出错: {str(e)}")
            # 即使解析出错，仍然发送原始行
            self.progress_update.emit({'output_line': line})
    
    def training_finished(self, success):
        """训练完成的回调"""
        self.training_thread = None
        self.training_finished.emit(success)
    
    def training_error(self, error_message):
        """训练错误的回调"""
        self.training_thread = None
        self.training_error.emit(error_message)
    
    # 定义信号
    progress_update = Signal(dict)
    training_finished = Signal(bool)
    training_error = Signal(str)
