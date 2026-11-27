# 卷帙 DeShelf

> 本地 TXT 整理工具 — 扫描 · 清洗 · 分章 · **导出 EPUB / TXT**
>
> **v1.5.9** · 上一版还漏了一种写法：**章节号和标题本来就挤在同一行**，而且标题里又带了一次章号，像
> `第1章 第1章:走向他的被窝`。盗版站导出目录常这么排。上一版只处理「标题写两行」的情况，
> 这种一行里自带两遍章号的，原样进了界面，读者看到的还是「第几章重复」。
>
> 这一版在分章收尾加了一道归并：章名里同一个号码、同一种单位（都是「章」）出现两遍，只留后面那截；
> 号码不同（`第1卷 第1章`）、单位不同（`第1章 第1节`）一律不动，免得把真正的层级压平。
> 桌面版和网页版用的是同一套判断。
>
> 验证：同一个函数在两端各跑 12 种写法（一行内重复的冒号写法、顿号写法、空格写法、全角冒号、
> 中文数字与阿拉伯数字混写、卷+章、章+节、号码不同、正常章名、序章、只有章号没有标题），
> 两端结果逐条一致；自带测试核心 8 组 0 失败、网页核心 56 项 0 失败。
>
> **v1.5.8** · 修「分章之后章名前头拖着一串第几章」——读者截图里看到的不是重复章节，是**一个章名里塞进了整页目录**。原因在分章逻辑：标题缓冲区还空着又遇到新标题时，代码直接把两行拼起来（本意是接「第三章 / 风起」这种分两行写的标题），**但没有判重**。txt 开头带一整页目录的书，就会拼成 `第1章 … 第25章 … 第1章`。
>
> 现在同一套规则用在桌面版和网页版：去掉空格后互相包含的，取更完整的那条；同一类（章/回/节）号码相同，取更完整的；号码不同，用新的（旧的没有正文，属于目录残留，直接丢掉）；卷后跟章、或者取不到号码，仍按原来的方式拼接，不冒险。
>
> 验证方式是拿**线上 1.5.7 的代码当基准**，11 种写法逐字对比（正常书、目录连排、两行标题、卷+章、正文提到章号、方括号标题、全角数字、阿拉伯数字、行首全角空格、盗版站噪声、121 章长篇）：**10 种完全一致**，只有「目录连排」那一个的章名变了 —— 旧版 `第1章 标题1 第2章 … 第25章 标题25 第1章 标题1`，新版 `第1章 标题1`，**正文 83 字一字未动**。桌面版与网页版逐例相同。自带测试：核心 8 组 0 失败、清洗一致性 36 项、网页核心 56 项、无头浏览器冒烟 23 项，全绿。
>
> 顺手补一个**打不开**的坑：配置文件现在只认字典。以前赶上断电、网盘同步冲突，或别的程序占用了 `~/.deshelf_config.json` 这个名字，`json.load` 会返回字符串或数组，`cfg.get` 直接抛异常，双击没反应。现在读不到合法字典就当没有配置。
>
> 旧版都留在 Releases 里，**v1.5.7 的安装包一个字节没动**，随时可以下回去。
>
> **v1.5.7** · 新增两条**段落修复**规则，专治「一句话没写完就换行」「收尾引号自己占一行」。这类毛病不是阅读器的锅——是盗版站抓取时**按手机屏宽硬断**留下的：一段话被切成十几行，`衣服湿答` / `答的。”`、`”，大宝还觉` / `得午后潮热` 这种断在词中间、字中间的都见过。
>
> ① **标点单独占一行（默认关）**：整行只有一个收尾引号、句号或逗号的，接回上一行末尾。**省略号、破折号独占一行一律不动**——290 本真实样本里这类共 153 行，多数是作者故意用它表示沉默、停顿（有一本 25 行全是「……」）；挡掉这些之后，规则只会落在真正的坏行上。默认关闭，是因为它属于"替你改正文"，请先预览再勾。
>
> ② **合并句中断行（默认关）**：对按屏宽硬断的文件，勾上后**以空行为段落界**把段内的行接回去。为什么不用「行尾没标点就并下一行」——那个更直觉的判据实测会崩：硬断点经常正好落在句号/问号后面，一张反馈截图里 5 处只并对 1 处。改成空行作界后，两张反馈截图 12 行 → 5 段、11 行 → 4 段，**逐字 9/9 全对**（含断在词中间、引号被挤成单独一行）。
>
> 保险：合并后单段超过 3000 字的**跳过不动**——281 个真实盗版 txt 里 63% 压根没有空行分段，硬并会连成一整段（最长一段 7 万字）。跑完报「合并 N 处 / 标点接回上一行 N 处 / N 段过长未合并」，误伤了当场能看出来。两条规则都关着时，也会扫一遍告诉你「另有 N 处标点独占一行、N 段疑似硬断」，不至于什么都没发现。
>
> 顺手修掉一处老漏网：「欢迎访问www.xxx.com，请记住本站地址，更多免费小说等你来看！」这种**网址前后都是推广语**的行，以前判成“正文里夹着网址”留了下来。现在只要网址前面不到 6 个字、后面还带着推广词，整行删除。
>
> **v1.5.6** · 修 iOS 上**「上传不了文件」**——不是上传失败，是**两个入口在 iPhone / iPad 上根本没有反应**。
>
> ①**「选择文件夹」点了没动静**：它用的是 File System Access API，而 **Safari 和 iOS 上所有浏览器都没有这个接口**，点击时抛 `TypeError` 被 `catch` 吞掉，看上去就是个死按钮。现在凡是没这个能力的浏览器（iOS 全系、Firefox、移动端），**收起「选择文件夹」、把「选择 TXT 文件」升成主按钮**，不再留一个点不动的按钮。
>
> ②**「选择 TXT 文件」弹不出选择器**：原先是 JS 现建一个 `<input type="file">` 就 `.click()`，**没有插进文档**；iOS Safari 对游离节点不打开选择器，而且给 `.onchange` 赋值在 iOS 上不触发，必须用 `addEventListener`。两条都改掉了。
>
> 触屏设备上虚线框的文案也从「拖到这里」改成「**点这里选 TXT 文件**」——手机上既没有拖放，也没有目录授权，原来那句话本身就指错了路。
>
> 修完用无头浏览器**在页面脚本执行前删掉 `showDirectoryPicker`** 来模拟 iOS（事后删是无效的，`canDir` 在加载时就算完了），逐项断言 14 项全过——包括「点下去之后 input 确实在文档里、parentNode 是 `BODY`」。旧回归照旧：清洗一致性 36 项、网页核心 56 项、分章边界 10 项，全绿。
>
> **v1.5.5** · 修一个**会整章消失**的分章 bug，**桌面版和网页版都中**（同一份逻辑）。有些 TXT 把标题和正文挤在同一行（`第2章 《华侨文阵》:她身处的是1965年的唐人街。`），旧版有一条「标题行不以句号结尾」的判据（本意是防正文里的「序章内容。」被当成标题），这类行被判成正文、**整章并进前一章**。同一本书里别的章断在逗号处所以没事，看着就像「只有某一章出事」——其实漏哪一章取决于排版在哪儿换行。
>
> 拿读者反馈的那本书（81 万字）实测：旧版分出 **81 章**，章号 `1→3→6→7→9→10→15→19…` 一路跳；新版 **106 章**（开篇 + 第 1~105 章），**缺号 0、重复 0、没有误判出来的假章**，正文覆盖 99.5%（差额是 105 个标题行本身的文字）。
>
> 同一类写法还有两个出口，一并修了：**①整行超过 50 字标题上限**的（`第31章 …:…` 有 52~55 字）；**②行里混着盗版站的字面 `\r\n`**，把长度撑爆的（第 18、57 章，剥掉后 44~45 字）。三处都改在分章判据里，正文一个字不动。
>
> 这个问题是小红书读者 **海盐柠檬** 反馈的 —— 附了书和截图，才定位到这三种写法。谢谢。
>
> **v1.5.4** · 把「自定义章节正则」讲明白——不再是一句话打发：**①分章页多了「常用写法」按钮**，窗口里按「书的写法」列了 8 条现成规则（第X章/第X折/卷一第X回/纯数字/中文序号/Chapter N/【第X话】/宽版兜底），选中一条点「填入」即可；窗口顶部把「什么时候才需要填」「全局与本书专用两个框的区别」「什么样的行算标题」写清楚。**②使用说明**里补了一整节，含三个常见坑（只写 [0-9] 会把正文行切成标题、只写「第[0-9]+章」漏「第一章」、本书规则别填到全局那格）。两端模板逐条比对，跑测试时若不一致会直接报错。
>
> **v1.5.3** · 简繁去重的三处收尾（用户截图指出的「第二行还是繁體版」就在这）：**①** `##########  繁體版  ##########` 这类**版本标记行整行删掉**——正文去重后这份标记已经没有意义，留着就是书里的一行垃圾；**②** 站点把乱码**整段追加**在一行上时，长度会差出一大截被旧的长度比挡掉，现在只要短的那行是长那行的完整前缀/后缀就认成同一句；**③** 镜像块里两份**字面一模一样**的行（如日文小标题）以前繁简打分打平就两边都留，正文里于是多出一行，现在只留一份。
>
> **v1.5.2** · 两处修复：**①简繁去重不再漏删**——繁→简字表补齐了 547 个常用字（旧表漏了「妳→你」「暱→昵」「瞭→了」这类，缺一个映射整行就对不上，整块繁体因此留了下来）；再叠两层判据：一边被插了网址/乱码的，按 bigram 包含率认回同一句；整章简繁两份的，按偏移找出成对整块整块删。用户发来的第五章样本：繁体行 138 → 残留 1。**②窗口底色统一**——卡片里的控件一直是灰底（判断控件类型的代码写错了类名，长期空转），白卡上冒出一个个灰方块；现在全线铺白、描边加深、页签条与进度槽配色跟上。
>
> **v1.5.1** · 两处收尾：**①「关于」升级为「版权与许可」窗口**——MIT 全文、署名要求的逐条说明、第三方组件清单、免责条款都在里面，可一键「复制说明全文」或「复制 MIT 全文」。**②主要按键上色**——次级但常用的按键（全选/反选/试分全部/导入导出规则/浏览）改成浅蓝底，主操作仍是实心蓝、执行写盘仍是实心绿，一眼能分出主次。**③顶栏右侧加了语言开关**——中文界面显示 `EN`、英文界面显示 `中文`，不用再去菜单里找「语言」两个字（菜单项也改成了双语「语言 Language」）。
>
> **v1.5.0** · 桌面版两件事：**①「添加文件…」**——不必先选整个目录，直接挑几个 txt 进书库（网页版早就有的入口，现在补上了）；可选文件不必在书库目录里，导出的相对路径会显示成 `..\` 开头；手滑加错了，右键「从列表移除（不删文件）」。**②界面重做皮肤**——原来的灰底 + 凹陷分组框是 tkinter 默认主题的老观感，现在换成浅底卡片 + 1px 描边 + 分层按钮（主操作实心蓝、执行实心绿），表格行高与表头也重新配过色。功能逻辑一行没动。

> **v1.4.0** · 七个改进：**①规则列表可滚动**（窗口小 / 系统缩放 125% 时最后几条不再被裁掉）；**②EPUB 封面**——自动把同目录下的同名图片打包当封面，没有图片就生成一张米色宣纸底的默认封面（竖排楷体书名 + 作者）；**③四套版面主题**（传统书籍 / 现代阅读 / 紧凑省纸 / 大字易读）；**④清洗规则导入导出**——规则包是 JSON，可分享、可自己加正则，不必改代码；**⑤每本书单独的分章正则**（③页「本书规则」，留空用全局）；**⑥高分屏适配**（125%/150% 缩放下界面不再变小）；**⑦修掉几处问题**：批量试分不再卡界面、书库「章节」列从空变成实际章数、书名作者识别更准（方括号作者、多字段同行、隐藏字符）、开头的「书名：/作者：」不再单独占一章。
>
> **v1.3.4** · 新增清洗规则「**简繁重复行（保留简体）**」——下载的书每章同时有简体和繁体两份时，一键删掉繁体那份：相邻成对、整章重复都能认，标题这类没有字形差异的行也会跟着整块删掉；纯繁体书、简体书里只引用一句繁体，一个字都不动。**默认关闭**，需要时在②勾选，先预览再应用。导出面板另加「另存时加后缀」与「原地覆盖原文件（先备份 `.bak`）」，不再堆一堆 `(1)(2)` 副本。
>
> **v1.3.3** · 修复「网址粘在段落末尾时，整段正文被当成广告删掉」——很多盗版站的 TXT 会把网址直接贴在每段末尾（…“你什么时候偷走的？”WwW.zhudao.com），上一版按整行删除，整本书的正文会被洗光。现在先判断这行是不是广告：**整行只有广告才整行删，广告只是粘在段尾就只裁掉那一截**，正文一个字不动；同时「请到」「百度搜索」这类正常对话里也会出现的词不再被单独判成广告。预览里能看清哪一段被裁、哪一行被删。（感谢小红书用户 **@芭比Q** 反馈这个问题）
>
> **v1.3.2** · 分章不再依赖先清洗：内置规则库支持**全角数字**（第１５章）与「〇」，章号写成全角也能直接分出章节；网页版「试分章节 / 全部一键分章」改为与桌面版一致，先按当前规则清洗再分章（此前未清洗只能分出 1 章，导出时却是另一个结果）
>
> **v1.3.1** · 修复「全角转半角」误改中文标点的问题：规则现在**只转换全角数字与字母**，中文的逗号、冒号、括号、引号等一律保持原样（此前整本书的「，」会被改成「,」；章号是全角数字的书仍然能正常分章）
>
> **v1.3** · 智能分章新增批量操作（Web：全部书籍一键分章并保存；EXE：试分全部选中）与「试分书籍」下拉选单本 · EXE 清洗页新增「应用到所选书籍」批量清洗 · **界面语言窗口内即时切换**（EXE 就地重建，无需重启）· 在线版日志栏默认展开 · 修复「关于」无法打开的占位符 bug
>
> **v1.2** · 新增中英双语界面（跟随系统语言，菜单可切换）· 记忆上次输出目录与模式 · 修复原地覆盖缺输出目录时静默跳过的校验
>
> **v1.1** · 新增启动开屏海报（淡入淡出，点击可跳过）· 主窗口居中

[中文](#中文) | [English](#english)

---

## 中文

### 它解决什么问题

你硬盘上躺着几百本从各处下载的 TXT：编码有的是 GBK 有的是 UTF-8，打开全是乱码；正文里夹着
"请收藏本站""本章未完"这类推广行；章节没有目录，丢进阅读器里是一整坨；同一个文件还下重了好几份。

卷帙就是把这批"野生 TXT"变成能直接读的书的流水线工具。它**不下载、不上传、不联网**，
只处理你本机已有的文件。

### 功能

| 步骤 | 做什么 |
|---|---|
| **1 扫描入库** | 递归扫描目录，自动识别编码（GBK / UTF-8 / UTF-8 BOM / UTF-16），统计字数，按内容 MD5 标出重复文件 |
| **2 批量清洗** | 勾选规则后一键清洗：网址行、站点宣传行、翻页导航残留、乱码行、**标点单独占一行**（默认关，省略号/破折号独占一行不动）、**合并句中断行**（默认关）、空行压缩、全角转半角、段落缩进。可先预览前后对比 |
| **3 智能分章** | 内置中文网文章节规则库，也支持自定义正则。分完直接在列表里看章节目录 |
| **4 导出分发** | 导出 EPUB（带完整目录）、合并 TXT、分章 TXT。清洗结果可选择输出到新目录、原地覆盖（先备份 .bak）或不落盘 |

其它：目录记忆、扫描索引缓存（秒开）、书单导出 CSV、按内容指纹找出重复文件。

### 为什么要转 EPUB

EPUB 是卷帙的主要输出格式，也是给电纸书/阅读器看书的推荐格式：

| 好处 | 说明 |
|---|---|
| 电纸书即插即用 | 文石 / 掌阅 / Kobo / 微信读书 / Apple Books 等均直接支持，打开就有章节目录、可跳章 |
| 可划线做笔记 | 支持高亮与批注留心得（笔记存在阅读器侧，换设备不丢） |
| 体积小近一半 | EPUB 是 zip 压缩容器，同一本书通常比 TXT 小 40%~55%，省电纸书存储 |
| 排版规范 | 段落缩进、标题层级完整保留，调字号自动重排，永不失真不乱码 |
| 开放标准 | EPUB 2.0 为 W3C 国际标准，不会过期，任何设备可长期阅读 |

**推荐流程**：卷帙把野生 TXT 清洗分章 → 导出最终版 EPUB → 放进电纸书精读做笔记。

### 和其它工具的区别

| | 卷帙 | Calibre | epubBuilder | 手机阅读 App |
|---|---|---|---|---|
| 批量处理整个目录 | ✅ 一次几百本 | ⚠️ 偏单本管理 | ❌ 一次做一本 | — |
| 中文编码自动识别 | ✅ 不用手填 | ❌ 默认 UTF-8，需手动指定 GBK | ✅ | 部分支持 |
| 广告行批量清洗 | ✅ 规则化 | ❌ | ❌ | 手动替换规则 |
| 不复制原文件 | ✅ 只写索引，原地不动 | ❌ 会复制进自己的书库 | ✅ | — |
| 带目录 EPUB 导出 | ✅ | ✅ | ✅ | — |
| 体积 | ~14 MB 单文件 | 100 MB+ 安装包 | 13 MB | — |

**卷帙不做阅读器。** 手机上看书交给成熟的阅读 App，卷帙只负责让书变得能顺畅导入。

### 安装

到 [Releases](https://github.com/podcatcher962/DeShelf/releases) 页下载 `DeShelf.exe`（软件中文名「卷帙」，Release 资产统一用英文名以兼容各平台下载），双击运行即可，无需安装 Python。

同页也可下载 **Web 版** `DeShelf.html`（或取源码 `web/DeShelf.html`）：双击本地用，或在线直接打开 👉 **https://podcatcher962.github.io/DeShelf/**

**用 macOS / Linux 或手机？** 桌面版 EXE 目前只出 Windows 版，别的系统直接用上面的网页版就是完整工具。
Mac 上用 Chrome / Edge 打开，可以授权整个文件夹、把结果写回原目录；Safari 和 Firefox 不支持文件夹授权，
会自动降到「文件模式」（逐本处理后下载）。手机也能打开，只是不适合几百本的大书库。

### 使用流程

1. 点「浏览…」选中你的小说目录 → 点「扫描」
2. 在「批量清洗」勾选规则 → 点「预览效果」确认
3. 在「智能分章」点「试分章节」看章节数对不对
4. 在「导出分发」选择去向与格式 → 点「开始处理」

### 技术说明

- Python 3 + Tkinter，单文件 EXE，**零第三方依赖**
- EPUB 由标准库 `zipfile` 手写（EPUB 2.0 + toc.ncx，兼容绝大多数阅读器）
- 编码识别不依赖 chardet：BOM 判断 → UTF-8 严格解码 → 含 NUL 字节判 UTF-16 → 回落 GBK
- 扫描结果缓存在目录下的 `.deshelf_index.json`，校验 mtime 与体积判断缓存是否过期
- 批量处理在后台线程执行，界面不卡，可随时停止

### 本版实测

每次发版前跑完整回归，下面是 v1.5.5 的实际结果（数字来自仓库里的测试脚本，不是估算）：

| 测试 | 覆盖什么 | 结果 |
|---|---|---|
| 清洗一致性 | `tools/test_clean_parity.py`：逐条规则比对两端输出 | 36 项通过 |
| 网页核心 | `tools/test_web_core.mjs`：分章 / 清洗 / 简繁 / 导出逻辑 | 56 项通过 |
| 端到端 | 6 本真实样本走完「扫描 → 清洗 → 分章 → 导出」 | 62 项通过 |
| 网页 EPUB | `test_web_epub.js`：用 epub.js 反向解析产物 | 36 项通过 |
| 浏览器冒烟 | `smoke_web_browser.mjs`：headless 真浏览器点界面 | 23 项通过 |
| 分章边界 | 标题与正文挤一行、副标题、引号结尾、正文提及章号等 10 种写法 | 10 项通过 |
| 真实书 | 反馈的那本 81 万字：桌面版与网页版各跑一遍，核章号是否连续、有无假章 | 旧 81 章 → 新 106 章，缺号 0 |

两条硬性约束，每次都过：

1. **两端逐字一致**——同一份文本（简繁混排、夹站点噪声、全角数字）在 Python 端与网页端的输出必须完全相同，
   差一个字符即判失败。做法是直接调网页里的清洗函数，与 Python 结果做 diff。
2. **不改坏原有行为**——每加一条规则，都拿上一版结果做对照，确认纯简体文本「一字不动」。

简繁去重这一版拿用户反馈的真实样本（5 章 334 行，每章繁简各一份）实测：

- 繁体行 138 → 清洗后残留 1 行（一句被站点插了乱码的标题，两份里都没有干净版本）；
- 简体行 0 误删；
- 22 000 行耗时 1.21 秒（单线程）。

产物：`DeShelf-v1.5.9.exe` 14.87 MB（PyInstaller onefile），网页版单文件 0.16 MB，均不联网。

### 免责声明

卷帙是一款纯本地文本整理工具：不联网、不下载、不上传、不提供也不存储任何书籍内容，
仅对用户本机已有的文件做清洗、分章与格式转换。使用者应确保所处理文件来源合法，
因使用本工具产生的任何版权或法律问题由使用者自行承担。软件按"现状"提供，
作者不对数据丢失或损坏承担责任；使用"原地覆盖"前请先确认备份。

### 许可与署名

本项目以 [MIT License](LICENSE) 发布：可以自由使用、修改、合并、再分发（含商业用途），不用付费，也不用事先告知。

**唯一硬性条件：保留作者署名。** 任何副本或实质性部分都必须保留版权声明与完整的 MIT 许可文本——也就是仓库根目录的 `LICENSE`。你可以改代码、改软件名、闭源分发，但不能删掉 `Copyright (c) 2026 Lanlan Eternal`，也不能改成自己的名字后声称原创。二次分发（含打包进你自己的产品）时，请在「关于」页或随附文档里保留本署名与 MIT 全文。

引用时建议注明：`卷帙 DeShelf © 2026 永远的兰兰 (Lanlan Eternal)，MIT License`。

第三方组件见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)：Python 3.12（PSF License）、Tcl/Tk（BSD-style）、Pillow（MIT-CMU）、OpenCC 简繁对照表（Apache-2.0，仅用于比对）。封面所用楷体是 Windows 自带字体，本项目不打包、不分发任何字体文件。

程序内「帮助 → 关于」有同一份说明，可一键复制全文或 MIT 原文。

### 卷帙 Web 版（同一份 HTML · 本地或在线双栖）

除桌面 EXE 外，卷帙还提供**单文件 HTML 版** `DeShelf.html`（78 KB，单击即用、零依赖），
支持两种使用方式：

| 方式 | 怎么用 | 适用范围 |
|---|---|---|
| **本地双击** | 双击 `DeShelf.html` 在 Chrome / Edge 打开 | 全部功能（含目录授权模式） |
| **在线版** | 传到任意 https 静态托管（如 GitHub Pages）后用网址打开 | 全部功能（数据仍留在你的浏览器里） |

**两种模式**自动检测浏览器能力：

| 模式 | 需要 | 能做什么 |
|---|---|---|
| 🅰️ **目录模式**（推荐） | Chrome / Edge · HTTPS 或本地文件 | 点「选择文件夹」授权整目录，扫描+缓存+批量保存到原目录（与桌面版 EXE 共享 `.deshelf_index.json`） |
| 🅱️ **文件模式** | 任何现代浏览器 | 把 TXT 文件或文件夹拖进网页，逐文件处理后下载到本机；无法原地写回 |

**在线版为什么安全**：`DeShelf.html` 是一个**纯前端**程序，打开后所有处理都在你浏览器里跑，
**不会上传任何文件、不与任何服务器通讯**。把这份 HTML 放到 GitHub Pages 等 https 静态托管只是给你一个访问入口，
服务器只负责把 HTML 文件送给你，之后的所有读写都发生在你的电脑里。换设备就失效（你的书不在服务器上），
这也是它能做成在线版的根本原因——无版权风险。

**在线版地址（GitHub Pages 托管）**：👉 **https://podcatcher962.github.io/DeShelf/** —— 与本地双击是同一份 HTML，打开即用，无需下载安装。

**桌面 vs Web 该选哪个**：

| | 桌面版 EXE | Web 版 HTML |
|---|---|---|
| 大书库（几百本）批量处理 | ✅ 推荐 | 浏览器内存有限 |
| 原地覆盖 + `.bak` 备份 | ✅ | ❌（下载副本） |
| 整目录写回（覆盖式） | ✅ | ❌（仅下载） |
| 跨平台（Windows / macOS / Linux / 手机） | 仅 Windows | ✅ 任何带现代浏览器的设备 |
| 中文 GBK 自动识别 | ✅ | ✅ |
| 联机分享 / 在线使用 | ❌ | ✅ |
| 离线纯本地 | ✅ | ✅ |

如果只是想把几本 TXT 整理成能直接塞进电纸书的 EPUB，**Web 版完全够用**，连 Python 都不用装。
需要批量"原地覆盖写回"原始文件时用桌面版 EXE。

**自检通过**：
- 核心纯逻辑 46/46 单测（编码识别 / 清洗 12 条规则（可加自定义） / 分章 / EPUB / ZIP）
- 真实浏览器冒烟 18/18（Edge headless · 页面初始化 / 双语切换 / 文件入库 / 清洗 / 分章 / 导出）
- 双语词典 125 键 + 125 键完全对齐

---

## English

> Local TXT organizing tool — scan · clean · split · **export EPUB / TXT**
>
> **v1.5.9** · The previous build still missed one layout: the **chapter number and the title on the same line**, with the number repeated inside the title — `第1章 第1章:走向他的被窝`. Pirate-site exports of a contents page are often written exactly like that. 1.5.8 only handled titles split across two lines, so this shape went to the interface untouched and still read as "the chapter number repeats".
>
> This build adds a final merge pass over chapter names: when the same number and the same unit (both 章) appear twice, keep the second half; a different number (`第1卷 第1章`) or a different unit (`第1章 第1节`) is left alone, so real hierarchy is not flattened. Same rule in the desktop and web builds.
>
> Verified by running the same function on both sides over 12 layouts (colon, ideographic comma, space, full-width colon, Chinese and Arabic numerals mixed, volume + chapter, chapter + section, mismatched numbers, a normal title, a prologue, a bare number with no title) — identical results on both sides; suites: 8 core groups and 56 web-core checks, 0 failures.
>
> **v1.5.8** · Fixes a chapter **title swallowing an entire table of contents**. What looked like duplicated chapter numbers was one title holding the whole TOC. When its title buffer was still empty and another title line arrived, the splitter concatenated the two — intended for titles written across two lines (`第三章` / `风起`), but with **no de-duplication**, so a book that opens with a page of contents produced `第1章 … 第25章 … 第1章`.
>
> The rule is now identical in the desktop and web builds: if one title (whitespace removed) contains the other, keep the longer; same class (章/回/节) with the same number, keep the longer; same class with a different number, take the new one (the old has no body — TOC residue); a volume followed by a chapter, or no number at all, still concatenates as before.
>
> Verified with **the shipped 1.5.7 code as the baseline** across 11 layouts (plain book, contents page, two-line titles, volume + chapter, chapter numbers quoted inside prose, bracketed titles, full-width digits, Arabic digits, leading ideographic space, pirate-site noise, a 121-chapter book): **10 are identical character for character**; only the contents case changed, from `第1章 标题1 第2章 … 第25章 标题25 第1章 标题1` to `第1章 标题1`, with the body untouched. Desktop and web output match case by case. Suites: 8 core groups 0 failures, 36 cleaning-parity checks, 56 web-core checks, 23 headless-browser smoke items — all green.
>
> Also fixed a **won't-start** case: config loading accepts a dict only. If power loss, a cloud-sync conflict, or another program claims `~/.deshelf_config.json`, `json.load` can return a string or a list, `cfg.get` throws, and double-clicking does nothing.
>
> Older builds stay on the Releases page — the v1.5.7 installer is byte-for-byte untouched and can still be downloaded.
>
> **v1.5.7** · Two new **paragraph-repair** rules for text where a sentence breaks mid-way and a closing quote sits alone on its own line. This is not the reader's fault — it is what happens when a scraper **hard-wraps at phone width**: one paragraph gets cut into a dozen lines, and the breaks land inside words (`衣服湿答` / `答的。”`) and inside clauses (`”，大宝还觉` / `得午后潮热`).
>
> (1) **Punctuation alone on a line (off by default).** A line holding only a closing quote, a full stop or a comma is pulled back onto the previous line. **Ellipsis and dash lines are never touched** — across 290 real books there are 153 such lines and most are deliberate (one book uses 25 lines of `……` alone to mark silence); excluding them leaves the rule working only on genuinely broken lines. It is off by default because it rewrites prose — preview first.
>
> (2) **Join mid-sentence line breaks (off by default).** For files hard-wrapped at screen width: when enabled, lines inside a paragraph are joined back, using **blank lines as paragraph boundaries**. The intuitive test — "join whenever the line does not end with punctuation" — fails in practice: hard breaks land right after a full stop or question mark often enough that one feedback screenshot scored 1 out of 5. Using blank lines instead, the two feedback screenshots went 12 lines → 5 paragraphs and 11 lines → 4 paragraphs, **9/9 character-for-character correct** (including a break inside a word and a quote pushed onto its own line).
>
> Guard: a merged paragraph longer than 3000 characters is **left untouched** — 63% of 281 real pirated TXT files have no blank-line paragraph separation at all, and joining them blindly produces one giant line (the longest observed: 70,000 characters). The run reports "N line breaks joined / N stray marks pulled back / N paragraphs left alone", so any damage is visible immediately. With both rules off, a scan still tells you "N lines hold punctuation only, N paragraphs look hard-wrapped".
>
> Also fixed an old leak: lines like `欢迎访问www.xxx.com，请记住本站地址，更多免费小说等你来看！` — a URL **surrounded by promo text** — used to be kept as "a URL inside a sentence". Now, if there are fewer than 6 characters before the URL and promo words follow it, the whole line is dropped.
>
> **v1.5.6** · Fixes **"can't upload a file" on iOS** — the upload never started; both entry points did nothing at all on iPhone and iPad.
>
> (1) **"Choose Folder" was a dead button.** It relies on the File System Access API, which **Safari — and therefore every browser on iOS — does not implement**. The click threw a `TypeError` that a `catch` swallowed, so nothing visible happened. Browsers without that capability (all of iOS, Firefox, mobile) now **hide "Choose Folder" and promote "Choose TXT files" to the primary button** instead of leaving a control that cannot work.
>
> (2) **"Choose TXT files" opened no picker.** The code built an `<input type="file">` in JavaScript and called `.click()` on it **without inserting it into the document**; iOS Safari refuses to open the picker for a detached node, and assigning `.onchange` does not fire there either — it has to be `addEventListener`. Both are fixed.
>
> On touch devices the drop zone now reads "**Tap here to choose TXT files**" rather than "drop files here" — a phone has neither drag-and-drop nor folder authorization, so the old wording pointed the wrong way.
>
> Verified by deleting `showDirectoryPicker` **before the page scripts run** in a headless browser to simulate iOS (deleting it afterwards is useless — `canDir` is computed at load). 14 assertions pass, including "after the click the input really is in the document and its `parentNode` is `BODY`". Earlier suites still green: 36 cleaning-parity, 56 web-core, 10 splitting-edge.
>
> **v1.5.5** · Fixes a split bug that could **silently swallow a whole chapter** — it hits **both the desktop and the web build** (one shared implementation). Some TXT files run the chapter heading and the first sentence together on one line (`第2章 《华侨文阵》:她身处的是1965年的唐人街。`). An old guard — "a heading line does not end with a full stop", meant to stop body lines like 「序章内容。」 from being read as headings — treated such a line as body text, so the chapter was merged into the previous one. Neighbouring chapters happened to break at a comma, which is why it looked like a single missing chapter; in fact which chapter you lose depends on where the typesetter wrapped.
>
> Measured on the book a reader reported (810k characters): the old build split it into **81 chapters** with the numbering jumping `1→3→6→7→9→10→15→19…`; the new one gives **106** (a front-matter section plus chapters 1–105) with **zero missing numbers, zero duplicates and no phantom chapters**, covering 99.5% of the body text (the remainder is the text of the 105 heading lines themselves).
>
> Two more exits of the same shape were fixed too: **①** lines longer than the 50-character heading cap (`第31章 …:…` runs 52–55 characters); **②** lines carrying the pirate site’s literal `\r\n` escapes, which inflate the length (chapters 18 and 57, 44–45 characters once stripped). All three live in the split logic; not a character of body text is touched.
>
> Reported by **海盐柠檬** on Xiaohongshu, who sent the book and the screenshots that made all three shapes visible. Thank you.
>
> **v1.5.4** · The custom chapter regex is finally explained, not just mentioned: **①** the chapter pane has a “Templates” dialog listing eight ready-made patterns by “Book looks like” (第X章 / 第X折 / 卷一 第X回 / plain numbers / Chinese ordinals / Chapter N / 【第X话】 / a catch-all) — pick one and hit Fill; the dialog also spells out when you need this at all, how the global and per-book boxes differ, and what line qualifies as a title. **②** the user guide gained a full section with the three classic traps (bare [0-9] turning body lines into titles, 第[0-9]+章 missing 第一章, a per-book rule typed into the global box). The two template tables are compared by the test suite, so they cannot drift apart.
>
> **v1.5.3** · Three finishing touches on script-duplicate removal (this is the 「second line is still 繁體版」 from the screenshot): **①** version-marker lines such as `##########  繁體版  ##########` are now dropped entirely — once the duplicate body is gone the label is just a stray line inside the book; **②** when a site appends a chunk of garbage to a line, the length gap used to trip the length-ratio guard — now, if the shorter line is the exact prefix/suffix of the longer one, they count as the same sentence; **③** lines that are byte-identical in both mirrored blocks (e.g. Japanese sub-headings) used to be kept twice when the traditionality score tied — now only one copy survives.
>
> **v1.5.2** · Two fixes: **① script-duplicate removal no longer leaves traditional lines behind** — the T→S character table was missing 547 common characters (no mapping for 妳→你, 暱→昵, 瞭→了 …), and one missing mapping makes a whole line fail to match, so entire traditional blocks survived; it now also matches lines by bigram containment (covers inserted URLs/garbage) and removes whole mirrored blocks by offset. On the user-submitted five-chapter sample: 138 traditional lines → 1 left. **② The window background is finally consistent** — widgets inside cards had kept their grey fill (the widget-type check compared the wrong class names and had silently done nothing for ages), so grey rectangles showed up on white cards; everything is white now, with a deeper hairline and matching tab strip / progress trough.
>
> **v1.5.1** · Two finishing touches: **① “About” became a “Copyright & License” window** — the full MIT text, a point-by-point explanation of the attribution requirement, the third-party list and the disclaimer, with one-click “Copy the full text” / “Copy the MIT text”. **② Primary buttons got colour** — secondary-but-frequent actions (select all/invert/try all/import-export rules/browse) now use a light blue fill, while the primary action stays solid blue and the write action stays solid green. **③ A language switch now sits at the right end of the top bar** — it reads `EN` in the Chinese UI and `中文` in the English one, so nobody has to hunt for the word “Language” in a menu (the menu item is bilingual too).
>
> **v1.5.0** · Two desktop-only changes: **① “Add files…”** — pick a few TXT files straight into the library instead of scanning a whole folder (the web build already had this); files outside the library folder are fine, their relative path just starts with `..\`, and a mis-click can be undone via right-click → “Remove from list (file kept)”. **② New skin** — the old grey panels with sunken group boxes were the stock tkinter look; now it is light cards with 1px borders and layered buttons (accent blue for primary, green for the run action), plus retuned table row height and headers. No behaviour changed.

> **v1.4.0** · Seven improvements: the **rule list scrolls** (the last rules are no longer clipped on small windows or at 125% scaling); **EPUB covers** — a same-named image in the same folder is packed as the cover, otherwise a default rice-paper cover with the vertical title is generated; **four layout themes** (classic print / modern reading / compact / large print); **rule packs** import & export as JSON, so you can add your own regexes without touching code; **per-book chapter regex** (the “this book” field in step ③); **HiDPI awareness**; and fixes — batch splitting no longer freezes the window, the chapter column shows real counts, book title/author detection is more accurate, and a leading “Title:/Author:” header no longer becomes its own chapter.
>
> **v1.3.4** · new cleaning rule **“Duplicate simplified/traditional lines”** — when a book carries both a simplified and a traditional copy of every chapter, drop the traditional one in a single pass. Alternating lines and whole duplicated chapters both work, and lines with no glyph difference (chapter titles) go with their block; traditional-only books, and a lone traditional quotation inside a simplified book, are left completely untouched. **Off by default** — tick it in step ②, preview first, then apply. The export panel also gains “suffix when saving as” and “overwrite originals (with `.bak` backup)” so you stop piling up `(1)(2)` copies.
>
> **v1.3.3** · fixed "a URL glued to the end of a paragraph made the whole paragraph look like an ad" — many pirated TXT dumps append the site URL to every paragraph (…“when did you take it?”WwW.zhudao.com). The previous build removed the whole line, which could wipe out an entire book's text. It now decides first whether the line really is an ad: **a line that is only an ad is removed whole; an ad merely glued to a paragraph tail is trimmed off, leaving the text untouched**. Words that also occur in normal dialogue (「请到」, 「百度搜索」) no longer count as ads on their own, and the preview shows exactly which tail was trimmed and which line was removed. (Thanks to **@芭比Q** for reporting it.)
>
> **v1.3.2** · chapter splitting no longer requires cleaning first: built-in rules now recognise **full-width digits** (第１５章) and 「〇」, so books numbered in full-width digits split correctly out of the box; the online edition's "Try splitting" / "Split all" now match the desktop edition by cleaning with the active rules before splitting (previously an uncleaned book yielded a single chapter while export produced a different result)
>
> **v1.3.1** · fixed "Full-width to half-width" mangling Chinese punctuation: the rule now converts **only full-width digits and letters**, leaving Chinese commas, colons, brackets and quotes untouched (previously every 「，」 in a book became 「,」; books numbered with full-width digits still split into chapters correctly)
>
> **v1.3** · smart chapter splitting now batch-capable (Web: chapter & save all books at once; EXE: try-split all selected) plus a "Book to split" dropdown · EXE Clean tab gains "Apply to selected books" batch cleaning · **in-window instant language switch** (EXE rebuilds in place, no restart) · online edition log panel open by default · fixed "About" dialog failing to open (placeholder bug)
>
> **v1.2** · bilingual UI (follows system language, switchable in the menu) · remembers last output folder & mode · fixed silent export skip when no output folder was set for in-place mode
>
> **v1.1** · new animated launch poster (fade in/out, click to skip) · centered main window

### What it does

You have hundreds of downloaded TXT files: mixed GBK / UTF-8 encodings that show up as mojibake,
promotional lines like "please bookmark this site" sprinkled through the text, no chapter structure,
and the same book downloaded twice.

DeShelf turns that pile of raw TXT into books you can actually read. It **never connects to the
network** — no downloading, no uploading. It only touches files already on your machine.

### Features

| Step | What happens |
|---|---|
| **1 Scan** | Recursively scans a folder, auto-detects encoding (GBK / UTF-8 / UTF-8 BOM / UTF-16), counts characters, flags duplicates by content MD5 |
| **2 Clean** | Rule-based batch cleaning: URL lines, site promo lines, page-nav leftovers, mojibake lines, **punctuation alone on a line** (off by default; ellipsis/dash-only lines are never touched), **join mid-sentence line breaks** (off by default), blank-line compression, full-width to half-width, paragraph indent. Preview before applying |
| **3 Chapters** | Built-in regex library for Chinese web-novel chapter headings, custom regex supported, live chapter preview |
| **4 Export** | EPUB with a real table of contents, merged TXT, or one file per chapter. Cleaned text can go to a new folder, overwrite in place (with `.bak` backup), or not be saved at all |

Also: remembers the last folder, caches the scan index for instant reload, exports the book list as CSV,
finds duplicates by content fingerprint.

### Why EPUB

EPUB is DeShelf's primary output format and the recommended way to read on e-readers / reading apps:

| Benefit | Detail |
|---|---|
| E-reader ready | Works out of the box on Boox, iReader, Kobo, WeRead, Apple Books, etc. — opens with a real table of contents and chapter jumps |
| Highlight & annotate | Full support for highlighting and margin notes (notes live in the reader, so they survive file changes) |
| Roughly half the size | EPUB is a zip container — the same book is typically 40–55% smaller than TXT |
| Clean typography | Paragraph indents and heading levels are preserved; text reflows at any font size — no mojibake, no distortion |
| Open standard | EPUB 2.0 is a W3C standard that will never go stale |

**Recommended workflow**: clean & split your raw TXT in DeShelf → export the final EPUB → read and annotate on your e-reader.

### How it differs

| | DeShelf | Calibre | epubBuilder | Reading apps |
|---|---|---|---|---|
| Batch process a whole folder | ✅ hundreds at once | ⚠️ single-book oriented | ❌ one book at a time | — |
| Automatic Chinese encoding detection | ✅ no manual input | ❌ defaults to UTF-8 | ✅ | partial |
| Batch ad-line cleaning | ✅ rule-based | ❌ | ❌ | manual rules |
| Leaves originals in place | ✅ index only | ❌ copies into its own library | ✅ | — |
| EPUB with TOC | ✅ | ✅ | ✅ | — |
| Size | ~14 MB single file | 100 MB+ installer | 13 MB | — |

**DeShelf is not a reader.** Hand the finished EPUB to whichever reading app you like.

### Install

Grab `DeShelf.exe` from the [Releases](https://github.com/podcatcher962/DeShelf/releases) page (the app is named 卷帙 in Chinese; release assets use the English name for cross-platform download) and double-click it. No Python required.

The **Web version** `DeShelf.html` is also on the same Release page (source: `web/DeShelf.html`). Double-click it for local use, or open the online copy at 👉 **https://podcatcher962.github.io/DeShelf/**

**On macOS / Linux or a phone?** The desktop EXE is Windows-only for now; everywhere else the Web version above *is* the full tool. On a Mac, open it in Chrome or Edge to authorize a whole folder and write results back in place. Safari and Firefox have no folder-permission API, so they fall back to file mode (one file in, one result downloaded). Phones work as well, though they are not suited to a library of several hundred books.

### Workflow

1. Browse to your novels folder → **Scan**
2. Tick the cleaning rules → **Preview**
3. **Try split** in the Chapters tab to check the chapter count
4. Choose destination and formats → **Start**

### Technical notes

- Python 3 + Tkinter, single-file EXE, **zero third-party dependencies**
- EPUB is written by hand with the standard-library `zipfile` (EPUB 2.0 + toc.ncx)
- Encoding detection without chardet: BOM check → strict UTF-8 decode → NUL byte test for UTF-16 → fall back to GBK
- Scan results cached in `.deshelf_index.json`, invalidated by mtime and size
- Batch jobs run on a worker thread; the UI stays responsive and can be stopped at any time

### What was actually tested

The full suite runs before every release; these are the real numbers for v1.5.5, taken from the
scripts in this repo rather than estimated:

| Suite | What it covers | Result |
|---|---|---|
| Clean parity | `tools/test_clean_parity.py` — every rule diffed across both ends | 36 checks pass |
| Web core | `tools/test_web_core.mjs` — split / clean / script-dedupe / export logic | 56 checks pass |
| End-to-end | six real books through scan → clean → split → export | 62 checks pass |
| Web EPUB | `test_web_epub.js` — output re-parsed with epub.js | 36 checks pass |
| Browser smoke | `smoke_web_browser.mjs` — a headless browser clicking the real UI | 23 checks pass |
| Split edges | heading-and-body-on-one-line, subtitle colons, quote-ending headings, body text naming a chapter, 10 shapes | 10 checks pass |
| Real book | the reported 810k-character book, run through both the desktop and the web core — chapter numbering and phantom-chapter check | 81 chapters → 106, no gaps |

Two hard rules that must hold every time:

1. **Python and the web page agree byte for byte.** The same input (mixed scripts, site-injected
   garbage, full-width digits) must produce identical output; one character off counts as a failure.
   The parity test does this by calling the page's own cleaning function and diffing the result.
2. **Nothing that used to work may break.** Every new rule is checked against the previous build to
   confirm plain simplified text comes out untouched.

The script-duplicate fix was measured on a real user sample (five chapters, 334 lines, one simplified
and one traditional copy of each):

- 138 traditional lines → 1 left after cleaning (a heading with site garbage appended, no clean version
  in either copy);
- 0 simplified lines lost;
- 22,000 lines processed in 1.21 s on a single thread.

Artifacts: `DeShelf-v1.5.9.exe` 14.87 MB (PyInstaller onefile), web version 0.16 MB as a single file,
both fully offline.

### Disclaimer

DeShelf is a purely local text-processing utility. It does not connect to the network, does not
download or upload anything, and neither provides nor stores any book content — it only cleans,
splits and converts files that already exist on the user's machine. Users are responsible for
ensuring they have the legal right to process their files. Provided "as is"; the author is not
liable for any data loss. Back up before using in-place overwrite.

### License & attribution

Released under the [MIT License](LICENSE): use, copy, modify, merge and redistribute freely, including commercially — no fee, and no need to ask first.

**The one hard requirement is attribution.** Every copy or substantial portion must retain the copyright notice and the full MIT text (the `LICENSE` file at the repository root). You may change the code, rename the app or ship it closed-source, but you may not remove `Copyright (c) 2026 Lanlan Eternal`, and you may not put your own name on it and claim it as original work. When redistributing (including bundling it into your own product), keep this attribution and the MIT text in the About screen or the bundled docs.

Suggested credit: `DeShelf © 2026 Lanlan Eternal, MIT License`.

Third-party components are listed in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md): Python 3.12 (PSF), Tcl/Tk (BSD-style), Pillow (MIT-CMU), OpenCC character tables (Apache-2.0, comparison only). The cover uses KaiTi shipped with Windows — no font file is bundled or redistributed.

The in-app “Help → About” screen carries the same text, with one-click copy for the full notice or the MIT wording.

### DeShelf Web (single-file HTML · local or online)

In addition to the desktop EXE, 卷帙 ships a **single-file HTML** called `DeShelf.html`
(78 KB, double-click to run, zero dependencies) — usable two ways:

| Mode | How | Scope |
|---|---|---|
| **Local double-click** | Open `DeShelf.html` in Chrome / Edge | All features (including directory mode) |
| **Online version** | Host it on any https static site (e.g. GitHub Pages) and open the URL | All features (data still stays in your browser) |

Two internal modes are auto-detected based on browser capability:

| Mode | Needs | What it can do |
|---|---|---|
| 🅰️ **Directory mode** (recommended) | Chrome / Edge · HTTPS or local file | Click "Choose Folder" to authorize a whole directory: scan, write an index cache, batch-save results into the same directory (shares `.deshelf_index.json` with the desktop EXE) |
| 🅱️ **File mode** | Any modern browser | Drop TXT files or a folder into the page; each book is processed and downloaded to your machine. No in-place writes |

**Why the online version is safe**: `DeShelf.html` is **purely client-side**. After opening,
all processing runs inside your browser — **no files are uploaded, no server communication**.
Putting it on GitHub Pages or any https static host only gives you a URL to load it. From that point on,
all reads and writes happen on your own computer. Switch devices and the access vanishes (your books
aren't on any server) — that is exactly why this design can be safely hosted online with no copyright risk.

**Online edition (hosted on GitHub Pages)**: 👉 **https://podcatcher962.github.io/DeShelf/** — the exact same HTML as the local file; open and use, no install needed.

**Desktop vs Web — which to pick**:

| | Desktop EXE | Web HTML |
|---|---|---|
| Big batch (hundreds of files) | ✅ Recommended | Limited by browser memory |
| In-place overwrite + `.bak` backup | ✅ | ❌ (downloads only) |
| Whole-directory in-place rewrite | ✅ | ❌ (downloads only) |
| Cross-platform (Win/macOS/Linux/phone) | Windows only | ✅ Any device with a modern browser |
| Auto GBK detection | ✅ | ✅ |
| Share / online use | ❌ | ✅ |
| 100% offline | ✅ | ✅ |

For most "I have a few TXT files and want a readable EPUB for my e-reader" jobs, **Web is enough** —
no Python, no install. Reach for the desktop EXE only when you need to batch-overwrite original files in place.

**Self-tests passing**:
- 46/46 core unit tests (encoding / 12 cleaning rules (plus your own) / chapters / EPUB / ZIP)
- 18/18 real-browser smoke (Edge headless: init / language / file import / clean / chapters / export)
- 125 keys × 2 in the bilingual dictionary, fully aligned

---

© 永远的兰兰 · Lanlan Eternal
