"""Playback state: which turn is shown and how far the animation is."""

MOVE_SHARE = 0.72  # share of a turn spent moving; the rest is a short hold
MIN_SPEED = 0.25
MAX_SPEED = 8.0


class Playback:
    """Tracks the animation between two snapshots.

    The display always draws the drones somewhere between snapshot
    ``from_index`` and snapshot ``to_index``. Stepping forward or backward
    just changes those two indices, so both directions animate the same way.
    """

    def __init__(
        self, last: int, seconds_per_turn: float = 0.9, autoplay: bool = True
    ) -> None:
        """Create a playback positioned on turn 0.

        Args:
            last: Index of the final snapshot (the number of turns).
            seconds_per_turn: Duration of one turn at speed 1.
            autoplay: Start playing immediately.
        """
        self.last = last
        self.seconds_per_turn = seconds_per_turn
        self.from_index = 0
        self.to_index = 0
        self.progress = 1.0
        self.speed = 1.0
        self.playing = autoplay and last > 0

    @property
    def eased(self) -> float:
        """Smoothed 0..1 position of the drones between the two snapshots."""
        t = min(1.0, self.progress / MOVE_SHARE)
        return t * t * (3.0 - 2.0 * t)

    @property
    def position(self) -> float:
        """Fractional turn number, used to draw the progress bar."""
        return self.from_index + (self.to_index - self.from_index) * self.eased

    @property
    def finished(self) -> bool:
        """Whether the last turn has been reached and fully played."""
        return self.to_index == self.last and self.progress >= 1.0

    def update(self, dt: float) -> None:
        """Advance the animation by dt seconds."""
        if self.progress < 1.0:
            step = dt * self.speed / self.seconds_per_turn
            self.progress = min(1.0, self.progress + step)
        if self.progress >= 1.0 and self.playing:
            if self.to_index < self.last:
                self._go(self.to_index + 1)
            else:
                self.playing = False

    def _go(self, index: int) -> None:
        """Start animating toward another snapshot."""
        self.from_index = self.to_index
        self.to_index = index
        self.progress = 0.0

    def step(self, delta: int) -> None:
        """Pause and move one or more turns forward (+) or back (-)."""
        self.playing = False
        index = max(0, min(self.last, self.to_index + delta))
        if index != self.to_index:
            self._go(index)

    def seek(self, index: int) -> None:
        """Pause and jump straight to a turn, without animation."""
        index = max(0, min(self.last, index))
        self.playing = False
        self.from_index = self.to_index = index
        self.progress = 1.0

    def restart(self) -> None:
        """Go back to turn 0 and play again."""
        self.seek(0)
        self.playing = self.last > 0

    def toggle(self) -> None:
        """Play or pause; replay from the start when everything is done."""
        if self.finished:
            self.restart()
        else:
            self.playing = not self.playing

    def change_speed(self, factor: float) -> None:
        """Multiply the playback speed, within sensible limits."""
        self.speed = max(MIN_SPEED, min(MAX_SPEED, self.speed * factor))
