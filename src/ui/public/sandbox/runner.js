// Page loaded in <iframe sandbox="allow-scripts"> WITHOUT allow-same-origin: opaque origin, so it cannot
// read the application storage, cookies or session tokens. The code runs in a Worker (own thread) that this page can
// terminate at any time; the parent can also destroy the whole iframe.
(function () {
  var base = new URL("./", document.baseURI).href;
  var MAX_CODE = 10000;
  var worker = null, ready = false, starting = null, timer = null, current = null;

  function post(msg) { parent.postMessage(msg, "*"); }

  function startWorker() {
    if (starting) return starting;
    post({ type: "status", state: "loading" });
    starting = fetch(base + "worker.js").then(function (r) { return r.text(); }).then(function (src) {
      var url = URL.createObjectURL(new Blob([src], { type: "text/javascript" }));
      worker = new Worker(url);
      return new Promise(function (resolve, reject) {
        worker.onmessage = function (e) {
          var m = e.data;
          if (m.type === "ready") { ready = true; post({ type: "status", state: "ready" }); worker.onmessage = onWorker; resolve(); }
        };
        worker.onerror = function (e) { reject(new Error(e.message || "worker error")); };
        worker.postMessage({ type: "init", base: base });
      });
    }).catch(function (err) { starting = null; post({ type: "status", state: "error", message: String(err.message || err) }); throw err; });
    return starting;
  }

  function kill(reason) {
    if (timer) { clearTimeout(timer); timer = null; }
    if (worker) { worker.terminate(); worker = null; }
    ready = false; starting = null;
    if (current !== null) { post({ type: "timeout", id: current, reason: reason }); current = null; }
    startWorker().catch(function () {});  // fresh interpreter for the next run
  }

  function onWorker(e) {
    var m = e.data;
    if (m.id !== current) return;
    if (timer) { clearTimeout(timer); timer = null; }
    current = null;
    post(m);
  }

  window.addEventListener("message", function (e) {
    if (e.source !== parent) return;
    var m = e.data || {};
    if (m.type === "run") {
      if (typeof m.code !== "string" || m.code.length > MAX_CODE) {
        post({ type: "failure", id: m.id, message: "Код длиннее " + MAX_CODE + " символов." });
        return;
      }
      current = m.id;
      var limit = Math.min(Math.max(Number(m.timeoutMs) || 8000, 1000), 20000);
      startWorker().then(function () {
        if (current !== m.id) return;
        post({ type: "status", state: "running" });
        timer = setTimeout(function () { kill("time"); }, limit);
        worker.postMessage({ type: "run", id: m.id, code: m.code, func: m.func, cases: m.cases });
      }).catch(function (err) { post({ type: "failure", id: m.id, message: String(err.message || err) }); current = null; });
    } else if (m.type === "kill") {
      kill("user");
    }
  });

  startWorker().catch(function () {});
})();
