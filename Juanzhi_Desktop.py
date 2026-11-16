# -*- coding: utf-8 -*-
"""卷帙 DeShelf — 本地文本整理工具（桌面版，中英双语界面）

扫描 → 清洗 → 分章 → 导出，全程在本机完成，不发起任何网络请求。
界面语言：默认跟随系统；菜单「语言 / Language」可即时切换（窗口内重建）并记忆。
"""

import os
import queue
import subprocess
import threading
import time
import traceback
from collections import Counter
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

try:
    import ctypes
except ImportError:              # 非 Windows / 精简解释器：全部 DPI 调用自动降级
    ctypes = None

import jzcore

APP_CN = jzcore.APP_CN
APP_EN = jzcore.APP_EN
APP_VER = jzcore.APP_VER
AUTHOR = "© 永远的兰兰 · Lanlan Eternal"
BG = "#F0F0F0"
FONT = ("Microsoft YaHei UI", 9)
FONT_S = ("Microsoft YaHei UI", 8)
MONO = ("Consolas", 9)

# ---- 开屏海报配色（书卷风深底 + 金线）----
SPLASH_W, SPLASH_H = 560, 340
SPLASH_BG = "#202838"
SPLASH_GOLD = "#C9A24B"
SPLASH_INK = "#F1E7CE"
SPLASH_GRAY = "#9AA5B6"
SPLASH_DIM = "#7C8695"
SPLASH_LINE = "#465061"

# ============================================================ 语言
ZH = "zh"
EN = "en"

HELP_ZH = """卷帙 DeShelf 使用说明

【1 扫描入库】
  选择一个目录后点「扫描」，程序会递归查找其中所有 .txt 文件，
  自动识别编码（GBK / UTF-8 / UTF-16）、统计字数、按内容指纹标出重复文件。
  原文件始终保持原地不动，卷帙只记录索引，不会把书搬进自己的库。

【2 批量清洗】
  勾选需要的规则，点「预览效果」可以对比清洗前后的文本。
  常用组合：含网址的行 + 站点宣传行 + 翻页导航残留 + 乱码行 + 压缩连续空行。
  「删除所有空行」与「压缩连续空行」建议二选一，前者把全文压成不分段的一片。

【3 智能分章】
  内置中文网文章节规则库，可识别「第1章 / 第一百二十三章 / 卷三 / 序章 / 番外」等写法。
  若内置规则不适合，可填写自定义正则（填写后将只使用自定义规则）。
  点「试分章节」可查看切分结果，章节数不对就调整正则再来。

【4 导出分发】
  清洗结果去向：
    输出到新目录 — 原文件一个字节都不动，最安全
    原地覆盖 — 先备份为 .bak 再写回，省空间但有风险
    仅导出 — 不落盘整理后的 TXT，只生成导出文件
  导出格式可多选：EPUB（兼容绝大多数阅读器）、合并 TXT、分章 TXT。

【小提示】
  · 双击书库中的行可切换勾选；右键可打开文件位置。
  · 扫描结果会缓存在目录下的 .deshelf_index.json，下次打开秒载入。
  · 导出到手机后，用支持本地导入的阅读器打开 EPUB 即可带目录阅读。
"""

HELP_EN = """DeShelf User Guide

[1] Scan Library
  Pick a folder and click Scan. DeShelf recursively finds every .txt file,
  detects the encoding (GBK / UTF-8 / UTF-16), counts characters and flags
  duplicates by content fingerprint. Your originals never move — only an
  index is stored.

[2] Batch Clean
  Tick the rules you need and hit Preview to compare before/after text.
  A common combo: URL lines + site promos + pagination leftovers +
  corrupted lines + collapse blank runs.
  “Delete all blank lines” and “Collapse blank runs” are alternatives —
  pick one; the former squeezes the whole book into an unbroken block.

[3] Smart Chapter Split
  Built-in Chinese web-novel patterns match lines like 第1章 / 第一百二十三章 /
  卷三 / 序章 / 番外. For special formats, fill in a custom regex
  (the custom rule then replaces the built-ins). Click “Try split” to
  check the result and adjust.

[4] Export
  Where cleaned text goes:
    New folder  — originals stay byte-identical, safest
    Overwrite   — .bak backup first, saves space but touches files
    Export only — keep no cleaned TXT, just generated files
  Formats (multi-select): EPUB (TOC, most readers), merged TXT,
  per-chapter TXT.

[Tips]
  · Double-click a library row to toggle selection; right-click for file actions.
  · Scan results are cached in .deshelf_index.json next to the folder —
    reopening loads instantly.
  · Send EPUBs to your phone and open them in any local-import reader.
"""

DISC_ZH = """免责声明

卷帙 DeShelf 是一款纯本地的文本整理工具：它不联网、不下载、不上传、
不提供也不存储任何书籍内容，仅对用户本机已有的文件做清洗、分章与格式转换。

用户应确保其处理的文件拥有合法来源并仅用于个人学习研究，
因使用本工具产生的任何版权或法律问题，由使用者自行承担。

本软件按「现状」提供，作者不对数据丢失或损坏承担责任。
请在执行「原地覆盖」前确认已做好备份。
"""

DISC_EN = """Disclaimer

DeShelf is a purely local text-organizing tool: it does not connect to the
network, download, upload, host or store any book content. It only cleans,
splits and converts files that already exist on the user's own machine.

Users are responsible for ensuring the files they process have a legal
source and are used for personal study only. Any copyright or legal issue
arising from the use of this tool is the sole responsibility of the user.

The software is provided “as is”. The author accepts no liability for data
loss or damage. Please confirm you have a backup before using “Overwrite”.
"""

