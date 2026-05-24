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

    if (type === "connected" && data.unread_count != null) {
      var badge = document.getElementById("notification-count");
      if (badge) {
        badge.textContent = data.unread_count;
        badge.classList.toggle("hidden", data.unread_count < 1);
      }
    }
  });
})();
