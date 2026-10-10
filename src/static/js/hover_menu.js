// Выпадающее меню шапки на ПК (Alpine-компонент hoverMenu): на устройствах с мышью открывается наведением,
// на тач-экранах и с клавиатуры — кликом. Подключается до Alpine: регистрация — в событии alpine:init.
document.addEventListener("alpine:init", () => {
  const CLOSE_DELAY = 200; // мс: мышь успевает пересечь зазор между кнопкой и панелью или чуть промахнуться
  const canHover = window.matchMedia("(hover: hover) and (pointer: fine)");

  window.Alpine.data("hoverMenu", () => ({
    expanded: false,
    hovering: false,
    timer: null,
    enter() {
      if (!canHover.matches) return;
      clearTimeout(this.timer);
      this.hovering = true;
      this.expanded = true;
    },
    leave() {
      if (!canHover.matches) return;
      this.hovering = false;
      clearTimeout(this.timer);
      this.timer = setTimeout(() => (this.expanded = false), CLOSE_DELAY);
    },
    // Клик, пока мышь над меню, его не закрывает: оно уже открыто наведением, а кликают по привычке.
    toggle() {
      this.expanded = this.hovering || !this.expanded;
    },
    close() {
      clearTimeout(this.timer);
      this.expanded = false;
    },
  }));
});
