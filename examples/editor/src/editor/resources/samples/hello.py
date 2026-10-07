"""A small sample for the editor."""

import math

WAVE = "👋 hi"  # an emoji in a string and one in a comment: 😀


@staticmethod
def area(radius: float) -> float:
    # Circles are round 😀 (an emoji keeps UTF-16 offsets honest)
    return math.pi * radius**2


class Greeter:
    def __init__(self, name="world"):
        self.name = name

    def greet(self):
        print(f"Hello, {self.name}!")


if __name__ == "__main__":
    Greeter().greet()
