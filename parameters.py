#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import yaml
from collections import OrderedDict


def load_default_parameters():
    """加载默认训练参数"""
    return {
        # 数据参数
        'data': {
            'data_path': '',  # 数据集路径
            'batch': 16,      # 批次大小
            'imgsz': 640,     # 图像大小
            'cache': False,   # 是否缓存图像到RAM
            'single_cls': False,  # 单类模式
            'rect': False,    # 矩形训练
            'fraction': 1.0,  # 数据集使用比例
        },
        
        # 模型参数
        'model': {
            'model': 'yolov8n.pt',  # 模型文件
            'task': 'detect',       # 任务类型 (detect, segment, classify, pose)
            'pretrained': True,     # 是否使用预训练权重
            'resume': False,        # 是否恢复训练
        },
        
        # 训练参数
        'training': {
            'epochs': 100,          # 训练轮数
            'patience': 50,         # 早停轮数
            'optimizer': 'SGD',     # 优化器
            'lr0': 0.01,            # 初始学习率
            'lrf': 0.01,            # 最终学习率系数
            'momentum': 0.937,      # SGD动量
            'weight_decay': 0.0005, # 权重衰减
            'warmup_epochs': 3.0,   # 预热轮数
            'warmup_momentum': 0.8, # 预热动量
            'warmup_bias_lr': 0.1,  # 预热偏置学习率
            'device': '',           # 训练设备
            'cos_lr': False,        # 余弦学习率
            'close_mosaic': 10,     # 最后N轮关闭马赛克增强
            'amp': True,            # 混合精度训练
        },
        
        # 超参数
        'hyp': {
            'hsv_h': 0.015,         # HSV-色调增强
            'hsv_s': 0.7,           # HSV-饱和度增强
            'hsv_v': 0.4,           # HSV-亮度增强
            'degrees': 0.0,         # 旋转角度 (±)
            'translate': 0.1,       # 平移 (±)
            'scale': 0.5,           # 缩放 (±)
            'fliplr': 0.5,          # 水平翻转概率
            'flipud': 0.0,          # 垂直翻转概率
            'mosaic': 1.0,          # 马赛克增强概率
            'mixup': 0.0,           # mixup增强概率
            'copy_paste': 0.0,      # 复制粘贴概率
        },
        
        # 增强参数
        'augment': {
            'albumentations': '',   # Albumentations设置
            'blur': 0.0,            # 模糊增强概率
            'perspective': 0.0,     # 透视变换概率
            'shear': 0.0,           # 剪切变换概率
        },
        
        # 保存参数
        'save': {
            'project': 'runs/train', # 保存目录
            'name': 'exp',           # 实验名称
            'exist_ok': False,       # 覆盖现有实验
            'save_period': -1,       # 权重保存间隔（-1为仅保存最终权重）
            'save_dir': '',          # 实际保存目录（自动生成）
        },
        
        # 可视化参数
        'visual': {
            'plots': True,          # 是否绘制训练图表
            'noval': False,         # 只训练，不验证
            'v5loader': False,      # 使用YOLOv5的数据加载器
        },
        
        # 高级参数
        'advanced': {
            'nbs': 64,              # 标准批量大小
            'overlap_mask': True,   # 掩码重叠（分割）
            'mask_ratio': 4,        # 掩码下采样率（分割）
            'dropout': 0.0,         # 使用Dropout正则化
            'val': True,            # 是否在训练中进行验证
            'seed': 0,              # 全局随机种子
            'workers': 8,           # 数据加载线程数
            'deterministic': True,  # 确定性训练
        }
    }


