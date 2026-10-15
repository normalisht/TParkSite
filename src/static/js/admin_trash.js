// Корзина админки: «Удалить навсегда» — только после подтверждения (без inline-обработчиков: CSP).
document.addEventListener("submit", (event) => {
  if (event.submitter?.name === "purge" && !window.confirm("Удалить навсегда? Восстановить будет нельзя.")) {
    event.preventDefault();
  }
});
