// static/game.js - WORKING VERSION
let ws = null;
let playerId = null;
let state = null;
let canvas = document.getElementById('game');
let ctx = canvas.getContext('2d');
let cellW, cellH;
let keys = {};

// Calculate cell dimensions
function calculateCellDimensions() {
    if (!state) return;
    cellW = canvas.width / state.width;
    cellH = canvas.height / state.height;
}

// Connect to WebSocket server
function connect(id) {
    if (!id.trim()) {
        alert('Please enter a player name');
        return;
    }

    playerId = id.trim();

    // Use the correct WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const wsUrl = protocol + window.location.host + '/ws/' + encodeURIComponent(playerId);

    console.log('Connecting to:', wsUrl);
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('Connected to server');
        document.getElementById('joinBtn').textContent = 'Connected';
        document.getElementById('joinBtn').disabled = true;
        document.getElementById('playerId').disabled = true;
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            console.log('Received message type:', msg.type);

            if (msg.type === 'state') {
                state = msg.data;
                calculateCellDimensions();
                render();
                updatePlayerList();
            } else if (msg.type === 'init') {
                console.log('Initialized:', msg.data);
            } else if (msg.type === 'notification') {
                console.log('Notification:', msg.data.message);
            }
        } catch (e) {
            console.error('Error parsing message:', e, event.data);
        }
    };

    ws.onclose = () => {
        console.log('Disconnected from server');
        document.getElementById('joinBtn').textContent = 'Join Game';
        document.getElementById('joinBtn').disabled = false;
        document.getElementById('playerId').disabled = false;
        state = null;

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Update player list
        document.getElementById('players').innerHTML = '<p>Disconnected</p>';
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        alert('Connection error. Please try again.');
    };
}

// Render game state
function render() {
    if (!state) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw background
    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw grid (subtle)
    ctx.strokeStyle = '#222';
    ctx.lineWidth = 0.5;

    // Only draw grid if cells are large enough
    if (cellW > 10 && cellH > 10) {
        for (let x = 0; x <= state.width; x++) {
            ctx.beginPath();
            ctx.moveTo(x * cellW, 0);
            ctx.lineTo(x * cellW, canvas.height);
            ctx.stroke();
        }
        for (let y = 0; y <= state.height; y++) {
            ctx.beginPath();
            ctx.moveTo(0, y * cellH);
            ctx.lineTo(canvas.width, y * cellH);
            ctx.stroke();
        }
    }

    // Draw food
    ctx.fillStyle = '#ff4444';
    for (let food of state.food) {
        const [x, y] = food;
        ctx.beginPath();
        ctx.arc(
            x * cellW + cellW / 2,
            y * cellH + cellH / 2,
            Math.min(cellW, cellH) * 0.4,
            0,
            Math.PI * 2
        );
        ctx.fill();
    }

    // Draw players
    for (let pid in state.players) {
        const player = state.players[pid];
        if (!player.body || player.body.length === 0) continue;

        // Draw snake body
        ctx.fillStyle = player.color;
        for (let i = 0; i < player.body.length; i++) {
            const [x, y] = player.body[i];

            // Draw segment
            ctx.fillRect(
                x * cellW + 2,
                y * cellH + 2,
                cellW - 4,
                cellH - 4
            );

            // Add rounded corners effect
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.strokeRect(
                x * cellW + 2,
                y * cellH + 2,
                cellW - 4,
                cellH - 4
            );

            // Draw head (first segment)
            if (i === 0) {
                // Eyes
                ctx.fillStyle = '#fff';
                const eyeSize = Math.max(2, cellW * 0.2);

                let eye1X, eye1Y, eye2X, eye2Y;

                if (player.body.length > 1) {
                    const head = player.body[0];
                    const neck = player.body[1];

                    // Calculate direction
                    let dx = neck[0] - head[0];
                    let dy = neck[1] - head[1];

                    // Handle wrap-around
                    if (Math.abs(dx) > state.width / 2) {
                        dx = dx > 0 ? dx - state.width : dx + state.width;
                    }
                    if (Math.abs(dy) > state.height / 2) {
                        dy = dy > 0 ? dy - state.height : dy + state.height;
                    }

                    // Position eyes based on direction
                    if (Math.abs(dx) > Math.abs(dy)) {
                        // Moving horizontally
                        if (dx > 0) {
                            // Moving right
                            eye1X = x * cellW + cellW * 0.2;
                            eye2X = x * cellW + cellW * 0.2;
                            eye1Y = y * cellH + cellH * 0.3;
                            eye2Y = y * cellH + cellH * 0.7;
                        } else {
                            // Moving left
                            eye1X = x * cellW + cellW * 0.8;
                            eye2X = x * cellW + cellW * 0.8;
                            eye1Y = y * cellH + cellH * 0.3;
                            eye2Y = y * cellH + cellH * 0.7;
                        }
                    } else {
                        // Moving vertically
                        if (dy > 0) {
                            // Moving down
                            eye1X = x * cellW + cellW * 0.3;
                            eye2X = x * cellW + cellW * 0.7;
                            eye1Y = y * cellH + cellH * 0.2;
                            eye2Y = y * cellH + cellH * 0.2;
                        } else {
                            // Moving up
                            eye1X = x * cellW + cellW * 0.3;
                            eye2X = x * cellW + cellW * 0.7;
                            eye1Y = y * cellH + cellH * 0.8;
                            eye2Y = y * cellH + cellH * 0.8;
                        }
                    }
                } else {
                    // New snake, default eyes (looking right)
                    eye1X = x * cellW + cellW * 0.2;
                    eye1Y = y * cellH + cellH * 0.3;
                    eye2X = x * cellW + cellW * 0.2;
                    eye2Y = y * cellH + cellH * 0.7;
                }

                // Draw eyes
                ctx.beginPath();
                ctx.arc(eye1X, eye1Y, eyeSize, 0, Math.PI * 2);
                ctx.arc(eye2X, eye2Y, eyeSize, 0, Math.PI * 2);
                ctx.fill();

                // Pupils
                ctx.fillStyle = '#000';
                ctx.beginPath();
                ctx.arc(eye1X, eye1Y, eyeSize * 0.5, 0, Math.PI * 2);
                ctx.arc(eye2X, eye2Y, eyeSize * 0.5, 0, Math.PI * 2);
                ctx.fill();

                // Reset color for body
                ctx.fillStyle = player.color;
            }
        }

        // Draw player name above head
        if (player.body.length > 0) {
            const [headX, headY] = player.body[0];
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 12px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';

            let nameText = player.name;
            if (pid === playerId) nameText += ' (You)';
            if (!player.alive) nameText += ' 💀';

            ctx.fillText(
                nameText,
                headX * cellW + cellW / 2,
                headY * cellH - 5
            );
        }
    }

    // Draw scoreboard
    drawScoreboard();
}

