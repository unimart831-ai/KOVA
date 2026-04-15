/**
 * Kova Pixel — Lightweight website tracking script (~3KB minified).
 *
 * Tracks page views, form submissions, and custom events on a user's website.
 * Events are sent to the Kova platform and attributed to social posts via UTM params.
 *
 * Usage:
 *   <script>
 *     window._kovaConfig = { token: 'YOUR_TOKEN', endpoint: 'https://app.kova.ai/analytics/pixel/track/' };
 *   </script>
 *   <script src="https://app.kova.ai/static/js/kova-pixel.js" defer></script>
 *
 * Custom events:
 *   KovaPixel.track('purchase', { revenue: 49.99, currency: 'USD' });
 *   KovaPixel.track('sign_up', { metadata: { plan: 'pro' } });
 */
(function() {
  'use strict';

  var KovaPixel = {
    _token: null,
    _endpoint: null,
    _visitorId: null,
    _sessionId: null,
    _initialized: false,

    /**
     * Initialize the pixel with configuration.
     * @param {Object} config - { token, endpoint, autoTrack, trackForms }
     */
    init: function(config) {
      if (!config || !config.token) return;
      if (this._initialized) return;

      this._token = config.token;
      this._endpoint = config.endpoint || '/analytics/pixel/track/';
      this._visitorId = this._getOrCreateId('_kova_vid', 365);
      this._sessionId = this._getOrCreateId('_kova_sid', 0);
      this._initialized = true;

      // Store UTM params from current URL for session persistence
      this._captureUTMs();

      // Auto-track page view
      if (config.autoTrack !== false) {
        this.track('page_view');
      }

      // Auto-track form submissions
      if (config.trackForms !== false) {
        this._observeForms();
      }

      // SPA support: detect client-side navigations
      this._observeSPA();
    },

    /**
     * Track an event.
     * @param {string} eventType - page_view|form_submit|button_click|purchase|add_to_cart|sign_up|custom
     * @param {Object} [data] - { name, revenue, currency, metadata }
     */
    track: function(eventType, data) {
      if (!this._initialized) return;

      data = data || {};
      var utms = this._getUTMs();

      var payload = {
        token: this._token,
        event_type: eventType || 'custom',
        event_name: data.name || '',
        page_url: window.location.href,
        page_title: document.title,
        referrer: document.referrer,
        visitor_id: this._visitorId,
        session_id: this._sessionId,
        screen_width: window.screen ? window.screen.width : 0,
        utm_source: utms.utm_source || '',
        utm_medium: utms.utm_medium || '',
        utm_campaign: utms.utm_campaign || '',
        utm_content: utms.utm_content || ''
      };

      if (data.revenue !== undefined) payload.revenue = data.revenue;
      if (data.currency) payload.currency = data.currency;
      if (data.metadata) payload.metadata = data.metadata;

      this._send(payload);
    },

    /**
     * Send payload to the tracking endpoint.
     * Uses sendBeacon (preferred) or XHR fallback.
     */
    _send: function(payload) {
      var body = JSON.stringify(payload);
      var endpoint = this._endpoint;

      // sendBeacon with text/plain avoids CORS preflight
      if (navigator.sendBeacon) {
        try {
          var blob = new Blob([body], { type: 'text/plain' });
          var sent = navigator.sendBeacon(endpoint, blob);
          if (sent) return;
        } catch (e) { /* fall through to XHR */ }
      }

      // XHR fallback
      try {
        var xhr = new XMLHttpRequest();
        xhr.open('POST', endpoint, true);
        xhr.setRequestHeader('Content-Type', 'text/plain');
        xhr.send(body);
      } catch (e) { /* silently fail — never break the host website */ }
    },

    /**
     * Capture UTM params from URL and persist in sessionStorage.
     */
    _captureUTMs: function() {
      var params = this._parseUTMs();
      if (params.utm_source) {
        try { sessionStorage.setItem('_kova_utms', JSON.stringify(params)); } catch (e) {}
      }
    },

    /**
     * Get UTMs from URL or sessionStorage.
     */
    _getUTMs: function() {
      var params = this._parseUTMs();
      if (params.utm_source) return params;

      // Fall back to stored UTMs (persists across page navigations within session)
      try {
        var stored = sessionStorage.getItem('_kova_utms');
        if (stored) return JSON.parse(stored);
      } catch (e) {}

      return {};
    },

    /**
     * Parse UTM params from current URL.
     */
    _parseUTMs: function() {
      var params = {};
      var search = window.location.search;
      if (!search) return params;

      var pairs = search.substring(1).split('&');
      for (var i = 0; i < pairs.length; i++) {
        var pair = pairs[i].split('=');
        var key = decodeURIComponent(pair[0] || '');
        if (key.indexOf('utm_') === 0 && pair[1]) {
          params[key] = decodeURIComponent(pair[1]);
        }
      }
      return params;
    },

    /**
     * SPA support: detect client-side navigation via pushState/popstate.
     * Tracks a page_view on each route change.
     */
    _observeSPA: function() {
      var self = this;
      var lastUrl = window.location.href;

      // Wrap pushState and replaceState
      var origPush = history.pushState;
      var origReplace = history.replaceState;

      history.pushState = function() {
        origPush.apply(this, arguments);
        self._onSPANav(lastUrl);
        lastUrl = window.location.href;
      };

      history.replaceState = function() {
        origReplace.apply(this, arguments);
        self._onSPANav(lastUrl);
        lastUrl = window.location.href;
      };

      // Back/forward buttons
      window.addEventListener('popstate', function() {
        self._onSPANav(lastUrl);
        lastUrl = window.location.href;
      });
    },

    _onSPANav: function(previousUrl) {
      // Only fire if the URL actually changed (ignore hash-only changes)
      if (window.location.href !== previousUrl) {
        // Re-capture UTMs in case the new URL has them
        this._captureUTMs();
        this.track('page_view');
      }
    },

    /**
     * Auto-track form submissions.
     * Captures non-sensitive form fields and sends as metadata.
     */
    _observeForms: function() {
      var self = this;
      document.addEventListener('submit', function(e) {
        var form = e.target;
        if (!form || form.tagName !== 'FORM') return;
        // Allow opt-out via data attribute
        if (form.getAttribute('data-kova-ignore') === 'true') return;

        var formData = {};
        var inputs = form.querySelectorAll('input, select, textarea');
        for (var i = 0; i < inputs.length; i++) {
          var input = inputs[i];
          // Skip password, hidden, and file fields — never capture sensitive data
          if (!input.name) continue;
          var type = (input.type || '').toLowerCase();
          if (type === 'password' || type === 'hidden' || type === 'file') continue;
          if (input.name.toLowerCase().match(/password|pass|pwd|credit|card|cvv|ssn|secret/)) continue;
          formData[input.name] = input.value;
        }

        self.track('form_submit', {
          name: form.getAttribute('data-kova-form') || form.id || form.getAttribute('name') || 'form',
          metadata: formData
        });
      }, true);
    },

    /**
     * Get or create a persistent ID via cookies.
     * @param {string} name - Cookie name
     * @param {number} days - Expiry in days (0 = session cookie)
     */
    _getOrCreateId: function(name, days) {
      var id = this._getCookie(name);
      if (!id) {
        id = this._generateId();
        this._setCookie(name, id, days);
      }
      return id;
    },

    /**
     * Generate a random ID (UUID v4 format).
     */
    _generateId: function() {
      // Use crypto.getRandomValues if available, else Math.random fallback
      if (window.crypto && crypto.getRandomValues) {
        var buf = new Uint8Array(16);
        crypto.getRandomValues(buf);
        buf[6] = (buf[6] & 0x0f) | 0x40;
        buf[8] = (buf[8] & 0x3f) | 0x80;
        var hex = '';
        for (var i = 0; i < 16; i++) {
          var h = buf[i].toString(16);
          hex += (h.length === 1 ? '0' : '') + h;
        }
        return hex.substr(0, 8) + '-' + hex.substr(8, 4) + '-' +
               hex.substr(12, 4) + '-' + hex.substr(16, 4) + '-' + hex.substr(20);
      }

      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0;
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
      });
    },

    _getCookie: function(name) {
      var match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '=([^;]*)'));
      return match ? decodeURIComponent(match[1]) : null;
    },

    _setCookie: function(name, value, days) {
      var expires = '';
      if (days > 0) {
        var d = new Date();
        d.setTime(d.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = '; expires=' + d.toUTCString();
      }
      document.cookie = name + '=' + encodeURIComponent(value) + expires + '; path=/; SameSite=Lax';
    }
  };

  // Expose globally
  window.KovaPixel = KovaPixel;

  // Auto-init if config was defined before this script loaded
  if (window._kovaConfig) {
    KovaPixel.init(window._kovaConfig);
  }
})();
