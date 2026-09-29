"""The pygame window: event loop, keyboard and mouse controls."""

from typing import Sequence

import pygame

from .layout import Layout
from .playback import Playback
from .renderer import Renderer
from .timeline import Move, Timeline
from .world import MapLike, World


class Viewer:
    """Shows a finished simulation as an animation you can scrub through."""

    def __init__(
        self,
        source: MapLike,
        turns: Sequence[Sequence[Move]],
        size: tuple[int, int] = (1100, 720),
        seconds_per_turn: float = 0.9,
        autoplay: bool = True,
        flip_y: bool = True,
    ) -> None:
        """Prepare the animation (no window is opened yet).

        Args:
            source: The parser result (start/end hubs, hubs, connections).
            turns: One list of ``Move`` per simulation turn.
            size: Initial window size in pixels.
            seconds_per_turn: Duration of one turn at speed 1.
            autoplay: Start playing as soon as the window opens.
            flip_y: Draw larger y values higher up, like a graph.

        Raises:
            ReplayError: If the turns do not match the map.
        """
        self.world = World(source)
        self.timeline = Timeline(self.world, turns)
        self.layout = Layout(self.world, flip_y)
        self.renderer = Renderer(self.world, self.timeline, self.layout)
        self.playback = Playback(self.timeline.last, seconds_per_turn,
                                 autoplay)
        self.size = size
        self._scrubbing = False

    def run(self) -> None:
        """Open the window and run until it is closed."""
        pygame.init()
        try:
            pygame.display.set_mode(self.size, pygame.RESIZABLE)
            pygame.display.set_caption("Fly-in")
            clock = pygame.time.Clock()
            running = True
            while running:
                dt = min(clock.tick(60) / 1000.0, 0.1)
                for event in pygame.event.get():
                    running = self._handle(event) and running
                screen = pygame.display.get_surface()
                if screen is None:
                    break
                self.playback.update(dt)
                self.renderer.draw(screen, self.playback)
                pygame.display.flip()
        finally:
            pygame.quit()

    def _handle(self, event: pygame.event.Event) -> bool:
        """React to one event; return False to stop the program."""
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            return self._on_key(event.key)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            grab = self.renderer.bar.inflate(0, 24)
            self._scrubbing = grab.collidepoint(event.pos)
            self._scrub(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            self._scrubbing = False
        elif event.type == pygame.MOUSEMOTION:
            self._scrub(event.pos[0])
        return True

    def _scrub(self, x: int) -> None:
        """Jump to the turn under the mouse while dragging the bar."""
        if not self._scrubbing:
            return
        bar = self.renderer.bar
        ratio = (x - bar.left) / bar.width
        self.playback.seek(round(ratio * self.timeline.last))

    def _on_key(self, key: int) -> bool:
        """Handle a key press; return False to quit."""
        play = self.playback
        if key in (pygame.K_ESCAPE, pygame.K_q):
            return False
        if key == pygame.K_SPACE:
            play.toggle()
        elif key == pygame.K_RIGHT:
            play.step(1)
        elif key == pygame.K_LEFT:
            play.step(-1)
        elif key == pygame.K_UP:
            play.change_speed(1.25)
        elif key == pygame.K_DOWN:
            play.change_speed(0.8)
        elif key in (pygame.K_r, pygame.K_HOME):
            play.restart()
        elif key == pygame.K_f:
            self.layout.flip_y = not self.layout.flip_y
            self.renderer.refresh()
        elif key == pygame.K_s:
            self._screenshot()
        return True

    def _screenshot(self) -> None:
        """Save the current frame as fly_in_turn_<n>.png."""
        screen = pygame.display.get_surface()
        if screen is not None:
            turn = self.timeline[self.playback.to_index].turn
            pygame.image.save(screen, f"fly_in_turn_{turn}.png")