TEXTS = {
    ZH: {
        # 窗口 / 菜单
        "w_title": "%s %s %s",
        "m_file": "文件", "m_lib": "书库", "m_lang": "语言", "m_help": "帮助",
        "m_pick_dir": "选择目录…", "m_rescan": "重新扫描",
        "m_rescan_fresh": "重新扫描（忽略缓存）", "m_quit": "退出",
        "m_sel_all": "全选", "m_sel_none": "全不选", "m_invert": "反选",
        "m_sel_dup": "只选重复文件", "m_export_csv": "导出书单 CSV",
        "m_usage": "使用说明", "m_disclaimer": "免责声明", "m_about": "关于",
        "lang_busy": "正在处理中",
        "lang_busy_msg": "请等待当前任务完成后再切换语言。",
        # 顶部栏
        "lib_dir": "书库目录：", "browse": "浏览…", "scan": "扫描",
        "stop": "停止",
        # 页标签
        "tab1": " 1 扫描入库 ", "tab2": " 2 批量清洗 ",
        "tab3": " 3 智能分章 ", "tab4": " 4 导出分发 ",
        # 页1 书库
        "lib_hint": "  双击行可切换勾选，右键可打开文件位置",
        "lib_info": "共 {0} 本 · 已选 {1} 本",
        "lib_info_dup": " · 重复 {0} 本",
        "col_title": "书名", "col_author": "作者", "col_chars": "字数",
        "col_enc": "编码", "col_chap": "章节", "col_size": "大小", "col_rel": "相对路径",
        # 页2 清洗
        "grp_rules": "清洗规则", "b_all_rules": "全选规则", "b_def_rules": "恢复默认",
        "b_preview": "预览效果",
        "b_clean_apply": "应用到所选书籍",
        "d_rule_none": "未选择清洗规则", "d_rule_none_msg": "请至少勾选一条清洗规则后再应用。",
        "prog_clean": "清洗 {0}/{1}：《{2}》",
        "st_clean_done": "已清洗 {0} 本 · 共删除 {1} 行",
        "log_clean_done": "批量清洗完成：{0} 本 · 删除 {1} 行",
        "clean_hint": "  对第一本勾选的书试跑，左边原文、右边清洗后",
        "col_pre": "清洗前", "col_post": "清洗后",
        "cmp_var": "删除 {0} 行，{1} → {2} 字",
        "cmp_var_cut": "删除 {0} 行、另 {3} 行只裁了行尾网址，{1} → {2} 字",
        "cmp_jsdup": "（其中简繁重复 {0} 行）",
        # 页3 分章
        "re_label": "章节正则（留空使用内置中文规则库）：",
        "b_try": "试分章节",
        "b_try_all": "试分全部选中",
        "lab_chap_pick": "试分书籍：",
        "chap_pick_hint": "选单本试分；「试分全部选中」处理①书库勾选的全部书",
        "chap_hint": "内置可识别：第1章 / 第一百二十三章 / 卷三 / Chapter 5 / 序章 / 楔子 / 番外 / 后记；"
                    "填写自定义正则后将只使用自定义规则。",
        "col_chap_title": "章节标题",
        "col_c_book": "书名", "col_c_chaps": "章节",
        "chap_res": "点「试分章节」查看结果",
        "chap_all_done": "试分 {0} 本：共 {1} 章，异常 {2} 本（见日志）",
        "chap_sum": "《{0}》共切出 {1} 章，正文合计 {2} 字",
        # 页4 导出
        "grp_where": "清洗结果的去向",
        "r_new": "输出到新目录（原文件不动，推荐）",
        "r_inplace": "原地覆盖（先备份为 .bak）",
        "r_none": "仅导出，不保存整理后的 TXT",
        "grp_fmt": "导出格式（可多选）",
        "f_epub": "EPUB（带目录，推荐）",
        "f_merge": "合并 TXT（整本一个文件）",
        "f_split": "分章 TXT（一章一个文件）",
        "grp_out": "输出目录",
        "b_go": "开始处理",
        "out_note": "处理期间请勿关闭窗口。大批量任务建议先选少量书试跑。",
        "out_suffix": "_卷帙整理",
        # 日志 / 状态
        "grp_log": "运行日志", "st_ready": "就绪", "stopping": "正在停止…",
        "log_scan_start": "开始扫描：{0}",
        "log_found": "发现 {0} 个文本文件，开始读取…",
        "log_skip": "  跳过 {0}（{1}）",
        "prog_scan": "扫描中 {0}/{1}",
        "log_idx_load": "已从索引载入 {0} 本（{1}）{2}",
        "log_idx_stale": "，{0} 本已失效建议重新扫描",
        "log_idx_missing": "提示：索引中有 {0} 个文件已不存在，建议点「重新扫描」。",
        "st_scan_done": "扫描完成：{0} / {1} 本",
        "log_scan_done": "扫描完成，共 {0} 本。{1}",
        "log_stopped": "（已停止）",
        "log_run_done": "处理完成：成功 {0} 本，失败 {1} 本",
        "st_run_done": "处理完成：成功 {0} 本，失败 {1} 本",
        "prog_run": "处理中 {0}/{1}：{2}",
        "prog_done": "处理完成",
        "log_per_book": "[{0}/{1}] {2}：{3} 章，清洗删除 {4} 行",
        "log_book_fail": "[{0}/{1}] {2} 失败：{3}",
        "log_outdir_fail": "无法创建输出目录：{0}",
        "log_open_fail": "无法打开资源管理器：{0}",
        "log_file_fail": "无法打开文件：{0}",
        "log_csv_ok": "书单已导出：{0}",
        "log_dup_sel": "已选中 {0} 个重复文件，可在书库中取消保留项的勾选后清理。",
        "log_out_final": "原地覆盖",
        # 对话框
        "d_info": "提示", "d_warn": "警告", "d_error": "错误", "d_confirm": "确认",
        "d_close": "关闭",
        "d_dir_invalid": "目录无效", "d_dir_invalid_msg": "请先选择一个存在的目录。",
        "d_no_sel": "未选择", "d_no_sel_msg": "请先在书库中勾选至少一本书。",
        "d_no_dup": "没有重复", "d_no_dup_msg": "当前书库中未发现内容完全相同的文件。",
        "d_no_out": "缺少输出目录", "d_no_out_msg": "请先选择输出目录。",
        "d_nothing": "无事可做",
        "d_nothing_msg": "你选择了「仅导出」却又没有勾选任何导出格式。",
        "d_confirm_ip": "确认原地覆盖",
        "d_confirm_ip_msg": "将把清洗后的内容写回 {0} 个原文件，每个原文件会先备份为 .bak。\n\n"
                           "此操作会改动你的原始文件，确定继续吗？",
        "d_re_bad": "正则无效", "d_re_bad_msg": "自定义章节正则无效，请检查语法。",
        "d_preview_fail": "预览失败", "d_chap_fail": "分章失败",
        "d_export_fail": "导出失败",
        # CSV
        "csv_hdr": "书名,作者,字数,编码,大小,相对路径",
        "csv_name": "书单.csv", "csv_type": "CSV 文件",
        # 关于 / 帮助
        "about_title": "关于 %s %s",
        "about_what": "本地文本整理工具：扫描 · 清洗 · 分章 · 导出\n"
                      "纯离线运行，不联网、不下载、不上传任何内容。",
        "about_repo": "GitHub 主页 / 查看最新版：\nhttps://github.com/podcatcher962/DeShelf/releases",
        "usage_title": "使用说明", "disclaimer_title": "免责声明",
        "help_text": HELP_ZH, "disclaimer_text": DISC_ZH,
        # 右键菜单
        "m_open_loc": "打开文件位置", "m_open_note": "用记事本打开",
        "m_copy_path": "复制完整路径",
        # 通用
        "unnamed": "未命名",
        # 开屏
        "sp_tag": "扫描 · 清洗 · 分章 · 导出",
        "sp_bottom": "{0} · 纯本地离线工具 · 点击或按任意键跳过",
    },
    EN: {
        "w_title": "%s %s %s",
        "m_file": "File", "m_lib": "Library", "m_lang": "Language", "m_help": "Help",
        "m_pick_dir": "Choose folder…", "m_rescan": "Rescan",
        "m_rescan_fresh": "Rescan (ignore cache)", "m_quit": "Exit",
        "m_sel_all": "Select all", "m_sel_none": "Select none", "m_invert": "Invert",
        "m_sel_dup": "Select duplicates only", "m_export_csv": "Export list as CSV",
        "m_usage": "User guide", "m_disclaimer": "Disclaimer", "m_about": "About",
        "lang_busy": "Busy",
        "lang_busy_msg": "Please wait for the current task to finish before switching language.",
        "lib_dir": "Library folder:", "browse": "Browse…", "scan": "Scan",
        "stop": "Stop",
        "tab1": " 1 Scan Library ", "tab2": " 2 Batch Clean ",
        "tab3": " 3 Split Chapters ", "tab4": " 4 Export ",
        "lib_hint": "  Double-click a row to toggle; right-click for file actions",
        "lib_info": "{0} books · {1} selected",
        "lib_info_dup": " · {0} duplicated",
        "col_title": "Title", "col_author": "Author", "col_chars": "Chars",
        "col_enc": "Encoding", "col_chap": "Chap", "col_size": "Size", "col_rel": "Path",
        "grp_rules": "Cleaning Rules", "b_all_rules": "Check all", "b_def_rules": "Reset",
        "b_preview": "Preview",
        "b_clean_apply": "Apply to selected books",
        "d_rule_none": "No cleaning rule", "d_rule_none_msg": "Tick at least one cleaning rule first.",
        "prog_clean": "Cleaning {0}/{1}: {2}",
        "st_clean_done": "Cleaned {0} books · {1} lines removed",
        "log_clean_done": "Batch clean done: {0} books · {1} lines removed",
        "clean_hint": "  Dry-run on the first selected book: original left, cleaned right",
        "col_pre": "Original", "col_post": "Cleaned",
        "cmp_var": "{0} lines removed, {1} → {2} chars",
        "cmp_var_cut": "{0} lines removed, {3} more only had a trailing URL trimmed, {1} → {2} chars",
        "cmp_jsdup": " ({0} of them were script duplicates)",
        "re_label": "Chapter regex (blank = built-in Chinese rules):",
        "b_try": "Try Split",
        "b_try_all": "Try Split (all selected)",
        "lab_chap_pick": "Book to split:",
        "chap_pick_hint": "Pick a book here; \"Try Split (all selected)\" acts on every book ticked in ①Library",
        "chap_hint": "Built-in patterns match 第1章 / 第一百二十三章 / 卷三 / Chapter 5 / "
                    "序章 / 楔子 / 番外 / 后记; a custom regex replaces the built-ins.",
        "col_chap_title": "Chapter Title",
        "col_c_book": "Book", "col_c_chaps": "Chapters",
        "chap_res": "Click \u201cTry Split\u201d to preview",
        "chap_all_done": "Tried {0} books: {1} chapters in total, {2} failed (see log)",
        "chap_sum": "\u201c{0}\u201d: {1} chapters, {2} chars total",
        "grp_where": "Where Cleaned Text Goes",
        "r_new": "Output to a new folder (originals untouched, recommended)",
        "r_inplace": "Overwrite in place (.bak backup first)",
        "r_none": "Export only — don't save cleaned TXT",
        "grp_fmt": "Export Formats (multi-select)",
        "f_epub": "EPUB (with TOC, recommended)",
        "f_merge": "Merged TXT (one file per book)",
        "f_split": "Per-chapter TXT (one file per chapter)",
        "grp_out": "Output Folder",
        "b_go": "Start",
        "out_note": "Keep the window open while processing. For large batches, try a few books first.",
        "out_suffix": "_DeShelf",
        "grp_log": "Log", "st_ready": "Ready", "stopping": "Stopping…",
        "log_scan_start": "Scanning: {0}",
        "log_found": "Found {0} text files, reading…",
        "log_skip": "  Skipped {0} ({1})",
        "prog_scan": "Scanning {0}/{1}",
        "log_idx_load": "Loaded {0} books from index ({1}){2}",
        "log_idx_stale": ", {0} stale — rescan advised",
        "log_idx_missing": "{0} files in the index no longer exist — click \u201cRescan\u201d.",
        "st_scan_done": "Scan done: {0}/{1}",
        "log_scan_done": "Scan finished: {0} books.{1}",
        "log_stopped": " (stopped)",
        "log_run_done": "Done: {0} ok, {1} failed",
        "st_run_done": "Done: {0} ok, {1} failed",
        "prog_run": "Processing {0}/{1}: {2}",
        "prog_done": "Done",
        "log_per_book": "[{0}/{1}] {2}: {3} chapters, {4} lines removed",
        "log_book_fail": "[{0}/{1}] {2} failed: {3}",
        "log_outdir_fail": "Cannot create output folder: {0}",
        "log_open_fail": "Cannot open Explorer: {0}",
        "log_file_fail": "Cannot open file: {0}",
        "log_csv_ok": "List exported: {0}",
        "log_dup_sel": "Selected {0} duplicates — uncheck the copies you keep, then process.",
        "log_out_final": "overwritten in place",
        "d_info": "Info", "d_warn": "Warning", "d_error": "Error", "d_confirm": "Confirm",
        "d_close": "Close",
        "d_dir_invalid": "Invalid Folder", "d_dir_invalid_msg": "Please choose an existing folder.",
        "d_no_sel": "Nothing Selected", "d_no_sel_msg": "Select at least one book in the library first.",
        "d_no_dup": "No Duplicates",
        "d_no_dup_msg": "No content-identical files found in the library.",
        "d_no_out": "Output Folder Needed", "d_no_out_msg": "Please choose an output folder.",
        "d_nothing": "Nothing to Do",
        "d_nothing_msg": "You picked \u201cExport only\u201d but selected no format.",
        "d_confirm_ip": "Confirm Overwrite",
        "d_confirm_ip_msg": "Cleaned text will be written back to {0} original files, each backed "
                           "up as .bak first.\n\nThis modifies your original files. Continue?",
        "d_re_bad": "Invalid Regex", "d_re_bad_msg": "Custom chapter regex is invalid — check the syntax.",
        "d_preview_fail": "Preview Failed", "d_chap_fail": "Split Failed",
        "d_export_fail": "Export Failed",
        "csv_hdr": "Title,Author,Chars,Encoding,Size,Path",
        "csv_name": "library_list.csv", "csv_type": "CSV files",
        "about_title": "About %s %s",
        "about_what": "A local TXT organizer: scan · clean · split · export\n"
                      "Fully offline — no network, no upload, nothing leaves your computer.",
        "about_repo": "GitHub homepage / latest release:\nhttps://github.com/podcatcher962/DeShelf/releases",
        "usage_title": "User Guide", "disclaimer_title": "Disclaimer",
        "help_text": HELP_EN, "disclaimer_text": DISC_EN,
        "m_open_loc": "Open file location", "m_open_note": "Open with Notepad",
        "m_copy_path": "Copy full path",
        "unnamed": "Untitled",
        "sp_tag": "Scan · Clean · Split · Export",
        "sp_bottom": "{0} · Fully offline · Click or press any key to skip",
    },
}


