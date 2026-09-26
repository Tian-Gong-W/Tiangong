#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""".NET-Java逆向: 从数据中抽取有效信息
用法: python script.py -t target -o output.txt"""
import argparse, os, re, ssl, sys, urllib.request, urllib.error

def main():
    ap = argparse.ArgumentParser(description=".NET-Java逆向")
    ap.add_argument("-t", "--target", help="目标")
    ap.add_argument("-o", "--output", default="output.txt", help="输出文件")
    args = ap.parse_args()
    target = args.target or "localhost"
    print("[*] .NET-Java逆向")
    print("[*] 目标:", target)
    # 核心逻辑: 从数据中抽取有效信息

    print("    执行数据提取...")
    result = []
    if args.target and os.path.isfile(args.target):
        with open(args.target, encoding="utf-8", errors="ignore") as f:
            data = f.read()
        tokens = re.findall(r'[A-Za-z0-9_-]{20,100}', data)
        result = tokens[:50]
        print(f"    提取 {len(result)} 个 token")
    with open(args.output, "w") as f:
        f.write("\n".join(result))

    print("[+] 任务完成")
if __name__ == "__main__":
    main()
