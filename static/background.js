/*
 * Distinct offline canvas worlds for the two screens:
 * future = soft yellow/green circles, past = blue/purple polygons.
 */
(function () {
  "use strict";

  const canvas = document.getElementById("temporal-canvas");
  if (!canvas) return; // The control page does not have a canvas.

  const context = canvas.getContext("2d");
  const selfType = document.body.dataset.selfType;
  const isFuture = selfType === "future";
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let width = 0;
  let height = 0;
  let time = Math.random() * 100;
  let shapes = [];

  function resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    makeShapes();
  }

  function makeShapes() {
    const count = Math.max(16, Math.floor((width * height) / 42000));
    shapes = Array.from({ length: count }, (_, index) => ({
      x: Math.random() * width,
      y: Math.random() * height,
      size: 18 + Math.random() * Math.min(width, height) * 0.14,
      speed: 0.08 + Math.random() * 0.2,
      phase: Math.random() * Math.PI * 2,
      sides: 3 + (index % 5),
      rotation: Math.random() * Math.PI,
      alpha: 0.05 + Math.random() * 0.15,
    }));
  }

  function paintBackground() {
    const gradient = context.createLinearGradient(0, 0, width, height);
    if (isFuture) {
      gradient.addColorStop(0, "#071008");
      gradient.addColorStop(0.5, "#10180b");
      gradient.addColorStop(1, "#06100b");
    } else {
      gradient.addColorStop(0, "#060817");
      gradient.addColorStop(0.52, "#11102b");
      gradient.addColorStop(1, "#08051b");
    }
    context.fillStyle = gradient;
    context.fillRect(0, 0, width, height);
  }

  function drawCircle(shape, x, y) {
    const glow = context.createRadialGradient(x, y, 0, x, y, shape.size);
    glow.addColorStop(0, `rgba(226, 239, 77, ${shape.alpha * 1.7})`);
    glow.addColorStop(0.38, `rgba(145, 207, 73, ${shape.alpha})`);
    glow.addColorStop(1, "rgba(62, 129, 53, 0)");
    context.beginPath();
    context.arc(x, y, shape.size, 0, Math.PI * 2);
    context.fillStyle = glow;
    context.fill();

    context.beginPath();
    context.arc(x, y, shape.size * .55, 0, Math.PI * 2);
    context.strokeStyle = `rgba(224, 242, 106, ${shape.alpha * .55})`;
    context.lineWidth = 1;
    context.stroke();
  }

  function drawPolygon(shape, x, y) {
    context.save();
    context.translate(x, y);
    context.rotate(shape.rotation + time * shape.speed * .002);
    context.beginPath();
    for (let side = 0; side < shape.sides; side += 1) {
      const angle = (side / shape.sides) * Math.PI * 2;
      const radius = shape.size * (side % 2 ? .78 : 1);
      const px = Math.cos(angle) * radius;
      const py = Math.sin(angle) * radius;
      if (side === 0) context.moveTo(px, py);
      else context.lineTo(px, py);
    }
    context.closePath();
    context.fillStyle = `rgba(77, 85, 195, ${shape.alpha * .45})`;
    context.strokeStyle = `rgba(149, 120, 235, ${shape.alpha * 1.3})`;
    context.lineWidth = 1;
    context.fill();
    context.stroke();
    context.restore();
  }

  function connectShapes() {
    context.beginPath();
    for (let index = 0; index < shapes.length - 1; index += 1) {
      const first = shapes[index];
      const second = shapes[index + 1];
      context.moveTo(first.x, first.y);
      context.lineTo(second.x, second.y);
    }
    context.strokeStyle = isFuture ? "rgba(174, 218, 79, .035)" : "rgba(115, 121, 225, .06)";
    context.lineWidth = 1;
    context.stroke();
  }

  function draw() {
    paintBackground();
    connectShapes();

    shapes.forEach((shape) => {
      const x = shape.x + Math.sin(time * shape.speed * .025 + shape.phase) * 35;
      const y = shape.y + Math.cos(time * shape.speed * .02 + shape.phase) * 28;
      if (isFuture) drawCircle(shape, x, y);
      else drawPolygon(shape, x, y);
    });

    if (!reducedMotion) time += 0.55;
    requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(draw);
})();
