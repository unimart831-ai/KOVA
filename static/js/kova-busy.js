/**
 * Kova busy indicator — opt-in only (data-kova-busy="on" | "instant").
 * Shows a slim top progress bar; no full-screen modal, no fetch/link hijacking.
 */
(function () {
  "use strict";

  var DELAY_MS = 3500;

  var depth = 0;
  var visible = false;
  var delayTimer = null;

  function busyNode(el) {
    return el && el.closest ? el.closest("[data-kova-busy]") : null;
  }

  function busyMode(el) {
    var node = busyNode(el);
    return node ? node.getAttribute("data-kova-busy") : null;
  }

  function shouldSkip(el) {
    if (!el) return true;
    var mode = busyMode(el);
    if (!mode || mode === "off") return true;
    var trigger = el.getAttribute && el.getAttribute("hx-trigger");
    if (trigger && /\bevery\b/.test(trigger)) return true;
    return false;
  }

  function isOptIn(el) {
    var mode = busyMode(el);
    return mode === "on" || mode === "instant";
  }

  function messageFor(el) {
    var node = el && el.closest ? el.closest("[data-kova-busy-message]") : null;
    if (node) return node.getAttribute("data-kova-busy-message");
    if (el && el.getAttribute) {
      var direct = el.getAttribute("data-kova-busy-message");
      if (direct) return direct;
    }
    return null;
  }

  function dispatchShow(detail) {
    window.dispatchEvent(
      new CustomEvent("kova:busy:show", { detail: detail || {} })
    );
    visible = true;
  }

  function showNow(opts) {
    clearTimeout(delayTimer);
    delayTimer = null;
    if (!visible) {
      dispatchShow({ message: (opts && opts.message) || "" });
    }
  }

  function scheduleShow(opts) {
    if (visible || delayTimer) return;
    delayTimer = setTimeout(function () {
      delayTimer = null;
      if (depth > 0) {
        dispatchShow({ message: (opts && opts.message) || "" });
      }
    }, DELAY_MS);
  }

  function hideOverlay() {
    visible = false;
    clearTimeout(delayTimer);
    delayTimer = null;
    window.dispatchEvent(new CustomEvent("kova:busy:hide"));
  }

  function start(opts) {
    opts = opts || {};
    depth += 1;
    if (opts.instant) {
      showNow(opts);
      return;
    }
    scheduleShow(opts);
  }

  function stop() {
    depth = Math.max(0, depth - 1);
    if (depth > 0) return;
    hideOverlay();
  }

  function forceStop() {
    depth = 0;
    hideOverlay();
  }

  // HTMX — only when explicitly opted in, or mutating verbs with data-kova-busy
  document.body.addEventListener("htmx:beforeRequest", function (evt) {
    var el = evt.detail.elt;
    if (shouldSkip(el)) return;
    if (!isOptIn(el)) return;
    var verb = ((evt.detail.requestConfig && evt.detail.requestConfig.verb) || "get").toLowerCase();
    var mode = busyMode(el);
    if (verb === "get" && mode !== "on" && mode !== "instant") return;
    start({ instant: mode === "instant", message: messageFor(el) });
  });

  document.body.addEventListener("htmx:afterRequest", stop);
  document.body.addEventListener("htmx:responseError", stop);
  document.body.addEventListener("htmx:sendError", stop);

  // Full-page forms — opt-in only
  document.addEventListener(
    "submit",
    function (evt) {
      var form = evt.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (shouldSkip(form) || !isOptIn(form)) return;
      if (form.hasAttribute("hx-post") || form.hasAttribute("hx-get") || form.hasAttribute("hx-put")) return;
      start({
        instant: form.getAttribute("data-kova-busy") === "instant",
        message: form.getAttribute("data-kova-busy-message"),
      });
    },
    true
  );

  window.addEventListener("pageshow", forceStop);
  window.addEventListener("popstate", forceStop);

  window.addEventListener("kova:busy", function (evt) {
    var d = (evt && evt.detail) || {};
    if (d.show) {
      start({ instant: !!d.instant, message: d.message || null });
    } else {
      forceStop();
    }
  });

  window.KovaBusy = {
    start: start,
    stop: stop,
    forceStop: forceStop,
  };
})();
