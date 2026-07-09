/*
 * Offline abstract fluid backgrounds for the two exhibition screens.
 *
 * Past   = warm, soft, memory-like amber/pink flow.
 * Future = cool, blue/purple, more sci-fi luminous flow.
 *
 * This uses only the browser canvas API, so it works without internet and
 * without extra dependencies on Raspberry Pi.
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
  let ratio = 1;
  let time = Math.random() * 1000;
  let blobs = [];
  let ribbons = [];

  function resize() {
    ratio = Math.min(window.devicePixelRatio || 1, 1.35);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    makeWorld();
  }

  function makeWorld() {
    const blobCount = Math.max(10, Math.floor((width * height) / 90000));
    const ribbonCount = isFuture ? 7 : 5;

    blobs = Array.from({ length: blobCount }, (_, index) => ({
      x: Math.random() * width,
      y: Math.random() * height,
      radius: Math.min(width, height) * (0.12 + Math.random() * 0.22),
      phase: Math.random() * Math.PI * 2,
      speed: 0.18 + Math.random() * 0.42,
      drift: 20 + Math.random() * 70,
      colorIndex: index % 4,
    }));

    ribbons = Array.from({ length: ribbonCount }, (_, index) => ({
      y: height * (0.18 + (index / Math.max(1, ribbonCount - 1)) * 0.66),
      phase: Math.random() * Math.PI * 2,
      amplitude: height * (0.035 + Math.random() * 0.06),
      speed: 0.16 + Math.random() * 0.28,
      thickness: isFuture ? 1.2 + Math.random() * 2.2 : 14 + Math.random() * 28,
    }));
  }

  function fillBase() {
    const gradient = ctx.createLinearGradient(0, 0, width, height);

    if (isFuture) {
      gradient.addColorStop(0, "#030718");
      gradient.addColorStop(0.45, "#08102d");
      gradient.addColorStop(1, "#12071e");
    } else {
      gradient.addColorStop(0, "#190907");
      gradient.addColorStop(0.48, "#24120b");
      gradient.addColorStop(1, "#0b0708");
    }

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
  }

  function blobColor(index, alpha) {
    const future = [
      `rgba(58, 130, 255, ${alpha})`,
      `rgba(132, 72, 255, ${alpha})`,
      `rgba(39, 229, 220, ${alpha})`,
      `rgba(202, 87, 255, ${alpha})`,
    ];
    const past = [
      `rgba(255, 159, 76, ${alpha})`,
      `rgba(255, 105, 98, ${alpha})`,
      `rgba(255, 211, 121, ${alpha})`,
      `rgba(207, 90, 143, ${alpha})`,
    ];
    return (isFuture ? future : past)[index % 4];
  }

  function drawBlobs() {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.filter = isFuture ? "blur(18px)" : "blur(34px)";

    blobs.forEach((blob) => {
      const pulse = Math.sin(time * blob.speed + blob.phase);
      const x = blob.x + Math.sin(time * blob.speed * 0.47 + blob.phase) * blob.drift;
      const y = blob.y + Math.cos(time * blob.speed * 0.38 + blob.phase) * blob.drift;
      const radius = blob.radius * (0.88 + pulse * 0.12);
      const glow = ctx.createRadialGradient(x, y, 0, x, y, radius);

      glow.addColorStop(0, blobColor(blob.colorIndex, isFuture ? 0.22 : 0.18));
      glow.addColorStop(0.45, blobColor(blob.colorIndex + 1, isFuture ? 0.07 : 0.08));
      glow.addColorStop(1, "rgba(0,0,0,0)");

      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fill();
    });

    ctx.restore();
  }

  function drawRibbon(ribbon, index) {
    const steps = 80;
    ctx.beginPath();

    for (let step = 0; step <= steps; step += 1) {
      const progress = step / steps;
      const x = progress * width;
      const waveA = Math.sin(progress * Math.PI * 2.2 + time * ribbon.speed + ribbon.phase);
      const waveB = Math.sin(progress * Math.PI * 5.1 - time * ribbon.speed * 0.72);
      const y = ribbon.y + waveA * ribbon.amplitude + waveB * ribbon.amplitude * 0.38;

      if (step === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    if (isFuture) {
      ctx.strokeStyle = index % 2
        ? "rgba(131, 83, 255, .26)"
        : "rgba(74, 207, 255, .24)";
      ctx.lineWidth = ribbon.thickness;
      ctx.shadowBlur = 18;
      ctx.shadowColor = index % 2 ? "rgba(151, 70, 255, .75)" : "rgba(64, 220, 255, .75)";
      ctx.stroke();
      ctx.shadowBlur = 0;
    } else {
      ctx.strokeStyle = index % 2
        ? "rgba(255, 181, 99, .075)"
        : "rgba(255, 115, 112, .06)";
      ctx.lineWidth = ribbon.thickness;
      ctx.lineCap = "round";
      ctx.stroke();
    }
  }

  function drawRibbons() {
    ctx.save();
    ctx.globalCompositeOperation = isFuture ? "screen" : "lighter";
    ctx.filter = isFuture ? "blur(0px)" : "blur(14px)";
    ribbons.forEach(drawRibbon);
    ctx.restore();
  }

  function drawFutureGrid() {
    if (!isFuture) return;

    ctx.save();
    ctx.globalAlpha = 0.16;
    ctx.strokeStyle = "rgba(83, 137, 255, .22)";
    ctx.lineWidth = 1;

    const spacing = 95;
    const offset = (time * 12) % spacing;
    for (let x = -spacing + offset; x < width + spacing; x += spacing) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x + width * 0.12, height);
      ctx.stroke();
    }
    for (let y = -spacing + offset; y < height + spacing; y += spacing) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y + height * 0.06);
      ctx.stroke();
    }

    ctx.restore();
  }

  function drawMemoryGrain() {
    if (isFuture) return;

    ctx.save();
    ctx.globalAlpha = 0.05;
    ctx.fillStyle = "#ffd79a";
    for (let i = 0; i < 70; i += 1) {
      const x = (Math.sin(i * 91.7 + time * 0.2) * 0.5 + 0.5) * width;
      const y = (Math.cos(i * 53.3 + time * 0.17) * 0.5 + 0.5) * height;
      ctx.fillRect(x, y, 1.2, 1.2);
    }
    ctx.restore();
  }

  function draw() {
    fillBase();
    drawFutureGrid();
    drawBlobs();
    drawRibbons();
    drawMemoryGrain();

    if (!reducedMotion) time += 0.0085;
    requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(draw);
})();
