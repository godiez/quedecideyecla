(function () {
  "use strict";
  var input = document.getElementById("q");
  var config = document.getElementById("search-indexes");
  if (!input || !config) return;
  var indexes = JSON.parse(config.textContent);
  var yearSelect = document.getElementById("year");
  var yearField = document.getElementById("year-field");
  var status = document.getElementById("status");
  var entitySection = document.getElementById("entity-results");
  var entityList = document.getElementById("entity-list");
  var decisionSection = document.getElementById("decision-results");
  var decisionList = document.getElementById("decision-list");
  var form = input.form;
  var STOP = { a: 1, al: 1, con: 1, de: 1, del: 1, e: 1, el: 1, en: 1, la: 1, las: 1, lo: 1, los: 1, o: 1,
               para: 1, por: 1, u: 1, un: 1, una: 1, y: 1 };
  // Decision row: [slug, title, meta, summary, entities, place, case file, concepts]
  // [column, label in the snippet, separator of its items]; the snippet uses the first field with the word.
  var FIELDS = [[1, ""], [4, "Quién aparece", " · "], [5, "Lugar"], [6, "Expediente", ", "],
                [7, "Desglose", " · "], [3, ""]];
  var decisions = null;
  var entities = null;
  var loading = null;
  var results = [];
  // Only the latest search is shown: two launched while loading (typing, then «Buscar») would both fill the lists.
  var lastRun = 0;

  // One character in, one out: positions in the folded text are positions in the original (needed to highlight).
  // FOLDED converts each character once: normalize() per character froze the first search for seconds.
  var FOLDED = {};
  function fold(s) {
    return s.replace(/[^a-z0-9]/g, function (c) {
      var f = FOLDED[c];
      if (f === undefined) {
        f = c.normalize("NFD").charAt(0).toLowerCase();
        f = FOLDED[c] = /[a-z0-9]/.test(f) ? f : " ";
      }
      return f;
    });
  }

  function words(q) {
    var all = fold(q).split(/\s+/).filter(Boolean);
    var useful = all.filter(function (w) { return !STOP[w]; });
    return (useful.length ? useful : all).map(function (w) {
      return w.length > 3 && w.charAt(w.length - 1) === "s" ? w.slice(0, -1) : w;
    });
  }

  function at(text, w) {
    var i = text.indexOf(w);
    while (i > 0 && text.charAt(i - 1) !== " ") i = text.indexOf(w, i + 1);
    return i;
  }

  function load() {
    if (loading) return loading;
    status.textContent = "Cargando…";
    var years = Object.keys(indexes.years).sort().reverse();
    function get(url) {
      return fetch(url).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      });
    }
    loading = Promise.all([get(indexes.entities)].concat(years.map(function (y) { return get(indexes.years[y]); })))
      .then(function (parts) {
        entities = parts[0].map(function (r) { return { row: r, name: " " + fold(r[1]) }; });
        decisions = [];
        parts.slice(1).forEach(function (rows) {
          rows.forEach(function (r) {
            decisions.push({ row: r, year: r[0].slice(0, 4), date: r[0].slice(0, 10), folded: null });
          });
        });
      })
      .catch(function () {
        loading = null;
        status.textContent = "No se ha podido cargar el buscador. Prueba a recargar la página.";
        throw new Error("load");
      });
    return loading;
  }

  function matches(d, ws) {
    if (!d.folded) d.folded = FIELDS.map(function (f) { return " " + fold(d.row[f[0]] || ""); });
    return ws.every(function (w) {
      return d.folded.some(function (f) { return at(f, w) !== -1; });
    });
  }

  function el(tag, cls, text) {
    var x = document.createElement(tag);
    if (cls) x.className = cls;
    if (text) x.textContent = text;
    return x;
  }

  function highlight(node, text, ws, from, to) {
    var folded = fold(text);
    var marks = [];
    ws.forEach(function (w) {
      var i = -1;
      while ((i = folded.indexOf(w, i + 1)) !== -1) {
        if (i === 0 || folded.charAt(i - 1) === " ") marks.push([i, i + w.length]);
      }
    });
    marks.sort(function (a, b) { return a[0] - b[0]; });
    var pos = from || 0;
    var end = to === undefined ? text.length : to;
    marks.forEach(function (mk) {
      if (mk[0] < pos || mk[1] > end) return;
      node.appendChild(document.createTextNode(text.slice(pos, mk[0])));
      node.appendChild(el("mark", "", text.slice(mk[0], mk[1])));
      pos = mk[1];
    });
    node.appendChild(document.createTextNode(text.slice(pos, end)));
  }

  function snippet(d, ws) {
    var title = d.folded[0];
    var missing = ws.filter(function (w) { return at(title, w) === -1; });
    if (!missing.length) return null;
    for (var j = 1; j < FIELDS.length; j++) {
      if (at(d.folded[j], missing[0]) === -1) continue;
      var text = d.row[FIELDS[j][0]];
      var p = el("p", "snippet");
      if (FIELDS[j][1]) {
        var items = FIELDS[j][2] ? text.split(FIELDS[j][2]) : [text];
        var hits = items.filter(function (x) {
          var f = " " + fold(x);
          return ws.some(function (w) { return at(f, w) !== -1; });
        });
        var rest = items.length - Math.min(hits.length, 3);
        p.appendChild(el("span", "label", FIELDS[j][1] + ": "));
        highlight(p, hits.slice(0, 3).join(FIELDS[j][2] || ""), ws);
        if (rest > 0) p.appendChild(document.createTextNode(" y " + rest + " más"));
      } else {
        var i = at(d.folded[j], missing[0]) - 1;
        var from = Math.max(0, text.lastIndexOf(" ", Math.max(0, i - 60)));
        var to = text.indexOf(" ", Math.min(text.length, i + 100));
        if (to === -1) to = text.length;
        if (from > 0) p.appendChild(document.createTextNode("…"));
        highlight(p, text, ws, from === 0 ? 0 : from + 1, to);
        if (to < text.length) p.appendChild(document.createTextNode("…"));
      }
      return p;
    }
    return null;
  }

  function link(slugPath, text, ws) {
    var a = el("a");
    a.href = "../" + slugPath;
    highlight(a, text, ws);
    return a;
  }

  function render(ws) {
    for (var i = 0; i < results.length; i++) {
      var d = results[i];
      var art = el("article", "item");
      art.appendChild(link("decision/" + d.row[0] + "/", d.row[1], ws));
      art.appendChild(el("span", "meta", d.row[2]));
      var s = snippet(d, ws);
      if (s) art.appendChild(s);
      decisionList.appendChild(art);
    }
    if (window.paginate) window.paginate(decisionList).go(0);
  }

  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  function run() {
    var id = ++lastRun;
    var q = input.value.trim();
    saveToUrl(q);
    var ws = words(q);
    entityList.textContent = "";
    decisionList.textContent = "";
    entitySection.hidden = decisionSection.hidden = true;
    if (!ws.length) {
      status.textContent = "";
      return;
    }
    load().then(function () {
      if (id !== lastRun) return;
      entityList.textContent = "";
      decisionList.textContent = "";
      var year = yearSelect ? yearSelect.value : "";
      var found = entities.filter(function (x) {
        return ws.every(function (w) { return at(x.name, w) !== -1; });
      }).sort(function (a, b) {
        return b.row[3] - a.row[3] || a.row[1].localeCompare(b.row[1], "es");
      });
      var perYear = {};
      results = [];
      decisions.forEach(function (d) {
        if (!matches(d, ws)) return;
        perYear[d.year] = (perYear[d.year] || 0) + 1;
        if (!year || d.year === year) results.push(d);
      });
      // A stable sort: within a day, the decisions keep the order of the index, which is that of the minute.
      results.sort(function (a, b) { return a.date < b.date ? 1 : a.date > b.date ? -1 : 0; });
      if (yearSelect) {
        Array.prototype.forEach.call(yearSelect.options, function (o) {
          var n = o.value ? perYear[o.value] || 0 : Object.keys(perYear).reduce(function (t, y) { return t + perYear[y]; }, 0);
          o.textContent = (o.value || "Todos los años") + " (" + n + ")";
        });
        yearField.hidden = false;
      }
      found.slice(0, 8).forEach(function (x) {
        var li = el("li", "news-item");
        li.appendChild(link("entidad/" + x.row[0] + "/", x.row[1], ws));
        li.appendChild(el("span", "meta", x.row[2]));
        entityList.appendChild(li);
      });
      entitySection.hidden = found.length === 0;
      decisionSection.hidden = results.length === 0;
      render(ws);
      var parts = [];
      if (found.length) parts.push(plural(found.length, "entidad", "entidades"));
      parts.push(plural(results.length, "decisión", "decisiones") + (year ? " en " + year : ""));
      status.textContent = found.length || results.length
        ? parts.join(" y ") + "."
        : "No hay resultados. Prueba con menos palabras o con otra forma de escribirlo.";
      if (found.length > 8) status.textContent += " Se muestran las 8 primeras entidades: añade otra palabra para afinar.";
    }).catch(function () { /* the message is already shown */ });
  }

  function saveToUrl(q) {
    if (!window.history || !history.replaceState) return;
    var p = new URLSearchParams(location.search);
    if (q) p.set("q", q); else p.delete("q");
    if (yearSelect && yearSelect.value) p.set("año", yearSelect.value); else p.delete("año");
    var s = p.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash);
  }

  var pending;
  input.addEventListener("input", function () {
    clearTimeout(pending);
    pending = setTimeout(run, 200);
  });
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    clearTimeout(pending);
    run();
  });
  if (yearSelect) yearSelect.addEventListener("change", run);

  var params = new URLSearchParams(location.search);
  if (yearSelect && Array.prototype.some.call(yearSelect.options, function (o) { return o.value === params.get("año"); })) {
    yearSelect.value = params.get("año");
  }
  if (params.get("q")) {
    input.value = params.get("q");
    run();
  }
})();
