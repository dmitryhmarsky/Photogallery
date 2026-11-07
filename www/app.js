/* Съёмки: календарь фотографа. Данные лежат в том же бакете R2, что и Photo Gallery:
   _calendar/events.json (события), _calendar/refs/<id>/... (референсы), _calendar/clients.json (клиенты с компьютера). */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const MONTHS = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"];
  const MONTHS_G = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"];
  const WD_S = ["Вс","Пн","Вт","Ср","Чт","Пт","Сб"];
  const WD_L = ["воскресенье","понедельник","вторник","среда","четверг","пятница","суббота"];
  const REMIND = [[10080,"за неделю"],[1440,"за день"],[180,"за 3 часа"],[60,"за 1 час"],[30,"за 30 мин"],[0,"в момент съёмки"]];
  const KEY_EVENTS = "_calendar/events.json", KEY_CLIENTS = "_calendar/clients.json";
  const LS_CFG = "shoots_cfg", LS_DATA = "shoots_data";
  const cap = window.Capacitor;
  const native = !!(cap && cap.isNativePlatform && cap.isNativePlatform());
  const LN = native ? cap.registerPlugin("LocalNotifications") : null;
  const WB = native ? cap.registerPlugin("WidgetBridge") : null;

  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* переполнено/запрещено */ } },
  };
  let cfg = Object.assign({ account: "", access: "", secret: "", bucket: "", endpoint: "", remind: [1440, 60] }, store.get(LS_CFG, {}));
  let data = store.get(LS_DATA, null) || { events: {}, trash: [] };
  data.trash = data.trash || [];
  let clients = [];
  let view = { y: 0, m: 0, sel: "", tab: "cal", seg: "up" };
  let editing = null;      // редактируемая копия съёмки
  let viewerIdx = 0, skipPop = false;

  /* ---------- утилиты ---------- */
  const pad = (n) => String(n).padStart(2, "0");
  const isoDate = (d) => d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  const parseDate = (s) => { const p = s.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); };
  const todayIso = () => isoDate(new Date());
  const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  const cfgOk = () => !!(cfg.account && cfg.access && cfg.secret && cfg.bucket) || !!(cfg.endpoint && cfg.access && cfg.secret && cfg.bucket);
  function toast(t) { const e = $("toast"); e.textContent = t; e.classList.add("show"); clearTimeout(toast.t); toast.t = setTimeout(() => e.classList.remove("show"), 2600); }
  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function evTs(ev) { const d = parseDate(ev.date); const t = (ev.time || "09:00").split(":"); d.setHours(+t[0], +t[1], 0, 0); return d.getTime(); }
  function dayLabel(iso) {
    const t = todayIso(), tm = isoDate(new Date(Date.now() + 864e5));
    if (iso === t) return "Сегодня"; if (iso === tm) return "Завтра";
    const d = parseDate(iso); return WD_S[d.getDay()] + ", " + d.getDate() + " " + MONTHS_G[d.getMonth()].slice(0, 3);
  }
  const live = () => Object.values(data.events).filter((e) => !e.del);
  const byTime = (a, b) => evTs(a) - evTs(b);
  function saveLocal() { store.set(LS_DATA, data); }

  /* ---------- IndexedDB: файлы фото (на телефоне, пока не загружены, и как кэш) ---------- */
  let dbp = null;
  function db() {
    if (!dbp) dbp = new Promise((res, rej) => {
      const r = indexedDB.open("shoots", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("blobs");
      r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
    });
    return dbp;
  }
  async function idb(mode, fn) {
    try {
      const d = await db();
      return await new Promise((res, rej) => { const tx = d.transaction("blobs", mode); const out = fn(tx.objectStore("blobs")); tx.oncomplete = () => res(out && out.result); tx.onerror = () => rej(tx.error); });
    } catch (e) { return undefined; }
  }
  const blobGet = (k) => idb("readonly", (s) => s.get(k));
  const blobPut = (k, b) => idb("readwrite", (s) => s.put(b, k));
  const blobDel = (k) => idb("readwrite", (s) => s.delete(k));
  const urlCache = {};
  async function refUrl(key) {
    if (urlCache[key]) return urlCache[key];
    let b = await blobGet(key);
    if (!b && cfgOk()) { try { b = await R2.getBlob(cfg, key); await blobPut(key, b); } catch (e) { b = null; } }
    if (!b) return "";
    return (urlCache[key] = URL.createObjectURL(b));
  }

  /* ---------- сжатие фото ---------- */
  async function shrink(file, max, q) {
    let bmp;
    try { bmp = await createImageBitmap(file, { imageOrientation: "from-image" }); }
    catch (e) { bmp = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = URL.createObjectURL(file); }); }
    const w = bmp.width, h = bmp.height, k = Math.min(1, max / Math.max(w, h));
    const c = document.createElement("canvas"); c.width = Math.round(w * k); c.height = Math.round(h * k);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    return new Promise((res) => c.toBlob((b) => res(b), "image/jpeg", q));
  }

  /* ---------- синхронизация ---------- */
  let syncing = false, syncTimer = null, lastSync = store.get("shoots_last", 0);
  function setStatus(t) { $("syncSt").textContent = t; }
  function statusText() { return !cfgOk() ? "Облако не настроено" : (lastSync ? "Синхронизировано " + new Date(lastSync).toTimeString().slice(0, 5) : "Не синхронизировано"); }
  function mergeEvents(remote) {
    const out = {}; const all = Object.assign({}, remote || {});
    for (const id in data.events) { const a = data.events[id], b = all[id]; all[id] = !b || (a.u || 0) >= (b.u || 0) ? a : b; }
    const cutoff = Date.now() - 60 * 864e5;
    for (const id in all) { const e = all[id]; if (e.del && (e.u || 0) < cutoff) continue; out[id] = e; }
    return out;
  }
  async function sync(manual) {
    if (!cfgOk()) { if (manual) toast("Сначала настройте облако"); return false; }
    if (syncing) return false;
    syncing = true; setStatus("Синхронизация…");
    try {
      const remote = await R2.getJson(cfg, KEY_EVENTS);
      const before = JSON.stringify(remote && remote.events || {});
      data.events = mergeEvents(remote && remote.events);
      // загрузка новых фото
      for (const id in data.events) {
        const ev = data.events[id]; if (ev.del) continue;
        for (const r of ev.refs || []) {
          if (!r.pending) continue;
          const f = await blobGet(r.f), t = await blobGet(r.t);
          if (!f || !t) { r.pending = false; continue; }
          await R2.putBlob(cfg, r.f, f); await R2.putBlob(cfg, r.t, t); r.pending = false;
        }
      }
      for (const k of data.trash.slice()) { await R2.del(cfg, k); data.trash = data.trash.filter((x) => x !== k); blobDel(k); }
      if (JSON.stringify(data.events) !== before) await R2.putJson(cfg, KEY_EVENTS, { v: 1, events: data.events });
      try { const c = await R2.getJson(cfg, KEY_CLIENTS); if (c && Array.isArray(c.clients)) clients = c.clients; } catch (e) { /* список клиентов необязателен */ }
      store.set("shoots_clients", clients);
      lastSync = Date.now(); store.set("shoots_last", lastSync);
      saveLocal(); render(); afterChange(); setStatus(statusText());
      if (manual) toast("Готово: синхронизировано");
      return true;
    } catch (e) {
      setStatus("Офлайн");
      if (manual) toast(explain(e));
      return false;
    } finally { syncing = false; }
  }
  function explain(e) {
    const m = String(e && e.message || e);
    if (/R2 403/.test(m)) return "Нет доступа: проверьте ключи и имя бакета";
    if (/R2 404/.test(m)) return "Бакет не найден";
    if (/Failed to fetch|NetworkError|Load failed/.test(m)) return "Нет связи или не включён CORS. Проверьте интернет и нажмите «Подготовить бакет для телефона» в Photo Gallery на компьютере";
    return "Ошибка: " + m;
  }
  function scheduleSync() { clearTimeout(syncTimer); syncTimer = setTimeout(() => sync(false), 1200); }

  /* ---------- уведомления и виджеты ---------- */
  function hash(s) { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return Math.abs(h) % 2000000000 + 1; }
  function remindText(min, ev) {
    const where = ev.place ? " · " + ev.place : "", tm = ev.time ? ev.time : "";
    const lead = min === 0 ? "Съёмка сейчас" : "Съёмка " + (min >= 1440 ? (min / 1440 === 1 ? "завтра" : "через " + (min / 1440) + " дн.") : min >= 60 ? "через " + (min / 60) + " ч" : "через " + min + " мин");
    return lead + (tm ? ", " + tm : "") + (ev.client ? " · " + ev.client : "") + where;
  }
  async function scheduleNotifications() {
    if (!LN) return;
    try {
      const pend = await LN.getPending();
      if (pend.notifications && pend.notifications.length) await LN.cancel({ notifications: pend.notifications.map((n) => ({ id: n.id })) });
      const now = Date.now(), list = [];
      for (const ev of live().sort(byTime)) {
        const ts = evTs(ev);
        for (const min of ev.remind || []) {
          const at = ts - min * 60000; if (at <= now + 5000) continue;
          list.push({ id: hash(ev.id + ":" + min), title: ev.title || "Съёмка", body: remindText(min, ev), channelId: "shoots",
            schedule: { at: new Date(at), allowWhileIdle: true }, extra: { id: ev.id } });
        }
        if (list.length >= 120) break;
      }
      if (list.length) await LN.schedule({ notifications: list.slice(0, 120) });
    } catch (e) { /* нет разрешения: покажем в настройках */ }
  }
  async function pushWidget() {
    if (!WB) return;
    const now = Date.now();
    const arr = live().filter((e) => evTs(e) + 2 * 3600e3 > now).sort(byTime).slice(0, 8).map((e) => ({
      ts: evTs(e), when: dayLabel(e.date) + (e.time ? " · " + e.time : ""), title: e.title || "Съёмка",
      sub: [e.client, e.place].filter(Boolean).join(" · ") }));
    try { await WB.update({ json: JSON.stringify(arr) }); } catch (e) { /* виджеты не добавлены */ }
  }
  function afterChange() { scheduleNotifications(); pushWidget(); }
  async function ensurePermission(askSettings) {
    if (!LN) { toast("Уведомления работают в установленном приложении"); return; }
    try {
      await LN.createChannel({ id: "shoots", name: "Напоминания о съёмках", importance: 4, visibility: 1, vibration: true });
      let p = await LN.checkPermissions();
      if (p.display !== "granted") p = await LN.requestPermissions();
      if (p.display !== "granted") { toast("Уведомления запрещены в настройках телефона"); return; }
      try {
        const ex = await LN.checkExactNotificationSetting();
        if (ex.exact_alarm !== "granted" && askSettings) { toast("Разрешите «Будильники и напоминания»"); await LN.changeExactNotificationSetting(); }
      } catch (e) { /* старые версии Android */ }
      toast("Напоминания включены"); afterChange();
    } catch (e) { toast("Не удалось включить уведомления"); }
  }

  /* ---------- отрисовка ---------- */
  function cardFor(ev) {
    const b = el("button", "ev"); b.type = "button";
    const t = el("div", "t", ev.time || "весь день");
    if (!ev.time) t.style.fontSize = "13px";
    const body = el("div", "b");
    body.appendChild(el("div", "n", ev.title || "Без названия"));
    const sub = [ev.client, ev.place].filter(Boolean).join(" · ");
    if (sub) body.appendChild(el("div", "s", sub));
    const m = el("div", "m");
    if (ev.notes) m.appendChild(el("span", "", "Заметки"));
    if ((ev.refs || []).length) m.appendChild(el("span", "", "Фото: " + ev.refs.length));
    if ((ev.remind || []).length) m.appendChild(el("span", "", "Напоминание"));
    if (m.children.length) body.appendChild(m);
    b.appendChild(t); b.appendChild(body);
    b.onclick = () => openEditor(ev.id);
    return b;
  }
  function renderCal() {
    $("monthName").textContent = MONTHS[view.m] + " " + view.y;
    const days = $("days"); days.textContent = "";
    const first = new Date(view.y, view.m, 1), lead = (first.getDay() + 6) % 7;
    const start = new Date(view.y, view.m, 1 - lead), counts = {};
    live().forEach((e) => { counts[e.date] = (counts[e.date] || 0) + 1; });
    const t = todayIso();
    for (let i = 0; i < 42; i++) {
      const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i), iso = isoDate(d);
      if (i >= 35 && d.getMonth() !== view.m) break;
      const c = el("button", "day" + (d.getMonth() !== view.m ? " out" : "") + (iso === t ? " today" : "") + (iso === view.sel ? " sel" : ""));
      c.type = "button"; c.appendChild(el("b", "", String(d.getDate())));
      if (counts[iso]) { const dots = el("span", "dots"); for (let k = 0; k < Math.min(3, counts[iso]); k++) dots.appendChild(el("i")); c.appendChild(dots); }
      c.onclick = () => { view.sel = iso; if (d.getMonth() !== view.m) { view.y = d.getFullYear(); view.m = d.getMonth(); } renderCal(); };
      days.appendChild(c);
    }
    const sd = parseDate(view.sel);
    $("dayTitle").textContent = sd.getDate() + " " + MONTHS_G[sd.getMonth()] + ", " + WD_L[sd.getDay()];
    const list = $("dayList"); list.textContent = "";
    const evs = live().filter((e) => e.date === view.sel).sort(byTime);
    evs.forEach((e) => list.appendChild(cardFor(e)));
    if (!evs.length) {
      const em = el("div", "empty", "На этот день съёмок нет");
      const b = el("button", "btn ghost", "Добавить съёмку"); b.onclick = () => openEditor(null, view.sel); em.appendChild(b); list.appendChild(em);
    }
  }
  function renderList() {
    const box = $("allList"); box.textContent = "";
    document.querySelectorAll("#seg button").forEach((b) => b.classList.toggle("on", b.dataset.v === view.seg));
    const now = Date.now();
    let evs = live().sort(byTime);
    evs = view.seg === "up" ? evs.filter((e) => evTs(e) + 3 * 3600e3 >= now) : evs.filter((e) => evTs(e) + 3 * 3600e3 < now).reverse();
    let last = "";
    evs.forEach((e) => {
      const d = parseDate(e.date), key = MONTHS[d.getMonth()] + " " + d.getFullYear();
      if (key !== last) { box.appendChild(el("div", "month-sep", key)); last = key; }
      const c = cardFor(e); c.querySelector(".t").textContent = d.getDate() + " " + MONTHS_G[d.getMonth()].slice(0, 3) + (e.time ? "\n" + e.time : "");
      c.querySelector(".t").style.whiteSpace = "pre-line"; box.appendChild(c);
    });
    if (!evs.length) box.appendChild(el("div", "empty", view.seg === "up" ? "Предстоящих съёмок нет" : "Прошедших съёмок нет"));
  }
  function render() { renderCal(); renderList(); $("clientList").textContent = ""; clients.forEach((c) => { const o = el("option"); o.value = c.name; $("clientList").appendChild(o); }); }
  const TITLES = { cal: "Съёмки", list: "Все съёмки", set: "Настройки" };
  function showTab(t) {
    view.tab = t;
    $("pgCal").hidden = t !== "cal"; $("pgList").hidden = t !== "list"; $("pgSet").hidden = t !== "set";
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.t === t));
    $("title").textContent = TITLES[t]; $("addBtn").hidden = t === "set";
    $("main").scrollTop = 0;
    if (t === "set") fillSettings(); if (t === "list") renderList();
  }

  /* ---------- чипы напоминаний ---------- */
  function drawChips(box, selected, onChange) {
    box.textContent = "";
    REMIND.forEach(([min, label]) => {
      const c = el("button", "chip" + (selected.includes(min) ? " on" : ""), label); c.type = "button";
      c.onclick = () => { const i = selected.indexOf(min); if (i >= 0) selected.splice(i, 1); else selected.push(min); selected.sort((a, b) => b - a); drawChips(box, selected, onChange); if (onChange) onChange(); };
      box.appendChild(c);
    });
  }

  /* ---------- редактор ---------- */
  function openEditor(id, date) {
    const ev = id ? JSON.parse(JSON.stringify(data.events[id])) :
      { id: uid(), title: "", client: "", place: "", date: date || view.sel || todayIso(), time: "", notes: "", remind: cfg.remind.slice(), refs: [], isNew: true };
    editing = ev;
    $("shTitle").textContent = ev.isNew ? "Новая съёмка" : "Съёмка";
    $("eTitle").value = ev.title; $("eClient").value = ev.client; $("ePlace").value = ev.place;
    $("eDate").value = ev.date; $("eTime").value = ev.time; $("eNotes").value = ev.notes;
    drawChips($("eRem"), editing.remind);
    drawRefs(); $("delBtn").hidden = !!ev.isNew;
    $("sheet").classList.add("open"); $("sheet").setAttribute("aria-hidden", "false");
    history.pushState({ s: 1 }, "");
  }
  function closeEditor(fromPop) {
    if (!$("sheet").classList.contains("open")) return;
    $("sheet").classList.remove("open"); $("sheet").setAttribute("aria-hidden", "true"); editing = null;
    if (!fromPop && history.state && history.state.s) { skipPop = true; history.back(); }
  }
  async function drawRefs() {
    const box = $("eRefs"); box.textContent = "";
    for (let i = 0; i < editing.refs.length; i++) {
      const r = editing.refs[i], w = el("button", "ref"); w.type = "button";
      const im = el("img"); im.alt = ""; w.appendChild(im); if (r.pending) w.appendChild(el("span", "st"));
      w.onclick = () => openViewer(i); box.appendChild(w);
      refUrl(r.t).then((u) => { if (u) im.src = u; });
    }
  }
  async function addRefs(files) {
    const ev = editing; if (!ev) return;
    $("addRef").textContent = "Обработка…";
    for (const f of files) {
      try {
        const id = uid(), base = "_calendar/refs/" + ev.id + "/" + id;
        const full = await shrink(f, 1800, 0.85), th = await shrink(f, 480, 0.8);
        await blobPut(base + "-f.jpg", full); await blobPut(base + "-t.jpg", th);
        ev.refs.push({ id: id, name: f.name || "photo", f: base + "-f.jpg", t: base + "-t.jpg", pending: true });
      } catch (e) { toast("Не удалось добавить фото"); }
    }
    $("addRef").textContent = "Добавить фото"; drawRefs();
  }
  function commit() {
    const ev = editing; if (!ev) return;
    ev.title = $("eTitle").value.trim(); ev.client = $("eClient").value.trim(); ev.place = $("ePlace").value.trim();
    ev.date = $("eDate").value || todayIso(); ev.time = $("eTime").value; ev.notes = $("eNotes").value.trim();
    if (!ev.title) ev.title = ev.client ? "Съёмка: " + ev.client : "Съёмка";
    // файлы, удалённые из редактора, уберём из облака
    const old = data.events[ev.id], keep = new Set(ev.refs.flatMap((r) => [r.f, r.t]));
    if (old) (old.refs || []).forEach((r) => { if (!keep.has(r.f)) { data.trash.push(r.f, r.t); } });
    delete ev.isNew; ev.u = Date.now(); data.events[ev.id] = ev;
    view.sel = ev.date; const d = parseDate(ev.date); view.y = d.getFullYear(); view.m = d.getMonth();
    saveLocal(); closeEditor(); render(); afterChange(); scheduleSync();
    if ((ev.remind || []).length && LN) ensurePermission(false);
    toast("Сохранено");
  }
  function removeEvent() {
    const ev = editing; if (!ev || ev.isNew) return;
    if (!confirm("Удалить съёмку «" + ev.title + "»?")) return;
    const old = data.events[ev.id];
    (old.refs || []).forEach((r) => data.trash.push(r.f, r.t));
    data.events[ev.id] = { id: ev.id, del: true, u: Date.now(), date: ev.date };
    saveLocal(); closeEditor(); render(); afterChange(); scheduleSync(); toast("Удалено");
  }

  /* ---------- просмотр референсов ---------- */
  async function openViewer(i) {
    viewerIdx = i; const r = editing.refs[i]; if (!r) return;
    $("vCnt").textContent = (i + 1) + " / " + editing.refs.length;
    $("vImg").removeAttribute("src");
    $("viewer").classList.add("open"); history.pushState({ v: 1 }, "");
    const u = await refUrl(r.f); if (viewerIdx === i && u) $("vImg").src = u; else if (!u) { const t = await refUrl(r.t); if (t) $("vImg").src = t; }
  }
  function closeViewer(fromPop) { $("viewer").classList.remove("open"); if (!fromPop && history.state && history.state.v) { skipPop = true; history.back(); } }
  function deleteRef() {
    const r = editing && editing.refs[viewerIdx]; if (!r) return;
    if (!confirm("Удалить это фото из съёмки?")) return;
    editing.refs.splice(viewerIdx, 1); closeViewer(); drawRefs();
  }

  /* ---------- настройки ---------- */
  function fillSettings() {
    $("cAcc").value = cfg.account; $("cAccess").value = cfg.access; $("cSecret").value = cfg.secret; $("cBucket").value = cfg.bucket;
    drawChips($("defRem"), cfg.remind, () => { store.set(LS_CFG, cfg); });
    $("syncInfo").textContent = statusText();
  }
  function applyPaste() {
    const t = $("cPaste").value.trim(); if (!t) return true;
    try {
      const j = JSON.parse(t);
      $("cAcc").value = j.account || j.account_id || ""; $("cAccess").value = j.access || j.access_key_id || "";
      $("cSecret").value = j.secret || j.secret_access_key || ""; $("cBucket").value = j.bucket || "";
      if (j.endpoint) cfg.endpoint = j.endpoint; $("cPaste").value = ""; return true;
    } catch (e) { $("cfgMsg").className = "msg err"; $("cfgMsg").textContent = "Не удалось разобрать вставленный текст. Нужна строка из Photo Gallery."; return false; }
  }
  async function saveCfg() {
    if (!applyPaste()) return;
    cfg.account = $("cAcc").value.trim(); cfg.access = $("cAccess").value.trim(); cfg.secret = $("cSecret").value.trim(); cfg.bucket = $("cBucket").value.trim();
    store.set(LS_CFG, cfg);
    const m = $("cfgMsg"); m.className = "msg";
    if (!cfgOk()) { m.className = "msg err"; m.textContent = "Заполните Account ID, ключи и имя бакета."; return; }
    m.textContent = "Проверяю подключение…";
    try {
      const st = await R2.head(cfg);
      if (st === 200) { m.textContent = "Подключено. Загружаю данные…"; await sync(true); m.textContent = "Всё работает: календарь связан с облаком."; }
      else if (st === 403) { m.className = "msg err"; m.textContent = "Облако отклонило ключи (403). Проверьте Access Key, Secret и что у токена есть права на запись."; }
      else if (st === 404) { m.className = "msg err"; m.textContent = "Бакет не найден. Проверьте имя бакета и Account ID."; }
      else { m.className = "msg err"; m.textContent = "Ответ облака: " + st; }
    } catch (e) { m.className = "msg err"; m.textContent = explain(e); }
  }

  /* ---------- запуск ---------- */
  function init() {
    clients = store.get("shoots_clients", []);
    const n = new Date(); view.y = n.getFullYear(); view.m = n.getMonth(); view.sel = todayIso();
    $("prevM").onclick = () => { view.m--; if (view.m < 0) { view.m = 11; view.y--; } renderCal(); };
    $("nextM").onclick = () => { view.m++; if (view.m > 11) { view.m = 0; view.y++; } renderCal(); };
    $("todayBtn").onclick = () => { const t = new Date(); view.y = t.getFullYear(); view.m = t.getMonth(); view.sel = todayIso(); renderCal(); };
    document.querySelectorAll("#tabs button").forEach((b) => (b.onclick = () => showTab(b.dataset.t)));
    document.querySelectorAll("#seg button").forEach((b) => (b.onclick = () => { view.seg = b.dataset.v; renderList(); }));
    $("addBtn").onclick = () => openEditor(null, view.tab === "cal" ? view.sel : todayIso());
    $("shCancel").onclick = () => closeEditor(); $("shSave").onclick = commit; $("delBtn").onclick = removeEvent;
    $("addRef").onclick = () => $("refInput").click();
    $("refInput").onchange = (e) => { const f = [...e.target.files]; e.target.value = ""; if (f.length) addRefs(f); };
    $("vClose").onclick = () => closeViewer(); $("vDel").onclick = deleteRef;
    let sx = null; const st = $("vStage");
    st.addEventListener("touchstart", (e) => { sx = e.touches[0].clientX; }, { passive: true });
    st.addEventListener("touchend", (e) => { if (sx === null || !editing) return; const dx = e.changedTouches[0].clientX - sx; sx = null;
      if (Math.abs(dx) > 50) openViewerStep(dx < 0 ? 1 : -1); }, { passive: true });
    $("saveCfg").onclick = saveCfg; $("syncNow").onclick = () => sync(true); $("permBtn").onclick = () => ensurePermission(true);
    window.addEventListener("popstate", () => { if (skipPop) { skipPop = false; return; } if ($("viewer").classList.contains("open")) closeViewer(true); else if ($("sheet").classList.contains("open")) closeEditor(true); });
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && cfgOk() && Date.now() - lastSync > 60000) sync(false); });
    if (LN) LN.addListener("localNotificationActionPerformed", (a) => { const id = a && a.notification && a.notification.extra && a.notification.extra.id; if (id && data.events[id] && !data.events[id].del) openEditor(id); });
    render(); showTab("cal"); setStatus(statusText());
    if (cfgOk()) sync(false); else showTab("set");
    afterChange();
  }
  function openViewerStep(d) { const n = editing.refs.length; if (n < 2) return; openViewer((viewerIdx + d + n) % n); }
  window.__shoots = { sync: sync, data: () => data, cfg: () => cfg, openEditor: openEditor };
  init();
})();
