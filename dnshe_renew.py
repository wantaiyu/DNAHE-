#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DNSHE 免费域名 自动续期脚本
================================
定期检查所有子域名的到期时间; 对进入"免费续期窗口"的域名自动执行续期。

API 依据官方文档:
  https://my.dnshe.com/knowledgebase/13/DNSHE-Free-Domain-API-User-Guide-V2.0.html

  Endpoint : https://api005.dnshe.com/index.php?m=domain_hub
  认证     : Header  X-API-Key / X-API-Secret
  限速     : 30 次/分钟

用法:
  # 1) 检查所有域名到期情况 (不执行续期)
  python dnshe_renew.py --check

  # 2) 仅列出将到期的域名
  python dnshe_renew.py --list-expiring --days 180

  # 3) 到期前 N 天内自动续期 (窗口开了就续, 没开则跳过)
  python dnshe_renew.py --auto-renew --days 180

  # 注: DNSHE 免费域名在到期前 180 天即可续期(免费窗口),
  #     默认阈值已设为 180 天; GitHub Actions 每月 1 号自动运行一次,
  #     永久有效域名(never_expires=1)会被识别并自动跳过。

环境变量 (GitHub Actions 里通过 Secrets 注入):
  DNSHE_API_KEY / DNSHE_API_SECRET
  可选通知: SERVERCHAN_KEY / PUSHPLUS_TOKEN / TG_BOT_TOKEN / TG_CHAT_ID
