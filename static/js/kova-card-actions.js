/**
 * Post card actions — one delegated handler for schedule modals (no per-card scripts).
 */
(function () {
  "use strict";

  function csrfToken() {
    var tok = document.querySelector("[name=csrfmiddlewaretoken]");
    if (tok && tok.value) return tok.value;
    var headers = document.body.getAttribute("hx-headers");
    if (!headers) return "";
    try {
      return JSON.parse(headers)["X-CSRFToken"] || "";
    } catch (e) {
      return "";
    }
  }

  document.addEventListener("kova:schedule-post", function (evt) {
    var detail = (evt && evt.detail) || {};
    var postId = detail.postId;
    var url = detail.url;
    var intent = detail.intent || "post_now";
    if (!postId || !url) return;

    var values = { schedule_intent: intent };
    if (intent === "exact" && detail.datetime) {
      values.exact_datetime = detail.datetime;
    }
    var token = csrfToken();
    if (token) values.csrfmiddlewaretoken = token;

    htmx.ajax("POST", url, {
      target: "#post-" + postId,
      swap: "outerHTML settle:80ms",
      values: values,
      indicator: "#post-" + postId + "-busy",
    });
  });
})();
