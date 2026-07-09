/*
 * Lightweight moving canvas backgrounds for Raspberry Pi.
 *
 * This is not a heavy fluid simulation. It is a small, stable illusion:
 * slow moving translucent blobs + animated wave lines.
 *
 * Past   = soft floral memory: cream light, warm petals, gentle grain.
 * Future = cold geometric sci-fi system: lines, blocks, data points.
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
    [255, 214, 76],  // soft yellow
    [255, 126, 54],  // orange
    [255, 157, 142], // peach pink
    [116, 172, 166], // faded blue-green
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
    const count = isFuture ? 0 : 8;
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
      gradient.addColorStop(0, "#d8e4ee");
      gradient.addColorStop(0.48, "#9eb9cc");
      gradient.addColorStop(1, "#476274");
    } else {
      gradient.addColorStop(0, "#fff6dc");
      gradient.addColorStop(0.35, "#ffe7ba");
      gradient.addColorStop(0.72, "#f7c785");
      gradient.addColorStop(1, "#9ab9aa");
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
    gradient.addColorStop(0, rgba(blob.color, 0.22));
    gradient.addColorStop(0.45, rgba(blob.color, 0.12));
    gradient.addColorStop(1, rgba(blob.color, 0));

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    // A smaller moving core makes the motion easier to see on a screen.
    if (index % 2 === 0) {
      ctx.fillStyle = rgba(blob.color, 0.08);
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

    ctx.strokeStyle = row % 2
      ? "rgba(224, 173, 70, 0.28)"
      : "rgba(81, 112, 54, 0.22)";
    ctx.lineWidth = row % 2 ? 2 : 8;
    ctx.lineCap = "round";
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

  function drawFutureGeometry() {
    if (!isFuture) return;

    ctx.save();

    // Large dark, horizontal data blocks. They move slightly like scanned video.
    const blocks = [
      [0.10, 0.28, 0.28, 0.16],
      [0.56, 0.32, 0.34, 0.20],
      [0.18, 0.62, 0.50, 0.09],
      [0.68, 0.70, 0.22, 0.12],
    ];

    blocks.forEach(([x, y, w, h], index) => {
      const drift = Math.sin(time * 0.7 + index) * width * 0.012;
      const px = x * width + drift;
      const py = y * height + Math.cos(time * 0.5 + index) * height * 0.01;
      const bw = w * width;
      const bh = h * height;

      const gradient = ctx.createLinearGradient(px, py, px + bw, py);
      gradient.addColorStop(0, "rgba(3, 17, 26, 0)");
      gradient.addColorStop(0.25, "rgba(2, 18, 28, 0.48)");
      gradient.addColorStop(0.75, "rgba(2, 18, 28, 0.72)");
      gradient.addColorStop(1, "rgba(3, 17, 26, 0)");
      ctx.fillStyle = gradient;
      ctx.fillRect(px, py, bw, bh);

      ctx.fillStyle = "rgba(8, 28, 40, 0.28)";
      for (let stripe = 0; stripe < 8; stripe += 1) {
        ctx.fillRect(px, py + (stripe / 8) * bh, bw, 2);
      }
    });

    // Rectangular wireframe system.
    ctx.strokeStyle = "rgba(117, 31, 52, 0.48)";
    ctx.lineWidth = 1;
    const offset = (time * 18) % 80;
    for (let x = -80 + offset; x < width + 80; x += 120) {
      ctx.beginPath();
      ctx.moveTo(x, height * 0.12);
      ctx.lineTo(x + width * 0.08, height * 0.88);
      ctx.stroke();
    }

    ctx.strokeStyle = "rgba(30, 64, 82, 0.26)";
    for (let y = height * 0.16; y < height * 0.9; y += height * 0.13) {
      ctx.beginPath();
      ctx.moveTo(width * 0.08, y + Math.sin(time + y) * 8);
      ctx.lineTo(width * 0.92, y + Math.sin(time * 0.7 + y) * 8);
      ctx.stroke();
    }

    // Small data squares and ticks.
    ctx.fillStyle = "rgba(190, 20, 35, 0.86)";
    ctx.fillRect(width * 0.14, height * 0.30, 22, 22);
    ctx.fillRect(width * 0.80, height * 0.18, 8, 8);
    ctx.fillRect(width * 0.70, height * 0.72, 6, 6);

    ctx.fillStyle = "rgba(14, 38, 52, 0.68)";
    for (let i = 0; i < 38; i += 1) {
      const x = ((i * 97) % width) + Math.sin(time + i) * 10;
      const y = ((i * 53) % height) + Math.cos(time * 0.8 + i) * 8;
      ctx.fillRect(x, y, 2, 2);
    }

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

  function drawPetal(cx, cy, radiusX, radiusY, rotation, color, alpha) {
    const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(radiusX, radiusY));
    gradient.addColorStop(0, rgba(color, alpha));
    gradient.addColorStop(0.62, rgba(color, alpha * 0.45));
    gradient.addColorStop(1, rgba(color, 0));

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(rotation);
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.ellipse(0, 0, radiusX, radiusY, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawPastFlower(centerX, centerY, scale, phase, warmColor, leafColor) {
    const sway = Math.sin(time * 0.55 + phase);
    const x = centerX + sway * width * 0.018;
    const y = centerY + Math.cos(time * 0.4 + phase) * height * 0.012;

    // Soft stem and leaves, like out-of-focus film.
    ctx.save();
    ctx.strokeStyle = rgba(leafColor, 0.18);
    ctx.lineWidth = 14 * scale;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(x, y + 20 * scale);
    ctx.quadraticCurveTo(
      x - 34 * scale,
      y + 145 * scale,
      x - 10 * scale,
      height * 1.08
    );
    ctx.stroke();

    drawPetal(x - 48 * scale, y + 170 * scale, 70 * scale, 30 * scale, -0.45, leafColor, 0.13);
    drawPetal(x + 38 * scale, y + 205 * scale, 82 * scale, 34 * scale, 0.42, leafColor, 0.12);
    ctx.restore();

    // Flower head made of slow breathing translucent petals.
    for (let i = 0; i < 7; i += 1) {
      const angle = (i / 7) * Math.PI * 2 + sway * 0.12;
      const px = x + Math.cos(angle) * 34 * scale;
      const py = y + Math.sin(angle) * 24 * scale;
      drawPetal(
        px,
        py,
        (58 + Math.sin(time + i) * 5) * scale,
        (35 + Math.cos(time * 0.8 + i) * 4) * scale,
        angle + Math.PI * 0.2,
        warmColor,
        0.18
      );
    }

    drawPetal(x, y, 56 * scale, 42 * scale, sway * 0.1, [255, 220, 85], 0.20);
  }

  function drawPastFloralMemory() {
    if (isFuture) return;

    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    blobs.forEach(drawBlob);
    ctx.restore();

    ctx.save();
    ctx.globalCompositeOperation = "source-over";
    drawPastFlower(width * 0.33, height * 0.42, Math.min(width, height) / 720, 0.1, [255, 118, 72], [93, 150, 158]);
    drawPastFlower(width * 0.64, height * 0.36, Math.min(width, height) / 820, 1.8, [255, 183, 72], [96, 155, 132]);
    drawPastFlower(width * 0.50, height * 0.68, Math.min(width, height) / 900, 3.2, [255, 210, 88], [86, 139, 132]);
    ctx.restore();

    // Fine moving film grain, kept sparse for Pi performance.
    ctx.save();
    ctx.globalAlpha = 0.12;
    ctx.fillStyle = "#7d6a3d";
    for (let i = 0; i < 180; i += 1) {
      const x = (Math.sin(i * 17.13 + time * 0.7) * 0.5 + 0.5) * width;
      const y = (Math.cos(i * 23.71 + time * 0.5) * 0.5 + 0.5) * height;
      ctx.fillRect(x, y, 1, 1);
    }
    ctx.restore();
  }

  function draw() {
    drawBase();

    if (isFuture) {
      drawFutureGeometry();
      drawFutureScanLines();
      drawFuturePosterMarks();
    } else {
      drawPastFloralMemory();
    }

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