def _sys_lang():
    """按 Windows 界面语言判断默认界面语言（不抛异常）。"""
    try:
        import ctypes
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return ZH if (lid & 0x3FF) == 0x04 else EN   # 0x0804/0x0404/0x0004 = Chinese
    except Exception:
        return ZH


def pick_lang():
    """优先级：环境变量 JUANZHI_LANG > 配置文件 lang > 系统语言。"""
    env = os.environ.get("JUANZHI_LANG")
    if env in (ZH, EN):
        return env
    cfg = jzcore.load_config()
    if cfg.get("lang") in (ZH, EN):
        return cfg["lang"]
    return _sys_lang()


def safe_name(s, maxlen=60, fallback="未命名"):
    s = (s or "").strip()
    s = "".join(c for c in s if c not in '\\/:*?"<>|\r\n\t')
    s = s.strip(" .")
    return (s or fallback)[:maxlen]


# ============================================================ DPI / 屏幕几何
_SCALE = 1.0        # 96 DPI 逻辑像素 → 当前 DPI 物理像素的倍率（125% = 1.25）


def px(v):
    """96 DPI 下的逻辑像素 → 当前 DPI 下的物理像素。

    界面里所有写死的像素尺寸（窗口大小、行高、列宽、内边距、画布坐标）
    都必须经过这里换算，否则开启系统缩放后只有字号变大、布局不变。
    """
    return int(round(v * _SCALE))


def _set_dpi_aware():
    """声明进程 DPI 感知。**必须**在 tk.Tk() 之前调用。

    Tk 只在初始化时按当时的屏幕 DPI 计算一次 tk scaling 并缓存；
    若像旧代码那样在 Tk() 之后才 SetProcessDpiAwareness(1)，进程此时已
    变为 DPI 感知（窗口不再被系统位图放大），而 Tk 仍按 96 DPI 出图，
    于是 125%/150% 下文字与控件全部偏小。

    这里选 System DPI Aware 而非 Per-Monitor：Tk 8.6 不处理
    WM_DPICHANGED，声明 Per-Monitor 后把窗口拖到另一块不同 DPI 的屏幕
    会停留在旧的缩放倍率上，反而更糟。
    """
    if ctypes is None or os.name != "nt":
        return
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(1) == 0:   # S_OK
            return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _init_metrics(root):
    """读取真实 DPI，校准点字号（tk scaling）与像素尺寸（px）的倍率。

    点字号由 tk scaling 缩放、像素尺寸由 px() 缩放，两者用同一个 DPI
    基准，所以字体与控件保持设计稿的相对比例，不会互相挤压。
    """
    global _SCALE
    try:
        dpi = float(root.winfo_fpixels("1i"))
    except Exception:
        dpi = 0.0
    if not (60.0 <= dpi <= 480.0):        # 取值异常时退回 96 DPI
        dpi = 96.0
    # 只放大不缩小：84 DPI 之类的老屏 / 非 Windows 平台保持设计尺寸，
    # 免得为了「适配」反而把界面整体压小。
    _SCALE = max(1.0, dpi / 96.0)
    try:
        root.tk.call("tk", "scaling", dpi / 72.0)   # 1 point = dpi/72 px
    except Exception:
        pass
    return _SCALE


def _work_area():
    """主显示器工作区（物理像素，已剔除任务栏）；失败返回 None。"""
    if ctypes is None or os.name != "nt":
        return None
    try:
        class _RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        r = _RECT()
        # SPI_GETWORKAREA = 0x0030
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
            if r.right > r.left and r.bottom > r.top:
                return r.right - r.left, r.bottom - r.top, r.left, r.top
    except Exception:
        pass
    return None


def _center_win(win, w, h):
    """把窗口严格居中到主显示器工作区（水平 + 垂直）。

    w/h 以 96 DPI 逻辑像素传入，内部按 DPR 换算并按工作区夹取：
    · 不再有硬编码的 -12 偏移，所以是真正的几何居中；
    · 用工作区而不是整屏，任务栏不会把视觉中心顶高；
    · 开屏与主窗走同一函数，两者中心重合、切换时不会跳动。
    """
    try:
        win.update_idletasks()
    except Exception:
        pass
    W, H = px(w), px(h)
    area = _work_area()
    if area:
        aw, ah, ax, ay = area
    else:
        try:
            aw, ah, ax, ay = win.winfo_screenwidth(), win.winfo_screenheight(), 0, 0
        except Exception:
            return None
    W = max(1, min(W, aw - px(24)))       # 小屏 + 高缩放时别超出可见区域
    H = max(1, min(H, ah - px(24)))
    x = ax + (aw - W) // 2
    y = ay + (ah - H) // 2
    win.geometry("%dx%d+%d+%d" % (W, H, x, y))
    return W, H


