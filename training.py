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
from PySide6.QtWidgets import QApplication

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
            
            # 创建一个线程来持续读取输出，避免缓冲区填满导致阻塞
            def read_output():
                for line in iter(self.process.stdout.readline, ''):
                    if self.stopped:
                        break
                    if line:
                        self.progress_line.emit(line.strip())
                        # 让UI有机会更新
                        QApplication.processEvents()
            
            # 启动读取线程
            read_thread = threading.Thread(target=read_output)
            read_thread.daemon = True
            read_thread.start()
            
            # 等待进程完成
            exit_code = self.process.wait()
            # 等待读取线程结束
            read_thread.join(timeout=2)
            
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
        if self.process and self.process.poll() is None:
            try:
                # 尝试先正常终止
                self.process.terminate()
                time.sleep(1)
                # 如果进程仍在运行，强制终止
                if self.process.poll() is None:
                    self.process.kill()
            except:
                pass
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
        
        # 确保params包含data_path键，以保持与main.py的兼容性
        if 'data_path' not in params and 'train_folder' in params:
            params['data_path'] = params['train_folder']
        
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
                            
                            # 修复 f-string 问题 - 不在表达式内使用反斜杠替换
                            replaced_path = actual_path.replace('\\', '/')
                            cmd.append(f"data={replaced_path}")
                        else:
                            # 使用YAML文件所在的目录
                            # 修复 f-string 问题
                            dirname_path = os.path.dirname(data_path).replace('\\', '/')
                            cmd.append(f"data={dirname_path}")
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
            'lrf': 0.01,
            'momentum': 0.937,
            'weight_decay': 0.0005,
            'warmup_epochs': 3.0,
            'warmup_momentum': 0.8,
            'warmup_bias_lr': 0.1,
            'box': 7.5,
            'cls': 0.5,
            'dfl': 1.5,
            'fl_gamma': 0.0,
            'hsv_h': 0.015,
            'hsv_s': 0.7,
            'hsv_v': 0.4,
            'degrees': 0.0,
            'translate': 0.1,
            'scale': 0.5,
            'shear': 0.0,
            'perspective': 0.0,
            'flipud': 0.0,
            'fliplr': 0.5,
            'mosaic': 1.0,
            'mixup': 0.0,
            'copy_paste': 0.0
        }
        
        # 设置工作目录为项目目录，避免路径问题
        if 'project' in params:
            # 修复 f-string 问题
            project_path = params['project'].replace('\\', '/')
            cmd.append(f"project={project_path}")
        
        for key, value in params.items():
            if key not in ['data_path', 'train_folder', 'is_classification', 'direct_folder_mode', 'model', 'task', 'project', 'imgsz']:
                # 只添加非默认值或明确需要的值
                if key not in default_params or value != default_params.get(key):
                    # 如果是路径类型的参数，确保使用正斜杠
                    if key.endswith('_path') or key in ['save_dir']:
                        if isinstance(value, str):
                            # 修复 f-string 问题
                            replaced_value = value.replace('\\', '/')
                            cmd.append(f"{key}={replaced_value}")
                    else:
                        cmd.append(f"{key}={value}")
        
        print(f"执行命令: {' '.join(cmd)}")
        
        # 设置环境变量
        env_vars = os.environ.copy()
        # 添加PYTHONIOENCODING环境变量以确保正确处理UTF-8
        env_vars["PYTHONIOENCODING"] = "utf-8"
        
        # 处理device参数 - 确保有效值，避免空值引起错误
        if 'device' in params:
            device_value = params['device']
            # 如果device为空字符串，默认使用所有可用设备(不设置CUDA_VISIBLE_DEVICES)
            if device_value and device_value != 'cpu':
                # 提取设备ID，去掉'cuda:'前缀
                device_id = device_value.replace('cuda:', '')
                if device_id and device_id.strip():
                    env_vars['CUDA_VISIBLE_DEVICES'] = device_id
        
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
            self.training_thread.wait(5000)  # 等待最多5秒让线程结束
            # 如果线程仍然在运行，我们不再等待
            if self.training_thread.isRunning():
                print("警告: 训练线程没有及时结束")
    
    def process_progress_line(self, line):
        """处理训练进程的输出行"""
        # 尝试解析YOLOv8的输出
        try:
            # 创建基本的进度信息结构
            progress_info = {
                'current_epoch': self.current_epoch,
                'total_epochs': self.total_epochs,
                'metrics': self.current_metrics.copy() if hasattr(self, 'current_metrics') else {},
                'output_line': line
            }
            
            # 捕获训练目录
            if "Results saved to" in line:
                try:
                    self.training_dir = re.search(r"Results saved to\s+([^\s]+)", line).group(1)
                except:
                    # 如果无法解析路径，使用一个安全的默认值
                    self.training_dir = "runs/train/exp"
                    print(f"无法解析训练目录，使用默认值: {self.training_dir}")
            
            # 匹配YOLOv8标准输出格式 - 例如： 1/100      1.49G      3.755         16        640:  90%|████████▉ | 2699/3000 [03:42<00:26, 11.17it/s]
            epoch_pattern = r"^(\d+)/(\d+)\s+[\d\.]+G\s+([0-9\.]+)\s+\d+\s+\d+:\s+(\d+)%\|[^|]*\|\s*(\d+)/(\d+)"
            epoch_match = re.search(epoch_pattern, line)
            
            if epoch_match:
                # 获取当前轮次和总轮次
                current_epoch = int(epoch_match.group(1))
                total_epochs = int(epoch_match.group(2))
                self.current_epoch = current_epoch
                self.total_epochs = total_epochs
                
                # 获取损失值
                loss = float(epoch_match.group(3))
                
                # 获取进度百分比
                percent = int(epoch_match.group(4))
                
                # 获取当前批次和总批次
                current_batch = int(epoch_match.group(5))
                total_batch = int(epoch_match.group(6))
                
                # 计算更精确的进度
                if current_epoch > 0 and total_epochs > 0:
                    # 计算轮次进度和批次进度的组合
                    epoch_progress = (current_epoch - 1) / total_epochs
                    batch_progress = (current_batch / total_batch) / total_epochs
                    total_progress = (epoch_progress + batch_progress) * 100
                    progress_info['progress'] = total_progress
                
                # 提取时间信息 [03:42<00:26, 11.17it/s]
                time_pattern = r"\[(\d+):(\d+)<(\d+):(\d+)"
                time_match = re.search(time_pattern, line)
                if time_match:
                    elapsed_min = int(time_match.group(1))
                    elapsed_sec = int(time_match.group(2))
                    remain_min = int(time_match.group(3))
                    remain_sec = int(time_match.group(4))
                    
                    elapsed_time = str(timedelta(minutes=elapsed_min, seconds=elapsed_sec))
                    eta = str(timedelta(minutes=remain_min, seconds=remain_sec))
                    
                    progress_info['elapsed_time'] = elapsed_time
                    progress_info['eta'] = eta
                
                # 更新当前指标
                self.current_metrics['loss'] = loss
                progress_info['metrics'] = self.current_metrics.copy()
            
            # 匹配验证指标行 - 例如： classes   top1_acc   top5_acc:   0%|          | 0/300 [00:00<?, ?it/s]
            val_pattern = r"classes\s+top1_acc\s+top5_acc"
            if re.search(val_pattern, line):
                # 这是验证进度行，但还没有指标值
                pass
            
            # 捕获最终指标 - 例如: all      0.911      0.983
            final_metrics_pattern = r"all\s+(\d+\.\d+)\s+(\d+\.\d+)"
            metrics_match = re.search(final_metrics_pattern, line)
            if metrics_match:
                top1_acc = float(metrics_match.group(1))
                top5_acc = float(metrics_match.group(2))
                
                # 更新指标
                self.current_metrics['top1_acc'] = top1_acc
                self.current_metrics['top5_acc'] = top5_acc
                
                # 分类任务中，为了兼容性，同时也设置 mAP 指标（虽然技术上不准确，但UI需要）
                self.current_metrics['mAP50-95'] = top1_acc  # 使用top1_acc作为主要指标
                self.current_metrics['precision'] = top1_acc  # 为了UI显示
                self.current_metrics['recall'] = top5_acc  # 为了UI显示
                
                progress_info['metrics'] = self.current_metrics.copy()
            
            # 对于检测/分割任务，捕获mAP值
            map_pattern = r"mAP50-95\s+([0-9\.]+).+mAP50\s+([0-9\.]+)"
            map_match = re.search(map_pattern, line)
            if map_match:
                map50_95 = float(map_match.group(1))
                map50 = float(map_match.group(2))
                
                self.current_metrics['mAP50-95'] = map50_95
                self.current_metrics['mAP50'] = map50
                progress_info['metrics'] = self.current_metrics.copy()
            
            # 捕获precision和recall
            pr_pattern = r"precision\s+([0-9\.]+).+recall\s+([0-9\.]+)"
            pr_match = re.search(pr_pattern, line)
            if pr_match:
                precision = float(pr_match.group(1))
                recall = float(pr_match.group(2))
                
                self.current_metrics['precision'] = precision
                self.current_metrics['recall'] = recall
                progress_info['metrics'] = self.current_metrics.copy()
            
            # 发送进度更新
            self.progress_update.emit(progress_info)
                
        except Exception as e:
            print(f"处理输出行时出错: {str(e)}\n行内容: {line}")
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
