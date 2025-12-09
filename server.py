# server.py - COMPLETE WORKING VERSION
import asyncio
import json
import random
import time
import os
import logging
from typing import Dict, List, Set, Tuple
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Game configuration
WIDTH = 40
HEIGHT = 30
TICK = 0.12  # seconds per tick
START_LENGTH = 3
FOOD_COUNT = 5

# Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, player_id: str):
        await websocket.accept()
        async with self.lock:
            self.active_connections[player_id] = websocket
        logger.info(f"Player {player_id} connected")

    def disconnect(self, player_id: str):
        if player_id in self.active_connections:
            del self.active_connections[player_id]
        logger.info(f"Player {player_id} disconnected")

    async def send_to(self, player_id: str, message: dict):
        if player_id in self.active_connections:
            try:
                await self.active_connections[player_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending to {player_id}: {e}")
                self.disconnect(player_id)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return

        to_remove = []
        for player_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_json(message)
            except Exception:
                to_remove.append(player_id)

        for pid in to_remove:
            self.disconnect(pid)

manager = ConnectionManager()

# Game Utilities
def clamp_pos(x: int, y: int) -> Tuple[int, int]:
    """Wrap position around the board edges."""
    return (x % WIDTH, y % HEIGHT)

def find_empty_position(occupied: Set[Tuple[int, int]]) -> Tuple[int, int]:
    """Find a random empty position."""
    # Try random positions first (fast)
    for _ in range(100):
        x = random.randint(0, WIDTH - 1)
        y = random.randint(0, HEIGHT - 1)
        if (x, y) not in occupied:
            return (x, y)

    # Fallback: exhaustive search
    for x in range(WIDTH):
        for y in range(HEIGHT):
            if (x, y) not in occupied:
                return (x, y)

    # Last resort: random position
    return (random.randint(0, WIDTH - 1), random.randint(0, HEIGHT - 1))

# Game State
class GameState:
    def __init__(self):
        self.players: Dict[str, dict] = {}
        self.food: List[Tuple[int, int]] = []
        self.occupied: Set[Tuple[int, int]] = set()
        self.tick = 0
        self.death_reasons: Dict[str, str] = {}
        logger.info(f"Game initialized: {WIDTH}x{HEIGHT}")

    def spawn_food(self):
        """Spawn food avoiding snakes."""
        while len(self.food) < FOOD_COUNT:
            # Get all occupied positions
            all_occupied = self.occupied.copy()

            pos = find_empty_position(all_occupied)
            if pos not in all_occupied:
                self.food.append(pos)
                self.occupied.add(pos)
                logger.debug(f"Spawned food at {pos}")

    def add_player(self, player_id: str, display_name: str = None):
        """Add a new player with safe spawning."""
        if display_name is None:
            display_name = player_id

        # Get all occupied positions
        all_occupied = self.occupied.copy()

        # Try to find safe spawn location
        max_attempts = 100
        for attempt in range(max_attempts):
            # Pick random position with margin
            spawn_x = random.randint(START_LENGTH + 2, WIDTH - START_LENGTH - 3)
            spawn_y = random.randint(2, HEIGHT - 3)

            # Create snake body (horizontal, going right)
            body = []
            valid_spawn = True

            for i in range(START_LENGTH):
                segment_x = (spawn_x - i) % WIDTH
                segment_y = spawn_y
                pos = (segment_x, segment_y)

                if pos in all_occupied:
                    valid_spawn = False
                    break

                body.append(pos)

            if valid_spawn:
                # Found valid spawn
                for segment in body:
                    self.occupied.add(segment)

                # Generate random color
                hue = random.randint(0, 360)
                color = f"hsl({hue}, 100%, 50%)"

                self.players[player_id] = {
                    "id": player_id,
                    "display_name": display_name,
                    "body": body,
                    "dir": (1, 0),  # Start moving right
                    "pending_dir": (1, 0),
                    "alive": True,
                    "score": 0,
                    "food_collected": 0,
                    "color": color,
                    "last_input_time": time.time(),
                    "spawn_tick": self.tick
                }

                logger.info(f"Player {player_id} spawned at {spawn_x},{spawn_y}")
                return

        # Fallback: spawn anywhere
        logger.warning(f"Fallback spawn for {player_id}")
        spawn_x = random.randint(0, WIDTH - 1)
        spawn_y = random.randint(0, HEIGHT - 1)
        body = [(spawn_x, spawn_y)]
        for i in range(1, START_LENGTH):
            body.append(((spawn_x - i) % WIDTH, spawn_y))

        for segment in body:
            self.occupied.add(segment)

        hue = random.randint(0, 360)
        color = f"hsl({hue}, 100%, 50%)"

        self.players[player_id] = {
            "id": player_id,
            "display_name": display_name,
            "body": body,
            "dir": (1, 0),
            "pending_dir": (1, 0),
            "alive": True,
            "score": 0,
            "food_collected": 0,
            "color": color,
            "last_input_time": time.time(),
            "spawn_tick": self.tick
        }

    def remove_player(self, player_id: str):
        """Remove a player from the game."""
        if player_id not in self.players:
            return

        player = self.players[player_id]

        # Free occupied positions
        for segment in player["body"]:
            if segment in self.occupied:
                self.occupied.remove(segment)

        # Remove from players
        del self.players[player_id]

        if player_id in self.death_reasons:
            del self.death_reasons[player_id]

        logger.info(f"Player {player_id} removed")

    def step(self):
        """Advance the game by one tick."""
        # Calculate new heads
        new_heads: Dict[str, Tuple[int, int]] = {}
        snakes_to_grow: List[str] = []

        # First pass: calculate new heads and update directions
        for player_id, player in self.players.items():
            if not player["alive"]:
                continue

            # Update direction if not reversing
            pending_dx, pending_dy = player["pending_dir"]
            current_dx, current_dy = player["dir"]

            # Prevent 180-degree turns
            if (pending_dx, pending_dy) != (-current_dx, -current_dy):
                player["dir"] = (pending_dx, pending_dy)

            # Calculate new head position
            head_x, head_y = player["body"][0]
            dx, dy = player["dir"]
            new_head = clamp_pos(head_x + dx, head_y + dy)
            new_heads[player_id] = new_head

        # Create temporary occupied set (current positions)
        temp_occupied = set()
        for player in self.players.values():
            if player["alive"]:
                for segment in player["body"]:
                    temp_occupied.add(segment)
        for food_pos in self.food:
            temp_occupied.add(food_pos)

        # Check collisions and food collection
        dead_snakes: Set[str] = set()

        for player_id, player in self.players.items():
            if not player["alive"]:
                continue

            new_head = new_heads[player_id]

            # Check if new head is on food
            if new_head in self.food:
                snakes_to_grow.append(player_id)
                self.food.remove(new_head)
                player["food_collected"] += 1
                # Food was in temp_occupied, remove it
                if new_head in temp_occupied:
                    temp_occupied.remove(new_head)

            # Check head-to-head collisions
            for other_id, other_new_head in new_heads.items():
                if other_id == player_id:
                    continue
                if new_head == other_new_head:
                    # Both snakes die in head-to-head collision
                    dead_snakes.add(player_id)
                    dead_snakes.add(other_id)
                    self.death_reasons[player_id] = "head_collision"
                    self.death_reasons[other_id] = "head_collision"

            # Check collision with other occupied positions
            if player_id not in dead_snakes:
                # Determine which positions to exclude from collision check
                excluded_positions = set()
                # Exclude current tail if snake is not growing
                if player_id not in snakes_to_grow and player["body"]:
                    excluded_positions.add(player["body"][-1])

                # Check collision
                for pos in temp_occupied:
                    if pos == new_head and pos not in excluded_positions:
                        dead_snakes.add(player_id)
                        self.death_reasons[player_id] = "self" if pos in player["body"] else "other"
                        break

        # Move all snakes
        self.occupied.clear()

        # Add food to occupied
        for food_pos in self.food:
            self.occupied.add(food_pos)

        for player_id, player in self.players.items():
            if not player["alive"]:
                continue

            if player_id in dead_snakes:
                player["alive"] = False
                logger.info(f"Player {player_id} died by {self.death_reasons.get(player_id, 'unknown')}")
                # Don't move dead snakes
                continue

            # Add new head
            new_head = new_heads[player_id]
            player["body"].insert(0, new_head)

            # Remove tail if not growing
            if player_id in snakes_to_grow:
                player["score"] += 1
                logger.debug(f"Player {player_id} grew, score: {player['score']}")
            else:
                if len(player["body"]) > START_LENGTH:
                    player["body"].pop()

            # Add new positions to occupied set
            for segment in player["body"]:
                self.occupied.add(segment)

        # Clean up dead snakes
        for player_id in dead_snakes:
            if player_id in self.players:
                player = self.players[player_id]
                player["alive"] = False
                # Remove body from occupied set
                for segment in player["body"]:
                    if segment in self.occupied:
                        self.occupied.remove(segment)

        # Respawn food
        self.spawn_food()
        self.tick += 1

        # Log game state every 100 ticks
        if self.tick % 100 == 0:
            alive_players = sum(1 for p in self.players.values() if p["alive"])
            logger.info(f"Tick {self.tick}: {alive_players} players alive, {len(self.food)} food")

    def snapshot(self):
        """Create a snapshot for clients."""
        return {
            "tick": self.tick,
            "players": {
                pid: {
                    "id": pid,
                    "body": player["body"],
                    "alive": player["alive"],
                    "color": player["color"],
                    "score": player["score"],
                    "name": player["display_name"],
                    "food_collected": player.get("food_collected", 0),
                    "snake_length": len(player["body"])
                }
                for pid, player in self.players.items()
            },
            "food": self.food,
            "width": WIDTH,
            "height": HEIGHT,
        }

game = GameState()

# Background tasks
async def game_loop():
    """Main game loop running in the background."""
    logger.info("Game loop started")
    loop_count = 0

    while True:
        try:
            game.step()

            # Broadcast game state to all connected players
            if manager.active_connections:
                snapshot = game.snapshot()
                await manager.broadcast({
                    "type": "state",
                    "data": snapshot
                })

                loop_count += 1
                if loop_count % 50 == 0:
                    logger.info(f"Broadcasted to {len(manager.active_connections)} players")

        except Exception as e:
            logger.error(f"Error in game loop: {e}", exc_info=True)

        await asyncio.sleep(TICK)

# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Snake Game Server")

    # Spawn initial food
    game.spawn_food()

    # Start game loop
    game_task = asyncio.create_task(game_loop())

    logger.info(f"Server started on port {SERVER_PORT}")

    yield

    # Shutdown
    logger.info("Shutting down server...")
    game_task.cancel()
    try:
        await game_task
    except asyncio.CancelledError:
        pass
    logger.info("Server shutdown complete")

# Create FastAPI app
SERVER_PORT = int(os.getenv('SERVER_PORT', 10001))

app = FastAPI(
    title="Multiplayer Snake Game",
    version="1.0.0",
    lifespan=lifespan
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routes
@app.get("/")
async def get_index():
    """Serve the main HTML page."""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(html)
    except FileNotFoundError:
        return HTMLResponse("<h1>Snake Game - Place index.html in static/ folder</h1>", status_code=404)

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "game_tick": game.tick,
        "players_online": len(game.players),
        "active_connections": len(manager.active_connections)
    })