class App:
    def __init__(self, root):
        self.root = root
        self.books = []
        self.q = queue.Queue()
        self.busy = False
        self.cancel = False
        self.cfg = jzcore.load_config()
        self.lang = pick_lang()
        self.S = TEXTS[self.lang]
        last = self.cfg.get("lastdir", "")
        self.dir_var = tk.StringVar(value=last)
        self.out_var = tk.StringVar(value=self.cfg.get("outdir", ""))
        self.custom_re = tk.StringVar()
        self.mode_var = tk.StringVar(value=self.cfg.get("mode", "new") or "new")
        self.rule_vars = {r["id"]: tk.BooleanVar(value=r["id"] in jzcore.DEFAULT_ON)
                          for r in jzcore.RULES}
        self.fmt_vars = {"epub": tk.BooleanVar(value=True),
                         "merge": tk.BooleanVar(value=False),
                         "split": tk.BooleanVar(value=False)}
        self.status_var = tk.StringVar(value=self.S["st_ready"])
        self.prog_var = tk.DoubleVar(value=0)

        root.title(self.S["w_title"] % (APP_CN, APP_EN, APP_VER))
        root.geometry("%dx%d" % (px(1080), px(720)))
        root.minsize(px(900), px(620))
        root.configure(bg=BG)
        self._style()
        self._menu()
        self._top(root)
        self._tabs(root)
        self._log(root)
        self._status(root)
        self.poll()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        d = self.dir_var.get()
        if d and os.path.isdir(d):
            if not self.out_var.get():
                self.out_var.set(d.rstrip("\\/") + self.S["out_suffix"])
            self.load_index(d)

    # ------------------------------------------------------------ 界面
    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=BG, font=FONT)
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG)
        st.configure("TLabelframe", background=BG)
        st.configure("TLabelframe.Label", background=BG)
        st.configure("TCheckbutton", background=BG)
        st.configure("TRadiobutton", background=BG)
        st.configure("TNotebook", background=BG)
        st.configure("Treeview", rowheight=px(23))
        st.configure("Accent.TButton", background="#4A7EBB", foreground="white")
        st.configure("Go.TButton", background="#2E7D32", foreground="white")

    def _menu(self):
        S = self.S
        m = tk.Menu(self.root)
        self.root.configure(menu=m)
        fm = tk.Menu(m, tearoff=0)
        fm.add_command(label=S["m_pick_dir"], command=self.pick_dir)
        fm.add_command(label=S["m_rescan"], command=self.do_scan)
        fm.add_command(label=S["m_rescan_fresh"], command=lambda: self.do_scan(fresh=True))
        fm.add_separator()
        fm.add_command(label=S["m_quit"], command=self.on_close)
        m.add_cascade(label=S["m_file"], menu=fm)
        sm = tk.Menu(m, tearoff=0)
        sm.add_command(label=S["m_sel_all"], command=lambda: self.set_all(True))
        sm.add_command(label=S["m_sel_none"], command=lambda: self.set_all(False))
        sm.add_command(label=S["m_invert"], command=self.invert_sel)
        sm.add_separator()
        sm.add_command(label=S["m_sel_dup"], command=self.sel_dup)
        sm.add_command(label=S["m_export_csv"], command=self.export_list)
        m.add_cascade(label=S["m_lib"], menu=sm)
        lm = tk.Menu(m, tearoff=0)
        self._lang_rb = tk.StringVar(value=self.lang)
        lm.add_radiobutton(label="中文", value=ZH, variable=self._lang_rb,
                           command=lambda: self.switch_lang(ZH))
        lm.add_radiobutton(label="English", value=EN, variable=self._lang_rb,
                           command=lambda: self.switch_lang(EN))
        m.add_cascade(label=S["m_lang"], menu=lm)
        hm = tk.Menu(m, tearoff=0)
        hm.add_command(label=S["m_usage"],
                       command=lambda: self.show_text(S["usage_title"], S["help_text"]))
        hm.add_command(label=S["m_disclaimer"],
                       command=lambda: self.show_text(S["disclaimer_title"], S["disclaimer_text"]))
        hm.add_separator()
        hm.add_command(label=S["m_about"], command=self.show_about)
        m.add_cascade(label=S["m_help"], menu=hm)

    def _top(self, root):
        S = self.S
        f = ttk.Frame(root, padding=(px(8), px(6)))
        f.pack(fill="x")
        ttk.Label(f, text=S["lib_dir"]).pack(side="left")
        e = ttk.Entry(f, textvariable=self.dir_var)
        e.pack(side="left", fill="x", expand=True, padx=px(4))
        e.bind("<Return>", lambda _e: self.do_scan())
        ttk.Button(f, text=S["browse"], command=self.pick_dir).pack(side="left")
        ttk.Button(f, text=S["scan"], style="Accent.TButton",
                   command=self.do_scan).pack(side="left", padx=(px(4), 0))
        ttk.Button(f, text=S["m_rescan_fresh"],
                   command=lambda: self.do_scan(fresh=True)).pack(side="left", padx=px(4))
        self.btn_stop = ttk.Button(f, text=S["stop"], command=self.do_stop, state="disabled")
        self.btn_stop.pack(side="left")

    def _tabs(self, root):
        S = self.S
        nb = ttk.Notebook(root)
        self.nb = nb
        nb.pack(fill="both", expand=True, padx=px(8), pady=(0, px(4)))
        self.tab_lib = ttk.Frame(nb)
        self.tab_clean = ttk.Frame(nb)
        self.tab_chap = ttk.Frame(nb)
        self.tab_out = ttk.Frame(nb)
        nb.add(self.tab_lib, text=S["tab1"])
        nb.add(self.tab_clean, text=S["tab2"])
        nb.add(self.tab_chap, text=S["tab3"])
        nb.add(self.tab_out, text=S["tab4"])
        self._build_lib()
        self._build_clean()
        self._build_chap()
        self._build_out()
        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_lib(self):
        S = self.S
        f = self.tab_lib
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(px(6), px(4)))
        for txt, cmd in ((S["m_sel_all"], lambda: self.set_all(True)),
                         (S["m_sel_none"], lambda: self.set_all(False)),
                         (S["m_invert"], self.invert_sel),
                         (S["m_sel_dup"], self.sel_dup)):
            ttk.Button(bar, text=txt, command=cmd).pack(side="left", padx=px(2))
        ttk.Label(bar, text=S["lib_hint"], foreground="#666666").pack(side="left")
        self.info_var = tk.StringVar(value=S["lib_info"].format(0, 0))
        ttk.Label(bar, textvariable=self.info_var).pack(side="right")

        cols = ("sel", "title", "author", "chars", "enc", "chap", "size", "rel")
        wrap = ttk.Frame(f)
        wrap.pack(fill="both", expand=True)
        self.tv = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended")
        heads = {"sel": "✓", "title": S["col_title"], "author": S["col_author"],
                 "chars": S["col_chars"], "enc": S["col_enc"], "chap": S["col_chap"],
                 "size": S["col_size"], "rel": S["col_rel"]}
        widths = {"sel": px(32), "title": px(190), "author": px(100), "chars": px(80),
                  "enc": px(76), "chap": px(56), "size": px(78), "rel": px(320)}
        for c in cols:
            self.tv.heading(c, text=heads[c])
            self.tv.column(c, width=widths[c], anchor="w" if c in ("title", "author", "rel") else "center")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv.pack(side="left", fill="both", expand=True)
        self.tv.tag_configure("dup", foreground="#C05621")
        self.tv.bind("<Double-1>", self.toggle_row)
        self.tv.bind("<Button-3>", self.popup)

    def _build_clean(self):
        S = self.S
        f = self.tab_clean
        left = ttk.LabelFrame(f, text=S["grp_rules"], width=px(280))
        left.pack(side="left", fill="y", padx=(px(6), px(4)), pady=px(6))
        left.pack_propagate(False)
        en = self.lang == EN
        for r in jzcore.RULES:
            name = r["name_en"] if en else r["name"]
            tip = r["tip_en"] if en else r["tip"]
            cb = ttk.Checkbutton(left, text=name, variable=self.rule_vars[r["id"]])
            cb.pack(anchor="w", padx=px(8), pady=px(2))
            ttk.Label(left, text="    " + tip, foreground="#777777",
                      font=FONT_S, wraplength=px(250)).pack(anchor="w", padx=px(8))
        bf = ttk.Frame(left)
        bf.pack(anchor="w", padx=px(8), pady=px(8))
        ttk.Button(bf, text=S["b_all_rules"], command=lambda: self.set_rules(True)).pack(side="left")
        ttk.Button(bf, text=S["b_def_rules"], command=lambda: self.set_rules(None)).pack(side="left", padx=px(4))

        right = ttk.Frame(f)
        right.pack(side="left", fill="both", expand=True, padx=px(4), pady=px(6))
        bar = ttk.Frame(right)
        bar.pack(fill="x")
        ttk.Button(bar, text=S["b_preview"], style="Accent.TButton",
                   command=self.preview_clean).pack(side="left")
        self.btn_clean_apply = ttk.Button(bar, text=S["b_clean_apply"],
                                          command=self.start_clean)
        self.btn_clean_apply.pack(side="left", padx=(px(6), 0))
        ttk.Label(bar, text=S["clean_hint"], foreground="#666666").pack(side="left")
        self.cmp_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.cmp_var, foreground="#2E7D32").pack(side="right")
        box = ttk.Frame(right)
        box.pack(fill="both", expand=True, pady=px(4))
        self.txt_before = self._mk_text(box, S["col_pre"])
        self.txt_after = self._mk_text(box, S["col_post"])

    def _mk_text(self, parent, title):
        f = ttk.LabelFrame(parent, text=title)
        f.pack(side="left", fill="both", expand=True, padx=px(2))
        # width 必须给小值：pack 按顺序满足请求宽度，80 字符会吃满空间导致两栏不等分
        t = tk.Text(f, wrap="none", font=MONO, width=30, height=10, bg="#FFFFFF",
                    relief="solid", borderwidth=1)
        sb = ttk.Scrollbar(f, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        return t

    def _build_chap(self):
        S = self.S
        f = self.tab_chap
        top = ttk.Frame(f)
        top.pack(fill="x", padx=px(8), pady=(px(8), px(4)))
        ttk.Label(top, text=S["re_label"]).pack(side="left")
        e = ttk.Entry(top, textvariable=self.custom_re)
        e.pack(side="left", fill="x", expand=True, padx=px(4))
        ttk.Button(top, text=S["b_try"], style="Accent.TButton",
                   command=self.preview_chap).pack(side="left")
        ttk.Button(top, text=S["b_try_all"],
                   command=self.preview_chap_all).pack(side="left", padx=(px(6), 0))
        pick = ttk.Frame(f)
        pick.pack(fill="x", padx=px(8), pady=(px(2), 0))
        ttk.Label(pick, text=S["lab_chap_pick"]).pack(side="left")
        self.chap_pick_text = tk.StringVar()
        self.cb_chap = ttk.Combobox(pick, textvariable=self.chap_pick_text,
                                    state="readonly", width=46)
        self.cb_chap.pack(side="left", padx=px(4))
        ttk.Label(pick, text=S["chap_pick_hint"], foreground="#666666",
                  font=FONT_S).pack(side="left")
        ttk.Label(f, text=S["chap_hint"],
                  foreground="#666666", font=FONT_S).pack(anchor="w", padx=px(8))
        wrap = ttk.Frame(f)
        wrap.pack(fill="both", expand=True, padx=px(8), pady=px(4))
        self.tv_chap = ttk.Treeview(wrap, columns=("no", "title", "chars"),
                                    show="headings", height=8)
        for c, w, t in (("no", px(60), "#"), ("title", px(520), S["col_chap_title"]),
                        ("chars", px(100), S["col_chars"])):
            self.tv_chap.heading(c, text=t)
            self.tv_chap.column(c, width=w, anchor="w" if c == "title" else "center")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tv_chap.yview)
        self.tv_chap.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_chap.pack(side="left", fill="both", expand=True)
        self.chap_var = tk.StringVar(value=S["chap_res"])
        ttk.Label(f, textvariable=self.chap_var).pack(anchor="w", padx=px(8), pady=(0, px(6)))

    def _build_out(self):
        S = self.S
        f = self.tab_out
        g1 = ttk.LabelFrame(f, text=S["grp_where"])
        g1.pack(fill="x", padx=px(8), pady=(px(10), px(6)))
        for v, t in (("new", S["r_new"]), ("inplace", S["r_inplace"]), ("none", S["r_none"])):
            ttk.Radiobutton(g1, text=t, value=v, variable=self.mode_var,
                            command=self.sync_out).pack(anchor="w", padx=px(10), pady=px(2))

        g2 = ttk.LabelFrame(f, text=S["grp_fmt"])
        g2.pack(fill="x", padx=px(8), pady=px(6))
        row = ttk.Frame(g2)
        row.pack(fill="x", padx=px(10), pady=px(4))
        ttk.Checkbutton(row, text=S["f_epub"],
                        variable=self.fmt_vars["epub"]).pack(side="left", padx=(0, px(16)))
        ttk.Checkbutton(row, text=S["f_merge"],
                        variable=self.fmt_vars["merge"]).pack(side="left", padx=(0, px(16)))
        ttk.Checkbutton(row, text=S["f_split"],
                        variable=self.fmt_vars["split"]).pack(side="left")

        g3 = ttk.LabelFrame(f, text=S["grp_out"])
        g3.pack(fill="x", padx=px(8), pady=px(6))
        r = ttk.Frame(g3)
        r.pack(fill="x", padx=px(10), pady=px(6))
        ttk.Entry(r, textvariable=self.out_var).pack(side="left", fill="x", expand=True, padx=(0, px(4)))
        ttk.Button(r, text=S["browse"], command=self.pick_out).pack(side="left")

        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=px(8), pady=px(10))
        self.btn_go = ttk.Button(bar, text=S["b_go"], style="Go.TButton", command=self.start_run)
        self.btn_go.pack(side="left")
        self.pb = ttk.Progressbar(bar, variable=self.prog_var, maximum=100)
        self.pb.pack(side="left", fill="x", expand=True, padx=px(10))
        ttk.Label(f, text=S["out_note"],
                  foreground="#777777", font=FONT_S).pack(anchor="w", padx=px(8))

    def _log(self, root):
        S = self.S
        f = ttk.LabelFrame(root, text=S["grp_log"], height=px(130))
        f.pack(fill="x", padx=px(8), pady=(0, px(4)))
        f.pack_propagate(False)
        self.logbox = tk.Text(f, height=7, font=FONT_S, bg="#FFFFFF",
                              relief="solid", borderwidth=1)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.logbox.yview)
        self.logbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.logbox.pack(fill="both", expand=True)

    def _status(self, root):
        ttk.Label(root, textvariable=self.status_var, anchor="w",
                  relief="sunken",
                  padding=(px(6), px(2))).pack(fill="x", padx=px(8), pady=(0, px(6)))

    # ------------------------------------------------------------ 基础操作
    def log(self, msg):
        self.q.put(("log", msg))

    def poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.logbox.insert("end", payload + "\n")
                    self.logbox.see("end")
                elif kind == "book":
                    self.add_book(payload)
                elif kind == "prog":
                    cur, total, label = payload
                    self.prog_var.set(0 if not total else cur * 100.0 / total)
                    if label:
                        self.status_var.set(label)
                elif kind == "done":
                    self.on_done(payload)
        except queue.Empty:
            pass
        self.root.after(80, self.poll)

    def set_busy(self, busy):
        self.busy = busy
        self.btn_stop.configure(state="normal" if busy else "disabled")
        self.btn_go.configure(state="disabled" if busy else "normal")

    def do_stop(self):
        self.cancel = True
        self.status_var.set(self.S["stopping"])

    def switch_lang(self, lang):
        """窗口内即时切换语言：就地销毁并重建全部界面控件（数据留在 self.books）。"""
        if lang == self.lang:
            return
        if self.busy:
            messagebox.showinfo(self.S["lang_busy"], self.S["lang_busy_msg"])
            return
        try:
            cur_tab = self.nb.index(self.nb.select())
        except Exception:
            cur_tab = 0
        old_log = ""
        try:
            old_log = self.logbox.get("1.0", "end-1c")
        except Exception:
            pass
        for w in self.root.winfo_children():
            w.destroy()
        # 切语言并保存记忆
        self.lang = lang
        self.S = TEXTS[lang]
        self.cfg["lang"] = lang
        jzcore.save_config(self.cfg)
        # 就地重建（各 _build 方法幂等；复用 __init__ 创建的 var，勾选/输入值天然保留）
        self.root.title(self.S["w_title"] % (APP_CN, APP_EN, APP_VER))
        self._style()
        self._menu()
        self._top(self.root)
        self._tabs(self.root)
        self._log(self.root)
        self._status(self.root)
        self.status_var.set(self.S["st_ready"])
        self.reload_rows()          # books 数据在内存，整表重灌（含勾选状态）
        self._fill_chap_pick()      # 重建后重填「试分书籍」下拉
        try:
            self.nb.select(cur_tab)
        except Exception:
            self.nb.select(0)
        if old_log:
            self.logbox.insert("end", old_log + "\n")
        self.log("✓ Language switched / 语言已切换：%s" % ("English" if lang == EN else "中文"))

    def on_close(self):
        cfg = self.cfg
        cfg["lastdir"] = self.dir_var.get()
        cfg["outdir"] = self.out_var.get()
        cfg["mode"] = self.mode_var.get()
        jzcore.save_config(cfg)
        self.root.destroy()

    def pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get() or None)
        if d:
            self.dir_var.set(d)
            self.out_var.set(d.rstrip("\\/") + self.S["out_suffix"])
            self.do_scan()

    def pick_out(self):
        d = filedialog.askdirectory(initialdir=self.out_var.get() or self.dir_var.get() or None)
        if d:
            self.out_var.set(d)

    def sync_out(self):
        if not self.out_var.get() and self.dir_var.get():
            self.out_var.set(self.dir_var.get().rstrip("\\/") + self.S["out_suffix"])

    def show_text(self, title, body):
        S = self.S
        w = tk.Toplevel(self.root)
        w.title(title)
        _center_win(w, 640, 520)          # 说明窗同样按 DPR 缩放并居中
        t = tk.Text(w, wrap="word", font=FONT, padx=px(10), pady=px(10))
        t.insert("1.0", body)
        t.configure(state="disabled")
        t.pack(fill="both", expand=True)
        ttk.Button(w, text=S["d_close"], command=w.destroy).pack(pady=px(6))

    def show_about(self):
        S = self.S
        messagebox.showinfo(
            S["about_title"] % (APP_CN, APP_EN),
            "%s %s %s\n\n%s\n\n%s\n\n%s"
            % (APP_CN, APP_EN, APP_VER, S["about_what"], S["about_repo"], AUTHOR))

    # ------------------------------------------------------------ 书库
    def add_book(self, info):
        idx = len(self.books)
        info.setdefault("chapters", -1)      # 章数字段：-1 = 尚未试分
        self.books.append(info)
        rel = info.get("rel", os.path.basename(info["path"]))
        self.tv.insert("", "end", iid=str(idx), values=(
            "✓" if info["sel"] else "", info["title"], info["author"],
            "{:,}".format(info["chars"]), info["enc"], self.chap_cell(info),
            jzcore.human_size(info["size"]), rel))
        self.refresh_info()

    def refresh_info(self):
        n = len(self.books)
        m = sum(1 for b in self.books if b["sel"])
        d = self.dup_count()
        s = self.S["lib_info"].format(n, m)
        if d:
            s += self.S["lib_info_dup"].format(d)
        self.info_var.set(s)

    def chap_cell(self, b):
        """书库「章节」列的显示值：未试分显示 -，试分后显示已切出的章数。

        章数唯一来源是书籍字典的 chapters 字段（scan_file 预置 -1），
        ③ 分章页试分后写回这里，① 书库列表据此渲染，两页共用同一份状态。
        """
        try:
            n = int(b.get("chapters", -1))
        except (TypeError, ValueError):
            n = -1
        return str(n) if n >= 0 else "-"

    def _set_book_chaps(self, b, n):
        """把试分结果写回书籍状态，并即时刷新①书库对应行的「章节」单元格。"""
        b["chapters"] = n
        try:
            iid = str(self.books.index(b))
        except ValueError:
            return
        if self.tv.exists(iid):
            self.tv.set(iid, "chap", self.chap_cell(b))

    def refresh_chap_col(self):
        """按 books 快照重灌全部「章节」单元格（切回①书库时与分章页对齐）。"""
        for i, b in enumerate(self.books):
            iid = str(i)
            if self.tv.exists(iid):
                self.tv.set(iid, "chap", self.chap_cell(b))

    def reload_rows(self):
        """按 books 快照整表重灌（批量清洗改 chars 后刷新书库列表）。"""
        for row in self.tv.get_children():
            self.tv.delete(row)
        for i, b in enumerate(self.books):
            self.tv.insert("", "end", iid=str(i), values=(
                "✓" if b["sel"] else "", b["title"], b["author"],
                "{:,}".format(b["chars"]), b["enc"], self.chap_cell(b),
                jzcore.human_size(b["size"]), b.get("rel", os.path.basename(b["path"]))))

    def dup_count(self):
        c = Counter(b["md5"] for b in self.books)
        return sum(v for v in c.values() if v > 1)

    def toggle_row(self, event):
        row = self.tv.identify_row(event.y)
        if not row:
            return
        b = self.books[int(row)]
        b["sel"] = not b["sel"]
        self.tv.set(row, "sel", "✓" if b["sel"] else "")
        self.refresh_info()

    def set_all(self, val):
        for i, b in enumerate(self.books):
            b["sel"] = val
            self.tv.set(str(i), "sel", "✓" if val else "")
        self.refresh_info()

    def invert_sel(self):
        for i, b in enumerate(self.books):
            b["sel"] = not b["sel"]
            self.tv.set(str(i), "sel", "✓" if b["sel"] else "")
        self.refresh_info()

    def sel_dup(self):
        S = self.S
        c = Counter(b["md5"] for b in self.books)
        dups = {k for k, v in c.items() if v > 1}
        if not dups:
            messagebox.showinfo(S["d_no_dup"], S["d_no_dup_msg"])
            return
        for i, b in enumerate(self.books):
            b["sel"] = b["md5"] in dups
            self.tv.set(str(i), "sel", "✓" if b["sel"] else "")
        self.refresh_info()
        self.log(S["log_dup_sel"].format(sum(1 for b in self.books if b["sel"])))

    def popup(self, event):
        S = self.S
        row = self.tv.identify_row(event.y)
        if not row:
            return
        self.tv.selection_set(row)
        b = self.books[int(row)]
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=S["m_open_loc"],
                      command=lambda: self.open_folder(b["path"]))
        m.add_command(label=S["m_open_note"],
                      command=lambda: self.open_file(b["path"]))
        m.add_separator()
        m.add_command(label=S["m_copy_path"],
                      command=lambda: self.copy_path(b["path"]))
        m.tk_popup(event.x_root, event.y_root)

    def open_folder(self, path):
        try:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        except OSError:
            self.log(self.S["log_open_fail"].format(path))

    def open_file(self, path):
        try:
            os.startfile(path)
        except OSError:
            self.log(self.S["log_file_fail"].format(path))

    def copy_path(self, path):
        self.root.clipboard_clear()
        self.root.clipboard_append(path)

    def export_list(self):
        S = self.S
        if not self.books:
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv",
                                         filetypes=[(S["csv_type"], "*.csv")],
                                         initialfile=S["csv_name"])
        if not p:
            return
        try:
            with open(p, "w", encoding="utf-8-sig", newline="") as f:
                f.write(S["csv_hdr"] + "\n")
                for b in self.books:
                    f.write('"%s","%s",%d,%s,%d,"%s"\n' % (
                        b["title"].replace('"', '""'), b["author"].replace('"', '""'),
                        b["chars"], b["enc"], b["size"], b.get("rel", "").replace('"', '""')))
            self.log(S["log_csv_ok"].format(p))
        except OSError as e:
            messagebox.showerror(S["d_export_fail"], str(e))

    # ------------------------------------------------------------ 扫描
    def do_scan(self, fresh=False):
        S = self.S
        d = self.dir_var.get().strip()
        if not d or not os.path.isdir(d):
            messagebox.showwarning(S["d_dir_invalid"], S["d_dir_invalid_msg"])
            return
        if self.busy:
            return
        if not fresh and self.load_index(d):
            return
        self.clear_books()
        self.set_busy(True)
        self.cancel = False
        self.log(S["log_scan_start"].format(d))
        threading.Thread(target=self.scan_worker, args=(d,), daemon=True).start()

    def clear_books(self):
        self.books = []
        for i in self.tv.get_children():
            self.tv.delete(i)
        self.refresh_info()

    def scan_worker(self, root):
        S = self.S
        files = []
        for dp, _dn, fn in os.walk(root):
            for f in fn:
                if f.lower().endswith((".txt", ".text")):
                    files.append(os.path.join(dp, f))
        files.sort()
        total = len(files)
        self.q.put(("log", S["log_found"].format(total)))
        got = 0
        for i, p in enumerate(files, 1):
            if self.cancel:
                break
            try:
                info = jzcore.scan_file(p)
                info["rel"] = os.path.relpath(p, root)
                self.q.put(("book", info))
                got += 1
            except Exception as e:
                self.q.put(("log", S["log_skip"].format(os.path.basename(p), e)))
            if i % 5 == 0 or i == total:
                self.q.put(("prog", (i, total, S["prog_scan"].format(i, total))))
        self.q.put(("done", ("scan", root, got, total)))

    def load_index(self, root):
        S = self.S
        data = jzcore.load_index(root)
        books = data.get("books") or []
        if not books:
            return False
        self.clear_books()
        missing = 0
        for b in books:
            p = os.path.join(root, b.get("rel", ""))
            if not os.path.exists(p):
                missing += 1
                continue
            if int(os.path.getmtime(p)) != int(b.get("mtime", 0)) or os.path.getsize(p) != b.get("size"):
                b["stale"] = True
            b["path"] = p
            b.setdefault("sel", True)
            self.add_book(b)
        self.mark_dup()
        if not self.out_var.get():
            self.out_var.set(root.rstrip("\\/") + S["out_suffix"])
        stale_n = sum(1 for b in self.books if b.get("stale"))
        extra = S["log_idx_stale"].format(stale_n) if stale_n else ""
        self.log(S["log_idx_load"].format(
            len(self.books), time.strftime("%Y-%m-%d %H:%M", time.localtime(data.get("scanned", 0))), extra))
        if missing:
            self.log(S["log_idx_missing"].format(missing))
        return True

    def mark_dup(self):
        c = Counter(b["md5"] for b in self.books)
        for i, b in enumerate(self.books):
            if c[b["md5"]] > 1:
                self.tv.item(str(i), tags=("dup",))

    def on_done(self, payload):
        S = self.S
        kind = payload[0]
        self.set_busy(False)
        self.prog_var.set(0)
        if kind == "scan":
            _s, root, got, total = payload
            self.mark_dup()
            self.status_var.set(S["st_scan_done"].format(got, total))
            self.log(S["log_scan_done"].format(got, S["log_stopped"] if self.cancel else ""))
            jzcore.save_index(root, {
                "root": root, "scanned": time.time(),
                "books": [{k: v for k, v in b.items() if k != "path"} for b in self.books]})
        elif kind == "run":
            _s, ok, fail, outdir = payload
            self.reload_rows()          # 回写实际切分章数/字数后重灌书库列表
            self.mark_dup()
            self.status_var.set(S["st_run_done"].format(ok, fail))
            self.log(S["log_run_done"].format(ok, fail) + "，输出目录 %s" % outdir)
            if outdir and os.path.isdir(outdir) and not self.cancel:
                try:
                    os.startfile(outdir)
                except OSError:
                    pass
        elif kind == "clean":
            _s, ok, rm_sum, cancelled = payload
            self.reload_rows()
            self.status_var.set(S["st_clean_done"].format(ok, "{:,}".format(rm_sum)))
            self.log(S["log_clean_done"].format(ok, "{:,}".format(rm_sum))
                     + (S["log_stopped"] if cancelled else ""))

    # ------------------------------------------------------------ 预览
    def first_selected(self):
        for b in self.books:
            if b["sel"]:
                return b
        return None

    def active_rules(self):
        return [i for i, v in self.rule_vars.items() if v.get()]

    def set_rules(self, val):
        for r in jzcore.RULES:
            v = self.rule_vars[r["id"]]
            v.set(val if val is not None else r["id"] in jzcore.DEFAULT_ON)

    def preview_clean(self):
        S = self.S
        b = self.first_selected()
        if not b:
            messagebox.showinfo(S["d_no_sel"], S["d_no_sel_msg"])
            return
        try:
            text = jzcore.load_text(b["path"])
            rules = self.active_rules()
            stats = {}
            cleaned, removed = jzcore.clean_text(text, rules, stats)
        except Exception as e:
            messagebox.showerror(S["d_preview_fail"], str(e))
            return
        for t, s in ((self.txt_before, text), (self.txt_after, cleaned)):
            t.configure(state="normal")
            t.delete("1.0", "end")
            t.insert("1.0", "\n".join(s.splitlines()[:400]))
            t.configure(state="disabled")
        cut = stats.get("trimmed", 0)
        key = "cmp_var_cut" if cut else "cmp_var"
        dup = stats.get("jsdup", 0)
        msg = S[key].format(removed, len(text), len(cleaned), cut)
        if dup:
            msg += S["cmp_jsdup"].format(dup)
        self.cmp_var.set(msg)
        self.log("《%s》规则 %d 条，删除 %d 行，只裁行尾 %d 行，简繁重复 %d 行"
                 % (b["title"], len(rules), removed, cut, dup))

    def start_clean(self):
        """批量清洗：对勾选书籍按当前规则清洗，结果缓存到内存供后续分章/导出复用。"""
        S = self.S
        sel = [b for b in self.books if b["sel"]]
        if not sel:
            messagebox.showinfo(S["d_no_sel"], S["d_no_sel_msg"])
            return
        if not self.active_rules():
            messagebox.showinfo(S["d_rule_none"], S["d_rule_none_msg"])
            return
        if self.busy:
            return
        # 规则必须在主线程预取：tk 变量在线程内读取会 RuntimeError
        rules = self.active_rules()
        self.set_busy(True)
        self.cancel = False
        threading.Thread(target=self.clean_worker, args=(sel, rules), daemon=True).start()

    def clean_worker(self, sel, rules):
        S = self.S
        total = len(sel)
        ok = rm_sum = 0
        for i, b in enumerate(sel, 1):
            if self.cancel:
                break
            self.q.put(("prog", (i - 1, total, S["prog_clean"].format(i, total, b["title"]))))
            try:
                text = jzcore.load_text(b["path"])
                text, removed = jzcore.clean_text(text, rules)
                b["_clean"] = text          # 清洗快照：分章/导出优先使用（与 Web 版一致）
                b["chars"] = len(text)
                b["chapters"] = -1          # 正文已变，旧章数作废（与 Web 版一致）
                rm_sum += removed
                ok += 1
            except Exception as e:
                self.q.put(("log", S["log_book_fail"].format(i, total, b["title"], e)))
        self.q.put(("prog", (total, total, S["prog_done"])))
        self.q.put(("done", ("clean", ok, rm_sum, self.cancel)))

    def _fill_chap_pick(self):
        """同步「试分书籍」下拉：列出书库全部书；保持当前选中，失效则默认勾选首本。"""
        names = [(b["title"] or os.path.splitext(b["name"])[0]) for b in self.books]
        try:
            self.cb_chap["values"] = names
        except Exception:
            return
        cur = self.chap_pick_text.get()
        if cur not in names:
            fb = self.first_selected()
            cur = (fb["title"] or os.path.splitext(fb["name"])[0]) if fb else (names[0] if names else "")
        self.chap_pick_text.set(cur or "")

    def picked_book(self):
        """单本试分目标 = 下拉所选；下拉无有效值时回退勾选首本。"""
        self._fill_chap_pick()
        t = self.chap_pick_text.get()
        for b in self.books:
            if (b["title"] or os.path.splitext(b["name"])[0]) == t:
                return b
        return self.first_selected()

    def _on_tab_changed(self, _e=None):
        """切换页签时对齐两页共享状态：③ 同步试分下拉，① 重刷「章节」列。"""
        try:
            idx = self.nb.index("current")
        except Exception:
            return
        if idx == 2:
            self._fill_chap_pick()
        elif idx == 0:
            self.refresh_chap_col()

    def preview_chap(self):
        S = self.S
        self._chap_cols(False)
        b = self.picked_book()
        if not b:
            messagebox.showinfo(S["d_no_sel"], S["d_no_sel_msg"])
            return
        custom = self.custom_re.get().strip() or None
        try:
            text = b.get("_clean")
            if text is None:
                text = jzcore.load_text(b["path"])
                rules = self.active_rules()
                if rules:
                    text, _r = jzcore.clean_text(text, rules)
            chapters = jzcore.split_chapters(text, custom)
        except ValueError as e:
            messagebox.showerror(S["d_re_bad"], str(e))
            return
        except Exception as e:
            messagebox.showerror(S["d_chap_fail"], str(e))
            return
        for i in self.tv_chap.get_children():
            self.tv_chap.delete(i)
        for i, (t, body) in enumerate(chapters[:2000], 1):
            self.tv_chap.insert("", "end", values=(i, t, "{:,}".format(len(body))))
        total = sum(len(x[1]) for x in chapters)
        self.chap_var.set(S["chap_sum"].format(b["title"], len(chapters), "{:,}".format(total)))
        self._set_book_chaps(b, len(chapters))      # 写回书籍状态 → ① 书库「章节」列同步
        self.log("《%s》试分 %d 章" % (b["title"], len(chapters)))

    def _chap_cols(self, batch):
        """分章表格列头：False=单本预览(章序/标题/字数)，True=批量试分(序号/书名/章节)。"""
        S = self.S
        self.tv_chap.heading("no", text="#")
        self.tv_chap.heading("title", text=S["col_c_book"] if batch else S["col_chap_title"])
        self.tv_chap.heading("chars", text=S["col_c_chaps"] if batch else S["col_chars"])
        self.tv_chap.column("title", width=px(320) if batch else px(520))
        self.tv_chap.column("chars", width=px(140) if batch else px(100))
        self._chap_batch = batch

    def preview_chap_all(self):
        """批量试分：对书库中所有勾选的书籍逐本切章，结果按 序号/书名/章节 列出。"""
        S = self.S
        sel = [b for b in self.books if b["sel"]]
        if not sel:
            messagebox.showinfo(S["d_no_sel"], S["d_no_sel_msg"])
            return
        custom = self.custom_re.get().strip() or None
        self._chap_cols(True)
        for i in self.tv_chap.get_children():
            self.tv_chap.delete(i)
        ok_n = sum_n = bad = 0
        for b in sel:
            try:
                text = b.get("_clean")
                if text is None:
                    text = jzcore.load_text(b["path"])
                    rules = self.active_rules()
                    if rules:
                        text, _r = jzcore.clean_text(text, rules)
                chapters = jzcore.split_chapters(text, custom)
            except ValueError as e:
                messagebox.showerror(S["d_re_bad"], str(e))
                return
            except Exception as e:
                bad += 1
                self.log("《%s》试分失败：%s" % (b["title"], e))
                continue
            ok_n += 1
            sum_n += len(chapters)
            self._set_book_chaps(b, len(chapters))      # 逐本写回，书库「章节」列即时可见
            self.tv_chap.insert("", "end", values=(ok_n, b["title"], str(len(chapters))))
        self.refresh_chap_col()
        self.chap_var.set(S["chap_all_done"].format(ok_n, sum_n, bad))
        self.log("批量试分：%d 本成功 · %d 本异常 · 共 %d 章" % (ok_n, bad, sum_n))

    # ------------------------------------------------------------ 执行
    def start_run(self):
        S = self.S
        sel = [b for b in self.books if b["sel"]]
        if not sel:
            messagebox.showinfo(S["d_no_sel"], S["d_no_sel_msg"])
            return
        fmts = [k for k, v in self.fmt_vars.items() if v.get()]
        mode = self.mode_var.get()
        outdir = self.out_var.get().strip()
        if mode in ("new", "none") and not outdir:
            messagebox.showwarning(S["d_no_out"], S["d_no_out_msg"])
            return
        # 原地覆盖清洗不需要输出目录；但只要勾了导出格式，仍必须有输出目录
        if mode == "inplace" and fmts and not outdir:
            messagebox.showwarning(S["d_no_out"], S["d_no_out_msg"])
            return
        if mode == "none" and not fmts:
            messagebox.showwarning(S["d_nothing"], S["d_nothing_msg"])
            return
        if mode == "inplace":
            if not messagebox.askyesno(
                    S["d_confirm_ip"],
                    S["d_confirm_ip_msg"].format(len(sel))):
                return
        if self.busy:
            return
        self.set_busy(True)
        self.cancel = False
        # 规则/正则必须在主线程预取：tk 变量在线程内读取会 RuntimeError
        rules = self.active_rules()
        custom = self.custom_re.get().strip() or None
        threading.Thread(target=self.run_worker,
                         args=(sel, fmts, mode, outdir, rules, custom),
                         daemon=True).start()

    def run_worker(self, sel, fmts, mode, outdir, rules, custom):
        S = self.S
        ok = fail = 0
        if mode != "inplace" and outdir:
            try:
                os.makedirs(outdir, exist_ok=True)
            except OSError as e:
                self.q.put(("log", S["log_outdir_fail"].format(e)))
                self.q.put(("done", ("run", 0, len(sel), outdir)))
                return
        total = len(sel)
        for i, b in enumerate(sel, 1):
            if self.cancel:
                break
            self.q.put(("prog", (i - 1, total, S["prog_run"].format(i, total, b["title"]))))
            try:
                # 原地覆盖始终从磁盘原文按当前规则重洗写回；其余模式优先用内存清洗快照
                if mode == "inplace":
                    text = jzcore.load_text(b["path"])
                    removed = 0
                    if rules:
                        text, removed = jzcore.clean_text(text, rules)
                else:
                    text = b.get("_clean")
                    removed = 0
                    if text is None:
                        text = jzcore.load_text(b["path"])
                        if rules:
                            text, removed = jzcore.clean_text(text, rules)
                chapters = jzcore.split_chapters(text, custom)
                b["chapters"] = len(chapters)       # 实际切分结果回写，供①书库展示
                title = b["title"] or os.path.splitext(b["name"])[0]
                base = safe_name(title, fallback=S["unnamed"])
                if mode == "inplace":
                    bak = b["path"] + ".bak"
                    if not os.path.exists(bak):
                        try:
                            os.replace(b["path"], bak)
                        except OSError:
                            pass
                    with open(b["path"], "w", encoding="utf-8", newline="\n") as f:
                        f.write(text)
                elif mode == "new" and outdir:
                    with open(self.uniq(outdir, base + ".txt"), "w",
                              encoding="utf-8", newline="\n") as f:
                        f.write(text)
                if outdir:
                    if "epub" in fmts:
                        jzcore.write_epub(self.uniq(outdir, base + ".epub"),
                                          title, b["author"], chapters)
                    # “输出到新目录”落盘的 TXT 与合并 TXT 内容等价，避免生成重复文件
                    if "merge" in fmts and mode != "new":
                        jzcore.save_txt(chapters, self.uniq(outdir, base + ".txt"), merge=True)
                    if "split" in fmts:
                        jzcore.save_txt(chapters, self.uniq(outdir, base + ".txt"), merge=False)
                self.q.put(("log", S["log_per_book"].format(i, total, title, len(chapters), removed)))
                ok += 1
            except Exception as e:
                fail += 1
                self.q.put(("log", S["log_book_fail"].format(i, total, b["title"], e)))
                self.q.put(("log", traceback.format_exc(limit=1).strip()))
        self.q.put(("prog", (total, total, S["prog_done"])))
        final = outdir if mode != "inplace" else (outdir or S["log_out_final"])
        self.q.put(("done", ("run", ok, fail, final)))

    def uniq(self, outdir, filename):
        p = os.path.join(outdir, filename)
        if not os.path.exists(p):
            return p
        stem, ext = os.path.splitext(filename)
        n = 1
        while True:
            p = os.path.join(outdir, "%s (%d)%s" % (stem, n, ext))
            if not os.path.exists(p):
                return p
            n += 1


