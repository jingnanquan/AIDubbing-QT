#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动性能测试脚本
用于监控AI配音软件的启动性能优化效果
"""

import time
import cProfile
import pstats
import io
import sys
import os

def test_startup_performance():
    """测试启动性能"""
    print("=" * 50)
    print("AI配音软件启动性能测试")
    print("=" * 50)
    
    # 记录开始时间
    start_time = time.time()
    
    # 测试Config导入性能
    print("\n1. 测试Config模块导入性能...")
    config_start = time.time()
    try:
        from Config import initialize_config
        config_import_time = time.time() - config_start
        print(f"   Config导入耗时: {config_import_time:.3f}秒")
        
        # 测试配置初始化性能
        config_init_start = time.time()
        initialize_config()
        config_init_time = time.time() - config_init_start
        print(f"   配置初始化耗时: {config_init_time:.3f}秒")
        
    except Exception as e:
        print(f"   Config导入失败: {e}")
        return
    
    # 测试主界面导入性能
    print("\n2. 测试主界面导入性能...")
    main_start = time.time()
    try:
        from AIMainPage import Window
        main_import_time = time.time() - main_start
        print(f"   主界面导入耗时: {main_import_time:.3f}秒")
    except Exception as e:
        print(f"   主界面导入失败: {e}")
        return
    
    # 测试重量级组件导入性能
    print("\n3. 测试重量级组件导入性能...")
    heavy_start = time.time()
    try:
        # 测试UVR模型导入
        from Service.uvrMain.separate import AudioPre
        uvr_import_time = time.time() - heavy_start
        print(f"   UVR模型导入耗时: {uvr_import_time:.3f}秒")
        
        # 测试ElevenLabs导入
        eleven_start = time.time()
        from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
        eleven_import_time = time.time() - eleven_start
        print(f"   ElevenLabs导入耗时: {eleven_import_time:.3f}秒")
        
    except Exception as e:
        print(f"   重量级组件导入失败: {e}")
    
    # 测试完整启动流程
    print("\n4. 测试完整启动流程...")
    full_start = time.time()
    try:
        # 模拟主程序启动
        from PyQt5.QtWidgets import QApplication
        app = QApplication([])
        
        # 创建主窗口（不显示）
        window = Window()
        full_startup_time = time.time() - full_start
        print(f"   完整启动耗时: {full_startup_time:.3f}秒")
        
        # 清理
        window.deleteLater()
        app.quit()
        
    except Exception as e:
        print(f"   完整启动测试失败: {e}")
    
    # 总耗时统计
    total_time = time.time() - start_time
    print("\n" + "=" * 50)
    print("性能测试结果汇总")
    print("=" * 50)
    print(f"总测试耗时: {total_time:.3f}秒")
    print(f"Config模块总耗时: {config_import_time + config_init_time:.3f}秒")
    print(f"主界面导入耗时: {main_import_time:.3f}秒")
    print(f"重量级组件导入耗时: {uvr_import_time + eleven_import_time:.3f}秒")
    
    # 性能建议
    print("\n性能优化建议:")
    if config_import_time + config_init_time > 0.5:
        print("  - Config模块导入较慢，建议进一步优化")
    if main_import_time > 1.0:
        print("  - 主界面导入较慢，建议延迟加载更多组件")
    if uvr_import_time + eleven_import_time > 2.0:
        print("  - 重量级组件导入较慢，建议实现更彻底的延迟加载")
    
    print("\n测试完成!")

def profile_startup():
    """使用cProfile分析启动性能"""
    print("\n使用cProfile分析启动性能...")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        # 执行启动测试
        test_startup_performance()
    except Exception as e:
        print(f"性能分析失败: {e}")
    finally:
        profiler.disable()
        
        # 输出性能统计
        s = io.StringIO()
        stats = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        stats.print_stats(20)  # 显示前20个最耗时的函数
        print("\n" + "=" * 50)
        print("cProfile性能分析结果")
        print("=" * 50)
        print(s.getvalue())

if __name__ == "__main__":
    print("启动性能测试脚本")
    print("选择测试模式:")
    print("1. 基础性能测试")
    print("2. 详细性能分析(cProfile)")
    
    try:
        choice = input("请输入选择 (1 或 2): ").strip()
        
        if choice == "2":
            profile_startup()
        else:
            test_startup_performance()
            
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试执行失败: {e}") 