@app.get("/api/info")
async def get_server_info():
    """Get server information."""
    return JSONResponse({
        "name": "Multiplayer Snake Game",
        "version": "1.0.0",
        "game_config": {
            "width": WIDTH,
            "height": HEIGHT,
            "tick_interval": TICK,
            "start_length": START_LENGTH,
            "food_count": FOOD_COUNT
        }
    })

# WebSocket endpoint
@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    """Handle WebSocket connections for players."""
    # Accept connection
    await manager.connect(websocket, player_id)

    # Optional: get display name from query parameter
    from fastapi import Query
    display_name = player_id  # Default to player_id

    try:
        # Add player to game
        game.add_player(player_id, display_name)

        logger.info(f"Player {player_id} added to game")

        # Send initial game state
        await manager.send_to(player_id, {
            "type": "init",
            "data": {
                "player_id": player_id,
                "display_name": display_name,
                "game_config": {
                    "width": WIDTH,
                    "height": HEIGHT
                }
            }
        })

        # Send current game state
        await manager.send_to(player_id, {
            "type": "state",
            "data": game.snapshot()
        })

        # Handle incoming messages
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()

                # Parse JSON
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    continue

                # Handle different message types
                msg_type = message.get("type")

                if msg_type == "input":
                    # Handle movement input
                    direction = message.get("dir")
                    if (isinstance(direction, list) and len(direction) == 2 and
                            player_id in game.players and game.players[player_id]["alive"]):
                        dx, dy = direction
                        # Validate direction
                        if dx in (-1, 0, 1) and dy in (-1, 0, 1) and (dx != 0 or dy != 0):
                            game.players[player_id]["pending_dir"] = (dx, dy)
                            game.players[player_id]["last_input_time"] = time.time()
                            logger.debug(f"Player {player_id} set direction to ({dx}, {dy})")

                elif msg_type == "respawn":
                    # Handle respawn request
                    if player_id in game.players:
                        if not game.players[player_id]["alive"]:
                            logger.info(f"Player {player_id} respawning")
                            game.remove_player(player_id)
                            game.add_player(player_id, display_name)

                elif msg_type == "rename":
                    # Handle name change
                    new_name = message.get("name")
                    if (player_id in game.players and new_name and
                            isinstance(new_name, str) and len(new_name.strip()) > 0):
                        new_name = new_name.strip()[:20]
                        game.players[player_id]["display_name"] = new_name
                        await manager.send_to(player_id, {
                            "type": "notification",
                            "data": {"message": f"Name changed to {new_name}"}
                        })

            except Exception as e:
                logger.error(f"Error processing message from {player_id}: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"Player {player_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for {player_id}: {e}")
    finally:
        # Clean up
        game.remove_player(player_id)
        manager.disconnect(player_id)