class _Splash:
    """开屏海报：无边框置顶窗，alpha 淡入 → 回调构建主窗 → close() 淡出销毁。

    任意键或点击海报可跳过等待，直接进入主界面。
    时序全部由 after 驱动；_skipped 置位后淡入链立即收敛。
    文案按界面语言渲染（构造时传入 lang）。
    """

    def __init__(self, root, lang=None):
        self.root = root
        self._fade_job = None
        self._skipped = False
        self._fade_done = None
        self._hold_then = None
        self._then = None
        self.S = TEXTS[lang or pick_lang()]
        win = tk.Toplevel(root)
        self.win = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=SPLASH_BG)
        # 画布随窗口尺寸自适应：_paint 按画布实际尺寸等比缩放并居中绘制
        c = self.cv = tk.Canvas(win, width=px(SPLASH_W), height=px(SPLASH_H),
                                bg=SPLASH_BG, highlightthickness=0, bd=0)
        c.pack(fill="both", expand=True)
        self._paint(c)
        c.bind("<Configure>", lambda _e: self._paint(c))
        _center_win(win, SPLASH_W, SPLASH_H)      # 严格水平 + 垂直居中
        try:
            win.attributes("-alpha", 0.0)
        except tk.TclError:
            # 极少数远程环境不支持窗口透明度：直接亮起并让 owner 尽快接手
            win.attributes("-alpha", 1.0)
            self._skipped = True
        win.bind("<Button-1>", self._skip)
        win.bind("<Key>", self._skip)
        win.focus_force()
        win.update_idletasks()
        self._paint(c)                            # 映射后按真实像素再绘一次

    def _paint(self, c):
        """在 560x340 的设计坐标系里绘制，再按画布实际尺寸等比缩放并居中。

        所有坐标经 X()/Y() 平移缩放，文字用负字号（像素）跟随 k，
        因此窗口尺寸或 DPR 如何变化，海报内容始终水平垂直居中且不拉伸。
        """
        S = self.S
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 2 or H < 2:                        # 尚未映射：先用设计尺寸
            W, H = px(SPLASH_W), px(SPLASH_H)
        k = min(W / float(SPLASH_W), H / float(SPLASH_H))   # 等比，不拉伸版式
        ox = (W - SPLASH_W * k) / 2.0             # 水平居中偏移
        oy = (H - SPLASH_H * k) / 2.0             # 垂直居中偏移

        def X(x):
            return ox + x * k

        def Y(y):
            return oy + y * k

        def P(v):                                 # 线宽 / 字号（像素）
            return max(1, int(round(v * k)))

        g, ln = SPLASH_GOLD, SPLASH_LINE
        cx = X(SPLASH_W / 2.0)
        # 细金外框
        c.create_rectangle(X(11), Y(11), X(SPLASH_W - 11), Y(SPLASH_H - 11),
                           outline=g, width=P(2))
        # 四角回形小装饰（沿框延伸的短金线）
        L = 22
        for x0, y0, dx, dy in ((11, 11, 1, 0), (11, 11, 0, 1),
                               (SPLASH_W - 11, 11, -1, 0), (SPLASH_W - 11, 11, 0, 1),
                               (11, SPLASH_H - 11, 1, 0), (11, SPLASH_H - 11, 0, -1),
                               (SPLASH_W - 11, SPLASH_H - 11, -1, 0),
                               (SPLASH_W - 11, SPLASH_H - 11, 0, -1)):
            c.create_line(X(x0), Y(y0), X(x0 + dx * L), Y(y0 + dy * L),
                          fill=g, width=P(3))
        # 主标题「卷帙」：楷体大字（负字号 = 像素，避免被 tk scaling 二次放大）
        c.create_text(cx, Y(88), text=APP_CN, font=("KaiTi", -P(77)),
                      fill=SPLASH_INK, anchor="n")
        # 英文名（字母间隔拉宽，模拟字距）
        c.create_text(cx, Y(172), text=" ".join(APP_EN), font=(FONT[0], -P(17)),
                      fill=SPLASH_GOLD, anchor="n")
        # 一句定位
        c.create_text(cx, Y(212), text=S["sp_tag"],
                      font=(FONT[0], -P(15)), fill=SPLASH_GRAY, anchor="n")
        # 分隔线 + 底部信息
        c.create_line(X(SPLASH_W / 2.0 - 90), Y(250),
                      X(SPLASH_W / 2.0 + 90), Y(250), fill=ln, width=P(1))
        c.create_text(cx, Y(272), text=S["sp_bottom"].format(APP_VER),
                      font=(FONT[0], -P(12)), fill=SPLASH_DIM, anchor="n")

    # ------------------------------------------------------------ 动画
    def fade_in(self, done):
        """从透明淡入到完全不透明，完成时调用 done()（供 owner 构建主窗）。"""
        self._fade_done = done
        self._step(0.0, 1.0)

    def hold(self, ms, then):
        """不透明状态停留 ms 后执行 then；停留期间点击可提前触发。"""
        self._hold_then = then
        self._fade_job = self.root.after(ms, self._fire_hold)

    def _fire_hold(self):
        self._fade_job = None
        cb, self._hold_then = self._hold_then, None
        if cb:
            cb()

    def _cancel_job(self):
        if self._fade_job:
            try:
                self.root.after_cancel(self._fade_job)
            except Exception:
                pass
            self._fade_job = None

    def _step(self, a0, a1):
        a = min(a1, a0 + 0.13) if not self._skipped else a1
        try:
            self.win.attributes("-alpha", a)
        except tk.TclError:
            a = a1
        if a < a1 - 1e-9:
            self._fade_job = self.root.after(20, lambda: self._step(a, a1))
        else:
            cb, self._fade_done = self._fade_done, None
            if cb:
                cb()

    def close(self, then=None):
        """从当前透明度淡出并销毁，完成后回调 then（进入主窗口）。"""
        self._then = then
        self._step_out()

    def _step_out(self):
        try:
            cur = float(self.win.attributes("-alpha"))
        except tk.TclError:
            cur = 0.0
        a = max(0.0, cur - 0.15)
        try:
            self.win.attributes("-alpha", a)
        except tk.TclError:
            a = 0.0
        if a > 1e-9:
            self._fade_job = self.root.after(18, self._step_out)
        else:
            self._destroy()

    def _destroy(self):
        self._fade_job = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        cb, self._then = self._then, None
        if cb:
            cb()

    def _skip(self, _e=None):
        """点击 / 按键：从当前阶段尽量跳到终点，可连点逐级推进。"""
        self._cancel_job()
        if self._fade_done:                 # 淡入中：直接到最亮并继续原流程
            self._skipped = True
            try:
                self.win.attributes("-alpha", 1.0)
            except tk.TclError:
                pass
            cb, self._fade_done = self._fade_done, None
            if cb:
                cb()
        elif self._hold_then:               # 停驻中：提前结束停留
            self._fire_hold()
        elif self._then:                    # 淡出中：立即销毁收尾
            self._destroy()


def _boot(root):
    app = App(root)
    _center_win(root, 1080, 720)      # 与开屏海报同一套居中对齐逻辑


def main():
    _set_dpi_aware()                 # 必须在 tk.Tk() 之前：Tk 只初始化一次缩放
    root = tk.Tk()
    _init_metrics(root)              # 必须在任何控件/画布创建之前
    if os.environ.get("JUANZHI_NO_SPLASH"):     # 测试/调试逃生门
        _boot(root)
        root.mainloop()
        return
    root.withdraw()
    try:
        sp = _Splash(root)
    except Exception:
        root.deiconify()
        _boot(root)
        root.mainloop()
        return

    def build_and_go():
        _boot(root)                             # 海报最亮时构建主窗，无感
        sp.hold(550, lambda: sp.close(then=lambda: root.deiconify()))

    sp.fade_in(build_and_go)
    root.mainloop()


if __name__ == "__main__":
    main()
