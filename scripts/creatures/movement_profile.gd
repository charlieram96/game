class_name MovementProfile
extends Resource
## How a species walks. Values are world units (1 unit = 1 logical cell).

@export var speed: float = 6.0  ## Top walking speed, units/second.
@export var acceleration: float = 40.0  ## units/second² when speeding up.
@export var deceleration: float = 50.0  ## units/second² when releasing input.
## Acceleration used when the new direction opposes the current velocity
## (> 90°). Low values make heavy creatures slow to change direction.
@export var turn_acceleration: float = 60.0
@export var collision_radius: float = 0.45
## Relative mass for body-to-body pushing.
@export var mass: float = 1.0
## Speed multiplier while guarding (0 = rooted).
@export var guard_move_mult: float = 0.0