"""
import os
import sys
import json
import argparse
import datetime
import urllib.request
import urllib.parse
import urllib.error

API_BASE = "https://api005.dnshe.com/index.php?m=domain_hub"

# ---------- 通知 (可选: 留空则不通知) ----------
# Server酱: https://sct.ftqq.com/<SENDKEY>.send
SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "")
# PushPlus: https://www.pushplus.plus/send?token=<TOKEN>
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")
# Telegram Bot
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")


def get_auth():
    key = os.environ.get("DNSHE_API_KEY", "")
    secret = os.environ.get("DNSHE_API_SECRET", "")
    if not key or not secret:
        print("[错误] 请设置环境变量 DNSHE_API_KEY 和 DNSHE_API_SECRET",
              file=sys.stderr)
        sys.exit(2)
    return key, secret


def api_request(endpoint, action, method="GET", params=None, body=None):
    """调用 DNSHE API, 返回解析后的 JSON dict"""
    key, secret = get_auth()
    url = API_BASE + "&endpoint=" + endpoint + "&action=" + action
    if params:
        url += "&" + urllib.parse.urlencode(params)

    headers = {
        "X-API-Key": key,
        "X-API-Secret": secret,
        "User-Agent": "dnshe-renew-bot/1.0",
    }
    data = None
    if method == "POST":
        headers["Content-Type"] = "application/json"
        data = json.dumps(body or {}).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"success": False, "error": f"HTTP {e.code}", "raw": str(e)}


def list_subdomains():
    """拉取全部子域名 (自动翻页)"""
    all_items = []
    page = 1
    while True:
        resp = api_request(
            "subdomains", "list",
            params={
                "page": page,
                "per_page": 500,
                "sort_by": "expires_at",
                "sort_dir": "asc",
                "include_total": 1,
            },
        )
        if not resp.get("success"):
            print(f"[警告] 拉取失败: {resp}")
            break
        # 兼容不同返回结构
        items = resp.get("data") or resp.get("subdomains") or resp.get("list") or []
        all_items.extend(items)
        total = resp.get("total", 0)
        if not items or page * 500 >= total:
            break
        page += 1
    return all_items


def parse_expiry(item):
    """从记录中解析到期时间, 返回 datetime 或 None"""
    # 永久有效域名 (never_expires=1) 没有到期时间, 无需续期
    if item.get("never_expires") in (1, "1", True, "true", "yes"):
        return "never"
    for field in ("expires_at", "expiry_date", "expires"):
        v = item.get(field)
        if v:
            try:
                return datetime.datetime.strptime(str(v)[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    return datetime.datetime.fromisoformat(str(v).replace("Z", ""))
                except ValueError:
                    continue
    return None


def renew_subdomain(subdomain_id):
    """执行续期, 返回 (ok, message)"""
    resp = api_request("subdomains", "renew", method="POST",
                       body={"subdomain_id": int(subdomain_id)})
    if resp.get("success"):
        return True, resp.get("message", "renewed")
    # 错误码: renewal_not_yet_available 表示免费窗口未开
    err = resp.get("error") or resp.get("message") or json.dumps(resp, ensure_ascii=False)
    err_code = resp.get("error_code", "")
    return False, f"{err} ({err_code})"


def days_left(expiry_dt):
    now = datetime.datetime.now()
    return (expiry_dt - now).days


def send_notification(title, content):
    """可选通知: Server酱 / PushPlus / Telegram"""
    msgs = []
    if SERVERCHAN_KEY:
        try:
            url = f"https://sct.ftqq.com/{SERVERCHAN_KEY}.send"
            urllib.request.urlopen(
                urllib.request.Request(
                    url,
                    data=urllib.parse.urlencode(
                        {"title": title, "desp": content}).encode(),
                ), timeout=15)
            msgs.append("Server酱✓")
        except Exception as e:
            msgs.append(f"Server酱✗{e}")
    if PUSHPLUS_TOKEN:
        try:
            url = "https://www.pushplus.plus/send"
            urllib.request.urlopen(
                urllib.request.Request(
                    url,
                    data=json.dumps(
                        {"token": PUSHPLUS_TOKEN, "title": title,
                         "content": content}).encode(),
                    headers={"Content-Type": "application/json"},
                ), timeout=15)
            msgs.append("PushPlus✓")
        except Exception as e:
            msgs.append(f"PushPlus✗{e}")
    if TG_BOT_TOKEN and TG_CHAT_ID:
        try:
            url = (f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage")
            urllib.request.urlopen(
                urllib.request.Request(
                    url,
                    data=urllib.parse.urlencode(
                        {"chat_id": TG_CHAT_ID, "text": f"{title}\n{content}"}).encode(),
                ), timeout=15)
            msgs.append("Telegram✓")
        except Exception as e:
            msgs.append(f"Telegram✗{e}")
    return msgs


def main():
    ap = argparse.ArgumentParser(description="DNSHE 免费域名自动续期")
    ap.add_argument("--check", action="store_true", help="仅检查全部域名到期情况")
    ap.add_argument("--list-expiring", action="store_true",
                    help="列出 N 天内到期的域名 (配合 --days)")
    ap.add_argument("--auto-renew", action="store_true",
                    help="对 N 天内到期且进入免费窗口的域名自动续期 (配合 --days)")
    ap.add_argument("--days", type=int, default=180,
                    help="提前天数阈值, DNSHE 免费域名到期前180天即可续, 默认180")
    ap.add_argument("--summary-file", type=str, default="",
                    help="将每日检查结果写入指定 Markdown 文件 (配合 GitHub Actions 的 "
                         "$GITHUB_STEP_SUMMARY 使用)")
    args = ap.parse_args()

    print(f"== DNSHE 域名检查 @ {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ==")
    items = list_subdomains()
    print(f"共获取 {len(items)} 个域名记录")

    rows = []
    for it in items:
        sub = it.get("full_domain") or it.get("subdomain") or it.get("domain") or "?"
        sid = it.get("id")
        status = it.get("status", "?")
        expiry = parse_expiry(it)
        rows.append((sub, sid, status, expiry, it))

    # 统计状态: 每个域名独立判断
    # 状态: "窗口外" (>180天, 无需处理) / "待续" (0~180天, 进入可续窗口)
    #        / "已过期" (剩余<0) / "永久有效" (never_expires) / "无到期时间"
    md_lines = [
        f"## DNSHE 域名每日检查 ({datetime.datetime.now():%Y-%m-%d %H:%M:%S})",
        "",
        f"共 {len(rows)} 个域名",
        "",
        "| 域名 | 状态 | 到期时间 | 剩余天数 | id |",
        "|---|---|---|---|---|",
    ]

    # 汇总
    line = []
    stats = {"窗口外": 0, "待续": 0, "已过期": 0, "永久有效": 0, "无到期时间": 0}
    for sub, sid, status, expiry, it in sorted(rows,
            key=lambda r: (r[3] is not None and r[3] != "never", r[3] if isinstance(r[3], datetime.datetime) else datetime.datetime.max)):
        if expiry == "never":
            dl = None
            dl_s = "∞"
            state = "永久有效"
            exp_s = "永久"
        elif expiry:
            dl = days_left(expiry)
            dl_s = f"{dl}天"
            if dl < 0:
                state = "已过期"
            elif dl <= args.days:
                state = "待续(窗口内)"
            else:
                state = "窗口外"
            exp_s = f"{expiry:%Y-%m-%d}"
        else:
            dl = None
            dl_s = "?"
            state = "无到期时间"
            exp_s = "?"
        stats["待续" if state == "待续(窗口内)" else
              "窗口外" if state == "窗口外" else
              "已过期" if state == "已过期" else
              "永久有效" if state == "永久有效" else "无到期时间"] += 1
        print(f"  [{state:>12}] {sub:<40} id={sid}  到期{exp_s} 剩余{dl_s}")
        line.append(f"{sub} 到期剩余 {dl_s} ({status})")
        md_lines.append(f"| {sub} | {state} | {exp_s} | {dl_s if dl is not None else '?'} | {sid} |")

    print(f"\n统计: {stats}")
    md_lines.append("")
    if args.auto_renew:
        md_lines.append("## 自动续期明细")
        md_lines.append("")

    # 需要处理: 0 ~ N 天内到期 (窗口内); 永久有效/无到期时间的排除
    need = [(sub, sid, expiry) for sub, sid, status, expiry, it in rows
            if isinstance(expiry, datetime.datetime)
            and 0 <= days_left(expiry) <= args.days]
    print(f"\n未来 {args.days} 天内到期(窗口内)的域名: {len(need)} 个")
    for sub, sid, expiry in need:
        print(f"  - {sub} (id={sid}) 剩余 {days_left(expiry)} 天")

    renewed, skipped, failed = [], [], []
    if args.auto_renew:
        print("\n== 尝试自动续期 ==")
        md_lines.append("| 域名 | 结果 | 说明 |")
        md_lines.append("|---|---|---|")
        for sub, sid, expiry in need:
            if sid is None:
                failed.append((sub, "无 id"))
                md_lines.append(f"| {sub} | 失败 | 无 id |")
                continue
            ok, msg = renew_subdomain(sid)
            tag = "成功" if ok else "跳过/失败"
            print(f"  [{tag}] {sub}: {msg}")
            if ok:
                renewed.append(sub)
                md_lines.append(f"| {sub} | ✅ 续期成功 | {msg} |")
            elif "not_yet_available" in msg or "窗口" in msg:
                skipped.append((sub, msg))
                md_lines.append(f"| {sub} | ⏳ 窗口未开 | {msg} |")
            else:
                failed.append((sub, msg))
                md_lines.append(f"| {sub} | ❌ 失败 | {msg} |")

        summary = (f"DNSHE 自动续期结果\n"
                   f"成功 {len(renewed)} 个: {', '.join(renewed) if renewed else '无'}\n"
                   f"窗口未开 {len(skipped)} 个: "
                   f"{', '.join(s for s, _ in skipped) if skipped else '无'}\n"
                   f"失败 {len(failed)} 个: "
                   f"{', '.join(s for s, _ in failed) if failed else '无'}")
        print("\n" + summary)
        md_lines.append("")
        md_lines.append(f"**续期成功 {len(renewed)} / 窗口未开 {len(skipped)} / 失败 {len(failed)}**")
        notif = send_notification("DNSHE 自动续期", summary)
        if notif:
            print("通知:", notif)

    elif args.list_expiring:
        print(f"\n== 未来 {args.days} 天到期清单 ==")
        for sub, sid, expiry in need:
            print(f"{sub} 剩余{days_left(expiry)}天 id={sid}")

    if args.summary_file:
        with open(args.summary_file, "a", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n\n")
        print(f"\n摘要已写入: {args.summary_file}")


if __name__ == "__main__":
    main()
