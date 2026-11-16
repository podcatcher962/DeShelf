# -*- coding: utf-8 -*-
"""卷帙 DeShelf — 本地文本整理核心逻辑层。

仅依赖 Python 标准库，不发起任何网络请求，只处理用户本机已有的文件。
"""

import hashlib
import json
import os
import re
import uuid
import zipfile

APP_CN = "卷帙"
APP_EN = "DeShelf"
APP_VER = "v1.3.4"
INDEX_NAME = ".deshelf_index.json"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".deshelf_config.json")

# ---------------------------------------------------------------- 编码识别

def detect_bytes(data):
    """根据字节内容猜测编码，返回可传给 decode 的名称。"""
    if data[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if data[:2] == b"\xff\xfe":
        return "utf-16-le"
    if data[:2] == b"\xfe\xff":
        return "utf-16-be"
    if b"\x00" in data[:2000]:
        return "utf-16-le"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    return "gbk"


def decode(data, enc):
    try:
        return data.decode(enc, errors="replace")
    except (UnicodeError, LookupError):
        return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- 元信息

# 正文里的字段标识。标识可以在行首，也可以跟在同一行前一个字段后面（用空白或分隔符隔开），
# 但前面必须是空白/分隔符，免得把「这本书的作者：某某」这类叙述句当成元信息。
_TITLE_LABELS = r"(?:书名|标题|题\s*目|小说名)"
_AUTHOR_LABELS = r"(?:作者|作\s*者)"
_FIELD_LABELS = r"(?:%s|%s)" % (_TITLE_LABELS, _AUTHOR_LABELS)
_LABEL_HEAD = r"(?:^|(?<=[\s\u3000,，;；、|｜/／]))"
_TITLE_IN_TEXT = re.compile(_LABEL_HEAD + _TITLE_LABELS + r"\s*[:：]\s*")
_AUTHOR_IN_TEXT = re.compile(_LABEL_HEAD + _AUTHOR_LABELS + r"\s*[:：]\s*")
# 同一行挤着多个字段时，值到此为止
_FIELD_END = re.compile(r"\s*%s\s*[:：]" % _FIELD_LABELS)
_BRACKET = re.compile(r"《(.+?)》")
_JUNK = re.compile(r"[（(].*?[]）)]|\[[^\]]*\]|\.txt$|\.TXT$", re.I)

# 文件名里常见的作者标识，可用 guess_meta_detail(author_keys=...) 替换
AUTHOR_KEYS = ("作者", "著者", "编者", "编著", "著")
# 零宽/BOM/方向控制符，常混在下载来的文件名里
_INVIS = re.compile("[\ufeff\u200b-\u200f\u2028\u2029\u2060]")
# 方括号里的名字：[作者]书名、书名[作者]；圆括号多是版本信息，不算
_BRACKET_AUTHOR = re.compile(r"[\[【]([^\[\]【】]{1,20})[\]】]")
# 版本 / 来源类标签，出现在方括号或标识后面时不是作者
_META_TAGS = {
    "全本", "全集", "全书", "完本", "完结", "完结本", "连载", "精校", "精校版",
    "校对", "校对版", "修订版", "珍藏版", "收藏版", "无删减", "未删节", "手打",
    "手打版", "全文", "全文字", "txt", "text", "下载", "免费", "最新章节",
}
# 占位词：出现了也不算识别出作者
_AUTHOR_BAD = {
    "未知", "佚名", "无名", "不详", "暂无", "无", "作者", "n/a", "na",
    "unknown", "null", "none",
}


def _author_keys_re(keys=None):
    """把标识元组编成正则分支，长标识在前（编著 先于 著）。"""
    return "|".join(re.escape(k) for k in sorted(keys or AUTHOR_KEYS, key=len, reverse=True))


def _author_re(keys=None):
    """「作者标识 + 作者名」的匹配式。

    标识后面必须跟冒号或者空白，否则「著作权法」「名著合集」会被误当成作者行；
    名字里碰到下一个「作者：」就停，免得「作者：甲作者：乙」拼成「甲作者」。
    """
    body = _author_keys_re(keys)
    return re.compile(
        r"(?:%s)\s*(?:[:：]\s*|\s+)"
        r"((?:(?!(?:%s)\s*[:：])[^\s\[\]【】()（）《》_\-—－:：,，。;；、])+)" % (body, body))


def _cut_field(s):
    """把字段值截到下一个「书名：」「作者：」等标识之前，并去掉残留分隔符。"""
    m = _FIELD_END.search(s)
    if m:
        s = s[:m.start()]
    return s.strip(" \t\u3000,，;；|｜/／、")


def _clean_author(s):
    """清洗作者串，去掉扩展名残留、书名号、多余空格与不可见字符。"""
    s = _INVIS.sub("", s or "")
    s = re.sub(r"(?:\.(?:txt|text))+$", "", s.strip(), flags=re.I)
    s = s.strip(" \t\u3000-—－_·.,，。;；:：、<>《》|｜/／\"'“”‘’")
    s = re.sub(r"\s+", " ", s).strip()
    if not s or len(s) > 20 or s.isdigit():
        return ""
    if s.lower() in _AUTHOR_BAD or s in _META_TAGS:
        return ""
    return s


def _clean_name(name):
    name = _JUNK.sub("", name)
    name = re.sub(r"[_\-—－]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def guess_meta_detail(filename, text, author_keys=None):
    """推断书名与作者，并给出各自的来源，无法识别时明确标为 "none"。

    author_keys 可替换文件名里的作者标识（默认 AUTHOR_KEYS）。
    返回 {"title", "author", "title_from", "author_from"}，
    来源取 "text"（正文明写）/ "filename"（文件名）/ "none"（没识别出来）。
    """
    title, author = "", ""
    title_from = author_from = "none"

    # 1) 正文优先：前 25 行里的「书名：」「作者：」，同一行有多个字段也能分别取到
    for line in (text or "").splitlines()[:25]:
        if not title:
            m = _TITLE_IN_TEXT.search(line)
            if m:
                cand = _cut_field(line[m.end():])
                if cand:
                    title, title_from = cand, "text"
        if not author:
            m = _AUTHOR_IN_TEXT.search(line)
            if m:
                cand = _clean_author(_cut_field(line[m.end():]))
                if cand:
                    author, author_from = cand, "text"

    # 2) 文件名：去掉 BOM/隐藏字符与所有 .txt 尾巴，只留主名
    base = _INVIS.sub("", os.path.basename(filename or ""))
    base = re.sub(r"(?:\.(?:txt|text))+$", "", base, flags=re.I)

    m = _BRACKET.search(base)
    if m and not title:
        cand = m.group(1).strip()
        if cand:
            title, title_from = cand, "filename"

    # 3) 文件名：方括号里的名字（[作者]书名 / 书名[作者]）
    rest = _BRACKET.sub("", base)
    for m in _BRACKET_AUTHOR.finditer(rest):
        cand = _clean_author(m.group(1))
        if cand:
            if not author:
                author, author_from = cand, "filename"
            rest = rest.replace(m.group(0), " ")
            break

    # 4) 文件名：「作者：xxx」等标识，只认第一个；正文已有作者时也照样剔出书名
    m = _author_re(author_keys).search(rest)
    if m:
        if not author:
            cand = _clean_author(m.group(1))
            if cand:
                author, author_from = cand, "filename"
        rest = rest.replace(m.group(0), " ")

    rest = _clean_name(rest)
    if rest:
        parts = [p for p in rest.split(" ") if p]
        if not title and parts:
            title, title_from = parts[0], "filename"
        if not author and len(parts) >= 2:
            cand = _clean_author(parts[-1])
            if cand and 1 < len(cand) <= 12:
                author, author_from = cand, "filename"

    return {"title": title.strip(), "author": author,
            "title_from": title_from, "author_from": author_from}


def guess_meta(filename, text):
    """从文件名与正文开头推断 (书名, 作者)，书名兜底为文件名本身。"""
    d = guess_meta_detail(filename, text)
    title = d["title"] or _clean_name(os.path.splitext(os.path.basename(filename or ""))[0])
    return (title.strip() or os.path.basename(filename or "")), d["author"]


def count_chars(text):
    """统计非空白字符数（比逐字符循环快得多）。"""
    return len(text) - sum(text.count(c) for c in "\n\r\t 　\xa0")


def load_text(path):
    """按需读取全文。批量场景下不要长期持有返回值，避免内存堆积。"""
    with open(path, "rb") as f:
        data = f.read()
    return decode(data, detect_bytes(data))


def scan_file(path, with_text=False):
    """读取一个文件的元信息（默认不保留全文，避免几百本撑爆内存）。

    一次读入同时得到 md5 / 体积 / 编码 / 字数，不重复 IO。
    """
    with open(path, "rb") as f:
        data = f.read()
    enc = detect_bytes(data)
    text = decode(data, enc)
    info = {
        "path": path,
        "name": os.path.basename(path),
        "size": len(data),
        "md5": hashlib.md5(data).hexdigest(),
        "enc": enc,
        "chars": count_chars(text),
        "mtime": os.path.getmtime(path),
        "chapters": -1,
        "sel": True,
    }
    title, author = guess_meta(path, text)
    info["title"] = title
    info["author"] = author
    if with_text:
        info["text"] = text
    return info


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 清洗规则

URL_RE = re.compile(r"(https?://|www\.|ftp://|[a-z0-9\-]+\.(com|net|org|cn|cc|me|la|tv|info|xyz)\b)", re.I)
# 强特征宣传词：正文里几乎不会出现，命中即可疑
SITE_RE = re.compile(
    r"(记住本站|收藏本站|本站地址|书籍地址|笔趣|顶点小说|手机阅读|"
    r"wap\.|txt下载|TXT下载|小说下载网|免费小说网|最新网址|首发网址|"
    r"天才一秒|无弹窗|更新最快|手打版|本章免费)",
    re.I,
)
# 说明：请记住 / 请收藏 / 请到 / 转载请 / 手机版 / 百度搜索 这些词在正常对话里也会出现
# （“把客人请到屋里”“你百度搜索一下”），所以不再作为单独判定广告的依据。
# 单独的 m. 同理去掉：它会把 "Mr." "com." 之类误判，手机域名靠 URL_RE 就能识别。

NAV_RE = re.compile(r"^\s*(上一页|下一页|上一章|下一章|返回目录|返回书城|加入书架|加入书签|"
                    r"推荐票|月票|投推荐|打赏|本章未完|未完待续|<--|-->|=====|-----)")
MOJI_RE = re.compile(r"[\ufffd\ue000-\uf8ff]|[\x00-\x08\x0b\x0c\x0e-\x1f]")

# 判定“这行是不是广告”用的尺子
AD_TAIL_MAX = 64    # 网址距离行尾超过这么多字，就不当成粘在段尾的广告
AD_MIN_BODY = 6     # 广告前面至少要有这么多字，才算“正文 + 广告尾巴”
AD_SHORT = 32       # 整行短于这个字数、前面又是推广语，就判为广告行
AD_TINY = 24        # 前面几乎没正文时，整行短于这个字数才丢
AD_AFTER = 10       # 网址后面还跟着这么多字，说明网址夹在句子中间
AD_HEAD_RE = re.compile(
    r"(记住|收藏|网址|本站|书站|手机阅读|手机版|最新章|一秒|更新最快|"
    r"推荐票|月票|笔趣阁|顶点|全文阅读|小说网|手打)"
)
_SLIM_RE = re.compile(
    r"[\s\u3000，,。.！!？?、；;：:…\-—－_“”‘’\"'（）()《》〈〉【】\[\]·~@#%&*+=|/\\<>^_]"
)

RULES = [
    {"id": "url", "name": "含网址的行", "name_en": "Lines with URLs",
     "tip": "删除只有网址的行；网址若粘在段尾，只裁掉网址本身，正文保留",
     "tip_en": "Removes URL-only lines; if a URL is glued to the end of a paragraph, only the URL is trimmed"},
    {"id": "site", "name": "站点宣传行", "name_en": "Site promo lines",
     "tip": "删除“请收藏本站”“笔趣阁”这类推广行；推广语贴在段尾时只裁掉那一截",
     "tip_en": "Removes promo lines; if the promo is glued to a paragraph end, only that part is trimmed"},
    {"id": "nav", "name": "翻页导航残留", "name_en": "Pagination leftovers",
     "tip": "删除“上一页”“本章未完”等导航整行", "tip_en": "Remove nav-only lines such as \u201cprev page\u201d / \u201cto be continued\u201d"},
    {"id": "moji", "name": "乱码行", "name_en": "Corrupted lines",
     "tip": "删除含替换符或不可见控制符的整行", "tip_en": "Remove lines with replacement or invisible control characters"},
    {"id": "blank", "name": "删除所有空行", "name_en": "Delete all blank lines",
     "tip": "不留任何空行（与下一项二选一）", "tip_en": "Remove every blank line (pick either this or the next)"},
    {"id": "blank2", "name": "压缩连续空行", "name_en": "Collapse blank runs",
     "tip": "多个空行合并为一个，保留段落间隔", "tip_en": "Merge consecutive blanks into one, keep paragraph spacing"},
    {"id": "trim", "name": "去除行首尾空白", "name_en": "Trim line ends",
     "tip": "清掉每行开头结尾的空格与制表符", "tip_en": "Strip spaces & tabs at the start/end of every line"},
    {"id": "half", "name": "全角转半角", "name_en": "Full-width to half-width",
     "tip": "只转全角数字与字母，中文标点保持原样", "tip_en": "Convert full-width digits & letters only; keep Chinese punctuation"},
    {"id": "indent", "name": "段落首行缩进两格", "name_en": "Indent paragraphs",
     "tip": "给每个非空段落开头补两个全角空格", "tip_en": "Prepend two full-width spaces to each non-empty paragraph"},
    {"id": "jsdup", "name": "简繁重复行（保留简体）",
     "name_en": "Duplicate simplified/traditional lines",
     "tip": "同一段正文同时有简体和繁体两份时，删掉繁体那份；相邻成对、整章重复都能认。全繁体的书不受影响，默认关闭",
     "tip_en": "When a paragraph exists in both simplified and traditional, drop the traditional copy. Handles alternating lines and whole duplicated chapters; traditional-only books are untouched. Off by default"},
]

DEFAULT_ON = ["url", "site", "nav", "moji", "blank2", "trim", "half"]


T2S_PAIRS = (
    "㑯㑔㑳㑇㑶㐹㓨刾㘚㘎㜄㚯㜏㛣㠏㟆㥮㤘㩜㨫㩳㧐㩵擜䁻䀥䃮鿎䊷䌶䋙䌺䋚䌻䋹䌿䋻䌾䍦䍠䎱䎬䙡䙌䜀䜧䝼䞍䥇䦂䥑鿏䥱䥾䦛䦶䦟䦷䯀䯅䰾鲃䱷䲣䱽䲝䲁鳚䲘鳤䴉鹮丟丢並并乾干亂乱亙亘亞亚佇伫佈布佔占併并來来侖仑侶侣侷局俁俣係系俔伣俠侠俥伡俬私倀伥倆俩倈俫倉仓"
    "個个們们倖幸倫伦倲㑈偉伟偑㐽側侧偵侦偽伪傌㐷傑杰傖伧傘伞備备傢家傭佣傯偬傳传傴伛債债傷伤傾倾僂偻僅仅僉佥僑侨僕仆僞伪僥侥僨偾僱雇價价儀仪儁俊儂侬億亿儈侩儉俭儎傤儐傧儔俦儕侪儘尽償偿優优儲储儷俪儸㑩儺傩儻傥儼俨兇凶兌兑兒儿兗兖內内兩两冊册冑胄"
    "冪幂凈净凍冻凜凛凱凯別别刪删剄刭則则剋克剎刹剗刬剛刚剝剥剮剐剴剀創创剷铲劃划劄札劇剧劉刘劊刽劌刿劍剑劏㓥劑剂劚㔉勁劲動动務务勛勋勝胜勞劳勢势勩勚勱劢勳勋勵励勸劝勻匀匭匦匯汇匱匮區区協协卹恤卻却卽即厙厍厠厕厤历厭厌厲厉厴厣參参叄叁叢丛吒咤吳吴"
    "吶呐呂吕咼呙員员唄呗唸念問问啓启啞哑啟启啢唡喎㖞喚唤喪丧喫吃喬乔單单喲哟嗆呛嗇啬嗊唝嗎吗嗚呜嗩唢嗶哔嘆叹嘍喽嘓啯嘔呕嘖啧嘗尝嘜唛嘩哗嘮唠嘯啸嘰叽嘵哓嘸呒嘽啴噁恶噓嘘噚㖊噝咝噠哒噥哝噦哕噯嗳噲哙噴喷噸吨噹当嚀咛嚇吓嚌哜嚐尝嚕噜嚙啮嚥咽嚦呖嚨咙"
    "嚮向嚲亸嚳喾嚴严嚶嘤囀啭囁嗫囂嚣囅冁囈呓囉啰囌苏囑嘱囪囱圇囵國国圍围園园圓圆圖图團团垻坝埡垭埰采執执堅坚堊垩堖垴堝埚堯尧報报場场塊块塋茔塏垲塒埘塗涂塚冢塢坞塤埙塵尘塹堑墊垫墜坠墮堕墰坛墳坟墶垯墻墙墾垦壇坛壋垱壎埙壓压壘垒壙圹壚垆壜坛壞坏壟垄"
    "壠垅壢坜壩坝壪塆壯壮壺壶壼壸壽寿夠够夢梦夥伙夾夹奐奂奧奥奩奁奪夺奬奖奮奋奼姹妝妆姍姗姦奸娛娱婁娄婦妇婭娅媧娲媯妫媰㛀媼媪媽妈嫋袅嫗妪嫵妩嫺娴嫻娴嫿婳嬀妫嬃媭嬈娆嬋婵嬌娇嬙嫱嬡嫒嬤嬷嬪嫔嬰婴嬸婶孃娘孋㛤孌娈孫孙學学孿孪宮宫寀采寢寝實实寧宁審审"
    "寫写寬宽寵宠寶宝將将專专尋寻對对導导尷尴屆届屍尸屓屃屜屉屢屡層层屨屦屬属岡冈峯峰峴岘島岛峽峡崍崃崑昆崗岗崙仑崢峥崬岽嵐岚嵗岁嵾㟥嶁嵝嶄崭嶇岖嶔嵚嶗崂嶠峤嶢峣嶧峄嶨峃嶮崄嶸嵘嶺岭嶼屿嶽岳巋岿巒峦巔巅巖岩巰巯巹卺帥帅師师帳帐帶带幀帧幃帏幓㡎幗帼"
    "幘帻幟帜幣币幫帮幬帱幷并幹干幾几庫库廁厕廂厢廄厩廈厦廎庼廕荫廚厨廝厮廟庙廠厂廡庑廢废廣广廩廪廬庐廳厅弒弑弔吊弳弪張张強强彆别彈弹彌弥彎弯彔录彙汇彠彟彥彦彫雕彲彨彿佛後后徑径從从徠徕復复徵征徹彻恆恒恥耻悅悦悞悮悵怅悶闷悽凄惡恶惱恼惲恽惻恻愛爱"
    "愜惬愨悫愴怆愷恺愾忾慄栗態态慍愠慘惨慚惭慟恸慣惯慤悫慪怄慫怂慮虑慳悭慶庆慺㥪慼戚慾欲憂忧憊惫憐怜憑凭憒愦憖慭憚惮憤愤憫悯憮怃憲宪憶忆懇恳應应懌怿懍懔懞蒙懟怼懣懑懤㤽懨恹懲惩懶懒懷怀懸悬懺忏懼惧懾慑戀恋戇戆戔戋戧戗戩戬戰战戱戯戲戏戶户扞捍拋抛"
    "拚拼挩捝挱挲挾挟捨舍捫扪捱挨捲卷掃扫掄抡掆㧏掗挜掙挣掛挂採采揀拣揚扬換换揮挥揯搄損损搖摇搗捣搧扇搵揾搶抢摑掴摜掼摟搂摯挚摳抠摶抟摺折摻掺撈捞撏挦撐撑撓挠撝㧑撟挢撣掸撥拨撫抚撲扑撳揿撻挞撾挝撿捡擁拥擄掳擇择擊击擋挡擓㧟擔担據据擠挤擡抬擣捣擬拟"
    "擯摈擰拧擱搁擲掷擴扩擷撷擺摆擻擞擼撸擽㧰擾扰攄摅攆撵攏拢攔拦攖撄攙搀攛撺攜携攝摄攢攒攣挛攤摊攪搅攬揽敎教敓敚敗败敘叙敵敌數数斂敛斃毙斆敩斕斓斬斩斷断於于旂旗旣既昇升時时晉晋晝昼暈晕暉晖暘旸暢畅暫暂曄晔曆历曇昙曉晓曏向曖暧曠旷曨昽曬晒書书會会"
    "朧胧朮术東东枴拐柵栅柺拐査查桿杆梔栀梘枧條条梟枭梲棁棄弃棊棋棖枨棗枣棟栋棡㭎棧栈棲栖棶梾椏桠椲㭏楊杨楓枫楨桢業业極极榘矩榦干榪杩榮荣榲榅榿桤構构槍枪槓杠槤梿槧椠槨椁槮椮槳桨槶椢槼椝樁桩樂乐樅枞樑梁樓楼標标樞枢樢㭤樣样樧榝樫㭴樳桪樸朴樹树樺桦"
    "樿椫橈桡橋桥機机橢椭橫横檁檩檉柽檔档檜桧檟槚檢检檣樯檮梼檯台檳槟檸柠檻槛櫃柜櫓橹櫚榈櫛栉櫝椟櫞橼櫟栎櫥橱櫧槠櫨栌櫪枥櫫橥櫬榇櫱蘖櫳栊櫸榉櫻樱欄栏欅榉權权欏椤欒栾欖榄欞棂欽钦歎叹歐欧歟欤歡欢歲岁歷历歸归歿殁殘残殞殒殤殇殨㱮殫殚殭僵殮殓殯殡殰㱩"
    "殲歼殺杀殻壳殼壳毀毁毆殴毿毵氂牦氈毡氌氇氣气氫氢氬氩氳氲氾泛汎泛汙污決决沒没沖冲況况泝溯洩泄洶汹浹浃涇泾涗涚涼凉淒凄淚泪淥渌淨净淩凌淪沦淵渊淶涞淺浅渙涣減减渢沨渦涡測测渾浑湊凑湞浈湧涌湯汤溈沩準准溝沟溫温溮浉溳涢溼湿滄沧滅灭滌涤滎荥滙汇滬沪"
    "滯滞滲渗滷卤滸浒滻浐滾滚滿满漁渔漊溇漚沤漢汉漣涟漬渍漲涨漵溆漸渐漿浆潁颍潑泼潔洁潙沩潚㴋潛潜潤润潯浔潰溃潷滗潿涠澀涩澆浇澇涝澐沄澗涧澠渑澤泽澦滪澩泶澮浍澱淀澾㳠濁浊濃浓濄㳡濕湿濘泞濚溁濛蒙濜浕濟济濤涛濧㳔濫滥濰潍濱滨濺溅濼泺濾滤瀂澛瀅滢瀆渎"
    "瀇㲿瀉泻瀋沈瀏浏瀕濒瀘泸瀝沥瀟潇瀠潆瀦潴瀧泷瀨濑瀰弥瀲潋瀾澜灃沣灄滠灑洒灕漓灘滩灝灏灡㳕灣湾灤滦灧滟灩滟災灾為为烏乌烴烃無无煉炼煒炜煙烟煢茕煥焕煩烦煬炀煱㶽熅煴熒荧熗炝熱热熲颎熾炽燁烨燈灯燉炖燒烧燙烫燜焖營营燦灿燬毁燭烛燴烩燶㶶燻熏燼烬燾焘"
    "爍烁爐炉爛烂爭争爲为爺爷爾尔牀床牆墙牘牍牴抵牽牵犖荦犛牦犢犊犧牺狀状狹狭狽狈猙狰猶犹猻狲獁犸獃呆獄狱獅狮獎奖獨独獪狯獫猃獮狝獰狞獱㺍獲获獵猎獷犷獸兽獺獭獻献獼猕玀猡現现琱雕琺珐琿珲瑋玮瑒玚瑣琐瑤瑶瑩莹瑪玛瑲玱璉琏璡琎璣玑璦瑷璫珰璯㻅環环璵玙"
    "璸瑸璽玺璿璇瓊琼瓏珑瓔璎瓚瓒甌瓯甕瓮產产産产畝亩畢毕畫画異异畵画當当疇畴疊叠痙痉痠酸痾疴瘂痖瘋疯瘍疡瘓痪瘞瘗瘡疮瘧疟瘮瘆瘲疭瘺瘘瘻瘘療疗癆痨癇痫癉瘅癒愈癘疠癟瘪癡痴癢痒癤疖癥症癧疬癩癞癬癣癭瘿癮瘾癰痈癱瘫癲癫發发皁皂皚皑皰疱皸皲皺皱盃杯盜盗"
    "盞盏盡尽監监盤盘盧卢盪荡眞真眥眦眾众睏困睜睁睞睐瞘眍瞜䁖瞞瞒瞶瞆瞼睑矇蒙矓眬矚瞩矯矫硃朱硜硁硤硖硨砗硯砚碕埼碩硕碭砀碸砜確确碼码碽䂵磑硙磚砖磠硵磣碜磧碛磯矶磽硗磾䃅礄硚礎础礙碍礦矿礪砺礫砾礬矾礱砻祕秘祿禄禍祸禎祯禕祎禡祃禦御禪禅禮礼禰祢禱祷"
    "禿秃秈籼稅税稈秆稏䅉稜棱稟禀種种稱称穀谷穇䅟穌稣積积穎颖穠秾穡穑穢秽穩稳穫获穭穞窩窝窪洼窮穷窯窑窵窎窶窭窺窥竄窜竅窍竇窦竈灶竊窃竪竖競竞筆笔筍笋筧笕筴䇲箇个箋笺箏筝箚札節节範范築筑篋箧篔筼篠筿篤笃篩筛篳筚簀箦簍篓簑蓑簞箪簡简簣篑簫箫簹筜簽签"
    "簾帘籃篮籌筹籔䉤籙箓籛篯籜箨籟籁籠笼籤签籩笾籪簖籬篱籮箩籲吁粵粤糉粽糝糁糞粪糧粮糰团糲粝糴籴糶粜糹纟糾纠紀纪紂纣約约紅红紆纡紇纥紈纨紉纫紋纹納纳紐纽紓纾純纯紕纰紖纼紗纱紘纮紙纸級级紛纷紜纭紝纴紡纺紬䌷紮扎細细紱绂紲绁紳绅紵纻紹绍紺绀紼绋紿绐"
    "絀绌終终絃弦組组絅䌹絆绊絎绗結结絕绝絛绦絝绔絞绞絡络絢绚給给絨绒絰绖統统絲丝絳绛絶绝絹绢綁绑綃绡綆绠綈绨綉绣綌绤綏绥綐䌼綑捆經经綜综綞缍綠绿綢绸綣绻綫线綬绶維维綯绹綰绾綱纲網网綳绷綴缀綵彩綸纶綹绺綺绮綻绽綽绰綾绫綿绵緄绲緇缁緊紧緋绯緑绿緒绪"
    "緓绬緔绱緗缃緘缄緙缂線线緝缉緞缎締缔緡缗緣缘緦缌編编緩缓緬缅緯纬緱缑緲缈練练緶缏緹缇緻致緼缊縈萦縉缙縊缢縋缒縐绉縑缣縕缊縗缞縛缚縝缜縞缟縟缛縣县縧绦縫缝縭缡縮缩縱纵縲缧縳䌸縴纤縵缦縶絷縷缕縹缥總总績绩繃绷繅缫繆缪繒缯織织繕缮繚缭繞绕繡绣繢缋"
    "繩绳繪绘繫系繭茧繮缰繯缳繰缲繳缴繸䍁繹绎繼继繽缤繾缱繿䍀纇颣纈缬纊纩續续纍累纏缠纓缨纔才纖纤纘缵纜缆缽钵罃䓨罈坛罌罂罎坛罰罚罵骂罷罢羅罗羆罴羈羁羋芈羣群羥羟羨羡義义羶膻習习翫玩翬翚翹翘翽翙耬耧耮耢聖圣聞闻聯联聰聪聲声聳耸聵聩聶聂職职聹聍聽听"
    "聾聋肅肃脅胁脈脉脛胫脣唇脩修脫脱脹胀腎肾腖胨腡脶腦脑腫肿腳脚腸肠膃腽膕腘膚肤膞䏝膠胶膩腻膽胆膾脍膿脓臉脸臍脐臏膑臘腊臚胪臟脏臠脔臢臜臥卧臨临臺台與与興兴舉举舊旧舖铺舘馆艙舱艤舣艦舰艫舻艱艰艷艳芻刍苧苎茲兹荊荆莊庄莖茎莢荚莧苋華华菴庵菸烟萇苌"
    "萊莱萬万萴荝萵莴葉叶葒荭葤荮葦苇葯药葷荤蒐搜蒓莼蒔莳蒕蒀蒞莅蒼苍蓀荪蓆席蓋盖蓮莲蓯苁蓴莼蓽荜蔔卜蔘参蔞蒌蔣蒋蔥葱蔦茑蔭荫蕁荨蕆蒇蕎荞蕒荬蕓芸蕕莸蕘荛蕢蒉蕩荡蕪芜蕭萧蕷蓣薀蕰薈荟薊蓟薌芗薑姜薔蔷薘荙薟莶薦荐薩萨薴苧薵䓓薹苔薺荠藍蓝藎荩藝艺藥药"
    "藪薮藭䓖藴蕴藶苈藹蔼藺蔺蘀萚蘄蕲蘆芦蘇苏蘊蕴蘋苹蘚藓蘞蔹蘢茏蘭兰蘺蓠蘿萝虆蔂處处虛虚虜虏號号虧亏虯虬蛺蛱蛻蜕蜆蚬蝕蚀蝟猬蝦虾蝨虱蝸蜗螄蛳螞蚂螢萤螮䗖螻蝼螿螀蟄蛰蟈蝈蟎螨蟣虮蟬蝉蟯蛲蟲虫蟶蛏蟻蚁蠁蚃蠅蝇蠆虿蠍蝎蠐蛴蠑蝾蠔蚝蠟蜡蠣蛎蠨蟏蠱蛊蠶蚕"
    "蠻蛮衆众衊蔑術术衕同衚胡衛卫衝冲袞衮袷夹裊袅裏里補补裝装裡里製制複复褌裈褘袆褲裤褳裢褸褛褻亵襇裥襉裥襏袯襖袄襝裣襠裆襤褴襪袜襬摆襯衬襲袭襴襕覈核見见覎觃規规覓觅視视覘觇覡觋覥觍覦觎親亲覬觊覯觏覲觐覷觑覺觉覽览覿觌觀观觴觞觶觯觸触訁讠訂订訃讣"
    "計计訊讯訌讧討讨訐讦訒讱訓训訕讪訖讫託托記记訛讹訝讶訟讼訢䜣訣诀訥讷訩讻訪访設设許许訴诉訶诃診诊註注証证詁诂詆诋詎讵詐诈詒诒詔诏評评詖诐詗诇詘诎詛诅詞词詠咏詡诩詢询詣诣試试詩诗詫诧詬诟詭诡詮诠詰诘話话該该詳详詵诜詼诙詿诖誄诔誅诛誆诓誇夸誌志"
    "認认誑诳誒诶誕诞誘诱誚诮語语誠诚誡诫誣诬誤误誥诰誦诵誨诲說说説说誰谁課课誶谇誹诽誼谊誾訚調调諂谄諄谆談谈諉诿請请諍诤諏诹諑诼諒谅論论諗谂諛谀諜谍諝谞諞谝諡谥諢诨諤谔諦谛諧谐諫谏諭谕諮咨諱讳諳谙諶谌諷讽諸诸諺谚諼谖諾诺謀谋謁谒謂谓謄誊謅诌謊谎"
    "謎谜謐谧謔谑謖谡謗谤謙谦謚谥講讲謝谢謠谣謡谣謨谟謫谪謬谬謭谫謳讴謹谨謾谩譁哗證证譎谲譏讥譖谮識识譙谯譚谭譜谱譟噪譫谵譭毁譯译議议譴谴護护譸诪譽誉譾谫讀读讅谉變变讋詟讌䜩讎雠讒谗讓让讕谰讖谶讚赞讜谠讞谳谿溪豈岂豎竖豐丰豔艳豬猪豶豮貍狸貓猫貙䝙"
    "貝贝貞贞貟贠負负財财貢贡貧贫貨货販贩貪贪貫贯責责貯贮貰贳貲赀貳贰貴贵貶贬買买貸贷貺贶費费貼贴貽贻貿贸賀贺賁贲賂赂賃赁賄贿賅赅資资賈贾賊贼賑赈賒赊賓宾賕赇賙赒賚赉賜赐賞赏賠赔賡赓賢贤賣卖賤贱賦赋賧赕質质賫赍賬账賭赌賰䞐賴赖賵赗賺赚賻赙購购賽赛"
    "賾赜贄贽贅赘贇赟贈赠贊赞贋赝贍赡贏赢贐赆贓赃贔赑贖赎贗赝贛赣贜赃赬赪趕赶趙赵趨趋趲趱跡迹踐践踰逾踴踊蹌跄蹕跸蹟迹蹠跖蹣蹒蹤踪蹺跷躂跶躉趸躊踌躋跻躍跃躎䟢躑踯躒跞躓踬躕蹰躚跹躡蹑躥蹿躦躜躪躏軀躯車车軋轧軌轨軍军軑轪軒轩軔轫軛轭軟软軤轷軫轸軲轱"
    "軸轴軹轵軺轺軻轲軼轶軾轼較较輅辂輇辁輈辀載载輊轾輒辄輓挽輔辅輕轻輛辆輜辎輝辉輞辋輟辍輥辊輦辇輩辈輪轮輬辌輯辑輳辏輸输輻辐輼辒輾辗輿舆轀辒轂毂轄辖轅辕轆辘轉转轍辙轎轿轔辚轟轰轡辔轢轹轤轳辦办辭辞辮辫辯辩農农迴回逕径這这連连週周進进遊游運运過过"
    "達达違违遙遥遜逊遞递遠远遡溯適适遲迟遶绕遷迁選选遺遗遼辽邁迈還还邇迩邊边邏逻邐逦郟郏郵邮鄆郓鄉乡鄒邹鄔邬鄖郧鄧邓鄭郑鄰邻鄲郸鄴邺鄶郐鄺邝酇酂酈郦醃腌醖酝醜丑醞酝醟蒏醣糖醫医醬酱醱酦釀酿釁衅釃酾釅酽釋释釐厘釒钅釓钆釔钇釕钌釗钊釘钉釙钋針针釣钓"
    "釤钐釦扣釧钏釩钒釵钗釷钍釹钕釺钎釾䥺鈀钯鈁钫鈃钘鈄钭鈅钥鈈钚鈉钠鈍钝鈎钩鈐钤鈑钣鈒钑鈔钞鈕钮鈞钧鈡钟鈣钙鈥钬鈦钛鈧钪鈮铌鈰铈鈳钶鈴铃鈷钴鈸钹鈹铍鈺钰鈽钸鈾铀鈿钿鉀钾鉅巨鉆钻鉈铊鉉铉鉋铇鉍铋鉑铂鉕钷鉗钳鉚铆鉛铅鉞钺鉢钵鉤钩鉦钲鉬钼鉭钽鉳锫鉶铏"
    "鉸铰鉺铒鉻铬鉿铪銀银銃铳銅铜銍铚銑铣銓铨銖铢銘铭銚铫銛铦銜衔銠铑銣铷銥铱銦铟銨铵銩铥銪铕銫铯銬铐銱铞銳锐銷销銹锈銻锑銼锉鋁铝鋃锒鋅锌鋇钡鋌铤鋏铗鋒锋鋙铻鋝锊鋟锓鋣铘鋤锄鋥锃鋦锔鋨锇鋩铓鋪铺鋭锐鋮铖鋯锆鋰锂鋱铽鋶锍鋸锯鋼钢錁锞錄录錆锖錇锫錈锩"
    "錏铔錐锥錒锕錕锟錘锤錙锱錚铮錛锛錟锬錠锭錡锜錢钱錦锦錨锚錩锠錫锡錮锢錯错録录錳锰錶表錸铼錼镎鍀锝鍁锨鍃锪鍅钫鍆钔鍇锴鍈锳鍊炼鍋锅鍍镀鍔锷鍘铡鍚钖鍛锻鍠锽鍤锸鍥锲鍩锘鍬锹鍰锾鍵键鍶锶鍺锗鍼针鍾钟鎂镁鎄锿鎇镅鎊镑鎌镰鎔镕鎖锁鎘镉鎚锤鎛镈鎡镃鎢钨"
    "鎣蓥鎦镏鎧铠鎩铩鎪锼鎬镐鎭镇鎮镇鎰镒鎲镋鎳镍鎵镓鎶鿔鎸镌鎿镎鏃镞鏇旋鏈链鏌镆鏍镙鏐镠鏑镝鏗铿鏘锵鏜镗鏝镘鏞镛鏟铲鏡镜鏢镖鏤镂鏨錾鏰镚鏵铧鏷镤鏹镪鏺䥽鏽锈鐃铙鐋铴鐐镣鐒铹鐓镦鐔镡鐘钟鐙镫鐝镢鐠镨鐥䦅鐦锎鐧锏鐨镄鐫镌鐮镰鐯䦃鐲镯鐳镭鐵铁鐶镮鐸铎"
    "鐺铛鐿镱鑄铸鑊镬鑌镔鑑鉴鑒鉴鑔镲鑕锧鑞镴鑠铄鑣镳鑥镥鑭镧鑰钥鑱镵鑲镶鑷镊鑹镩鑼锣鑽钻鑾銮鑿凿钁镢钂镋長长門门閂闩閃闪閆闫閈闬閉闭開开閌闶閎闳閏闰閑闲閒闲間间閔闵閘闸閡阂閣阁閤合閥阀閨闺閩闽閫阃閬阆閭闾閱阅閲阅閶阊閹阉閻阎閼阏閽阍閾阈閿阌闃阒"
    "闆板闇暗闈闱闊阔闋阕闌阑闍阇闐阗闒阘闓闿闔阖闕阙闖闯關关闞阚闠阓闡阐闢辟闤阛闥闼陘陉陝陕陞升陣阵陰阴陳陈陸陆陽阳隉陧隊队階阶隕陨際际隨随險险隯陦隱隐隴陇隸隶隻只雋隽雖虽雙双雛雏雜杂雞鸡離离難难雲云電电霑沾霢霡霧雾霽霁靂雳靄霭靆叇靈灵靉叆靚靓"
    "靜静靝靔靦腼靨靥鞏巩鞝绱鞦秋鞽鞒韁缰韃鞑韆千韉鞯韋韦韌韧韍韨韓韩韙韪韜韬韝鞲韞韫韻韵響响頁页頂顶頃顷項项順顺頇顸須须頊顼頌颂頎颀頏颃預预頑顽頒颁頓顿頗颇領领頜颌頡颉頤颐頦颏頭头頮颒頰颊頲颋頴颕頷颔頸颈頹颓頻频頽颓顆颗題题額额顎颚顏颜顒颙顓颛"
    "顔颜願愿顙颡顛颠類类顢颟顥颢顧顾顫颤顬颥顯显顰颦顱颅顳颞顴颧風风颭飐颮飑颯飒颱台颳刮颶飓颸飔颺飏颻飖颼飕飀飗飄飘飆飙飈飚飛飞飠饣飢饥飣饤飥饦飩饨飪饪飫饫飭饬飯饭飱飧飲饮飴饴飼饲飽饱飾饰飿饳餃饺餄饸餅饼餈糍餉饷養养餌饵餎饹餏饻餑饽餒馁餓饿餕馂"
    "餖饾餘余餚肴餛馄餜馃餞饯餡馅館馆餬糊餱糇餳饧餵喂餶馉餷馇餺馎餼饩餾馏餿馊饁馌饃馍饅馒饈馐饉馑饊馓饋馈饌馔饑饥饒饶饗飨饜餍饞馋饢馕馬马馭驭馮冯馱驮馳驰馴驯馹驲駁驳駐驻駑驽駒驹駔驵駕驾駘骀駙驸駛驶駝驼駟驷駡骂駢骈駭骇駰骃駱骆駸骎駿骏騁骋騂骍騅骓"
    "騌骔騍骒騎骑騏骐騖骛騙骗騤骙騧䯄騫骞騭骘騮骝騰腾騶驺騷骚騸骟騾骡驀蓦驁骜驂骖驃骠驄骢驅驱驊骅驌骕驍骁驏骣驕骄驗验驚惊驛驿驟骤驢驴驤骧驥骥驦骦驪骊驫骉骯肮髏髅髒脏體体髕髌髖髋髮发鬆松鬍胡鬚须鬢鬓鬥斗鬧闹鬨哄鬩阋鬮阄鬱郁鬹鬶魎魉魘魇魚鱼魛鱽魢鱾"
    "魨鲀魯鲁魴鲂魷鱿魺鲄鮁鲅鮃鲆鮊鲌鮋鲉鮍鲏鮎鲇鮐鲐鮑鲍鮒鲋鮓鲊鮚鲒鮜鲘鮝鲞鮞鲕鮣䲟鮦鲖鮪鲔鮫鲛鮭鲑鮮鲜鮳鲓鮶鲪鮺鲝鯀鲧鯁鲠鯇鲩鯉鲤鯊鲨鯒鲬鯔鲻鯕鲯鯖鲭鯗鲞鯛鲷鯝鲴鯡鲱鯢鲵鯤鲲鯧鲳鯨鲸鯪鲮鯫鲰鯰鲶鯴鲺鯷鳀鯽鲫鯿鳊鰁鳈鰂鲗鰃鳂鰆䲠鰈鲽鰉鳇鰌䲡鰍鳅"
    "鰏鲾鰐鳄鰒鳆鰓鳃鰛鳁鰜鳒鰟鳑鰠鳋鰣鲥鰥鳏鰧䲢鰨鳎鰩鳐鰭鳍鰮鳁鰱鲢鰲鳌鰳鳓鰵鳘鰷鲦鰹鲣鰺鲹鰻鳗鰼鳛鰾鳔鱂鳉鱅鳙鱈鳕鱉鳖鱒鳟鱔鳝鱖鳜鱗鳞鱘鲟鱝鲼鱟鲎鱠鲙鱣鳣鱤鳡鱧鳢鱨鲿鱭鲚鱯鳠鱷鳄鱸鲈鱺鲡鳥鸟鳧凫鳩鸠鳬凫鳲鸤鳳凤鳴鸣鳶鸢鳾䴓鴆鸩鴇鸨鴉鸦鴒鸰鴕鸵"
    "鴛鸳鴝鸲鴞鸮鴟鸱鴣鸪鴦鸯鴨鸭鴯鸸鴰鸹鴴鸻鴷䴕鴻鸿鴿鸽鵁䴔鵂鸺鵃鸼鵐鹀鵑鹃鵒鹆鵓鹁鵜鹈鵝鹅鵠鹄鵡鹉鵪鹌鵬鹏鵮鹐鵯鹎鵰雕鵲鹊鵷鹓鵾鹍鶄䴖鶇鸫鶉鹑鶊鹒鶓鹋鶖鹙鶘鹕鶚鹗鶡鹖鶥鹛鶩鹜鶪䴗鶬鸧鶯莺鶲鹟鶴鹤鶹鹠鶺鹡鶻鹘鶼鹣鶿鹚鷀鹚鷁鹢鷂鹞鷄鸡鷉䴘鷊鹝鷓鹧"
    "鷖鹥鷗鸥鷙鸷鷚鹨鷥鸶鷦鹪鷫鹔鷯鹩鷲鹫鷳鹇鷴鹇鷸鹬鷹鹰鷺鹭鷽鸴鸂㶉鸇鹯鸊䴙鸌鹱鸏鹲鸕鸬鸘鹴鸚鹦鸛鹳鸝鹂鸞鸾鹵卤鹹咸鹺鹾鹼碱鹽盐麗丽麥麦麩麸麪面麫面麯曲麴曲麵面麼么麽么黃黄黌黉點点黨党黲黪黴霉黶黡黷黩黽黾黿鼋鼂鼌鼉鼍鼕冬鼴鼹齊齐齋斋齎赍齏齑齒齿"
    "齔龀齕龁齗龂齙龅齜龇齟龃齠龆齡龄齣出齦龈齧啮齪龊齬龉齲龋齶腭齷龌龍龙龎厐龐庞龑䶮龔龚龕龛龜龟鿁䜤鿓鿒"
)

# 简繁两体都在用的字：参与归一、但不算繁体分，避免误删
_AMBI = set("乾著於籍瞭徵")
_T2S = None


def _t2s_map():
    """繁→简单字表，惰性构建一次（只用于比对，不改写正文）。"""
    global _T2S
    if _T2S is None:
        table = {}
        s = T2S_PAIRS
        for i in range(0, len(s) - 1, 2):
            table[s[i]] = s[i + 1]
        _T2S = table
    return _T2S


def _word_char(c):
    k = ord(c)
    if 0x4E00 <= k <= 0x9FFF or 0x3400 <= k <= 0x4DBF:
        return True
    if 0x30 <= k <= 0x39 or 0x41 <= k <= 0x5A or 0x61 <= k <= 0x7A:
        return True
    if 0xFF10 <= k <= 0xFF19 or 0xFF21 <= k <= 0xFF3A or 0xFF41 <= k <= 0xFF5A:
        return True
    return False


def _norm_key(s):
    """归一：繁→简 + 只留文字数字（标点空白不参与，繁体版换标点也认得出）。"""
    t = _t2s_map()
    return "".join(t.get(c, c) for c in s if _word_char(c))


def _trad_score(s):
    t = _t2s_map()
    return sum(1 for c in s if c in t and c not in _AMBI)


def dedupe_script_dup(lines):
    """同一段正文有简繁两份时删繁体那份，返回 (保留的行, 删掉的行)。

    判据与 Web 版一致：
      1) 繁→简归一后文本相同、字面不同、繁体字更多 → 删；
      2) 整章「简体一份 + 繁体一份」时，标题这类没有字形差异的行靠块对齐整块删。
    """
    n = len(lines)
    info = [None] * n
    lowest = {}
    for i, s in enumerate(lines):
        if not s:
            continue
        key = _norm_key(s)
        if not key:
            continue
        score = _trad_score(s)
        info[i] = (key, score)
        best = lowest.get(key)
        if best is None or score < best:
            lowest[key] = score
    gone = set()
    for i, it in enumerate(info):
        if it and lowest[it[0]] < it[1]:
            gone.add(i)
    if gone:
        base = set(gone)          # 第一遍的判定，块补齐时不再改动它
        near = [-1] * n
        last = {}
        for i, it in enumerate(info):
            if not it:
                continue
            prev = last.get(it[0])
            if prev is not None:
                near[i] = prev
            if i not in base:
                last[it[0]] = i
        done = set()
        for j in sorted(base):
            i = near[j]
            if i < 0:
                continue
            d = j - i
            if d <= 0:
                continue

            def paired(k, d=d):
                return (0 <= k < n and 0 <= k + d < n and info[k] and info[k + d]
                        and info[k][0] == info[k + d][0])

            s0 = e0 = i
            while paired(s0 - 1):
                s0 -= 1
            while paired(e0 + 1):
                e0 += 1
            if e0 - s0 + 1 < 2:
                continue                      # 单独一对不足以证明是整块副本
            if not any(lines[k] != lines[k + d] for k in range(s0, e0 + 1)):
                continue                      # 两块字面完全一样 = 原文自身重复，不碰
            if s0 in done:
                continue
            done.add(s0)
            for k in range(s0, e0 + 1):
                t = k + d
                if t not in base:
                    gone.add(t)
    kept, dels = [], []
    for i, s in enumerate(lines):
        if i in gone:
            dels.append(s)
        else:
            kept.append(s)
    return kept, dels


def to_halfwidth(s):
    """只把全角数字与全角字母转成半角；中文标点（，。：；！？等）一律不动。"""
    out = []
    for ch in s:
        code = ord(ch)
        if code == 0x3000:
            out.append(" ")
        elif 0xFF10 <= code <= 0xFF19 or 0xFF21 <= code <= 0xFF3A or 0xFF41 <= code <= 0xFF5A:
            out.append(chr(code - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def _slim(s):
    """去掉空白与常见标点后的字符数，用来衡量这行还剩多少真内容。"""
    return len(_SLIM_RE.sub("", s))


def _ad_split(s, use_url, use_site):
    """判定一行里的广告，返回 (动作, 位置)。

    动作：
      keep — 不当作广告（正文恰好撞到关键词，或网址夹在句子中间）
      cut  — 只从位置处裁掉行尾那一截，前面的正文保留
      drop — 整行都是广告，丢弃

    很多盗版站把网址直接粘在段落末尾（“……偷走的？”WwW.xxx.com），
    旧逻辑按整行删除，会把整本书的正文一起删光，所以这里要分情况。
    """
    mu = URL_RE.search(s) if use_url else None
    ms = SITE_RE.search(s) if use_site else None
    if not mu and not ms:
        return "keep", 0
    site_first = bool(ms) and (not mu or ms.start() <= mu.start())
    if site_first:
        start, end = ms.start(), ms.end()
    else:
        start, end = mu.start(), mu.end()
    head = s[:start]
    body = _slim(head)          # 这段广告前面还剩多少真内容
    total = _slim(s)            # 整行有多少真内容
    if site_first:
        # 命中的是推广语：短行整行删；长行只在推广语贴着行尾时裁掉
        if total < AD_SHORT:
            return "drop", 0
        if body >= AD_MIN_BODY and len(s) - start <= AD_TAIL_MAX:
            return "cut", start
        return "keep", 0
    # 命中的是网址
    if AD_HEAD_RE.search(head) and total < AD_SHORT:
        return "drop", 0            # 网址前面是推广语、整行很短 → 广告行
    if body < AD_MIN_BODY:
        if body == 0 and (total < AD_TINY or AD_HEAD_RE.search(head + s[end:])):
            return "drop", 0        # 网址打头、整行就是广告（前后都是推广语）
        return "keep", 0            # 其余是正文里夹着网址，宁可不动
    # 正文 + 贴行尾的广告尾巴（后面没有接着正文）→ 只裁尾巴
    if _slim(s[end:]) <= AD_AFTER and len(s) - start <= AD_TAIL_MAX:
        return "cut", start
    # 网址夹在长句中间 → 不动
    return "keep", 0


def clean_text(text, enabled, stats=None):
    """按启用的规则清洗文本，返回 (新文本, 删除行数)。

    stats 若传入 dict，会写入 trimmed（只裁了行尾广告、正文得以保留的行数）。
    """
    on = set(enabled or [])
    removed = 0
    trimmed = 0
    out = []
    prev_blank = False
    use_url = "url" in on
    use_site = "site" in on
    for raw in text.splitlines():
        s = raw
        if "trim" in on:
            s = s.strip()
        if "half" in on:
            s = to_halfwidth(s)
        cut = 0
        drop = False
        if use_url or use_site:
            act, pos = _ad_split(s, use_url, use_site)
            if act == "drop":
                drop = True
            elif act == "cut":
                cut = pos
        if not drop and not cut:
            if "nav" in on and NAV_RE.search(s):
                drop = True
            elif "moji" in on and MOJI_RE.search(s):
                drop = True
        if drop:
            removed += 1
            continue
        if cut:
            s = s[:cut].rstrip(" \u3000，,、；;：:")
            if not _slim(s):
                removed += 1
                continue
            trimmed += 1
        if "blank" in on and not s:
            removed += 1
            continue
        if "blank2" in on and not s:
            if prev_blank:
                removed += 1
                continue
            prev_blank = True
            out.append("")
            continue
        prev_blank = False
        if "indent" in on and s:
            s = "　　" + s
        out.append(s)
    # 简繁重复行：放在缩进之后、掐首尾空行之前，与 Web 版顺序一致
    jsdup_n = 0
    if "jsdup" in on and out:
        kept, dels = dedupe_script_dup(out)
        if dels:
            jsdup_n = len(dels)
            removed += jsdup_n
            out = kept
    # 去掉首尾空行：用指针扫描避免 pop(0) 在大文本上的 O(n²)
    start = 0
    while start < len(out) and not out[start]:
        start += 1
    end = len(out)
    while end > start and not out[end - 1]:
        end -= 1
    if start or end != len(out):
        out = out[start:end]
    if stats is not None:
        stats["removed"] = removed
        stats["trimmed"] = trimmed
        stats["jsdup"] = jsdup_n
    return "\n".join(out) + ("\n" if out else ""), removed


# ---------------------------------------------------------------- 分章

CHAPTER_PATTERNS = [
    r"第\s*[0-9０-９零〇一二三四五六七八九十百千万两]{1,15}\s*[章节節回卷篇集部]\s*[^\n]{0,40}",
    r"(?:^|\s)(?:卷|Chapter|CHAPTER|chapter)\s*[0-9０-９零〇一二三四五六七八九十百千万]{1,15}[^\n]{0,40}",
    r"(?:序章|序言|楔子|引子|尾声|後记|后记|番外|终章|結局|结局|完本)[^\n]{0,40}",
]
MAX_TITLE_LEN = 50


def split_chapters(text, custom=None):
    """切分章节，返回 [(标题, 正文)]。

    custom 非空时只使用自定义正则，否则使用内置中文规则库。
    """
    if custom:
        try:
            re.compile(custom)
        except re.error:
            raise ValueError("自定义章节正则无效，请检查语法")
        pats = [custom]
    else:
        pats = CHAPTER_PATTERNS
    chapters = []
    cur_title = "开篇"
    buf = []
    for raw in text.splitlines():
        s = raw.strip()
        hit = None
        # 以句号结尾的通常是正文而非标题，避免“序章内容。”这类误判
        if s and len(s) <= MAX_TITLE_LEN and not s.endswith("。"):
            for p in pats:
                if re.match(p, s):
                    hit = s
                    break
        if hit is not None:
            body = "\n".join(buf).strip()
            if body:
                chapters.append((cur_title, body))
                cur_title = hit
            else:
                # 连续标题或误判：合并标题，绝不丢弃已有的标题文字
                cur_title = hit if cur_title == "开篇" else cur_title + " " + hit
            buf = []
        else:
            buf.append(raw)
    body = "\n".join(buf).strip()
    if body:
        chapters.append((cur_title, body))
    elif chapters and cur_title not in ("开篇",):
        chapters[-1] = (chapters[-1][0], chapters[-1][1] + "\n" + cur_title)
    if not chapters:
        chapters = [("全文", text.strip())]
    return chapters


# ---------------------------------------------------------------- 导出

def save_txt(chapters, path, merge=True):
    if merge:
        parts = []
        for title, body in chapters:
            parts.append(title)
            parts.append(body)
        data = "\n\n".join(p for p in parts if p) + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
        return path
    base, ext = os.path.splitext(path)
    os.makedirs(base, exist_ok=True)
    width = max(4, len(str(len(chapters))))
    for i, (title, body) in enumerate(chapters, 1):
        safe = re.sub(r'[\\/:*?"<>|]', "_", title)[:60] or ("第%04d章" % i)
        fp = os.path.join(base, "%0*d_%s.txt" % (width, i, safe))
        with open(fp, "w", encoding="utf-8", newline="\n") as f:
            f.write(title + "\n\n" + body + "\n")
    return base


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


CSS = """body{margin:1.2em 1em;line-height:1.75;}
h2{font-size:1.25em;margin:1.4em 0 .8em;text-align:center;font-weight:normal;}
p{margin:0 0 .6em;text-indent:2em;font-size:1em;}
"""

CONTAINER = """<?xml version='1.0' encoding='utf-8'?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def write_epub(path, title, author, chapters):
    """用标准库 zipfile 手写 EPUB 2.0（含 toc.ncx，兼容绝大多数阅读器）。"""
    uid = "urn:uuid:" + str(uuid.uuid4())
    title = title or "未命名"
    author = author or "佚名"
    pages = []
    for i, (ctitle, body) in enumerate(chapters, 1):
        paras = []
        for p in body.splitlines():
            p = p.strip()
            if p:
                paras.append("    <p>%s</p>" % _esc(p))
        pages.append((i, ctitle, "\n".join(paras) or "    <p>（本章无正文）</p>"))

    manifest = []
    spine = []
    navpoints = []
    for i, ctitle, _ in pages:
        manifest.append('    <item id="c%d" href="c%04d.xhtml" media-type="application/xhtml+xml"/>' % (i, i))
        spine.append('    <itemref idref="c%d"/>' % i)
        navpoints.append(
            '    <navPoint id="np%d" playOrder="%d">\n'
            "      <navLabel><text>%s</text></navLabel>\n"
            '      <content src="c%04d.xhtml"/>\n'
            "    </navPoint>" % (i, i, _esc(ctitle), i)
        )

    opf = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="BookId">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:opf="http://www.idpf.org/2007/opf">\n'
        "    <dc:title>%s</dc:title>\n"
        "    <dc:creator opf:role=\"aut\">%s</dc:creator>\n"
        "    <dc:language>zh-CN</dc:language>\n"
        "    <dc:identifier id=\"BookId\">%s</dc:identifier>\n"
        "  </metadata>\n"
        "  <manifest>\n"
        '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>\n'
        '    <item id="css" href="style.css" media-type="text/css"/>\n'
        "%s\n"
        "  </manifest>\n"
        '  <spine toc="ncx">\n%s\n  </spine>\n'
        "</package>\n"
    ) % (_esc(title), _esc(author), uid, "\n".join(manifest), "\n".join(spine))

    ncx = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-01-01">\n'
        "  <head><meta name=\"dtb:uid\" content=\"%s\"/></head>\n"
        "  <docTitle><text>%s</text></docTitle>\n"
        "  <navMap>\n%s\n  </navMap>\n</ncx>\n"
    ) % (uid, _esc(title), "\n".join(navpoints))

    with zipfile.ZipFile(path, "w") as z:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        z.writestr(info, "application/epub+zip")
        z.writestr("META-INF/container.xml", CONTAINER, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS, zipfile.ZIP_DEFLATED)
        for i, ctitle, html_body in pages:
            page = (
                "<?xml version='1.0' encoding='utf-8'?>\n"
                '<!DOCTYPE html>\n'
                '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">\n'
                "<head>\n  <meta charset=\"utf-8\"/>\n"
                "  <title>%s</title>\n"
                '  <link rel="stylesheet" type="text/css" href="style.css"/>\n'
                "</head>\n<body>\n  <h2>%s</h2>\n%s\n</body>\n</html>\n"
            ) % (_esc(ctitle), _esc(ctitle), html_body)
            z.writestr("OEBPS/c%04d.xhtml" % i, page, zipfile.ZIP_DEFLATED)
    return path


# ---------------------------------------------------------------- 索引

def index_path(root):
    return os.path.join(root, INDEX_NAME)


def load_index(root):
    p = index_path(root)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def save_index(root, data):
    try:
        with open(index_path(root), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return True
    except OSError:
        return False


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.0f %s" % (n, unit) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f GB" % n
