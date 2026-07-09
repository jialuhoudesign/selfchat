/*
 * Lightweight moving canvas backgrounds for Raspberry Pi.
 *
 * This is not a heavy fluid simulation. It is a small, stable illusion:
 * slow moving translucent blobs + animated wave lines.
 *
 * Past   = warm green/yellow/orange gradient poster motion.
 * Future = cold blue-grey sci-fi poster motion with dark moving forms.
 */
(function () {
  "use strict";

  const canvas = document.getElementById("temporal-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d", { alpha: false });
  const selfType = document.body.dataset.selfType;
  const isFuture = selfType === "future";
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let width = 0;
  let height = 0;
  let time = Math.random() * 100;
  let blobs = [];

  const pastColors = [
    [244, 255, 116], // lemon
    [185, 245, 92],  // yellow green
    [255, 178, 78],  // orange
    [108, 218, 132], // natural green
  ];

  const futureColors = [
    [10, 35, 52],    // deep ink blue
    [18, 52, 73],    // cold shadow
    [37, 76, 96],    // blue grey
    [7, 18, 28],     // near black
  ];

  function resize() {
    // Keep the canvas at 1x resolution for Raspberry Pi performance.
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
    createBlobs();
  }

  function createBlobs() {
    const count = isFuture ? 9 : 8;
    const colors = isFuture ? futureColors : pastColors;

    blobs = Array.from({ length: count }, (_, index) => ({
      x: Math.random() * width,
      y: Math.random() * height,
      baseRadius: Math.min(width, height) * (0.2 + Math.random() * 0.2),
      driftX: 65 + Math.random() * 120,
      driftY: 45 + Math.random() * 95,
      speed: 0.28 + Math.random() * 0.34,
      phase: Math.random() * Math.PI * 2,
      color: colors[index % colors.length],
    }));
  }

  function rgba(color, alpha) {
    return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`;
  }

  function drawBase() {
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    if (isFuture) {
      gradient.addColorStop(0, "#dbe8f4");
      gradient.addColorStop(0.46, "#a9c5d9");
      gradient.addColorStop(1, "#5e7d95");
    } else {
      gradient.addColorStop(0, "#fff0a6");
      gradient.addColorStop(0.32, "#d7f36a");
      gradient.addColorStop(0.68, "#8ee47e");
      gradient.addColorStop(1, "#f2a64b");
    }
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
  }

  function drawBlob(blob, index) {
    const x = blob.x + Math.sin(time * blob.speed + blob.phase) * blob.driftX;
    const y = blob.y + Math.cos(time * blob.speed * 0.82 + blob.phase) * blob.driftY;
    const pulse = Math.sin(time * blob.speed * 1.4 + blob.phase) * 0.12 + 1;
    const radius = blob.baseRadius * pulse;

    const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, rgba(blob.color, isFuture ? 0.48 : 0.44));
    gradient.addColorStop(0.45, rgba(blob.color, isFuture ? 0.26 : 0.22));
    gradient.addColorStop(1, rgba(blob.color, 0));

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    // A smaller moving core makes the motion easier to see on a screen.
    if (index % 2 === 0) {
      ctx.fillStyle = rgba(blob.color, isFuture ? 0.2 : 0.18);
      ctx.beginPath();
      ctx.arc(x, y, radius * 0.22, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function drawWaveLine(row) {
    const steps = 70;
    const baseY = height * (0.2 + row * 0.16);
    const amplitude = height * (isFuture ? 0.035 : 0.075);
    const speed = isFuture ? 1.25 : 0.75;

    ctx.beginPath();
    for (let step = 0; step <= steps; step += 1) {
      const p = step / steps;
      const x = p * width;
      const y =
        baseY +
        Math.sin(p * Math.PI * 2.2 + time * speed + row) * amplitude +
        Math.sin(p * Math.PI * 5.0 - time * speed * 0.55) * amplitude * 0.35;

      if (step === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    if (isFuture) {
      ctx.strokeStyle = row % 2
        ? "rgba(170, 31, 62, 0.38)"
        : "rgba(45, 80, 100, 0.18)";
      ctx.lineWidth = row % 2 ? 1 : 7;
    } else {
      ctx.strokeStyle = row % 2
        ? "rgba(255, 135, 54, 0.42)"
        : "rgba(111, 180, 60, 0.25)";
      ctx.lineWidth = row % 2 ? 2 : 8;
      ctx.lineCap = "round";
    }
    ctx.stroke();
  }

  function drawFutureScanLines() {
    if (!isFuture) return;

    ctx.save();
    ctx.globalAlpha = 0.45;
    ctx.strokeStyle = "rgba(150, 20, 48, 0.42)";
    ctx.lineWidth = 1;

    const spacing = 170;
    const offset = (time * 24) % spacing;
    for (let x = -spacing; x < width + spacing; x += spacing * 1.4) {
      ctx.beginPath();
      ctx.moveTo(x + offset, height * 0.08);
      ctx.lineTo(x + offset + width * 0.28, height * 0.86);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawFuturePosterMarks() {
    if (!isFuture) return;

    ctx.save();
    ctx.strokeStyle = "rgba(150, 20, 48, 0.62)";
    ctx.fillStyle = "rgba(210, 15, 25, 0.85)";
    ctx.lineWidth = 1.2;

    const points = [
      [width * 0.18, height * 0.24],
      [width * 0.74, height * 0.18],
      [width * 0.36, height * 0.62],
      [width * 0.82, height * 0.70],
    ];

    points.forEach(([x, y], index) => {
      const ox = Math.sin(time * 0.8 + index) * 10;
      const oy = Math.cos(time * 0.6 + index) * 8;
      ctx.beginPath();
      ctx.moveTo(x + ox, y + oy);
      ctx.lineTo(width * (0.48 + index * 0.07), height * (0.42 + index * 0.08));
      ctx.stroke();
    });

    ctx.fillRect(width * 0.14, height * 0.30, 22, 22);
    ctx.beginPath();
    ctx.moveTo(width * 0.12, height * 0.10);
    ctx.lineTo(width * 0.78, height * 0.10);
    ctx.stroke();

    ctx.restore();
  }

  function drawPastPosterDetails() {
    if (isFuture) return;

    ctx.save();
    ctx.strokeStyle = "rgba(255, 150, 55, 0.46)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let step = 0; step <= 80; step += 1) {
      const p = step / 80;
      const x = width * (0.08 + p * 0.84);
      const y =
        height * 0.72 -
        Math.sin(p * Math.PI) * height * 0.18 +
        Math.sin(p * Math.PI * 4 + time * 0.9) * height * 0.018;
      if (step === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.setLineDash([2, 8]);
    ctx.strokeStyle = "rgba(117, 160, 56, 0.28)";
    ctx.lineWidth = 1;
    for (let row = 0; row < 3; row += 1) {
      ctx.beginPath();
      const y = height * (0.22 + row * 0.22);
      ctx.moveTo(width * 0.08, y + Math.sin(time + row) * 18);
      ctx.quadraticCurveTo(
        width * 0.52,
        y + height * 0.18,
        width * 0.94,
        y - height * 0.04
      );
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.restore();
  }

  function draw() {
    drawBase();

    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    blobs.forEach(drawBlob);
    for (let row = 0; row < 5; row += 1) drawWaveLine(row);
    ctx.restore();

    drawFutureScanLines();
    drawFuturePosterMarks();
    drawPastPosterDetails();

    if (!reducedMotion) {
      // This speed is intentionally visible but still calm.
      time += 0.018;
    }

    requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(draw);
})();
