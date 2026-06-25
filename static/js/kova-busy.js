/**
 * Kova global busy overlay — shows after ~2s for slow navigations, forms, HTMX, and fetch.
 * Skip polling with data-kova-busy="off". Show immediately with data-kova-busy="instant".
 */
(function () {
  "use strict";

  var DELAY_MS = 2000;
  var ROTATE_MS = 4500;

  var MESSAGES = [
    "Kova is on it — give us a moment.",
    "Your AI team is working behind the scenes.",
    "Almost there — crafting something worth posting.",
    "Good things take a second. Great posts take a minute.",
    "Sharpening hooks and polishing captions…",
    "Reading your brand voice so this sounds like you.",
    "Lining up visuals that match your vibe.",
    "Turning one photo into a full sell story…",
    "Your agents don't sleep — they're just thinking.",
    "Building your campaign, one platform at a time.",
    "Making sure this sounds like you, not a robot.",
    "Warming up the creative engines…",
  ];

  var depth = 0;
  var visible = false;
  var delayTimer = null;
  var rotateTimer = null;
  var msgIndex = 0;
  var customMessage = null;

  function pickMessage() {
    if (customMessage) return customMessage;
    var msg = MESSAGES[msgIndex % MESSAGES.length];
    msgIndex += 1;
    return msg;
  }

  function busyNode(el) {
    return el && el.closest ? el.closest("[data-kova-busy]") : null;
  }

  function shouldSkip(el) {
    if (!el) return false;
    var node = busyNode(el);
    if (node && node.getAttribute("data-kova-busy") === "off") return true;
    var trigger = el.getAttribute && el.getAttribute("hx-trigger");
    if (trigger && /\bevery\b/.test(trigger)) return true;
    return false;
  }

  function isInstant(el) {
    var node = busyNode(el);
    return !!(node && node.getAttribute("data-kova-busy") === "instant");
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

  function dispatchShow() {
    window.dispatchEvent(
      new CustomEvent("kova:busy:show", {
        detail: { message: pickMessage() },
      })
    );
    visible = true;
    if (!rotateTimer) {
      rotateTimer = setInterval(function () {
        if (!visible) return;
        window.dispatchEvent(
          new CustomEvent("kova:busy:message", {
            detail: { message: pickMessage() },
          })
        );
      }, ROTATE_MS);
    }
  }

  function showNow() {
    clearTimeout(delayTimer);
    delayTimer = null;
    if (!visible) dispatchShow();
  }

  function scheduleShow() {
    if (visible || delayTimer) return;
    delayTimer = setTimeout(function () {
      delayTimer = null;
      if (depth > 0) dispatchShow();
    }, DELAY_MS);
  }

  function hideOverlay() {
    customMessage = null;
    visible = false;
    clearTimeout(delayTimer);
    delayTimer = null;
    if (rotateTimer) {
      clearInterval(rotateTimer);
      rotateTimer = null;
    }
    window.dispatchEvent(new CustomEvent("kova:busy:hide"));
  }

  function start(opts) {
    opts = opts || {};
    depth += 1;
    if (opts.message) customMessage = opts.message;
    if (opts.instant) {
      showNow();
      return;
    }
    scheduleShow();
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

  // HTMX — POST/PUT/PATCH/DELETE and explicit data-kova-busy="on|instant"
  document.body.addEventListener("htmx:beforeRequest", function (evt) {
    var el = evt.detail.elt;
    if (shouldSkip(el)) return;
    var verb = ((evt.detail.requestConfig && evt.detail.requestConfig.verb) || "get").toLowerCase();
    var node = busyNode(el);
    var mode = node ? node.getAttribute("data-kova-busy") : null;
    if (verb === "get" && mode !== "on" && mode !== "instant" && !isInstant(el)) return;
    start({ instant: isInstant(el) || mode === "instant", message: messageFor(el) });
  });

  document.body.addEventListener("htmx:afterRequest", stop);
  document.body.addEventListener("htmx:responseError", stop);
  document.body.addEventListener("htmx:sendError", stop);

  // Full-page form navigation
  document.addEventListener(
    "submit",
    function (evt) {
      var form = evt.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (form.getAttribute("data-kova-busy") === "off") return;
      if (form.hasAttribute("hx-post") || form.hasAttribute("hx-get") || form.hasAttribute("hx-put")) return;
      var mode = form.getAttribute("data-kova-busy");
      start({
        instant: mode === "instant",
        message: form.getAttribute("data-kova-busy-message"),
      });
    },
    true
  );

  // Same-origin link navigation
  document.addEventListener(
    "click",
    function (evt) {
      var a = evt.target.closest && evt.target.closest("a[href]");
      if (!a || a.target === "_blank" || evt.metaKey || evt.ctrlKey || evt.shiftKey) return;
      if (a.getAttribute("data-kova-busy") === "off") return;
      if (a.hasAttribute("hx-get") || a.hasAttribute("hx-post")) return;
      var href = a.getAttribute("href");
      if (!href || href.charAt(0) === "#" || href.indexOf("javascript:") === 0) return;
      try {
        var url = new URL(href, window.location.origin);
        if (url.origin !== window.location.origin) return;
      } catch (e) {
        return;
      }
      start({
        instant: a.getAttribute("data-kova-busy") === "instant",
        message: a.getAttribute("data-kova-busy-message"),
      });
    },
    true
  );

  window.addEventListener("pageshow", forceStop);
  window.addEventListener("popstate", forceStop);

  // Long fetch calls (quick polls finish before the 2s delay)
  if (window.fetch) {
    var nativeFetch = window.fetch.bind(window);
    window.fetch = function () {
      var args = arguments;
      start({});
      return nativeFetch.apply(window, args).finally(stop);
    };
  }

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
