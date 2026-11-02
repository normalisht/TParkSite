// Предупреждение при уходе со страницы админки с несохранёнными изменениями.
// Сравниваем содержимое POST-форм со снимком при загрузке: так ловятся и программные
// изменения (перетаскивание меняет поля порядка без событий input), и правки в списках.
(() => {
  // Выбор строк и действия в списке записей — не данные, их потеря не страшна.
  const IGNORED = new Set(["csrfmiddlewaretoken", "_selected_action", "action", "select_across", "index"]);
  let snapshot = null;
  let submitting = false;

  const readFields = () =>
    [...document.querySelectorAll('form[method="post" i]')].flatMap((form, i) =>
      [...new FormData(form)]
        .filter(([name]) => !IGNORED.has(name))
        .map(([name, value]) => {
          const text = value instanceof File ? `${value.name}:${value.size}` : value;
          return { name, line: `${i}:${name}=${text}` };
        }),
    );
  const serialize = (fields) => fields.map(({ line }) => line).join("\n");

  window.addEventListener("load", () => {
    snapshot = readFields();
  });

  // Поля уже записаны на сервере без отправки формы (кнопка «Сгенерировать»): их потеря не грозит, но остальные
  // несохранённые правки предупреждение должно ловить по-прежнему, поэтому снимок обновляем только для этих полей.
  document.addEventListener("admin-unsaved:saved", ({ detail }) => {
    if (snapshot === null) return;
    const saved = readFields().filter(({ name }) => detail.names.includes(name));
    snapshot = snapshot.map((field) => saved.find(({ name }) => name === field.name) ?? field);
  });

  // Отправка формы (сохранение, действие над записями) — уход со страницы ожидаем.
  document.addEventListener("submit", () => {
    submitting = true;
  });

  window.addEventListener("beforeunload", (event) => {
    if (submitting || snapshot === null || serialize(readFields()) === serialize(snapshot)) return;
    event.preventDefault();
    event.returnValue = "";
  });
})();