# 参数解释字典
parameter_descriptions = {
    # 数据参数
    'data_path': '数据集配置文件路径，YAML格式',
    'batch': '训练批次大小，根据显存调整',
    'imgsz': '输入图像大小，单位为像素',
    'cache': '是否将图像缓存到RAM中以加速训练',
    'single_cls': '将多类数据集视为单类数据集',
    'rect': '使用矩形训练而不是方形训练',
    'fraction': '数据集使用比例，1.0表示使用全部数据',
    
    # 模型参数
    'model': '模型文件路径或预训练模型名称',
    'task': '任务类型：检测(detect)、分割(segment)、分类(classify)或姿态估计(pose)',
    'pretrained': '是否使用预训练权重',
    'resume': '从上次中断处恢复训练',
    
    # 训练参数
    'epochs': '训练总轮数',
    'patience': '无改进时早停的轮数',
    'optimizer': '优化器选择(SGD, Adam, AdamW等)',
    'lr0': '初始学习率',
    'lrf': '最终学习率=初始学习率×最终学习率系数',
    'momentum': 'SGD动量因子',
    'weight_decay': '权重衰减系数，用于L2正则化',
    'warmup_epochs': '学习率预热的轮数',
    'warmup_momentum': '预热阶段的初始动量',
    'warmup_bias_lr': '预热阶段的偏置学习率',
    'device': '训练设备，空为自动选择',
    'cos_lr': '使用余弦学习率调度',
    'close_mosaic': '最后N轮关闭马赛克增强以提高稳定性',
    'amp': '使用自动混合精度训练以加速',
    
    # 超参数
    'hsv_h': 'HSV色调增强因子',
    'hsv_s': 'HSV饱和度增强因子',
    'hsv_v': 'HSV亮度增强因子',
    'degrees': '随机旋转角度范围(±度)',
    'translate': '随机平移范围(±图像比例)',
    'scale': '随机缩放范围(±图像比例)',
    'fliplr': '水平翻转的概率',
    'flipud': '垂直翻转的概率',
    'mosaic': '马赛克增强的概率',
    'mixup': 'Mixup增强的概率',
    'copy_paste': '分割掩码复制粘贴的概率',
    
    # 增强参数
    'albumentations': 'Albumentations数据增强库的设置',
    'blur': '随机模糊的概率',
    'perspective': '透视变换的概率',
    'shear': '剪切变换的概率',
    
    # 保存参数
    'project': '结果保存的项目文件夹',
    'name': '实验名称',
    'exist_ok': '是否允许覆盖现有实验文件夹',
    'save_period': '权重保存间隔，-1表示只保存最终轮次',
    'save_dir': '实际保存目录（自动生成）',
    
    # 可视化参数
    'plots': '是否保存训练过程的图表',
    'noval': '仅训练不验证',
    'v5loader': '使用YOLOv5的数据加载器',
    
    # 高级参数
    'nbs': '标称批次大小，用于权重缩放',
    'overlap_mask': '在分割任务中是否允许掩码重叠',
    'mask_ratio': '分割掩码的下采样率',
    'dropout': 'Dropout比率，用于减少过拟合',
    'val': '是否在训练过程中进行验证',
    'seed': '随机种子，用于可重复性',
    'workers': '数据加载线程数',
    'deterministic': '是否使用确定性算法以确保可重复性',
}


def parse_data_yaml(yaml_path):
    """解析数据集YAML文件"""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
        return data
    except Exception as e:
        print(f"解析YAML错误: {str(e)}")
        return None


def save_data_yaml(yaml_path, data):
    """保存修改后的数据集YAML文件"""
    try:
        with open(yaml_path, 'w', encoding='utf-8') as file:
            yaml.dump(data, file, allow_unicode=True, default_flow_style=False)
        return True
    except Exception as e:
        print(f"保存YAML错误: {str(e)}")
        return False


def get_command_line_args(params):
    """将GUI参数转换为命令行参数"""
    args = []
    
    # 数据参数
    args.append(f"data={params['data_path']}")
    args.append(f"batch={params['batch']}")
    args.append(f"imgsz={params['imgsz']}")
    
    if params['cache']:
        args.append("cache=True")
    
    if params['single_cls']:
        args.append("single_cls=True")
    
    if params['rect']:
        args.append("rect=True")
    
    if params['fraction'] < 1.0:
        args.append(f"fraction={params['fraction']}")
    
    # 模型参数
    args.append(f"model={params['model']}")
    args.append(f"task={params['task']}")
    
    if not params['pretrained']:
        args.append("pretrained=False")
    
    if params['resume']:
        args.append("resume=True")
    
    # 训练参数
    args.append(f"epochs={params['epochs']}")
    args.append(f"patience={params['patience']}")
    args.append(f"optimizer={params['optimizer']}")
    args.append(f"lr0={params['lr0']}")
    args.append(f"lrf={params['lrf']}")
    args.append(f"momentum={params['momentum']}")
    args.append(f"weight_decay={params['weight_decay']}")
    args.append(f"warmup_epochs={params['warmup_epochs']}")
    args.append(f"warmup_momentum={params['warmup_momentum']}")
    args.append(f"warmup_bias_lr={params['warmup_bias_lr']}")
    
    if params['device']:
        args.append(f"device={params['device']}")
    
    if params['cos_lr']:
        args.append("cos_lr=True")
    
    if params['close_mosaic'] > 0:
        args.append(f"close_mosaic={params['close_mosaic']}")
    
    if not params['amp']:
        args.append("amp=False")
    
    # 超参数
    for key, value in params.items():
        if key.startswith('hsv_') or key in ['degrees', 'translate', 'scale', 'fliplr', 'flipud', 'mosaic', 'mixup', 'copy_paste']:
            args.append(f"{key}={value}")
    
    # 保存参数
    args.append(f"project={params['project']}")
    args.append(f"name={params['name']}")
    
    if params['exist_ok']:
        args.append("exist_ok=True")
    
    if params['save_period'] > 0:
        args.append(f"save_period={params['save_period']}")
    
    # 可视化参数
    if not params['plots']:
        args.append("plots=False")
    
    if params['noval']:
        args.append("noval=True")
    
    if params['v5loader']:
        args.append("v5loader=True")
    
    # 高级参数
    args.append(f"nbs={params['nbs']}")
    
    if not params['overlap_mask']:
        args.append("overlap_mask=False")
    
    args.append(f"mask_ratio={params['mask_ratio']}")
    
    if params['dropout'] > 0:
        args.append(f"dropout={params['dropout']}")
    
    if not params['val']:
        args.append("val=False")
    
    if params['seed'] != 0:
        args.append(f"seed={params['seed']}")
    
    args.append(f"workers={params['workers']}")
    
    if not params['deterministic']:
        args.append("deterministic=False")
    
    return args
