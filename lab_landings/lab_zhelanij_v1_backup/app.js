/* ЛАБОРАТОРИЯ ЖЕЛАНИЙ — клиентский JS (без зависимостей) */
(function () {
  'use strict';

  // 1. Счётчики: анимация чисел при появлении в зоне видимости
  const counters = document.querySelectorAll('.stat__num');
  if (counters.length) {
    const animate = (el) => {
      const target = parseInt(el.dataset.target, 10) || 0;
      const duration = 1600;
      const startTime = performance.now();
      const easeOut = (t) => 1 - Math.pow(1 - t, 3);

      const step = (now) => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const value = Math.floor(easeOut(progress) * target);
        el.textContent = value.toLocaleString('ru-RU');
        if (progress < 1) requestAnimationFrame(step);
        else el.textContent = target.toLocaleString('ru-RU');
      };
      requestAnimationFrame(step);
    };

    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animate(entry.target);
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0.4 });
      counters.forEach((c) => io.observe(c));
    } else {
      counters.forEach(animate);
    }
  }

  // 2. Reveal-анимация для секций при скролле
  const revealTargets = document.querySelectorAll('.section__title, .section__subtitle, .card, .quote, .contact');
  revealTargets.forEach((el) => el.classList.add('reveal'));

  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
          // лёгкий стагер через задержку
          setTimeout(() => entry.target.classList.add('is-visible'), i * 60);
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });
    revealTargets.forEach((el) => io.observe(el));
  } else {
    revealTargets.forEach((el) => el.classList.add('is-visible'));
  }

  // 3. Мягкий parallax для hero-орбов на десктопе
  const orbs = document.querySelectorAll('.orb');
  const isFinePointer = window.matchMedia('(pointer: fine)').matches;
  if (orbs.length && isFinePointer) {
    let ticking = false;
    window.addEventListener('mousemove', (e) => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const x = (e.clientX / window.innerWidth - 0.5) * 12;
        const y = (e.clientY / window.innerHeight - 0.5) * 12;
        orbs.forEach((orb, i) => {
          const k = (i + 1) * 0.6;
          orb.style.transform = `translate(${x * k}px, ${y * k}px)`;
        });
        ticking = false;
      });
    }, { passive: true });
  }
})();
