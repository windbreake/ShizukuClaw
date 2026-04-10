import argparse
import importlib
from pathlib import Path
import random
import subprocess
import sys

pygame = None
DEFAULT_PYGAME_REQUIREMENT = "pygame==2.5.2"


def ensure_runtime_dependencies():
	global pygame
	try:
		pygame = importlib.import_module("pygame")
		return
	except ModuleNotFoundError:
		pass

	requirements_path = Path(__file__).with_name("requirements.txt")
	install_cmd = [
		sys.executable,
		"-m",
		"pip",
		"install",
		"--disable-pip-version-check",
	]

	if requirements_path.exists():
		print(f"[BOOTSTRAP] 未检测到 pygame，正在安装依赖: {requirements_path}")
		install_cmd.extend(["-r", str(requirements_path)])
	else:
		print(f"[BOOTSTRAP] 未检测到 pygame，正在安装默认依赖: {DEFAULT_PYGAME_REQUIREMENT}")
		install_cmd.append(DEFAULT_PYGAME_REQUIREMENT)

	result = subprocess.run(install_cmd, check=False)
	if result.returncode != 0:
		print("[BOOTSTRAP] 依赖安装失败，请手动执行 pip install -r requirements.txt")
		sys.exit(result.returncode)

	pygame = importlib.import_module("pygame")


ensure_runtime_dependencies()

WIDTH, HEIGHT = 600, 600
GRID_SIZE = 20
GRID_WIDTH = WIDTH // GRID_SIZE
GRID_HEIGHT = HEIGHT // GRID_SIZE
FPS = 10

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
GRAY = (40, 40, 40)


