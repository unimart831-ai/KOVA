/**
 * Kova Commerce — public shop interactions
 */
(function () {
  "use strict";

  function initShare() {
    document.querySelectorAll(".shop-share-btn, .kc-share-btn").forEach(function (btn) {
      if (!navigator.share) return;
      btn.hidden = false;
      btn.addEventListener("click", function () {
        navigator.share({
          title: btn.dataset.shareTitle || document.title,
          url: btn.dataset.shareUrl || window.location.href,
        }).catch(function () {});
      });
    });
  }

  function initProductSearch() {
    var searchInput = document.getElementById("shop-product-search");
    if (!searchInput) return;
    var cards = Array.prototype.slice.call(document.querySelectorAll(".shop-product-card"));
    var emptyMsg = document.getElementById("shop-search-empty");
    var countEl = document.querySelector("[data-catalog-count]");

    function filterProducts() {
      var query = (searchInput.value || "").trim().toLowerCase();
      var visible = 0;
      cards.forEach(function (card) {
        var name = card.getAttribute("data-product-name") || "";
        var show = !query || name.indexOf(query) !== -1;
        card.hidden = !show;
        if (show) visible += 1;
      });
      if (emptyMsg) emptyMsg.hidden = visible > 0 || !query;
      if (countEl) countEl.textContent = visible + " item" + (visible === 1 ? "" : "s");
      document.querySelectorAll(".shop-category-section, .kc-category-block").forEach(function (section) {
        var sectionCards = section.querySelectorAll(".shop-product-card");
        var anyVisible = Array.prototype.some.call(sectionCards, function (c) { return !c.hidden; });
        section.hidden = query ? !anyVisible : false;
      });
    }

    searchInput.addEventListener("input", filterProducts);
    searchInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); filterProducts(); }
    });
  }

  function initCategoryChips() {
    document.querySelectorAll(".category-chip, .kc-category-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var target = chip.getAttribute("data-target") || chip.getAttribute("href");
        document.querySelectorAll(".category-chip, .kc-category-chip").forEach(function (c) {
          c.classList.remove("is-active");
        });
        chip.classList.add("is-active");
        if (target && target.charAt(0) === "#") {
          var el = document.querySelector(target);
          if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });
  }

  function initGallery() {
    var hero = document.getElementById("hero-img");
    var counter = document.getElementById("gallery-counter");
    var thumbs = Array.prototype.slice.call(document.querySelectorAll(".offer-thumb"));
    if (!hero || !thumbs.length) return;
    var currentIndex = 0;

    function setSlide(index) {
      currentIndex = (index + thumbs.length) % thumbs.length;
      var btn = thumbs[currentIndex];
      var src = btn.getAttribute("data-src");
      if (!src) return;
      hero.src = src;
      thumbs.forEach(function (b, i) {
        var active = i === currentIndex;
        b.classList.toggle("active", active);
        b.setAttribute("aria-selected", active ? "true" : "false");
      });
      if (counter) counter.textContent = (currentIndex + 1) + " / " + thumbs.length;
    }

    thumbs.forEach(function (btn, i) {
      btn.addEventListener("click", function () { setSlide(i); });
    });
    var prev = document.getElementById("gallery-prev");
    var next = document.getElementById("gallery-next");
    if (prev) prev.addEventListener("click", function () { setSlide(currentIndex - 1); });
    if (next) next.addEventListener("click", function () { setSlide(currentIndex + 1); });
  }

  function initDetailTabs() {
    document.querySelectorAll(".offer-details-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        var panelId = "panel-" + tab.getAttribute("data-panel");
        document.querySelectorAll(".offer-details-tab").forEach(function (t) {
          t.classList.remove("is-active");
          t.setAttribute("aria-selected", "false");
        });
        document.querySelectorAll(".offer-details-panel").forEach(function (p) {
          p.classList.remove("is-active");
        });
        tab.classList.add("is-active");
        tab.setAttribute("aria-selected", "true");
        var panel = document.getElementById(panelId);
        if (panel) panel.classList.add("is-active");
      });
    });
  }

  function initReels() {
    document.querySelectorAll(".reel-video, .product-reel-video").forEach(function (video) {
      video.muted = true;
      video.setAttribute("playsinline", "");
      var play = function () {
        var p = video.play();
        if (p && p.catch) p.catch(function () {});
      };
      if ("IntersectionObserver" in window) {
        var obs = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) play();
            else video.pause();
          });
        }, { threshold: 0.45 });
        obs.observe(video);
      } else {
        play();
      }
    });

    document.querySelectorAll(".reel-unmute-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var wrap = btn.closest(".kc-reel-card, .product-reel-hero, .kc-product-reel");
        var video = wrap && wrap.querySelector("video");
        if (!video) return;
        video.muted = !video.muted;
        btn.textContent = video.muted ? "🔇" : "🔊";
        if (!video.muted) video.play();
      });
    });
  }

  function initHeroCarousel() {
    var wrap = document.querySelector("[data-hero-carousel]");
    if (!wrap) return;
    var track = wrap.querySelector(".kc-hero-carousel-track");
    var slides = track ? track.children : [];
    if (!slides.length) return;
    var dots = Array.prototype.slice.call(document.querySelectorAll("[data-carousel-dot]"));
    var idx = 0;
    var timer;

    function go(n) {
      idx = (n + slides.length) % slides.length;
      track.style.transform = "translateX(-" + (idx * 100) + "%)";
      dots.forEach(function (d, i) {
        d.classList.toggle("is-active", i === idx);
        d.setAttribute("aria-selected", i === idx ? "true" : "false");
      });
    }

    function resetTimer() {
      clearInterval(timer);
      if (slides.length > 1) {
        timer = setInterval(function () { go(idx + 1); }, 6000);
      }
    }

    var prev = wrap.querySelector("[data-carousel-prev]");
    var next = wrap.querySelector("[data-carousel-next]");
    if (prev) prev.addEventListener("click", function () { go(idx - 1); resetTimer(); });
    if (next) next.addEventListener("click", function () { go(idx + 1); resetTimer(); });
    dots.forEach(function (d) {
      d.addEventListener("click", function () {
        go(parseInt(d.getAttribute("data-carousel-dot"), 10) || 0);
        resetTimer();
      });
    });
    resetTimer();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initShare();
    initProductSearch();
    initCategoryChips();
    initGallery();
    initDetailTabs();
    initReels();
    initHeroCarousel();
  });
})();
