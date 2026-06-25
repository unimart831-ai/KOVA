/**
 * Kova form validation & helpers.
 *
 * Alpine.js component: x-data="kovaForm(rules)"
 *
 * Example:
 *   <form x-data="kovaForm({
 *     company_name: { required: true, minLength: 2, maxLength: 100 },
 *     email: { required: true, pattern: 'email' },
 *     website_url: { pattern: 'url' },
 *     phone: { required: true, pattern: 'phone' }
 *   })" @submit.prevent="submitIfValid($el)">
 *
 *   <input name="company_name" @blur="validate('company_name', $el.value)">
 *   <p x-show="errors.company_name" x-text="errors.company_name"
 *      class="text-xs text-red-600 mt-1"></p>
 *
 * Built-in patterns: email, url, phone
 */
document.addEventListener("alpine:init", function () {
  var PATTERNS = {
    email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
    url: /^https?:\/\/.+\..+/,
    phone: /^\+?[\d\s\-()]{7,20}$/,
  };

  var MESSAGES = {
    required: "This field is required.",
    minLength: function (n) { return "Must be at least " + n + " characters."; },
    maxLength: function (n) { return "Must be " + n + " characters or fewer."; },
    email: "Enter a valid email address.",
    url: "Enter a valid URL (https://...).",
    phone: "Enter a valid phone number.",
    pattern: "Invalid format.",
  };

  window.kovaForm = function (rules) {
    return {
      errors: {},
      touched: {},
      submitting: false,

      validate: function (field, value) {
        this.touched[field] = true;
        var rule = rules[field];
        if (!rule) return true;

        var v = (value || "").trim();

        if (rule.required && !v) {
          this.errors[field] = MESSAGES.required;
          return false;
        }

        if (v && rule.minLength && v.length < rule.minLength) {
          this.errors[field] = MESSAGES.minLength(rule.minLength);
          return false;
        }

        if (v && rule.maxLength && v.length > rule.maxLength) {
          this.errors[field] = MESSAGES.maxLength(rule.maxLength);
          return false;
        }

        if (v && rule.pattern) {
          var re = PATTERNS[rule.pattern] || new RegExp(rule.pattern);
          if (!re.test(v)) {
            this.errors[field] = MESSAGES[rule.pattern] || MESSAGES.pattern;
            return false;
          }
        }

        delete this.errors[field];
        return true;
      },

      validateAll: function (form) {
        var valid = true;
        var self = this;
        Object.keys(rules).forEach(function (field) {
          var el = form.querySelector("[name='" + field + "']");
          var val = el ? (el.value || "") : "";
          if (!self.validate(field, val)) valid = false;
        });
        return valid;
      },

      hasErrors: function () {
        return Object.keys(this.errors).length > 0;
      },

      submitIfValid: function (form) {
        if (!this.validateAll(form)) {
          window.dispatchEvent(
            new CustomEvent("notify", {
              detail: { message: "Please fix the highlighted fields.", type: "warning" },
            })
          );
          return;
        }
        this.submitting = true;
        if (window.KovaBusy) {
          window.KovaBusy.start({
            instant: form.getAttribute("data-kova-busy") === "instant",
            message: form.getAttribute("data-kova-busy-message"),
          });
        }
        form.submit();
      },
    };
  };
});
