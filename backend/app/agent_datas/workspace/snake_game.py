import random
import sys

import pygame


WIDTH, HEIGHT = 600, 600
CELL = 20
GRID_W, GRID_H = WIDTH // CELL, HEIGHT // CELL
FPS = 10

BLACK = (18, 18, 18)
WHITE = (240, 240, 240)
GREEN = (46, 204, 113)
BLUE = (52, 152, 219)
RED = (231, 76, 60)
GRAY = (45, 45, 45)

UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)


class Snake:
	def __init__(self):
		self.reset()

	def reset(self):
		self.direction = RIGHT
		self.body = [(GRID_W // 2, GRID_H // 2)]
		self.target_len = 3
		self.score = 0

	def head(self):
		return self.body[0]

	def turn(self, direction):
		if (direction[0] * -1, direction[1] * -1) != self.direction:
			self.direction = direction

	def move(self):
		x, y = self.head()
		nx = (x + self.direction[0]) % GRID_W
		ny = (y + self.direction[1]) % GRID_H
		new_head = (nx, ny)

		if new_head in self.body[1:]:
			return False

		self.body.insert(0, new_head)
		if len(self.body) > self.target_len:
			self.body.pop()
		return True

	def grow(self):
		self.target_len += 1
		self.score += 10

	def draw(self, screen):
		for i, (x, y) in enumerate(self.body):
			color = GREEN if i == 0 else BLUE
			rect = pygame.Rect(x * CELL, y * CELL, CELL, CELL)
			pygame.draw.rect(screen, color, rect)
			pygame.draw.rect(screen, WHITE, rect, 1)


class Food:
	def __init__(self):
		self.pos = (0, 0)
		self.randomize([])

	def randomize(self, snake_body):
		while True:
			pos = (random.randint(0, GRID_W - 1), random.randint(0, GRID_H - 1))
			if pos not in snake_body:
				self.pos = pos
				return

	def draw(self, screen):
		rect = pygame.Rect(self.pos[0] * CELL, self.pos[1] * CELL, CELL, CELL)
		pygame.draw.rect(screen, RED, rect)
		pygame.draw.rect(screen, WHITE, rect, 1)


def draw_grid(screen):
	for y in range(0, HEIGHT, CELL):
		for x in range(0, WIDTH, CELL):
			pygame.draw.rect(screen, GRAY, (x, y, CELL, CELL), 1)


def draw_text(screen, text, x, y, font, color=WHITE):
	surface = font.render(text, True, color)
	screen.blit(surface, (x, y))


def main():
	pygame.init()
	screen = pygame.display.set_mode((WIDTH, HEIGHT))
	pygame.display.set_caption("Snake (Pygame) - ESC 退出, R 重开")
	clock = pygame.time.Clock()
	font = pygame.font.SysFont(None, 32)

	snake = Snake()
	food = Food()
	game_over = False

	while True:
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				pygame.quit()
				sys.exit(0)
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_ESCAPE:
					pygame.quit()
					sys.exit(0)
				if game_over and event.key == pygame.K_r:
					snake.reset()
					food.randomize(snake.body)
					game_over = False
				elif not game_over:
					if event.key == pygame.K_UP:
						snake.turn(UP)
					elif event.key == pygame.K_DOWN:
						snake.turn(DOWN)
					elif event.key == pygame.K_LEFT:
						snake.turn(LEFT)
					elif event.key == pygame.K_RIGHT:
						snake.turn(RIGHT)

		if not game_over:
			if not snake.move():
				game_over = True
			elif snake.head() == food.pos:
				snake.grow()
				food.randomize(snake.body)

		screen.fill(BLACK)
		draw_grid(screen)
		snake.draw(screen)
		food.draw(screen)
		draw_text(screen, f"Score: {snake.score}", 10, 10, font)
		if game_over:
			draw_text(screen, "GAME OVER - R 重开 / ESC 退出", 110, HEIGHT // 2 - 16, font, RED)

		pygame.display.flip()
		clock.tick(FPS)


if __name__ == "__main__":
	main()