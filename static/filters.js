(function () {
  "use strict";
  // Closed only for this visit: the footer of every page always says that the site is not official.
  var notice = document.querySelector(".notice");
  var close = document.querySelector(".close-notice");
  var KEY = "notice-closed";
  function isClosed() { try { return sessionStorage.getItem(KEY) === "1"; } catch (e) { return false; } }
  if (notice && close) {
    if (isClosed()) notice.hidden = true;
    close.hidden = false;
    close.addEventListener("click", function () {
      notice.hidden = true;
      try { sessionStorage.setItem(KEY, "1"); } catch (e) {}
      var main = document.getElementById("contenido");
      if (main) main.focus({ preventScroll: true });
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("button.collapse"), function (b) {
    b.hidden = false;
    b.addEventListener("click", function () {
      var det = b.closest("details");
      det.open = false;
      var sec = det.closest("section") || det;
      sec.scrollIntoView({ block: "start" });
      det.querySelector("summary").focus({ preventScroll: true });
    });
  });

  var toTop = document.querySelector(".to-top");
  if (toTop) {
    var ticking = false;
    var update = function () {
      toTop.hidden = window.scrollY < 2 * window.innerHeight;
      ticking = false;
    };
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(update); }
    }, { passive: true });
    update();
    toTop.addEventListener("click", function (ev) {
      ev.preventDefault();
      var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.scrollTo({ top: 0, behavior: still ? "auto" : "smooth" });
      var brand = document.querySelector(".brand");
      if (brand) brand.focus({ preventScroll: true });
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("details.month-picker"), function (d) {
    document.addEventListener("click", function (ev) {
      if (d.open && !d.contains(ev.target)) d.open = false;
    });
    d.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && d.open) {
        d.open = false;
        d.querySelector("summary").focus();
      }
    });
  });

  function Pager(box) {
    this.box = box;
    this.size = parseInt(box.getAttribute("data-page-size"), 10) || 50;
    this.page = 0;
    this.nav = document.createElement("nav");
    this.nav.className = "pager";
    var anchor = box.closest(".table-scroll") || box;
    // Named after the heading before the list, so two pagers on one page (Dinero) do not sound the same.
    var heading = anchor.previousElementSibling;
    while (heading && !/^H[1-3]$/.test(heading.tagName)) heading = heading.previousElementSibling;
    this.nav.setAttribute("aria-label", heading ? "Páginas de «" + heading.textContent.trim() + "»" : "Páginas de la lista");
    anchor.parentNode.insertBefore(this.nav, anchor.nextSibling);
    var self = this;
    this.nav.addEventListener("click", function (ev) {
      var b = ev.target.closest("button[data-page]");
      // detail 0: pressed with the keyboard. Only then the focus moves to the first item of the new page.
      if (b) self.go(parseInt(b.getAttribute("data-page"), 10), true, ev.detail === 0);
    });
    this.go(0);
  }
  Pager.prototype.items = function () {
    return this.box.tagName === "TABLE" ? this.box.tBodies[0].rows : this.box.children;
  };
  Pager.prototype.go = function (p, moved, keyboard) {
    var size = this.size;
    var items = this.items();
    var total = Array.prototype.filter.call(items, function (x) { return !x.hasAttribute("data-out"); }).length;
    var pages = Math.max(1, Math.ceil(total / size));
    p = Math.min(Math.max(0, p), pages - 1);
    this.page = p;
    var n = 0;
    Array.prototype.forEach.call(items, function (x) {
      if (x.hasAttribute("data-out")) { x.hidden = true; x.removeAttribute("data-paged-out"); return; }
      x.hidden = n < p * size || n >= (p + 1) * size;
      // Only hidden by the pager: printed anyway (style.css), a filter's choice is not.
      if (x.hidden) x.setAttribute("data-paged-out", ""); else x.removeAttribute("data-paged-out");
      n++;
    });
    this.render(pages, total);
    if (moved) {
      var top = this.box.closest(".table-scroll") || this.box;
      var target = top;
      for (var k = 0, x = top.previousElementSibling; x && k < 3; k++, x = x.previousElementSibling) {
        if (/^H[1-3]$/.test(x.tagName)) { target = x; break; }
      }
      target.scrollIntoView({ block: "start" });
      var first = Array.prototype.find.call(items, function (x) { return !x.hidden; });
      var link = first && first.querySelector("a");
      if (link && keyboard) link.focus({ preventScroll: true });
    }
  };
  Pager.prototype.render = function (pages, total) {
    var nav = this.nav;
    nav.textContent = "";
    nav.hidden = pages <= 1;
    if (pages <= 1) return;
    var p = this.page;
    var size = this.size;
    var status = document.createElement("p");
    status.className = "pager-status";
    status.textContent = "Del " + (p * size + 1) + " al " + Math.min(total, (p + 1) * size) + " de " + total;
    nav.appendChild(status);
    var ul = document.createElement("ul");
    function button(label, page, current, aria, word) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      if (word) {
        var w = document.createElement("span");
        w.className = "word";
        w.textContent = word;
        if (label === "‹") b.appendChild(w); else b.insertBefore(w, b.firstChild);
      }
      if (aria) b.setAttribute("aria-label", aria);
      if (current) b.setAttribute("aria-current", "page");
      if (page === null) b.disabled = true; else b.setAttribute("data-page", page);
      li.appendChild(b);
      ul.appendChild(li);
    }
    button("‹", p > 0 ? p - 1 : null, false, "Página anterior", " Anterior");
    var shown = [0, p - 1, p, p + 1, pages - 1].filter(function (x, i, a) {
      return x >= 0 && x < pages && a.indexOf(x) === i;
    }).sort(function (a, b) { return a - b; });
    shown.forEach(function (x, i) {
      if (i > 0 && x - shown[i - 1] > 1) {
        var gap = document.createElement("li");
        gap.className = "gap";
        gap.textContent = "…";
        ul.appendChild(gap);
      }
      button(String(x + 1), x, x === p, "Página " + (x + 1));
    });
    button("›", p < pages - 1 ? p + 1 : null, false, "Página siguiente", "Siguiente ");
    nav.appendChild(ul);
  };
  // search.js uses it.
  window.paginate = function (box) {
    if (!box._pager) box._pager = new Pager(box);
    return box._pager;
  };
  Array.prototype.forEach.call(document.querySelectorAll("[data-page-size]"), window.paginate);

  var unfolded = [];
  window.addEventListener("beforeprint", function () {
    unfolded = Array.prototype.filter.call(document.querySelectorAll("details:not([open])"), function (d) {
      return !d.closest(".month-picker");
    });
    unfolded.forEach(function (d) { d.open = true; });
  });
  window.addEventListener("afterprint", function () {
    unfolded.forEach(function (d) { d.open = false; });
    unfolded = [];
  });

  Array.prototype.forEach.call(document.querySelectorAll(".list-filter"), function (box) {
    var table = document.getElementById(box.getAttribute("data-filter-for"));
    var text = box.querySelector("input");
    var type = box.querySelector("select");
    var count = box.querySelector(".counter");
    if (!table) return;
    box.hidden = false;
    function fold(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
    function apply() {
      var words = fold(text.value).split(/\s+/).filter(Boolean);
      var kind = type ? type.value : "";
      var n = 0;
      Array.prototype.forEach.call(table.tBodies[0].rows, function (r) {
        var t = r.getAttribute("data-text") || "";
        var ok = (!kind || r.getAttribute("data-type") === kind) &&
          words.every(function (w) { return t.indexOf(w) !== -1; });
        if (ok) { r.removeAttribute("data-out"); n++; } else r.setAttribute("data-out", "");
      });
      if (count) count.textContent = words.length || kind ? (n === 1 ? "1 entidad" : n + " entidades") : "";
      if (table._pager) table._pager.go(0); else
        Array.prototype.forEach.call(table.tBodies[0].rows, function (r) { r.hidden = r.hasAttribute("data-out"); });
      var p = new URLSearchParams(location.search);
      if (text.value.trim()) p.set("q", text.value.trim()); else p.delete("q");
      if (kind) p.set("tipo", kind); else p.delete("tipo");
      var s = p.toString();
      if (window.history && history.replaceState) {
        history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash);
      }
    }
    var pending;
    text.addEventListener("input", function () { clearTimeout(pending); pending = setTimeout(apply, 120); });
    if (type) type.addEventListener("change", apply);
    var p = new URLSearchParams(location.search);
    if (p.get("q")) text.value = p.get("q");
    if (type && Array.prototype.some.call(type.options, function (o) { return o.value === p.get("tipo"); })) {
      type.value = p.get("tipo");
    }
    if (p.get("q") || p.get("tipo")) apply();
  });

  var search = document.getElementById("search");
  if (!search) return;
  var topicSelect = document.getElementById("topic");
  var bodySelect = document.getElementById("body");
  var body = "";
  var sections = Array.prototype.slice.call(document.querySelectorAll("section.edition"));
  var noResults = document.getElementById("no-results");
  var counter = document.getElementById("counter");
  var clear = document.getElementById("clear");
  var topic = "";
  var box = search.closest(".filters");
  if (box) box.hidden = false;

  // Same as fmt.plain() in Python.
  function plain(s) {
    return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }

  function apply() {
    var words = plain(search.value).split(/\s+/).filter(Boolean);
    var active = words.length > 0 || topic !== "" || body !== "";
    var total = 0;
    sections.forEach(function (sec) {
      var shown = 0;
      var bodyOk = body === "" || sec.getAttribute("data-body") === body;
      sec.querySelectorAll("article.item").forEach(function (art) {
        var text = art.getAttribute("data-text") || "";
        var ok = bodyOk && (topic === "" || art.getAttribute("data-topic") === topic) &&
          words.every(function (w) { return text.indexOf(w) !== -1; });
        art.hidden = !ok;
        if (ok) shown++;
      });
      if (shown === 0) sec.setAttribute("data-out", ""); else sec.removeAttribute("data-out");
      var det = sec.querySelector("details");
      if (det && active && !det.open) { det.open = true; det.setAttribute("data-opened-by-filter", ""); }
      if (det && !active && det.hasAttribute("data-opened-by-filter")) {
        det.open = false;
        det.removeAttribute("data-opened-by-filter");
      }
      // While filtering, the meeting only shows what matches: «Ocultar los 34 asuntos» would count the others.
      if (det) {
        det.querySelector("summary").hidden = active;
        var fold = det.querySelector("button.collapse");
        if (fold) fold.hidden = active;
      }
      total += shown;
    });
    var holder = sections.length ? sections[0].parentNode : null;
    if (holder && holder._pager) holder._pager.go(0);
    else sections.forEach(function (sec) { sec.hidden = sec.hasAttribute("data-out"); });
    if (noResults) noResults.hidden = total > 0;
    // The counter is the live region: it also says when nothing matches, so screen readers read it out.
    if (counter) {
      counter.textContent = !active ? "" : total === 0 ? "Ninguna decisión coincide."
        : total + (total === 1 ? " decisión" : " decisiones");
    }
    saveToUrl();
  }

  function saveToUrl() {
    if (!window.history || !history.replaceState) return;
    var p = new URLSearchParams(location.search);
    var q = search.value.trim();
    if (q) p.set("q", q); else p.delete("q");
    if (topic) p.set("tema", topic); else p.delete("tema");
    if (body) p.set("organo", body); else p.delete("organo");
    var s = p.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash);
  }

  function readFromUrl() {
    var p = new URLSearchParams(location.search);
    var q = p.get("q") || "";
    var t = p.get("tema") || "";
    if (topicSelect && t && Array.prototype.some.call(topicSelect.options, function (o) { return o.value === t; })) {
      topicSelect.value = t;
      topic = t;
    }
    var o = p.get("organo") || "";
    if (bodySelect && (o === "JGL" || o === "PLENO")) {
      bodySelect.value = o;
      body = o;
    }
    if (q) search.value = q;
    if (q || topic || body) apply();
  }

  if (bodySelect) {
    bodySelect.addEventListener("change", function () {
      body = bodySelect.value;
      apply();
    });
  }
  if (topicSelect) {
    topicSelect.addEventListener("change", function () {
      topic = topicSelect.value;
      apply();
    });
  }
  if (clear) {
    clear.addEventListener("click", function () {
      search.value = "";
      topic = "";
      body = "";
      if (topicSelect) topicSelect.value = "";
      if (bodySelect) bodySelect.value = "";
      apply();
      search.focus();
    });
  }
  var pending;
  search.addEventListener("input", function () {
    clearTimeout(pending);
    pending = setTimeout(apply, 120);
  });
  readFromUrl();
})();
