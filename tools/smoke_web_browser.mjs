/* 卷帙 DeShelf Web — 真实浏览器冒烟（Edge headless + CDP，零 npm 依赖）
 * 验证：页面初始化无 JS 报错、双语切换、规则网格、帮助弹窗、
 *       文件入库、清洗预览、分章、导出流程、拖拽函数。
 * 用法: node tools/smoke_web_browser.mjs
 */
import { execFile, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const FILE_URL = "file:///" + path.resolve("web/DeShelf.html").replace(/\\/g, "/");
const PORT = 9333;
const PROFILE = path.join(process.env.TEMP || "/tmp", "deshelf_smoke_" + Date.now());

const results = [];
function ok(name, cond, extra) {
  if (cond) { results.push("✓ " + name); console.log("  ✓ " + name); }
  else { results.push("✗ " + name + (extra !== undefined ? "  | " + extra : "")); console.error("  ✗ FAIL: " + name + (extra !== undefined ? " | " + extra : "")); }
}

// ---------- 启动 Edge ----------
const args = ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--disable-extensions", "--remote-debugging-port=" + PORT, "--user-data-dir=" + PROFILE, "about:blank"];
const edge = spawn(EDGE, args, { stdio: "ignore" });

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
async function waitFor(url, tries = 60) {
  for (let i = 0; i < tries; i++) {
    try { const r = await fetch(url); if (r.ok) return true; } catch (_) {}
    await sleep(500);
  }
  return false;
}
try {
  if (!(await waitFor("http://127.0.0.1:" + PORT + "/json/version"))) throw new Error("CDP 端口未就绪");
  // 新建页面并导航
  const put = await fetch("http://127.0.0.1:" + PORT + "/json/new?" + encodeURIComponent(FILE_URL), { method: "PUT" });
  const target = await put.json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  let seq = 0; const pend = new Map(); const errors = [];
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
    else if (m.method === "Runtime.exceptionThrown") {
      const d = m.params.exceptionDetails;
      errors.push("exception: " + (d.exception ? d.exception.description : d.text));
    } else if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
      const txt = m.params.entry.text || "";
      const url = m.params.entry.url || "";
      if (/busuanzi|ibruce/i.test(txt) || /busuanzi|ibruce/i.test(url)) return;  // 访问计数器，离线必 404
      // 离线/无网时第三方脚本的加载失败只走 Log 域，应用自身的异常走 Runtime.exceptionThrown，
      // 所以这里可以安全地忽略「资源加载失败」，否则每次离线跑都会误报
      if (/Failed to load resource/i.test(txt) &&
          /ERR_FILE_NOT_FOUND|ERR_NAME_NOT_RESOLVED|ERR_INTERNET_DISCONNECTED|ERR_CONNECTION/i.test(txt)) return;
      errors.push("console.error: " + txt);
    }
  };
  function send(method, params = {}) {
    return new Promise(res => { const i = ++seq; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  }
  async function evalv(expression) {
    const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (r.result && r.result.exceptionDetails) {
      return { err: r.result.exceptionDetails.exception ? r.result.exceptionDetails.exception.description : r.result.exceptionDetails.text };
    }
    return { val: r.result && r.result.result ? r.result.result.value : undefined };
  }
  await send("Runtime.enable");
  await send("Log.enable");
  await send("Page.enable");
  await sleep(2500); // 等 boot

  // 1. 初始渲染
  let r = await evalv("({rules:document.querySelectorAll('.rule').length, h2:document.querySelector('#pane0 h2').textContent, nav:document.querySelector('#stepNav .st b').textContent})");
  ok("规则网格已渲染", r.val && r.val.rules >= 10, JSON.stringify(r.err || r.val));
  ok("中文标题渲染", r.val && /书库/.test(r.val.h2), r.err || (r.val && r.val.h2));
  ok("无初始化报错", errors.length === 0, errors.join(" | "));

  // 2. 语言切换
  await evalv("document.getElementById('btnLang').click()");
  await sleep(400);
  r = await evalv("({h2:document.querySelector('#pane0 h2').textContent, btn:document.getElementById('btnLang').textContent, rules:document.querySelector('.rule .t').textContent})");
  ok("切到英文界面", /Library/.test(r.val.h2), JSON.stringify(r.val));
  await evalv("document.getElementById('btnLang').click()");
  await sleep(300);

  // 3. 帮助/关于弹窗
  await evalv("document.getElementById('btnHelp').click()");
  await sleep(300);
  r = await evalv("({dlg:!!document.querySelector('.dlg'), t:document.querySelector('.dlg .dh')?document.querySelector('.dlg .dh').childNodes[0].textContent:''})");
  ok("帮助弹窗打开", r.val.dlg && /帮助/.test(r.val.t), JSON.stringify(r.val));
  await evalv("document.querySelector('.dlg .x').click()");
  await sleep(200);
  r = await evalv("!document.querySelector('.dlg')");
  ok("弹窗可关闭", r.val === true);

  // 3b. 截图改在分章批量测试后（7d），此处仅回书库页
  await evalv("window.goStep(0)");

  // 4. 注入文件入库（等效拖拽）
  const bookText = "书名：《冒烟测试书》\n作者：测试君\n\n序章 引子\n这是序章正文内容。\n\n"
    + "第1章 开端\n请收藏本站 www.example.com\n正文甲第一段。\n\n第2章 发展\n上一页\n正文乙第二段。\n\n第3章 终章\n（乱码\uFFFD测试行）\n正文丙第三段，收尾。\n";
  r = await evalv(`(async () => {
    const f = new File([${JSON.stringify(bookText)}], "冒烟测试书.txt", {type:"text/plain"});
    await window.dropFilesToLib([f], false);
    await new Promise(r2=>setTimeout(r2,1200));
    const rows = document.querySelectorAll('#libTbl tr');
    return { rows: rows.length - 1, name: rows[1] ? rows[1].children[1].textContent : '' , st: document.querySelector('#libInfo').textContent};
  })()`);
  ok("注入文件入库成功", r.val && r.val.rows === 1, JSON.stringify(r.err || r.val));
  ok("书名识别", r.val && /冒烟测试书/.test(r.val.name), JSON.stringify(r.val));

  // 5. 清洗预览（需先载入所选书文本）
  r = await evalv(`(async () => {
    await window.previewClean();
    await new Promise(r2=>setTimeout(r2,600));
    const panes = document.querySelectorAll('#cleanPane .pane');
    return {panes: panes.length, hasDel: !!document.querySelector('#cleanPane .del'), info: document.querySelector('#cleanInfo').textContent};
  })()`);
  ok("清洗预览双栏渲染", r.val && r.val.panes === 2, JSON.stringify(r.err || r.val));

  // 6. 应用清洗（带异常栈诊断）
  r = await evalv(`(async () => {
    window.__dbg='';
    try{ await window.applyClean(); }
    catch(e){ window.__dbg=(e.stack||e.message)+' | '+(e&&e.message); }
    await new Promise(r2=>setTimeout(r2,600));
    return {msg: document.querySelector('#cleanInfo').textContent, err: window.__dbg};
  })()`);
  console.log("  · 清洗诊断:", JSON.stringify(r.val || r.err));
  ok("清洗应用完成", r.val && /清洗/.test(r.val.msg) && !/删除 0 行/.test(r.val.msg) && !r.val.err, JSON.stringify(r.err || r.val));

  // 7b. 分阶段探针：定位正则/清洗/导出错误的真实来源
  const probe = await evalv(`(async () => {
    const o = {};
    try { o.regValue = document.querySelector('#chapRegex').value; o.regLen = document.querySelector('#chapRegex').value.length; } catch(e){ o.r1 = e.message; }
    // File 构造探针（独立于 app 逻辑）
    try {
      const f0 = new File(["书名：X 内容ABC测试"], "x.txt", {type:"text/plain"});
      const ab = await f0.arrayBuffer();
      o.fileProbe = ab.byteLength;
      o.fileText = new TextDecoder().decode(ab);
    } catch(e){ o.fileErr = (e && e.message); }
    try {
      const b = (window.selectedBooks ? window.selectedBooks() : [])[0];
      if (!b) { o.phase = 'noBook'; return o; }
      o.phase = 'haveBook';
      try { o.t = await window.bookText(b); o.tlen = o.t.length; o.head = o.t.slice(0, 80); } catch(e){ o.phase = 'bookText ERR: ' + e.message; return o; }
      try { await window.previewClean(); } catch(e){ o.phase = 'preview ERR: ' + e.message; return o; }
      o.phase = 'preview ok';
    } catch(e){ o.phase = 'outer ERR: ' + e.message; }
    return o;
  })()`);
  console.log("  · 探针:", JSON.stringify(probe.val || probe.err, null, 1));
  let dbg = await evalv(`(async () => {
    window.goStep(2);
    await new Promise(r2=>setTimeout(r2,300));
    const sel=document.querySelector('#chapBook');
    const snap={selVal:sel?sel.value:'x', n:sel?sel.options.length:0,
      opt0:sel&&sel.options[0]?(sel.options[0].value+'|'+sel.options[0].textContent):'-',
      txtLen:(window.bookText&&true)?-1:0};
    window.__dbg='';
    try{ await window.tryChapters(); }
    catch(e){ window.__dbg=(e.stack||e.message)+'\\n'+(e&&e.message); }
    await new Promise(r2=>setTimeout(r2,400));
    snap.err=window.__dbg;
    snap.chs=document.querySelectorAll('#chapList .ch').length;
    snap.info=document.querySelector('#chapInfo').textContent;
    return snap;
  })()`);
  console.log("  · 分章诊断:", JSON.stringify(dbg.val||dbg.err, null, 1));
  ok("分章 select 有书", dbg.val && dbg.val.n === 1 && dbg.val.selVal === "0", JSON.stringify(dbg.val||dbg.err));
  // 样本含「书名/作者」元信息行：v1.4.0 起纯元信息的「开篇」不再单独成章，
  // 所以这里是 4 章、首章就是正文第一个标题（与桌面版 python 行为一致）
  ok("分章识别出 4 章", dbg.val && dbg.val.chs === 4, JSON.stringify(dbg.val));
  let titles = await evalv(`window._lastTry ? window._lastTry.chs.map(c=>c.t) : []`);
  ok("首章是正文标题而非开篇", titles.val && titles.val[0] === "序章 引子", JSON.stringify(titles.val));
  ok("含序章与第3章", titles.val && titles.val.includes("序章 引子") && titles.val.includes("第3章 终章"), JSON.stringify(titles.val));
  if (dbg.val && dbg.val.chs > 0) {
    await evalv(`window.applyChapters()`);
  }

  // 7c. 批量一键分章（v1.3 新功能）：整库按钮应把结果保存到各书
  r = await evalv(`(async () => {
    document.getElementById('btnChapAll').click();
    await new Promise(r2=>setTimeout(r2,1200));
    return {info: document.querySelector('#chapAllInfo').textContent,
            sel: document.querySelector('#chapBook option') ? document.querySelector('#chapBook option').textContent : ''};
  })()`);
  ok("批量一键分章完成", r.val && /完成/.test(r.val.info), JSON.stringify(r.err || r.val));
  ok("分章结果已保存到书(下拉带章数)", r.val && /\[\d+章\]/.test(r.val.sel), JSON.stringify(r.val));

  // 7d. 截图（分章页：批量按钮 + 日志默认展开）用于 UI 复查
  try {
    await sleep(400);
    const shot = await send("Page.captureScreenshot", { format: "png" });
    if (shot.result && shot.result.data) {
      fs.writeFileSync("web/_ui_shot.png", Buffer.from(shot.result.data, "base64"));
      console.log("  分章页截图已存 web/_ui_shot.png");
    }
  } catch (e) { console.error("截图失败:", e.message); }

  // 8. 导出（EPUB+合并TXT；headless 下载只触发不落盘）
  r = await evalv(`(async () => {
    window.goStep(3);
    await new Promise(r2=>setTimeout(r2,200));
    const selBefore = document.querySelector('#outSelInfo').textContent;
    document.getElementById('fmtEpub').checked = true;
    document.getElementById('fmtTxt').checked = true;
    document.getElementById('fmtSplit').checked = false;
    window.__dbg='';
    try{ await window.runExport(); }
    catch(e){ window.__dbg=(e.stack||e.message)+' | '+(e&&e.message); }
    await new Promise(r2=>setTimeout(r2,3000));
    const rows = document.querySelectorAll('#outTbl tr');
    return {sel: selBefore, out: document.querySelector('#outMsg').textContent, rows: rows.length-1,
      st: rows[1]?rows[1].children[1].textContent:'', err: window.__dbg};
  })()`);
  console.log("  · 导出诊断:", JSON.stringify(r.val && r.val.err ? r.val.err : (r.val && {out:r.val.out, st:r.val.st})));
  ok("导出面板显示已选 1 本", r.val && /1/.test(r.val.sel), JSON.stringify(r.err || r.val));
  ok("导出完成无失败", r.val && r.val.out && /成功 1 · 失败 0/.test(r.val.out) && r.val.rows >= 1 && !r.val.err, JSON.stringify(r.err || r.val));
  ok("结果行状态正常", r.val && /epub/i.test(r.val.st), JSON.stringify(r.val));

  // 8b. 「常用写法」窗口：8 条模板，能填进全局正则 / 本书专用
  r = await evalv(`(async () => {
    window.goStep(2);
    await new Promise(r2=>setTimeout(r2,250));
    document.getElementById('chapReHelp').click();
    await new Promise(r2=>setTimeout(r2,250));
    const rows = document.querySelectorAll('.dlg tbody tr').length;
    const radios = document.querySelectorAll('.dlg input[name=tplsel]').length;
    document.querySelectorAll('.dlg input[name=tplsel]')[1].checked = true;   /* 第一折 */
    document.querySelector('.dlg [data-fill=global]').click();
    await new Promise(r2=>setTimeout(r2,200));
    const g = document.getElementById('chapRegex').value;
    const closed = !document.querySelector('.dlg');
    document.getElementById('chapReHelp').click();
    await new Promise(r2=>setTimeout(r2,200));
    document.querySelectorAll('.dlg input[name=tplsel]')[0].checked = true;
    document.querySelector('.dlg [data-fill=book]').click();
    await new Promise(r2=>setTimeout(r2,200));
    const bk = document.getElementById('bookRegex').value;
    const onBook = !!(window.chapBookObj && window.chapBookObj().chapRe);
    /* 收尾：两格清空，别留给下次打开 */
    document.getElementById('chapRegex').value = '';
    document.getElementById('bookRegex').value = '';
    window.storeBookRegex();
    return {rows, radios, g, closed, bk, onBook};
  })()`);
  ok("常用写法列出 8 条模板", r.val && r.val.rows === 8 && r.val.radios === 8, JSON.stringify(r.err || r.val));
  ok("模板填入全局正则生效", r.val && /折/.test(r.val.g) && r.val.closed, JSON.stringify(r.val));
  ok("模板填入本书专用生效", r.val && /章/.test(r.val.bk) && r.val.onBook, JSON.stringify(r.val));

  // 9. 全部捕获的 JS 错误汇总
  ok("全程无 JS 运行时错误", errors.length === 0, errors.join(" | "));

  await send("Page.close");
  ws.close();
} catch (e) {
  console.error("冒烟运行失败：", e.message);
  process.exitCode = 1;
} finally {
  try { edge.kill(); } catch (_) {}
}
const failed = results.filter(x => x.startsWith("✗")).length;
console.log("\n冒烟结果：" + (results.length - failed) + " 通过 / " + failed + " 失败");
process.exit(failed ? 1 : 0);
