# -*- coding: utf-8 -*-
"""
Windows运行时钩子：修复PyInstaller onedir模式下的DLL搜索路径。

PyInstaller在Windows上打包为onedir时，会将Python DLL和依赖库放在_internal目录，
但某些情况下程序启动时无法正确找到这些DLL。此钩子在程序启动最早期添加DLL搜索路径。
"""
import os
import sys

if sys.platform == "win32":
    # 获取exe所在目录
    if getattr(sys, "frozen", False):
        bundle_dir = sys._MEIPASS
        exe_dir = os.path.dirname(sys.executable)

        # 将_internal目录添加到DLL搜索路径
        internal_dir = os.path.join(exe_dir, "_internal")
        if os.path.exists(internal_dir):
            # Python 3.8+ 使用os.add_dll_directory
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(internal_dir)
            # 同时添加到PATH环境变量（兼容旧版本）
            os.environ["PATH"] = internal_dir + os.pathsep + os.environ.get("PATH", "")
