#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BloodHound域分析: 分析输入数据提取特征
用法: python script.py -t target -o output.txt"""
import argparse, os, re, ssl, sys, urllib.request, urllib.error

def main():
    ap = argparse.ArgumentParser(description="BloodHound域分析")
    ap.add_argument("-t", "--target", help="目标")
    ap.add_argument("-o", "--output", default="output.txt", help="输出文件")
    args = ap.parse_args()
    target = args.target or "localhost"
    print("[*] BloodHound域分析")
    print("[*] 目标:", target)
    # 核心逻辑: 分析输入数据提取特征

    print("    执行数据分析...")
    result_lines = []
    if args.target and os.path.isfile(args.target):
        with open(args.target, encoding="utf-8", errors="ignore") as f:
            data = f.read()
        import collections
        urls = re.findall(r'https?://[^\s<>"]+', data)
        ips = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', data)
        hashes = re.findall(r'[a-f0-9]{32,64}', data)
        result_lines = [f"URLs: {len(urls)}", f"IPs: {len(ips)}", f"Hashes: {len(hashes)}"]
        print(f"    发现: URL {len(urls)}, IP {len(ips)}, Hash {len(hashes)}")
    else:
        result_lines = ["无输入文件, 请用 -t 指定文件路径"]
    with open(args.output, "w") as f:
        f.write("\n".join(result_lines))

    print("[+] 任务完成")
if __name__ == "__main__":
    main()
