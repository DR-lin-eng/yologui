#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import importlib.util
import platform
import torch
import shutil


class EnvironmentChecker:
    """检查YOLOv8训练所需的环境"""
    
    def __init__(self):
        self.status = {
            'yolov8_installed': False,
            'cuda_available': False,
            'gpu_info': [],
            'python_version': platform.python_version(),
            'os_info': f"{platform.system()} {platform.release()}",
            'torch_version': torch.__version__ if importlib.util.find_spec("torch") else "未安装",
            'cuda_version': "未安装"
        }
    
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
    
    def get_cuda_version(self):
        """获取CUDA版本"""
        if self.status['cuda_available']:
            try:
                cuda_version = torch.version.cuda
                self.status['cuda_version'] = cuda_version if cuda_version else "未知"
            except:
                self.status['cuda_version'] = "无法检测"
    
    def install_yolov8(self):
        """安装YOLOv8"""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "ultralytics"])
            # 安装后重新检查
            self.check_yolov8()
            return True
        except subprocess.CalledProcessError:
            return False


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
