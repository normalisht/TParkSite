// Согласие хранится в браузере, чтобы HTML сайта и его ETag не зависели от выбора посетителя.
(function () {
  const {counterId: rawCounterId, consentVersion, consentDocument, consentUrl, webvisor} = document.currentScript.dataset;
  const analyticsEnabled = Boolean(rawCounterId);
  const counterId = Number(rawCounterId);
  const disableCounter = `disableYaCounter${counterId}`;
  const storageKey = "metrika-consent";
  const attemptKey = "metrika-consent-attempt";
  const allowed = `allow:${consentVersion}`;
  const refused = "refuse";
  const pendingRefusal = "refuse-pending";
  const notice = document.getElementById("cookie-notice");
  const settingsButton = document.querySelector("[data-metrika-settings]");
  const allowButton = notice.querySelector("[data-metrika-allow]");
  const refuseButton = notice.querySelector("[data-metrika-refuse]");
  const closeButton = notice.querySelector("[data-consent-close]");
  const status = notice.querySelector("[data-metrika-status]");
  const errorMessage = notice.querySelector("[data-consent-error]");
  let choice = null;
  let accepting = false;
  let attempt;
  let revocation;
  let revision = 0;
  let openedFromFooter = false;
  let tag;
  let tagLoaded = false;
  let counterRunning = false;
  let confirmed = false;

  function initCounter() {
    if (choice !== allowed || !confirmed || counterRunning) return;
    window.ym(counterId, "init", {clickmap: true, trackLinks: true, accurateTrackBounce: true, webvisor: webvisor === "true"});
    counterRunning = true;
  }

  function startCounter() {
    window[disableCounter] = false;
    if (tagLoaded) {
      initCounter();
      return;
    }
    if (tag) return;
    window.ym ||= function () { (window.ym.a ||= []).push(arguments); };
    window.ym.l = Date.now();
    tag = document.createElement("script");
    tag.async = true;
    tag.src = "https://mc.yandex.ru/metrika/tag.js";
    tag.addEventListener("load", () => {
      tagLoaded = true;
      // Согласие могли отозвать, пока загружался скрипт.
      initCounter();
    }, {once: true});
    tag.addEventListener("error", () => {
      tag.remove();
      tag = null;
    }, {once: true});
    document.head.append(tag);
  }

  function clearAnalyticsStorage() {
    const isMetrikaKey = (key) => /^_ym(?:_|[0-9]+_)/.test(key);
    for (const entry of document.cookie.split(";")) {
      const name = entry.split("=", 1)[0].trim();
      if (!isMetrikaKey(name) && name !== "gdpr") continue;
      const expired = `${name}=; Max-Age=0; Path=/`;
      document.cookie = expired;
      document.cookie = `${expired}; Domain=${location.hostname}`;
    }
    for (const storageName of ["localStorage", "sessionStorage"]) {
      try {
        const storage = window[storageName];
        for (const key of Object.keys(storage)) {
          if (isMetrikaKey(key) || (storageName === "localStorage" && key === "zz")) storage.removeItem(key);
        }
      } catch (error) {
        // Браузер может запретить доступ к хранилищу.
      }
    }
  }

  function applyChoice() {
    if (analyticsEnabled && choice === allowed && confirmed) {
      startCounter();
      return;
    }
    if (counterRunning) {
      counterRunning = false;
      window.ym(counterId, "destruct");
    }
    if (analyticsEnabled) window[disableCounter] = true;
    clearAnalyticsStorage();
  }

  function showNotice(open) {
    notice.hidden = !open;
    document.documentElement.classList.toggle("cookie-open", open);
    settingsButton.setAttribute("aria-expanded", String(open));
  }

  async function serverState(query = "") {
    const response = await fetch(consentUrl + query, {cache: "no-store"});
    if (!response.ok) throw new Error("Consent state unavailable");
    return response.json();
  }

  async function record(data) {
    const {csrfToken} = await serverState();
    const response = await fetch(consentUrl, {
      method: "POST",
      cache: "no-store",
      headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken},
      body: JSON.stringify(data)
    });
    if (!response.ok) {
      const message = response.status === 409
        ? "Условия использования cookie обновились. Обновите страницу и повторите выбор."
        : "Не удалось сохранить согласие. Попробуйте ещё раз.";
      throw new Error(message);
    }
  }

  function remember(value) {
    choice = value;
    try {
      if (value === null) localStorage.removeItem(storageKey);
      else localStorage.setItem(storageKey, value);
    } catch (error) {}
  }

  function savedAttempt() {
    try { return JSON.parse(localStorage.getItem(attemptKey)) || attempt; } catch (error) { return attempt; }
  }

  function rememberAttempt(value) {
    attempt = value;
    try {
      if (value) localStorage.setItem(attemptKey, JSON.stringify(value));
      else localStorage.removeItem(attemptKey);
    } catch (error) {}
  }

  function clearAttempt(previous) {
    if (previous && savedAttempt()?.id === previous.id) rememberAttempt(null);
  }

  function retryRevocation() {
    if (!revocation) {
      const outstanding = savedAttempt();
      revocation = record({decision: "revoke", attempt: outstanding?.id})
        .then(() => {
          clearAttempt(outstanding);
          if (choice === pendingRefusal) {
            remember(refused);
            if (!analyticsEnabled) {
              closeNotice(document.getElementById("content"));
              settingsButton.hidden = true;
            }
          }
          return true;
        })
        .catch(() => false)
        .finally(() => { revocation = null; });
    }
    return revocation;
  }

  async function syncWithdrawal(checking) {
    showNotice(false);
    if (choice === pendingRefusal) {
      settingsButton.hidden = false;
      applyChoice();
      retryRevocation();
      return;
    }
    let canRevoke = choice?.startsWith("allow:");
    try {
      ({canRevoke} = await serverState("?check=withdrawal"));
    } catch (error) {
      // При сбое можно повторить отзыв известного браузеру согласия.
    }
    if (checking !== revision) return;
    settingsButton.hidden = !(canRevoke || savedAttempt());
    if (!settingsButton.hidden) applyChoice();
  }

  async function syncChoice() {
    const before = choice;
    const checking = ++revision;
    try { choice = localStorage.getItem(storageKey); } catch (error) {}
    if (choice !== before) confirmed = false;
    openedFromFooter = false;
    status.hidden = true;
    if (!analyticsEnabled) {
      await syncWithdrawal(checking);
      return;
    }
    if (choice === allowed) {
      showNotice(false);
      try {
        const state = await serverState();
        if (checking !== revision) return;
        confirmed = state.allowed && state.version === consentVersion;
        if (!confirmed) {
          remember(null);
          showNotice(true);
        }
      } catch (error) {
        if (checking !== revision) return;
        confirmed = false;
        showNotice(true);
      }
    } else {
      confirmed = false;
      showNotice(choice !== refused && choice !== pendingRefusal);
    }
    applyChoice();
    if (choice === pendingRefusal && !accepting) retryRevocation();
  }

  function closeNotice(focusTarget = openedFromFooter ? settingsButton : document.getElementById("content")) {
    const returnFocus = notice.contains(document.activeElement) || document.activeElement === settingsButton;
    openedFromFooter = false;
    showNotice(false);
    if (returnFocus) focusTarget.focus({preventScroll: true});
  }

  function refuse() {
    revision++;
    const previouslyAllowed = !analyticsEnabled || choice?.startsWith("allow:");
    remember(previouslyAllowed || accepting || savedAttempt() || choice === pendingRefusal ? pendingRefusal : refused);
    confirmed = false;
    closeNotice();
    applyChoice();
    if (choice === pendingRefusal && !accepting) retryRevocation();
  }

  async function allow() {
    const saving = ++revision;
    accepting = true;
    allowButton.disabled = true;
    errorMessage.hidden = true;
    try {
      if (choice === pendingRefusal && !await retryRevocation()) {
        throw new Error("Не удалось отправить предыдущий отзыв согласия. Попробуйте ещё раз.");
      }
      if (saving !== revision) return;
      let outstanding = savedAttempt();
      if (outstanding && outstanding.document !== consentDocument) {
        await record({decision: "revoke", attempt: outstanding.id});
        clearAttempt(outstanding);
        outstanding = null;
      }
      if (saving !== revision) return;
      outstanding ||= {id: crypto.randomUUID(), document: consentDocument};
      rememberAttempt(outstanding);
      await record({decision: "allow", document: consentDocument, attempt: outstanding.id});
      if (saving !== revision) {
        if (choice === refused) remember(pendingRefusal);
        return;
      }
      clearAttempt(outstanding);
      remember(allowed);
      confirmed = true;
      closeNotice();
      applyChoice();
    } catch (error) {
      if (saving === revision) {
        errorMessage.textContent = error.message.startsWith("Не удалось") || error.message.startsWith("Условия")
          ? error.message : "Не удалось сохранить согласие. Попробуйте ещё раз.";
        errorMessage.hidden = false;
      }
    } finally {
      accepting = false;
      allowButton.disabled = false;
      if (choice === pendingRefusal) retryRevocation();
    }
  }

  settingsButton.hidden = !analyticsEnabled;
  settingsButton.addEventListener("click", () => {
    openedFromFooter = true;
    if (analyticsEnabled) {
      status.textContent = choice === allowed && confirmed
        ? "Необязательные cookie разрешены." : "Необязательные cookie отключены.";
      status.hidden = false;
    } else {
      status.textContent = "Отзыв ещё не сохранён. Можно повторить отправку.";
      status.hidden = choice !== pendingRefusal;
    }
    errorMessage.hidden = true;
    showNotice(true);
    (closeButton || (confirmed ? refuseButton : allowButton)).focus({preventScroll: true});
  });
  notice.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && openedFromFooter) closeNotice();
  });
  closeButton?.addEventListener("click", () => closeNotice());
  allowButton?.addEventListener("click", allow);
  refuseButton.addEventListener("click", refuse);
  window.addEventListener("storage", (event) => {
    if (event.storageArea === window.localStorage && (event.key === storageKey || event.key === null)) syncChoice();
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) syncChoice();
  });
  syncChoice();

  // Цели в счётчике настроены как JavaScript-события с этими идентификаторами.
  document.addEventListener("click", function (event) {
    if (!counterRunning) return;
    var link = event.target.closest && event.target.closest("a[href]");
    if (!link) return;
    var href = link.getAttribute("href");
    var goal = href.indexOf("tel:") === 0 ? "call"
      : href.indexOf("wa.me/") !== -1 ? "whatsapp"
      : href.indexOf("t.me/") !== -1 ? "telegram"
      : href.indexOf("vk.com/") !== -1 ? "vk"
      : href.indexOf("max.ru/") !== -1 ? "max"
      : (href.indexOf("dzen.ru/") !== -1 && href.indexOf("/embed/") === -1) ? "dzen"
      : href.indexOf("instagram.com/") !== -1 ? "instagram" : "";
    if (goal) window.ym(counterId, "reachGoal", goal);
  });
})();