class Snake:
	def __init__(self):
		self.reset()

	def reset(self):
		self.positions = [(GRID_WIDTH // 2, GRID_HEIGHT // 2)]
		self.direction = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
		self.score = 0
		self.grow_pending = 2

	def get_head_position(self):
		return self.positions[0]

	def turn(self, point):
		if len(self.positions) > 1 and (point[0] * -1, point[1] * -1) == self.direction:
			return
		self.direction = point

	def move(self):
		head = self.get_head_position()
		x, y = self.direction
		new_x = (head[0] + x) % GRID_WIDTH
		new_y = (head[1] + y) % GRID_HEIGHT
		new_position = (new_x, new_y)

		if new_position in self.positions[1:]:
			return False

		self.positions.insert(0, new_position)
		if self.grow_pending > 0:
			self.grow_pending -= 1
		else:
			self.positions.pop()
		return True

	def grow(self):
		self.grow_pending += 1
		self.score += 10

	def draw(self, surface):
		for i, p in enumerate(self.positions):
			rect = pygame.Rect(p[0] * GRID_SIZE, p[1] * GRID_SIZE, GRID_SIZE, GRID_SIZE)
			if i == 0:
				pygame.draw.rect(surface, GREEN, rect)
				pygame.draw.rect(surface, WHITE, rect, 1)
			else:
				color_intensity = max(100, 255 - i * 10)
				body_color = (0, color_intensity, 0)
				pygame.draw.rect(surface, body_color, rect)
				pygame.draw.rect(surface, (0, 200, 0), rect, 1)


class Food:
	def __init__(self):
		self.position = (0, 0)
		self.randomize_position([])

	def randomize_position(self, snake_positions):
		while True:
			pos = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
			if pos not in snake_positions:
				self.position = pos
				return

	def draw(self, surface):
		rect = pygame.Rect(self.position[0] * GRID_SIZE, self.position[1] * GRID_SIZE, GRID_SIZE, GRID_SIZE)
		pygame.draw.rect(surface, RED, rect)
		pygame.draw.rect(surface, WHITE, rect, 1)
		center_x = self.position[0] * GRID_SIZE + GRID_SIZE // 2
		center_y = self.position[1] * GRID_SIZE + GRID_SIZE // 2
		pygame.draw.circle(surface, WHITE, (center_x, center_y), GRID_SIZE // 4)


def draw_grid(surface):
	for y in range(0, HEIGHT, GRID_SIZE):
		for x in range(0, WIDTH, GRID_SIZE):
			rect = pygame.Rect(x, y, GRID_SIZE, GRID_SIZE)
			pygame.draw.rect(surface, GRAY, rect, 1)


def draw_score(surface, score, high_score):
	font = pygame.font.SysFont('arial', 24)
	score_text = font.render(f'得分: {score}', True, WHITE)
	high_score_text = font.render(f'最高分: {high_score}', True, WHITE)
	surface.blit(score_text, (10, 10))
	surface.blit(high_score_text, (WIDTH - 150, 10))


def draw_game_over(surface, score):
	font_large = pygame.font.SysFont('arial', 48)
	font_small = pygame.font.SysFont('arial', 28)

	game_over_text = font_large.render('游戏结束!', True, RED)
	score_text = font_small.render(f'最终得分: {score}', True, WHITE)
	restart_text = font_small.render('按 R 重新开始', True, GREEN)
	quit_text = font_small.render('按 Q 退出游戏', True, WHITE)

	surface.blit(game_over_text, (WIDTH // 2 - game_over_text.get_width() // 2, HEIGHT // 2 - 90))
	surface.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, HEIGHT // 2 - 30))
	surface.blit(restart_text, (WIDTH // 2 - restart_text.get_width() // 2, HEIGHT // 2 + 15))
	surface.blit(quit_text, (WIDTH // 2 - quit_text.get_width() // 2, HEIGHT // 2 + 55))


def self_test():
	pygame.init()
	snake = Snake()
	food = Food()
	food.randomize_position(snake.positions)
	ok_move = snake.move()
	pygame.quit()
	print(f"[SELF-TEST] pygame_init=ok, snake_move={ok_move}, food={food.position}")


def main(max_frames=0):
	pygame.init()
	screen = pygame.display.set_mode((WIDTH, HEIGHT))
	pygame.display.set_caption('贪吃蛇游戏 - 方向键控制')
	clock = pygame.time.Clock()

	snake = Snake()
	food = Food()
	food.randomize_position(snake.positions)

	high_score = 0
	game_over = False
	frame_count = 0

	while True:
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				pygame.quit()
				return

			if event.type == pygame.KEYDOWN:
				if game_over:
					if event.key == pygame.K_r:
						snake.reset()
						food.randomize_position(snake.positions)
						game_over = False
					elif event.key == pygame.K_q:
						pygame.quit()
						return
				else:
					if event.key == pygame.K_UP:
						snake.turn((0, -1))
					elif event.key == pygame.K_DOWN:
						snake.turn((0, 1))
					elif event.key == pygame.K_LEFT:
						snake.turn((-1, 0))
					elif event.key == pygame.K_RIGHT:
						snake.turn((1, 0))

		if not game_over:
			if not snake.move():
				game_over = True
				high_score = max(high_score, snake.score)

			if snake.get_head_position() == food.position:
				snake.grow()
				food.randomize_position(snake.positions)

		screen.fill(BLACK)
		draw_grid(screen)
		snake.draw(screen)
		food.draw(screen)
		draw_score(screen, snake.score, high_score)

		if game_over:
			draw_game_over(screen, snake.score)

		pygame.display.update()
		clock.tick(FPS)
		frame_count += 1

		if max_frames > 0 and frame_count >= max_frames:
			pygame.quit()
			return


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Pygame 贪吃蛇")
	parser.add_argument("--self-test", action="store_true", help="运行无窗口自检")
	parser.add_argument("--max-frames", type=int, default=0, help="最多运行多少帧后退出（调试用）")
	args = parser.parse_args()

	if args.self_test:
		self_test()
		sys.exit(0)

	main(max_frames=args.max_frames)