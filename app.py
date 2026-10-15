import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Rail Runner 3D", page_icon="🏃", layout="centered")

st.title("🏃 Rail Runner 3D (Có Âm Thanh)")
st.caption("Game Endless Runner 3D có tích hợp nhạc nền và hiệu ứng âm thanh.")

game_html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {
      margin: 0;
      background: #111;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-family: Arial, sans-serif;
      user-select: none;
    }
    #gameCanvas {
      background: #87CEEB;
      border: 3px solid #333;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .guide {
      color: #ddd;
      font-size: 14px;
      margin-top: 8px;
      text-align: center;
    }
  </style>
</head>
<body>
  <canvas id="gameCanvas" width="400" height="580"></canvas>
  <div class="guide">
    <b>Điều khiển:</b> ⬅️ / ➡️ để chuyển làn | ⬆️ / Space để nhảy (Nhấn phím bất kỳ để bật tiếng)
  </div>

  <script>
    const canvas = document.getElementById("gameCanvas");
    const ctx = canvas.getContext("2d");

    // ==========================================
    // HỆ THỐNG ÂM THANH (WEB AUDIO API)
    // ==========================================
    let audioCtx = null;
    let bgmInterval = null;
    let bgmStep = 0;

    // Chuỗi nốt nhạc nền 8-bit sôi động
    const bgmNotes = [
      261.63, 293.66, 329.63, 392.00,
      329.63, 293.66, 261.63, 196.00,
      220.00, 261.63, 329.63, 392.00,
      440.00, 392.00, 329.63, 261.63
    ];

    function initAudio() {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        startBGM();
      } else if (audioCtx.state === "suspended") {
        audioCtx.resume();
      }
    }

    // Hiệu ứng âm thanh khi Nhảy
    function playJumpSound() {
      if (!audioCtx) return;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(160, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(450, audioCtx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.linearRampToValueAtTime(0.01, audioCtx.currentTime + 0.15);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.15);
    }

    // Hiệu ứng âm thanh khi Ăn Coin
    function playCoinSound() {
      if (!audioCtx) return;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(987.77, audioCtx.currentTime); // Note B5
      osc.frequency.setValueAtTime(1318.51, audioCtx.currentTime + 0.08); // Note E6
      gain.gain.setValueAtTime(0.25, audioCtx.currentTime);
      gain.gain.linearRampToValueAtTime(0.01, audioCtx.currentTime + 0.25);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.25);
    }

    // Hiệu ứng âm thanh Game Over (Va chạm)
    function playCrashSound() {
      if (!audioCtx) return;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(180, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(40, audioCtx.currentTime + 0.4);
      gain.gain.setValueAtTime(0.4, audioCtx.currentTime);
      gain.gain.linearRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.4);
    }

    // Vòng lặp phát nhạc nền (BGM)
    function startBGM() {
      if (bgmInterval) clearInterval(bgmInterval);
      bgmInterval = setInterval(() => {
        if (!player.alive || !audioCtx) return;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "square"; // Kiểu sóng vuông cổ điển
        const freq = bgmNotes[bgmStep % bgmNotes.length];
        bgmStep++;

        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.03, audioCtx.currentTime); // Âm lượng nền vừa phải
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.12);

        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.12);
      }, 150); // Nhịp điệu 150ms / nốt
    }

    function stopBGM() {
      if (bgmInterval) {
        clearInterval(bgmInterval);
        bgmInterval = null;
      }
    }

    // ==========================================
    // LOGIC GAME CHÍNH
    // ==========================================
    const VP_X = 200;
    const HORIZON = 150;
    const LANES_BASE_X = [80, 200, 320];

    let player = {
      lane: 1,
      targetX: 200,
      currentX: 200,
      yOffset: 0,
      jumpVelocity: 0,
      isJumping: false,
      score: 0,
      coins: 0,
      alive: true
    };

    let speed = 4.2;
    let obstacles = [];
    let coins = [];
    let spawnTimer = 0;

    function project(lane, z) {
      const bottomX = LANES_BASE_X[lane];
      const screenX = VP_X + (bottomX - VP_X) * z;
      const screenY = HORIZON + (canvas.height - HORIZON) * z;
      return { x: screenX, y: screenY, scale: z };
    }

    function resetGame() {
      player.lane = 1;
      player.currentX = 200;
      player.targetX = 200;
      player.yOffset = 0;
      player.jumpVelocity = 0;
      player.isJumping = false;
      player.score = 0;
      player.coins = 0;
      player.alive = true;
      speed = 4.2;
      obstacles = [];
      coins = [];
      spawnTimer = 0;
      bgmStep = 0;
      startBGM();
    }

    window.addEventListener("keydown", (e) => {
      // Khởi tạo Audio khi người chơi thao tác lần đầu
      initAudio();

      if (!player.alive) {
        if (e.code === "Space" || e.code === "Enter") {
          resetGame();
        }
        return;
      }

      if (e.code === "ArrowLeft" || e.code === "KeyA") {
        if (player.lane > 0) player.lane--;
      } else if (e.code === "ArrowRight" || e.code === "KeyD") {
        if (player.lane < 2) player.lane++;
      } else if ((e.code === "ArrowUp" || e.code === "Space" || e.code === "KeyW") && !player.isJumping) {
        player.isJumping = true;
        player.jumpVelocity = 14;
        playJumpSound(); // Phát âm thanh nhảy
      }
    });

    function update() {
      if (!player.alive) return;

      player.score += 1;
      speed += 0.0005;

      player.targetX = LANES_BASE_X[player.lane];
      player.currentX += (player.targetX - player.currentX) * 0.25;

      if (player.isJumping) {
        player.yOffset += player.jumpVelocity;
        player.jumpVelocity -= 0.85;
        if (player.yOffset <= 0) {
          player.yOffset = 0;
          player.isJumping = false;
        }
      }

      spawnTimer++;
      if (spawnTimer > Math.max(35, 75 - Math.floor(player.score / 150))) {
        spawnTimer = 0;
        const freeLane = Math.floor(Math.random() * 3);
        const types = ["barrier", "train", "coin"];
        const chosenType = types[Math.floor(Math.random() * types.length)];

        if (chosenType === "coin") {
          coins.push({ lane: freeLane, z: 0.05 });
        } else {
          obstacles.push({ lane: freeLane, type: chosenType, z: 0.05 });
        }
      }

      // Xử lý chướng ngại vật
      for (let i = obstacles.length - 1; i >= 0; i--) {
        let obs = obstacles[i];
        obs.z += speed * 0.0022;

        if (obs.z >= 0.82 && obs.z <= 0.96 && obs.lane === player.lane) {
          let hit = false;
          if (obs.type === "barrier" && player.yOffset < 28) hit = true;
          if (obs.type === "train") hit = true;

          if (hit) {
            player.alive = false;
            stopBGM();
            playCrashSound(); // Phát âm thanh va chạm
          }
        }
        if (obs.z > 1.1) obstacles.splice(i, 1);
      }

      // Xử lý ăn Coin
      for (let i = coins.length - 1; i >= 0; i--) {
        let coin = coins[i];
        coin.z += speed * 0.0022;

        if (coin.z >= 0.80 && coin.z <= 0.98 && coin.lane === player.lane) {
          player.coins += 1;
          playCoinSound(); // Phát âm thanh nhặt vàng
          coins.splice(i, 1);
          continue;
        }
        if (coin.z > 1.1) coins.splice(i, 1);
      }
    }

    function drawTrack() {
      ctx.fillStyle = "#64b5f6";
      ctx.fillRect(0, 0, canvas.width, HORIZON);
      ctx.fillStyle = "#4caf50";
      ctx.fillRect(0, HORIZON, canvas.width, canvas.height - HORIZON);

      ctx.fillStyle = "#757575";
      ctx.beginPath();
      ctx.moveTo(VP_X - 15, HORIZON);
      ctx.lineTo(VP_X + 15, HORIZON);
      ctx.lineTo(canvas.width - 20, canvas.height);
      ctx.lineTo(20, canvas.height);
      ctx.closePath();
      ctx.fill();

      ctx.strokeStyle = "#eee";
      ctx.lineWidth = 2;
      for (let i = 0; i <= 3; i++) {
        let bottomX = 35 + i * 110;
        ctx.beginPath();
        ctx.moveTo(VP_X, HORIZON);
        ctx.lineTo(bottomX, canvas.height);
        ctx.stroke();
      }
    }

    function drawObstacles() {
      const allObjects = [
        ...obstacles.map(o => ({ ...o, kind: "obstacle" })),
        ...coins.map(c => ({ ...c, kind: "coin" }))
      ].sort((a, b) => a.z - b.z);

      for (let item of allObjects) {
        let p = project(item.lane, item.z);

        if (item.kind === "coin") {
          let radius = 14 * p.scale;
          ctx.fillStyle = "#FFD700";
          ctx.beginPath();
          ctx.arc(p.x, p.y - 15 * p.scale, Math.max(3, radius), 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = "#DAA520";
          ctx.lineWidth = 2;
          ctx.stroke();
        } else if (item.type === "barrier") {
          let w = 80 * p.scale;
          let h = 30 * p.scale;
          ctx.fillStyle = "#d32f2f";
          ctx.fillRect(p.x - w / 2, p.y - h, w, h);
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(p.x - w / 4, p.y - h, w / 8, h);
          ctx.fillRect(p.x + w / 8, p.y - h, w / 8, h);
        } else if (item.type === "train") {
          let w = 85 * p.scale;
          let h = 90 * p.scale;
          ctx.fillStyle = "#1976d2";
          ctx.fillRect(p.x - w / 2, p.y - h, w, h);
          ctx.fillStyle = "#90caf9";
          ctx.fillRect(p.x - w * 0.35, p.y - h + 8 * p.scale, w * 0.7, h * 0.3);
          ctx.fillStyle = "#fff59d";
          ctx.beginPath();
          ctx.arc(p.x, p.y - h * 0.2, 5 * p.scale, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }

    function drawPlayer() {
      const p = project(1, 0.9);
      const drawX = player.currentX;
      const drawY = p.y - player.yOffset;

      ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
      ctx.beginPath();
      ctx.ellipse(drawX, p.y, 25, 8, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#00e676";
      ctx.beginPath();
      ctx.roundRect(drawX - 28, drawY - 4, 56, 8, [4]);
      ctx.fill();

      ctx.fillStyle = "#ff5722";
      ctx.fillRect(drawX - 14, drawY - 45, 28, 40);

      ctx.fillStyle = "#ffe0b2";
      ctx.beginPath();
      ctx.arc(drawX, drawY - 55, 12, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#3f51b5";
      ctx.fillRect(drawX - 12, drawY - 67, 24, 7);
      ctx.fillRect(drawX - 4, drawY - 64, 18, 4);
    }

    function drawHUD() {
      ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
      ctx.fillRect(10, 10, 170, 65);
      ctx.fillStyle = "#fff";
      ctx.font = "bold 15px Arial";
      ctx.fillText(`Điểm số: ${player.score}`, 20, 34);
      ctx.fillStyle = "#FFD700";
      ctx.fillText(`Vàng: 🪙 ${player.coins}`, 20, 60);

      if (!player.alive) {
        ctx.fillStyle = "rgba(0, 0, 0, 0.75)";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.fillStyle = "#f44336";
        ctx.font = "bold 34px Arial";
        ctx.textAlign = "center";
        ctx.fillText("GAME OVER", canvas.width / 2, canvas.height / 2 - 30);

        ctx.fillStyle = "#fff";
        ctx.font = "16px Arial";
        ctx.fillText(`Tổng điểm: ${player.score} | Vàng: ${player.coins}`, canvas.width / 2, canvas.height / 2 + 10);
        ctx.fillText("Nhấn SPACE hoặc ENTER để chơi lại", canvas.width / 2, canvas.height / 2 + 45);
        ctx.textAlign = "left";
      }
    }

    function gameLoop() {
      update();
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      drawTrack();
      drawObstacles();
      drawPlayer();
      drawHUD();
      requestAnimationFrame(gameLoop);
    }

    requestAnimationFrame(gameLoop);
  </script>
</body>
</html>
"""

components.html(game_html, height=660)
