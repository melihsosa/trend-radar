// Trend Radar açılır penceresi
(function () {
  "use strict";

  var hasChrome = typeof chrome !== "undefined" && chrome.storage;
  var W = 400;
  var page = 0;

  // ------------------------------------------------------------ depolama
  function getSync(keys) {
    return new Promise(function (res) {
      if (!hasChrome) return res({});
      chrome.storage.sync.get(keys, res);
    });
  }
  function getLocal(keys) {
    return new Promise(function (res) {
      if (!hasChrome) return res({});
      chrome.storage.local.get(keys, res);
    });
  }
  function setLocal(obj) {
    if (hasChrome) chrome.storage.local.set(obj);
  }

  function dataUrlFrom(cfg) {
    if (cfg.dataUrl) return cfg.dataUrl;
    if (cfg.ghUser && cfg.ghRepo) {
      return "https://raw.githubusercontent.com/" + cfg.ghUser + "/" + cfg.ghRepo + "/main/data/latest.json";
    }
    return null;
  }

  // ------------------------------------------------------------ yardımcılar
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  var SVG = "http://www.w3.org/2000/svg";
  function svg(tag, attrs) {
    var e = document.createElementNS(SVG, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  // "bugün 07:03", "dün 07:03" ya da "22 Eyl 07:03" (bilgisayarın saat dilimiyle)
  function fmtUpdated(iso) {
    var d = new Date(iso);
    if (isNaN(d)) return "";
    var hm = d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var day = new Date(d); day.setHours(0, 0, 0, 0);
    var diff = Math.round((today - day) / 86400000);
    if (diff === 0) return "bugün " + hm;
    if (diff === 1) return "dün " + hm;
    return d.toLocaleDateString("tr-TR", { day: "numeric", month: "short" }) + " " + hm;
  }
  function countryName(c) {
    var m = { US: "ABD", TR: "Türkiye", GB: "İngiltere", DE: "Almanya" };
    return m[c] || c || "";
  }

  // ------------------------------------------------------------ çizim
  function sparkline(values, cls) {
    var s = svg("svg", { width: 64, height: 24, viewBox: "0 0 64 24", "aria-hidden": "true", "class": cls });
    if (!values || values.length < 2) return s;
    var max = Math.max.apply(null, values), min = Math.min.apply(null, values);
    var step = 60 / (values.length - 1);
    var pts = values.map(function (v, i) {
      var y = 21 - ((v - min) / ((max - min) || 1)) * 18;
      return (2 + i * step).toFixed(1) + "," + y.toFixed(1);
    }).join(" ");
    s.appendChild(svg("polyline", {
      points: pts, fill: "none", stroke: "currentColor",
      "stroke-width": "1.8", "stroke-linejoin": "round", "stroke-linecap": "round"
    }));
    return s;
  }

  function renderProducts(list) {
    var box = document.getElementById("products");
    box.textContent = "";
    if (!list || !list.length) {
      box.appendChild(el("div", "empty", "Henüz talep verisi yok. İlk günlük tarama bittiğinde burada görünecek."));
      return;
    }
    list.forEach(function (p, i) {
      var up = p.change >= 0;
      var cls = up ? "up" : "down";
      var row = el("div", "row");
      row.appendChild(el("div", "rank", String(i + 1)));
      var mid = el("div");
      mid.style.minWidth = "0";
      var nm = el("div", "pname", p.name);
      nm.title = p.keyword ? "Google araması: " + p.keyword : p.name;
      mid.appendChild(nm);
      mid.appendChild(el("div", "porigin", (p.origin || "") + (p.stale ? " · eski veri" : "")));
      row.appendChild(mid);
      row.appendChild(sparkline(p.spark, cls));
      var chg = el("div", "chg " + cls);
      var arrow = svg("svg", { width: 10, height: 10, viewBox: "0 0 10 10", "aria-hidden": "true" });
      arrow.appendChild(svg("path", { d: up ? "M5 1L9 8H1Z" : "M5 9L1 2H9Z", fill: "currentColor" }));
      chg.appendChild(arrow);
      var v = Math.abs(p.change);
      chg.appendChild(el("span", null, (up ? "+" : "−") + (v % 1 === 0 ? v : v.toFixed(1)) + "%"));
      chg.setAttribute("aria-label", (up ? "yüzde " + v + " artış" : "yüzde " + v + " düşüş"));
      row.appendChild(chg);
      box.appendChild(row);
    });
  }

  function renderTrends(list) {
    var box = document.getElementById("trends");
    box.textContent = "";
    if (!list || !list.length) {
      box.appendChild(el("div", "empty", "Bugün yeni akım bulunamadı."));
      return;
    }
    list.forEach(function (t) {
      var card = el("article", "card");
      var top = el("div", "card-top");
      top.appendChild(el("div", "tname", t.name));
      top.appendChild(el("div", "pill heat", t.heat || "Yükseliyor"));
      card.appendChild(top);
      if (t.desc) card.appendChild(el("div", "tdesc", t.desc));
      if (t.why) card.appendChild(el("div", "twhy", t.why));
      var meta = el("div", "tmeta");
      var srcs = t.sources || [];
      if (srcs.length >= 2) meta.appendChild(el("span", "multi", "Çok platformda"));
      srcs.forEach(function (s) { meta.appendChild(el("span", "src", s)); });
      if (meta.childNodes.length) card.appendChild(meta);
      if (t.idea) {
        var idea = el("div", "idea");
        idea.appendChild(el("b", null, "Ürün fikri: "));
        idea.appendChild(document.createTextNode(t.idea));
        card.appendChild(idea);
      }
      box.appendChild(card);
    });
  }

  function renderStatus(status) {
    var box = document.getElementById("sources");
    box.textContent = "";
    var order = ["TikTok", "YouTube", "Reddit", "Google", "Yapay zeka"];
    order.forEach(function (name) {
      var s = status && status[name];
      if (!s) return;
      var d = el("span", "dot" + (s.ok ? "" : " bad"));
      d.appendChild(el("i"));
      d.appendChild(document.createTextNode(name));
      d.title = s.ok ? name + ": " + (s.count || 0) + " kayıt" : name + ": " + (s.error || "çalışmadı");
      box.appendChild(d);
    });
  }

  function render(data, opts) {
    opts = opts || {};
    var sample = !!data.sample;
    document.getElementById("badgeA").hidden = !sample;
    document.getElementById("badgeB").hidden = !sample;
    var when = data.generated_at ? fmtUpdated(data.generated_at) : "";
    document.getElementById("subtitle").textContent =
      sample ? "Örnek görünüm · henüz rapor yok" : "Son güncelleme: " + (when || "bilinmiyor");
    document.getElementById("updated").textContent =
      sample ? "" : countryName(data.country) + " · son 7 gün";
    document.getElementById("eyebrowA").textContent = data.products_updated_at
      ? "Günlük · " + fmtUpdated(data.products_updated_at) : "Haftalık talep · Google";
    document.getElementById("eyebrowB").textContent = data.trends_updated_at
      ? "3 saatte bir · " + fmtUpdated(data.trends_updated_at) : "Yapay zekanın seçtiği akımlar";
    renderProducts(data.products);
    renderTrends(data.trends);
    renderStatus(data.status);
  }

  function banner(msg, withSettingsLink) {
    var b = document.getElementById("banner");
    b.textContent = "";
    if (!msg) { b.hidden = true; return; }
    b.appendChild(document.createTextNode(msg + " "));
    if (withSettingsLink) {
      var a = el("a", null, "Ayarları aç");
      a.href = "#";
      a.addEventListener("click", function (e) { e.preventDefault(); openSettings(); });
      b.appendChild(a);
    }
    b.hidden = false;
  }

  // ------------------------------------------------------------ veri
  function loadSample() {
    return fetch("sample.json").then(function (r) { return r.json(); });
  }

  function load(force) {
    var btn = document.getElementById("refresh");
    btn.classList.add("spin");
    return getSync(["dataUrl", "ghUser", "ghRepo"]).then(function (cfg) {
      var url = dataUrlFrom(cfg);
      if (!url) {
        banner("Henüz GitHub bağlantısı yapılmadı, örnek veri gösteriliyor.", true);
        return loadSample().then(function (d) { render(d); });
      }
      var bust = force ? "?t=" + Date.now() : "";
      return fetch(url + bust, { cache: force ? "no-store" : "default" })
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .then(function (d) {
          banner(null);
          setLocal({ cache: d });
          render(d);
        })
        .catch(function () {
          return getLocal(["cache"]).then(function (c) {
            if (c.cache) {
              banner("Yeni veriye ulaşılamadı, son kaydedilen rapor gösteriliyor.");
              render(c.cache);
            } else {
              banner("Veriye ulaşılamadı. İlk tarama henüz bitmemiş olabilir ya da adres yanlış.", true);
              return loadSample().then(function (d) { render(d); });
            }
          });
        });
    }).finally(function () { btn.classList.remove("spin"); });
  }

  function openSettings() {
    if (hasChrome && chrome.runtime && chrome.runtime.openOptionsPage) chrome.runtime.openOptionsPage();
    else window.open("options.html");
  }

  // ------------------------------------------------------------ kaydırma
  var track = document.getElementById("track");
  var viewport = document.getElementById("viewport");
  var bar = document.getElementById("bar");
  var labelA = document.getElementById("labelA");
  var labelB = document.getElementById("labelB");
  var drag = null;
  var wheelLock = false;

  function paint(dx, animate) {
    if ((page === 0 && dx > 0) || (page === 1 && dx < 0)) dx = dx / 3;
    var x = -page * W + dx;
    var progress = Math.max(0, Math.min(1, -x / W));
    track.classList.toggle("animate", !!animate);
    bar.style.transition = animate ? "transform 260ms cubic-bezier(.2,.8,.2,1)" : "none";
    track.style.transform = "translateX(" + x + "px)";
    bar.style.transform = "translateX(" + progress * 100 + "%)";
    labelA.classList.toggle("on", progress < 0.5);
    labelB.classList.toggle("on", progress >= 0.5);
  }
  function goTo(p) {
    page = Math.max(0, Math.min(1, p));
    paint(0, true);
    setLocal({ lastPage: page });
  }

  viewport.addEventListener("pointerdown", function (e) {
    if (e.button !== 0) return;
    drag = { x: e.clientX, y: e.clientY, id: e.pointerId, axis: null, dx: 0 };
  });
  viewport.addEventListener("pointermove", function (e) {
    if (!drag) return;
    var mx = e.clientX - drag.x, my = e.clientY - drag.y;
    if (!drag.axis && (Math.abs(mx) > 8 || Math.abs(my) > 8)) {
      drag.axis = Math.abs(mx) > Math.abs(my) ? "x" : "y";
      if (drag.axis === "x") {
        try { viewport.setPointerCapture(drag.id); } catch (err) {}
        viewport.classList.add("dragging");
      }
    }
    if (drag.axis === "x") { drag.dx = mx; paint(mx, false); }
  });
  function endDrag() {
    if (!drag) return;
    var d = drag;
    drag = null;
    viewport.classList.remove("dragging");
    if (d.axis !== "x") return;
    if (d.dx < -60) goTo(page + 1);
    else if (d.dx > 60) goTo(page - 1);
    else goTo(page);
  }
  viewport.addEventListener("pointerup", endDrag);
  viewport.addEventListener("pointercancel", endDrag);
  viewport.addEventListener("wheel", function (e) {
    if (Math.abs(e.deltaX) < Math.abs(e.deltaY) || Math.abs(e.deltaX) < 25 || wheelLock) return;
    wheelLock = true;
    setTimeout(function () { wheelLock = false; }, 600);
    goTo(page + (e.deltaX > 0 ? 1 : -1));
  }, { passive: true });
  document.addEventListener("keydown", function (e) {
    if (e.key === "ArrowRight") goTo(1);
    if (e.key === "ArrowLeft") goTo(0);
  });

  // ------------------------------------------------------------ başlat
  document.getElementById("refresh").addEventListener("click", function () { load(true); });
  document.getElementById("settings").addEventListener("click", openSettings);

  getLocal(["lastPage", "cache"]).then(function (s) {
    page = s.lastPage === 1 ? 1 : 0;
    paint(0, false);
    if (s.cache) render(s.cache); // önce kayıtlı veriyi hemen göster
    load(false);
  });
})();
