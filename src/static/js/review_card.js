// Карточка отзыва (Alpine-компонент reviewCard): длинный текст свёрнут, «Читать полностью» плавно раскрывает его,
// «Свернуть» — плавно сворачивает. Анимируется max-height (он же ограничивает свёрнутый текст), затухание низа —
// CSS-переход --review-fade. Подключается до Alpine: регистрация — в событии alpine:init.
document.addEventListener("alpine:init", () => {
  const DURATION = 300; // мс, как у раскрытия <details data-smooth> в site.js
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  window.Alpine.data("reviewCard", () => ({
    open: false,
    long: true,
    animation: null,
    init() {
      this.$nextTick(() => (this.long = this.$refs.text.scrollHeight > this.$refs.text.clientHeight + 4));
    },
    toggle() {
      const text = this.$refs.text;
      // Посреди анимации это текущая (анимированная) высота — повторный клик разворачивает без скачка.
      const from = text.getBoundingClientRect().height;
      this.animation?.cancel();
      this.animation = null;
      this.open = !this.open;
      // Класс меняем сразу, не дожидаясь :class (Alpine обновит его позже, тем же значением): мерить конечную высоту
      // и запускать анимацию нужно в этой же задаче, иначе браузер успевает нарисовать кадр с конечной высотой.
      text.classList.toggle("is-clamped", this.long && !this.open);
      text.style.overflow = "";
      if (reducedMotion.matches) return;
      const to = this.open ? text.scrollHeight : text.getBoundingClientRect().height;
      text.style.overflow = "hidden"; // пока высота меняется, хвост текста не вылезает из карточки
      const animation = text.animate({ maxHeight: [`${from}px`, `${to}px`] }, { duration: DURATION, easing: "ease-out" });
      this.animation = animation;
      // Отменённая анимация сюда не попадёт, а следующая уже заменила this.animation — обрезку снимает только последняя.
      animation.onfinish = () => {
        if (this.animation !== animation) return;
        this.animation = null;
        text.style.overflow = "";
      };
    },
  }));
});
