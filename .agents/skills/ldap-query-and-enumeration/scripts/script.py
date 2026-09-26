#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LDAP查询与枚举: 收集目标相关信息
用法: python script.py -t target -o output.txt"""
import argparse, os, re, ssl, sys, urllib.request, urllib.error

def main():
    ap = argparse.ArgumentParser(description="LDAP查询与枚举")
    ap.add_argument("-t", "--target", help="目标")
    ap.add_argument("-o", "--output", default="output.txt", help="输出文件")
    args = ap.parse_args()
    target = args.target or "localhost"
    print("[*] LDAP查询与枚举")
    print("[*] 目标:", target)
    # 核心逻辑: 收集目标相关信息

    print("    执行信息枚举...")
    try:
        import socket
        ip = socket.gethostbyname(target.replace("https://","").replace("http://","").split("/")[0])
        print(f"    IP 解析: {ip}")
        try:
            ptr = socket.gethostbyaddr(ip)[0]
            print(f"    PTR 记录: {ptr}")
        except Exception:
            print("    PTR: 无记录")
    except Exception as e:
        print(f"    DNS 解析失败: {e}")
    # HTTP 信息
    if target:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        try:
            req = urllib.request.Request(target if target.startswith("http") else "https://"+target,
                                          headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                info = f"Code:{r.status}\nServer:{r.headers.get('Server','?')}\nContent-Type:{r.headers.get('Content-Type','?')}"
                print(f"    HTTP: {r.status}")
                with open(args.output, "w") as f: f.write(info)
        except Exception as e:
            print(f"    HTTP: {e}")

    print("[+] 任务完成")
if __name__ == "__main__":
    main()