// Draw scoreboard
function drawScoreboard() {
    if (!state || !state.players) return;

    const playersList = Object.entries(state.players)
        .sort((a, b) => b[1].score - a[1].score);

    // Draw background
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(10, 10, 200, 30 + playersList.length * 25);

    // Draw border
    ctx.strokeStyle = '#00a0ff';
    ctx.lineWidth = 2;
    ctx.strokeRect(10, 10, 200, 30 + playersList.length * 25);

    // Title
    ctx.fillStyle = '#00f0ff';
    ctx.font = 'bold 16px Arial';
    ctx.textAlign = 'left';
    ctx.fillText('SCOREBOARD', 20, 30);

    // Player scores
    ctx.font = '14px Arial';
    playersList.forEach(([pid, player], index) => {
        const y = 55 + index * 25;

        // Player color dot
        ctx.fillStyle = player.color;
        ctx.fillRect(20, y - 10, 10, 10);

        // Player name and score
        ctx.fillStyle = player.alive ? '#fff' : '#888';
        let playerText = `${player.name}: ${player.score}`;
        if (pid === playerId) playerText += ' (You)';

        ctx.fillText(playerText, 35, y);
    });
}

// Update player list in UI
function updatePlayerList() {
    if (!state || !state.players) return;

    const playersDiv = document.getElementById('players');
    const playersList = Object.entries(state.players)
        .sort((a, b) => b[1].score - a[1].score);

    let html = '<h4>Players Online</h4>';

    playersList.forEach(([pid, player]) => {
        const status = player.alive ? '🟢' : '🔴';
        const you = pid === playerId ? ' (You)' : '';
        html += `<p>${status} ${player.name}${you}: ${player.score} points</p>`;
    });

    playersDiv.innerHTML = html;
}

// Send input to server
function sendInput(dx, dy) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'input',
            dir: [dx, dy]
        }));
    }
}

// Send respawn request
function sendRespawn() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'respawn'
        }));
    }
}

// Keyboard input
document.addEventListener('keydown', (e) => {
    // Prevent default for game keys
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
        'w', 'a', 's', 'd', 'W', 'A', 'S', 'D', 'r', 'R'].includes(e.key)) {
        e.preventDefault();
    }

    const key = e.key.toLowerCase();

    // Movement keys
    if (key === 'arrowup' || key === 'w') {
        sendInput(0, -1);
    } else if (key === 'arrowdown' || key === 's') {
        sendInput(0, 1);
    } else if (key === 'arrowleft' || key === 'a') {
        sendInput(-1, 0);
    } else if (key === 'arrowright' || key === 'd') {
        sendInput(1, 0);
    } else if (key === 'r') {
        sendRespawn();
    }
});

// UI event listeners
document.getElementById('joinBtn').addEventListener('click', () => {
    const idInput = document.getElementById('playerId');
    let id = idInput.value.trim();

    if (!id) {
        id = `Player${Math.floor(Math.random() * 1000)}`;
        idInput.value = id;
    }

    connect(id);
});

document.getElementById('playerId').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        document.getElementById('joinBtn').click();
    }
});

// Auto-generate random name on focus if empty
document.getElementById('playerId').addEventListener('focus', (e) => {
    if (!e.target.value.trim()) {
        e.target.value = `Player${Math.floor(Math.random() * 1000)}`;
    }
});

// Handle window resize
window.addEventListener('resize', () => {
    calculateCellDimensions();
    if (state) render();
});

// Initialize
document.getElementById('players').innerHTML = '<p>Enter name and click Join</p>';

// Focus on input field
window.addEventListener('load', () => {
    document.getElementById('playerId').focus();
});