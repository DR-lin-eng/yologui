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
        self.process = None
        self.stopped = False
        self.mutex = QMutex()
        self.condition = QWaitCondition()
    
    def run(self):
        """运行训练进程"""
        # 启动进程并重定向输出
        try:
            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=self.env
            )
            
            # 读取进程输出
            while self.process.poll() is None and not self.stopped:
                line = self.process.stdout.readline()
                if line:
                    # 发送进度更新
                    self.progress_line.emit(line.strip())
            
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
        if params.get('is_classification', False):
            task = 'classify'
        
        # 添加任务类型和train命令
        cmd.append(task)
        cmd.append('train')
        
        # 处理数据路径
        if task == 'classify' and params.get('direct_folder_mode', False):
            # 分类任务直接使用文件夹
            cmd.append(f"data={params['train_folder']}")
        else:
            # 其他任务使用data.yaml
            cmd.append(f"data={params['data_path']}")
        
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
        
        # 添加其他参数 - 只添加非默认参数
        default_params = {
            'batch': 16,
            'imgsz': 640,
            'epochs': 100,
            'patience': 50,
            'lr0': 0.01,
            'lrf': 0.01
        }
        
        for key, value in params.items():
            if key not in ['data_path', 'train_folder', 'is_classification', 'direct_folder_mode', 'model', 'task']:
                # 只添加非默认值或明确需要的值
                if key not in default_params or value != default_params.get(key):
                    cmd.append(f"{key}={value}")
        
        print(f"执行命令: {' '.join(cmd)}")
        
        # 设置环境变量
        env = os.environ.copy()
        if 'device' in params and params['device']:
            env['CUDA_VISIBLE_DEVICES'] = params['device'].replace('cuda:', '')
        
        # 创建并启动训练线程
        self.training_thread = TrainingThread(cmd, env)
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
                self.training_dir = re.search(r"Results saved to\s+([^\s]+)", line).group(1)
            
            # 捕获训练进度
            if "Epoch" in line and "/" in line:
                # 提取当前轮次和总轮次
                epoch_match = re.search(r"Epoch\s+(\d+)/(\d+)", line)
                if epoch_match:
                    self.current_epoch = int(epoch_match.group(1))
                    self.total_epochs = int(epoch_match.group(2))
                
                # 提取指标
                metrics = {}
                metrics_matches = re.findall(r"(\w+)=([\d\.]+)", line)
                for key, value in metrics_matches:
                    try:
                        metrics[key] = float(value)
                    except ValueError:
                        metrics[key] = value
                
                self.current_metrics = metrics
                
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
