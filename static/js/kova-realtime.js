/**
 * Kova real-time UI — WebSocket events replace aggressive HTMX polling.
 */
(function () {
  if (typeof window === "undefined") return;

  window.addEventListener("kova:ws", function (event) {
    var data = event.detail || {};
    var type = data.type;

    if (type === "agent_status" && data.agent && typeof htmx !== "undefined") {
      var agentEl = document.getElementById("agent-" + data.agent);
      if (agentEl) htmx.trigger(agentEl, "kovaRefresh");
    }

    if (type === "post_status" && data.post_id && typeof htmx !== "undefined") {
      var postEl = document.getElementById("post-" + data.post_id);
      if (postEl) htmx.trigger(postEl, "kovaRefresh");
    }

    if (type === "seed_progress" && data.seed_id && typeof htmx !== "undefined") {
      var seedEl = document.getElementById("seed-" + data.seed_id);
      if (seedEl) htmx.trigger(seedEl, "kovaRefresh");
    }

    if (type === "brief_ready" && data.headline) {
      var toast = document.getElementById("brief-ready-toast");
      if (!toast) {
        toast = document.createElement("div");
        toast.id = "brief-ready-toast";
        toast.className =
          "fixed bottom-4 right-4 z-50 max-w-sm rounded-xl border border-kova-200 " +
          "bg-white dark:bg-gray-900 shadow-lg p-4 text-sm";
        toast.innerHTML =
          '<p class="font-semibold text-gray-900 dark:text-white">Your daily brief is ready</p>' +
          '<p class="text-gray-600 dark:text-gray-400 mt-1 brief-ready-headline"></p>' +
          '<a href="/brief/" class="inline-block mt-2 text-kova-600 dark:text-kova-400 font-medium">Open brief →</a>';
        document.body.appendChild(toast);
      }
      var headlineEl = toast.querySelector(".brief-ready-headline");
      if (headlineEl) headlineEl.textContent = data.headline;
      toast.classList.remove("hidden");
      setTimeout(function () {
        toast.classList.add("hidden");
      }, 12000);
    }

    if (type === "connected" && data.unread_count != null) {
      var badge = document.getElementById("notification-count");
      if (badge) {
        badge.textContent = data.unread_count;
        badge.classList.toggle("hidden", data.unread_count < 1);
      }
    }
  });
})();
