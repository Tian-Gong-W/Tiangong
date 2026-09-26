#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shellcode加密与编码: 探测目标状态与特征
用法: python script.py -t target -o output.txt"""
import argparse, os, re, ssl, sys, urllib.request, urllib.error

def main():
    ap = argparse.ArgumentParser(description="Shellcode加密与编码")
    ap.add_argument("-t", "--target", help="目标")
    ap.add_argument("-o", "--output", default="output.txt", help="输出文件")
    args = ap.parse_args()
    target = args.target or "localhost"
    print("[*] Shellcode加密与编码")
    print("[*] 目标:", target)
    # 核心逻辑: 探测目标状态与特征

    print("    执行扫描探测...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(target if target.startswith("http") else "https://"+target,
                                      headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            body = r.read().decode("utf-8","ignore")[:500]
            with open(args.output, "w") as f:
                f.write(f"Status: {r.status}\nServer: {r.headers.get('Server','?')}\nLen: {len(body)}")
            print(f"    状态: {r.status} | Server: {r.headers.get('Server','?')} | {len(body)}B")
    except urllib.error.HTTPError as e:
        print(f"    HTTP {e.code}")
    except Exception as e:
        print(f"    连接失败: {e}")

    print("[+] 任务完成")
if __name__ == "__main__":
    main()
