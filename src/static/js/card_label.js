// Подпись карточки категории (Alpine-компонент cardLabel): CSS не ужимает блок по тексту, если тот перенёсся, — блок
// остаётся шириной во весь max-width, и справа от текста пустое поле. Меряем самую длинную строку и ставим ширину по ней.
// Без JS подпись просто шире. Подключается до Alpine: регистрация — в событии alpine:init.
document.addEventListener("alpine:init", () => {
  window.Alpine.data("cardLabel", () => ({
    width: 0,
    init() {
      this.observer = new ResizeObserver(([entry]) => {
        const width = entry.contentRect.width;
        if (width === this.width) return;
        this.width = width;
        this.fit();
      });
      this.observer.observe(this.$root);
      // font-display: swap: со шрифтом меняется длина строк, а ширина карточки — нет, ResizeObserver этого не заметит.
      this.onFonts = () => this.fit();
      document.fonts.addEventListener("loadingdone", this.onFonts);
    },
    destroy() {
      this.observer.disconnect();
      document.fonts.removeEventListener("loadingdone", this.onFonts);
    },
    fit() {
      const label = this.$refs.label;
      label.style.width = "";
      const range = document.createRange();
      range.selectNodeContents(this.$refs.title);
      const lines = new Set([...range.getClientRects()].map((rect) => Math.round(rect.top)));
      if (lines.size < 2) return;
      const style = getComputedStyle(label);
      const padding = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
      label.style.width = `${Math.ceil(range.getBoundingClientRect().width + padding)}px`;
    },
  }));
});
