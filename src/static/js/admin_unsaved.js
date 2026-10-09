// Предупреждение при уходе со страницы админки с несохранёнными изменениями.
// Сравниваем содержимое POST-форм со снимком при загрузке: так ловятся и программные
// изменения (перетаскивание меняет поля порядка без событий input), и правки в списках.
(() => {
  // Выбор строк и действия в списке записей — не данные, их потеря не страшна.
  const IGNORED = new Set(["csrfmiddlewaretoken", "_selected_action", "action", "select_across", "index"]);
  let snapshot = null;
  let submitting = false;

  const serialize = () =>
    [...document.querySelectorAll('form[method="post" i]')]
      .map((form, i) =>
        [...new FormData(form)]
          .filter(([name]) => !IGNORED.has(name))
          .map(([name, value]) => {
            const text = value instanceof File ? `${value.name}:${value.size}` : value;
            return `${i}:${name}=${text}`;
          })
          .join("\n"),
      )
      .join("\n");

  window.addEventListener("load", () => {
    snapshot = serialize();
  });

  // Отправка формы (сохранение, действие над записями) — уход со страницы ожидаем.
  document.addEventListener("submit", () => {
    submitting = true;
  });

  window.addEventListener("beforeunload", (event) => {
    if (submitting || snapshot === null || serialize() === snapshot) return;
    event.preventDefault();
    event.returnValue = "";
  });
})();
