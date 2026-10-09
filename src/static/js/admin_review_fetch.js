// Кнопка «Подтянуть» у ссылки на отзыв: текст и дату с Яндекс Отзывов приносит админка
// (ReviewAdmin.fetch_yandex_view), текст вставляется в prose-editor, дата — в поле даты.
(() => {
  // Редактор создаётся асинхронно; ссылку на него получаем из события готовности django-prose-editor.
  const editors = new Map();
  document.addEventListener("prose-editor:ready", (event) => {
    editors.set(event.detail.textarea, event.detail.editor);
  });

  document.addEventListener("DOMContentLoaded", () => {
    const link = document.querySelector("input[data-yandex-fetch-url]");
    const textarea = document.getElementById("id_text");
    const dateInput = document.getElementById("id_date");
    if (!link || !textarea) return;

    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Подтянуть";
    button.className =
      "border border-base-200 cursor-pointer font-medium h-[38px] px-3 rounded-default shadow-xs shrink-0 text-sm " +
      "whitespace-nowrap hover:text-primary-600 dark:border-base-700 dark:hover:text-primary-500";
    const status = document.createElement("span");
    status.className = "text-sm";
    const row = document.createElement("div");
    row.className = "flex flex-wrap items-center gap-3";
    link.before(row);
    row.append(link, button, status);

    const show = (message, isError = false) => {
      status.textContent = message;
      status.classList.toggle("text-red-600", isError);
      status.classList.toggle("text-base-500", !isError);
    };

    button.addEventListener("click", async () => {
      const url = link.value.trim();
      if (!url) return show("Вставьте ссылку на отзыв.", true);
      if (textarea.value.trim() && !confirm("Заменить текущий текст отзыва текстом с Яндекса?")) return;
      button.disabled = true;
      show("Загружаем…");
      try {
        const response = await fetch(`${link.dataset.yandexFetchUrl}?${new URLSearchParams({ url })}`, {
          headers: { Accept: "application/json" },
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || "Не удалось получить отзыв.");
        const editor = editors.get(textarea);
        if (editor) editor.commands.setContent(data.text);
        else textarea.value = data.text;
        if (data.date && dateInput) dateInput.value = data.date;
        show("Готово — проверьте текст и сохраните.");
      } catch (error) {
        show(error.message, true);
      } finally {
        button.disabled = false;
      }
    });
  });
})();
