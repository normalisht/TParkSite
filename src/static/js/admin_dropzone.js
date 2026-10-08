// Перетаскивание файлов в поля загрузки админки (виджеты Unfold).
// Зона — рамка поля целиком; файл кладётся в скрытый <input type=file>, затем шлётся change:
// Unfold обновит подпись, admin_unsaved.js отметит форму изменённой.
(() => {
  const ready = new WeakSet(); // не data-атрибут: он скопировался бы в клон пустой inline-формы
  const hasFiles = (event) => Array.from(event.dataTransfer?.types || []).includes("Files");

  // Совпадает ли файл с accept поля: «image/*», «image/png», «.jpg».
  const accepts = (input, file) => {
    const rules = (input.accept || "").split(",").map((r) => r.trim().toLowerCase()).filter(Boolean);
    if (!rules.length) return true;
    const type = (file.type || "").toLowerCase();
    const name = file.name.toLowerCase();
    return rules.some((rule) =>
      rule.startsWith(".") ? name.endsWith(rule) : rule.endsWith("/*") ? type.startsWith(rule.slice(0, -1)) : type === rule,
    );
  };

  // Подпись поля: Unfold показывает только первый файл, при нескольких — перечисляем.
  const showNames = (input) => {
    const label = zoneOf(input)?.querySelector("input[type=text][disabled]");
    const names = Array.from(input.files || []).map((f) => f.name);
    if (label && names.length > 1) label.setAttribute("value", `Выбрано файлов: ${names.length} — ${names.join(", ")}`);
  };

  // Рамка виджета — ближайший предок, в котором есть и сам input, и текстовая подпись Unfold.
  const zoneOf = (input) => {
    for (let el = input.parentElement; el && el !== document.body; el = el.parentElement) {
      if (el.querySelector("input[type=text][disabled]")) return el;
    }
    return null;
  };

  const highlight = (zone, on) => {
    zone.style.outline = on ? "2px dashed var(--color-primary-500, #16a34a)" : "";
    zone.style.outlineOffset = on ? "2px" : "";
  };

  const setup = (input) => {
    const zone = zoneOf(input);
    if (!zone || ready.has(zone) || input.disabled) return;
    ready.add(zone);
    zone.title = input.multiple ? "Перетащите сюда файлы или нажмите, чтобы выбрать" : "Перетащите сюда файл или нажмите, чтобы выбрать";
    let depth = 0; // dragenter/dragleave срабатывают и на дочерних элементах

    zone.addEventListener("dragenter", (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      depth += 1;
      highlight(zone, true);
    });
    zone.addEventListener("dragover", (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
    });
    zone.addEventListener("dragleave", () => {
      depth = Math.max(depth - 1, 0);
      if (!depth) highlight(zone, false);
    });
    zone.addEventListener("drop", (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      depth = 0;
      highlight(zone, false);
      const dropped = Array.from(event.dataTransfer.files);
      const suitable = dropped.filter((file) => accepts(input, file));
      if (!suitable.length) {
        window.alert("Этот файл сюда не подходит. Для фото — jpg, png или webp.");
        return;
      }
      const transfer = new DataTransfer();
      (input.multiple ? suitable : suitable.slice(0, 1)).forEach((file) => transfer.items.add(file));
      input.files = transfer.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    // После подписи Unfold (она ставит имя первого файла) — своя, со всеми файлами.
    input.addEventListener("change", () => requestAnimationFrame(() => showNames(input)));
  };

  const scan = () => document.querySelectorAll("input[type=file]").forEach(setup);

  // Файл, брошенный мимо поля, браузер открыл бы вместо админки — и несохранённая форма пропала бы.
  window.addEventListener("dragover", (event) => hasFiles(event) && event.preventDefault());
  window.addEventListener("drop", (event) => hasFiles(event) && event.preventDefault());

  document.addEventListener("DOMContentLoaded", () => {
    scan();
    // Inline-формы добавляются кнопкой «Добавить ещё» — подхватываем новые поля.
    new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
  });
})();
