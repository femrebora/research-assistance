/* ═══════════════════════════════════════════════════════════════════════════
   Research Assistant — Theme & UI Helpers
   ═══════════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── Theme management ─────────────────────────────────────────────────── */
  const THEME_KEY = 'ra-theme';

  function getSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function getTheme() {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
    if (stored === 'system') return getSystemTheme();
    return getSystemTheme(); // default to system
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    updateToggleUI(localStorage.getItem(THEME_KEY) || 'system');
  }

  function setTheme(mode) {
    localStorage.setItem(THEME_KEY, mode);
    const resolved = mode === 'system' ? getSystemTheme() : mode;
    applyTheme(resolved);
  }

  function updateToggleUI(mode) {
    document.querySelectorAll('.theme-toggle-btn').forEach(function (btn) {
      var val = btn.getAttribute('data-theme-value');
      btn.classList.toggle('active', val === mode);
      btn.setAttribute('aria-pressed', val === mode ? 'true' : 'false');
    });
  }

  // Initialize theme immediately (before paint)
  var storedMode = localStorage.getItem(THEME_KEY) || 'system';
  var initialTheme = storedMode === 'system' ? getSystemTheme() : storedMode;
  document.documentElement.setAttribute('data-theme', initialTheme);

  // Listen for system theme changes when in system mode
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
    if (localStorage.getItem(THEME_KEY) === 'system') {
      applyTheme(getSystemTheme());
    }
  });

  // Expose for inline onclick handlers
  window.setTheme = setTheme;
  window.updateToggleUI = updateToggleUI;

  /* ── Tab switching ────────────────────────────────────────────────────── */
  window.switchTab = function (groupId, tabId) {
    var bar = document.getElementById(groupId + '-bar');
    if (!bar) return;

    // Update tab buttons
    bar.querySelectorAll('.tab-btn').forEach(function (btn) {
      var isActive = btn.getAttribute('data-tab') === tabId;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    // Update tab panels
    var panels = document.querySelectorAll('[id^="' + groupId + '-"]');
    panels.forEach(function (panel) {
      if (panel.id === groupId + '-' + tabId) {
        panel.classList.add('active');
      } else if (panel.getAttribute('role') === 'tabpanel') {
        panel.classList.remove('active');
      }
    });
  };

  /* ── Copy diagnostics ─────────────────────────────────────────────────── */
  window.copyDiagnostics = function (btn) {
    var pre = btn.closest('.state-box') ? btn.parentElement.parentElement.querySelector('pre') : null;
    if (!pre) pre = document.getElementById('diagnostics');
    if (!pre) return;

    var text = pre.textContent;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(function () {
          btn.textContent = 'Copy';
          btn.classList.remove('copied');
        }, 2000);
      });
    } else {
      // Fallback
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(function () {
        btn.textContent = 'Copy';
        btn.classList.remove('copied');
      }, 2000);
    }
  };

  /* ── Sidebar toggle (mobile) ──────────────────────────────────────────── */
  window.toggleSidebar = function () {
    var sidebar = document.querySelector('.app-sidebar');
    var overlay = document.querySelector('.sidebar-overlay');
    if (!sidebar) return;
    sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('open');
  };

  /* ── Advanced settings toggle ─────────────────────────────────────────── */
  document.addEventListener('click', function (e) {
    var toggle = e.target.closest('.advanced-toggle');
    if (toggle) {
      toggle.classList.toggle('open');
      var panel = toggle.nextElementSibling;
      if (panel) panel.classList.toggle('open');
      toggle.setAttribute('aria-expanded', panel && panel.classList.contains('open') ? 'true' : 'false');
    }
  });

  /* ── Initialize toggle UI on DOM ready ────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    updateToggleUI(storedMode);
  });

})();
