(function () {
  if (window.Turbo) {
    window.Turbo.setProgressBarDelay(120);
  }

  let pendingForm = null;

  function transitionBar() {
    return document.getElementById('pageTransition');
  }

  function showTransition() {
    transitionBar()?.classList.add('active');
    document.documentElement.classList.add('is-navigating');
    document.getElementById('mainContent')?.setAttribute('aria-busy', 'true');
  }

  function hideTransition() {
    transitionBar()?.classList.remove('active');
    document.documentElement.classList.remove('is-navigating');
    document.getElementById('mainContent')?.setAttribute('aria-busy', 'false');
  }

  function restoreSubmitter(submitter) {
    if (!submitter || !submitter.dataset.originalText) return;
    submitter.classList.remove('is-loading');
    submitter.removeAttribute('aria-disabled');
    submitter.disabled = false;
    if (submitter.tagName === 'BUTTON') {
      submitter.textContent = submitter.dataset.originalText;
    } else {
      submitter.value = submitter.dataset.originalText;
    }
    delete submitter.dataset.originalText;
  }

  function markSubmitterLoading(submitter) {
    if (!submitter || submitter.classList.contains('is-loading')) return;
    const originalText = submitter.textContent || submitter.value || '';
    submitter.dataset.originalText = originalText;
    submitter.classList.add('is-loading');
    submitter.setAttribute('aria-disabled', 'true');
    if (!submitter.name) submitter.disabled = true;
    if (submitter.tagName === 'BUTTON') {
      submitter.textContent = 'Đang xử lý...';
    } else {
      submitter.value = 'Đang xử lý...';
    }
  }

  function initFlashMessages() {
    document.querySelectorAll('.flash-close:not([data-bound])').forEach(function (btn) {
      btn.dataset.bound = 'true';
      btn.addEventListener('click', function () {
        btn.closest('.flash')?.remove();
      });
    });

    window.clearTimeout(window.__e16FlashTimer);
    window.__e16FlashTimer = window.setTimeout(function () {
      document.querySelectorAll('.flash').forEach(function (el) {
        el.classList.add('leaving');
        window.setTimeout(function () { el.remove(); }, 300);
      });
    }, 4500);
  }

  function initConfirmModal() {
    const overlay = document.getElementById('confirmOverlay');
    const titleEl = document.getElementById('confirmTitle');
    const msgEl = document.getElementById('confirmMessage');
    const iconEl = document.getElementById('confirmIcon');
    const okBtn = document.getElementById('confirmOk');
    const cancelBtn = document.getElementById('confirmCancel');
    if (!overlay || !titleEl || !msgEl || !iconEl || !okBtn || !cancelBtn) return;

    function showModal(title, message, icon) {
      titleEl.textContent = title || 'Xác nhận hành động';
      msgEl.textContent = message || 'Bạn có chắc chắn?';
      iconEl.textContent = icon || '!';
      overlay.classList.add('active');
    }

    function hideModal() {
      overlay.classList.remove('active');
      pendingForm = null;
    }

    if (!overlay.dataset.bound) {
      overlay.dataset.bound = 'true';
      cancelBtn.addEventListener('click', hideModal);
      overlay.addEventListener('click', function (event) {
        if (event.target === overlay) hideModal();
      });
      okBtn.addEventListener('click', function () {
        if (pendingForm) {
          pendingForm.setAttribute('data-confirmed', 'true');
          pendingForm.requestSubmit ? pendingForm.requestSubmit() : pendingForm.submit();
        }
        hideModal();
      });
      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && overlay.classList.contains('active')) hideModal();
      });
    }

    window.confirmAction = function (form, title, message, icon) {
      if (form.getAttribute('data-confirmed') === 'true') {
        form.removeAttribute('data-confirmed');
        return true;
      }
      pendingForm = form;
      showModal(title, message, icon);
      return false;
    };
    window.__e16HideConfirmModal = hideModal;
  }

  function initFormLoading() {
    if (document.documentElement.dataset.formLoadingBound) return;
    document.documentElement.dataset.formLoadingBound = 'true';

    document.addEventListener('submit', function (event) {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) return;
      const submitter = event.submitter || form.querySelector('button[type="submit"], input[type="submit"]');
      window.setTimeout(function () { markSubmitterLoading(submitter); }, 0);
    });

    document.addEventListener('turbo:submit-end', function (event) {
      restoreSubmitter(event.detail.formSubmission?.submitter);
      hideTransition();
    });
  }

  function initTurboEvents() {
    if (document.documentElement.dataset.turboEventsBound) return;
    document.documentElement.dataset.turboEventsBound = 'true';

    document.addEventListener('turbo:click', function () {
      showTransition();
    });
    document.addEventListener('turbo:before-fetch-request', showTransition);
    document.addEventListener('turbo:load', hideTransition);
    document.addEventListener('turbo:fetch-request-error', hideTransition);
    document.addEventListener('turbo:before-cache', function () {
      hideTransition();
      window.__e16HideConfirmModal?.();
      document.querySelectorAll('.flash').forEach(function (el) { el.remove(); });
      document.querySelectorAll('.is-loading').forEach(restoreSubmitter);
    });
  }

  function initNotificationBadge() {
    const badge = document.querySelector('.notification-badge[data-unread-url]');
    if (!badge || badge.dataset.loaded === 'true') return;
    badge.dataset.loaded = 'true';

    fetch(badge.dataset.unreadUrl, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin'
    })
      .then(function (response) {
        if (!response.ok) throw new Error('Unread count request failed');
        return response.json();
      })
      .then(function (data) {
        const count = Number(data.count || 0);
        if (count > 0) {
          badge.textContent = count > 99 ? '99+' : String(count);
          badge.hidden = false;
        } else {
          badge.hidden = true;
        }
      })
      .catch(function () {
        badge.hidden = true;
      });
  }

  function initShell() {
    initConfirmModal();
    initFlashMessages();
    initFormLoading();
    initTurboEvents();
    initNotificationBadge();
    document.getElementById('mainContent')?.setAttribute('aria-busy', 'false');
  }

  document.addEventListener('DOMContentLoaded', initShell);
  document.addEventListener('turbo:load', initShell);
})();
