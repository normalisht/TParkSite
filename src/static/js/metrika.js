// Счётчик Яндекс Метрики и цели. Номер счётчика — в data-counter-id тега <script> (partials/metrika.html).
(function () {
  var counterId = Number(document.currentScript.dataset.counterId);

  // Официальный код счётчика.
  (function (m, e, t, r, i, k, a) {
    m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
    m[i].l = 1 * new Date();
    for (var j = 0; j < document.scripts.length; j++) { if (document.scripts[j].src === r) { return; } }
    k = e.createElement(t), a = e.getElementsByTagName(t)[0], k.async = 1, k.src = r, a.parentNode.insertBefore(k, a);
  })(window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
  ym(counterId, "init", {clickmap: true, trackLinks: true, accurateTrackBounce: true, webvisor: true});

  // Цели: звонок и переходы в мессенджеры (в Метрике — цели типа «JavaScript-событие» с этими идентификаторами).
  document.addEventListener("click", function (event) {
    var link = event.target.closest && event.target.closest("a[href]");
    if (!link) return;
    var href = link.getAttribute("href");
    var goal = href.indexOf("tel:") === 0 ? "call"
      : href.indexOf("wa.me/") !== -1 ? "whatsapp"
      : href.indexOf("t.me/") !== -1 ? "telegram"
      : href.indexOf("vk.com/") !== -1 ? "vk"
      : href.indexOf("max.ru/") !== -1 ? "max" : "";
    if (goal) ym(counterId, "reachGoal", goal);
  });
})();
