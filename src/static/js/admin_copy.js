// Кнопки «Скопировать адрес» в админке: копируют абсолютный URL из data-copy-url.
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-url]");
  if (!button) return;
  event.preventDefault();
  const url = new URL(button.dataset.copyUrl, window.location.origin).href;
  try {
    await navigator.clipboard.writeText(url);
  } catch {
    // Clipboard API недоступен вне HTTPS — копируем через временное поле.
    const field = document.createElement("textarea");
    field.value = url;
    document.body.append(field);
    field.select();
    document.execCommand("copy");
    field.remove();
  }
  const icon = button.querySelector(".material-symbols-outlined");
  icon.textContent = "check";
  button.title = "Скопировано";
  setTimeout(() => {
    icon.textContent = "content_copy";
    button.title = "Скопировать адрес";
  }, 1500);
});
